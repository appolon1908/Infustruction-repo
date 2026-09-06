#!/usr/bin/env python3
"""Hardened immutable Codestra staging, recovery, and canary controller.

Version 2 keeps the source-only, exact-digest boundary from release_control.py
and closes four certification gaps:

* authenticated requests never follow redirects;
* each runtime version response must read back both source SHA and image digest;
* staging and production use separate protected endpoint/credential manifests;
* production canary evidence is bound to the exact successful staging run.

It also verifies local filestore/configuration archives and restores the database
backup into an isolated, no-network PostgreSQL container before accepting a
recovery point.
"""

from __future__ import annotations

import argparse
import copy
import contextlib
import dataclasses
import datetime as dt
import hashlib
import json
import os
import re
import secrets
import ssl
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

import release_control as core

STAGING_ENVIRONMENT = "staging-readonly"
CANARY_ENVIRONMENT = "production-readonly-canary"
ZERO_SHA = "0" * 40
ZERO_HASH = "0" * 64
ZERO_DIGEST = "sha256:" + ZERO_HASH
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ALLOWED_KONG_RESULTS = frozenset(
    {
        200,
        201,
        202,
        204,
        301,
        302,
        307,
        308,
        400,
        401,
        403,
        405,
        409,
        410,
        415,
        422,
        429,
    }
)
EXPECTED_TOKEN_NAMES = {
    STAGING_ENVIRONMENT: (
        "STAGING_READONLY_BEARER_TOKEN",
        "STAGING_METRICS_BEARER_TOKEN",
    ),
    CANARY_ENVIRONMENT: (
        "PRODUCTION_READONLY_BEARER_TOKEN",
        "PRODUCTION_METRICS_BEARER_TOKEN",
    ),
}
PRODUCER_WORKFLOW = ".github/workflows/staging-readonly-certification.yml"


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects before reusing a bearer token on another request."""

    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


@dataclasses.dataclass
class Evidence:
    candidate_id: str
    candidate_source_lock_sha: str
    candidate_manifest_sha256: str
    workload_identities: list[dict[str, str]]
    mode: str
    producer: dict[str, Any]
    started_at: str = dataclasses.field(default_factory=core.utc_now)
    completed_at: str | None = None
    verdict: str = "NO_GO"
    gates: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    measurements: dict[str, Any] = dataclasses.field(default_factory=dict)
    artifacts: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    rollback_performed: bool = False
    error: str | None = None

    def record(self, gate: str, status: str, **detail: Any) -> None:
        self.gates.append({"gate": gate, "status": status, **detail})

    def finish(self, verdict: str) -> None:
        self.completed_at = core.utc_now()
        self.verdict = verdict

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def producer_identity() -> dict[str, Any]:
    run_id = os.environ.get("GITHUB_RUN_ID")
    run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT")
    return {
        "repository": os.environ.get("GITHUB_REPOSITORY", "appolon1908-hue/Infustruction-repo"),
        "workflow": PRODUCER_WORKFLOW,
        "workflow_ref": os.environ.get("GITHUB_WORKFLOW_REF"),
        "head_sha": os.environ.get("GITHUB_SHA"),
        "head_ref": os.environ.get("GITHUB_REF"),
        "run_id": int(run_id) if run_id and run_id.isdigit() else None,
        "run_attempt": int(run_attempt) if run_attempt and run_attempt.isdigit() else None,
    }


def new_evidence(candidate: Mapping[str, Any], candidate_sha256: str, mode: str) -> Evidence:
    return Evidence(
        candidate_id=str(candidate.get("candidate_id", "invalid")),
        candidate_source_lock_sha=str(candidate.get("candidate_source_lock_sha", "")),
        candidate_manifest_sha256=candidate_sha256,
        workload_identities=[
            {
                "name": str(item.get("name", "")),
                "service": str(item.get("service", "")),
                "repository": str(item.get("repository", "")),
                "source_sha": str(item.get("source_sha", "")),
                "image": str(item.get("image", "")),
            }
            for item in candidate.get("workloads", [])
            if isinstance(item, Mapping)
        ],
        mode=mode,
        producer=producer_identity(),
    )


def write_evidence(path: Path, evidence: Evidence) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(evidence.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.chmod(0o600)
    temporary.replace(path)


def image_digest(image: str) -> str:
    if not core.IMAGE_RE.fullmatch(image):
        raise core.GateError("image is not digest qualified")
    return image.rsplit("@", 1)[1]


def validate_candidate(candidate: Mapping[str, Any]) -> None:
    # Permit an optional previous migration identity while retaining every v1
    # structural check.
    compatible = copy.deepcopy(candidate)
    rollback = compatible.get("rollback")
    if isinstance(rollback, dict) and isinstance(rollback.get("workloads"), list):
        for item in rollback["workloads"]:
            if isinstance(item, dict):
                item.pop("expected_migration", None)
    core.validate_candidate(compatible)

    if candidate.get("candidate_source_lock_sha") == ZERO_SHA:
        raise core.GateError("candidate source lock cannot use the zero SHA")
    for index, workload in enumerate(candidate["workloads"]):
        if workload["source_sha"] == ZERO_SHA:
            raise core.GateError(f"workloads[{index}] cannot use the zero source SHA")
        if image_digest(workload["image"]) == ZERO_DIGEST:
            raise core.GateError(f"workloads[{index}] cannot use the zero image digest")
    if candidate["rollback"]["previous_source_lock_sha"] == ZERO_SHA:
        raise core.GateError("previous source lock cannot use the zero SHA")
    current_by_service = {item["service"]: item for item in candidate["workloads"]}
    for index, previous in enumerate(candidate["rollback"]["workloads"]):
        allowed = {"service", "source_sha", "image", "expected_migration"}
        extra = set(previous) - allowed
        missing = {"service", "source_sha", "image"} - set(previous)
        if missing or extra:
            raise core.GateError(
                f"rollback.workloads[{index}] has missing or unknown keys"
            )
        if previous["source_sha"] == ZERO_SHA or image_digest(previous["image"]) == ZERO_DIGEST:
            raise core.GateError(f"rollback.workloads[{index}] uses a zero identity")
        current = current_by_service[previous["service"]]
        if current["image"].split("@", 1)[0] != previous["image"].split("@", 1)[0]:
            raise core.GateError(
                f"rollback.workloads[{index}] changes the image repository"
            )
        migration = previous.get("expected_migration")
        if migration is not None and (
            not isinstance(migration, str)
            or not migration.strip()
            or len(migration) > 128
        ):
            raise core.GateError(
                f"rollback.workloads[{index}].expected_migration is invalid"
            )
    if candidate["canary"]["controller_sha256"] == ZERO_HASH:
        raise core.GateError("canary controller cannot use the zero SHA-256")
    for route in candidate["kong"]["smoke_routes"]:
        statuses = set(route["expected_statuses"])
        if not statuses or not statuses <= ALLOWED_KONG_RESULTS:
            raise core.GateError(
                f"Kong route {route['name']} permits an inconclusive status"
            )
        if 404 in statuses:
            raise core.GateError(
                f"Kong route {route['name']} cannot treat HTTP 404 as success"
            )


def _validate_target_workload(
    value: Mapping[str, Any],
    candidate_workload: Mapping[str, Any],
    label: str,
    *,
    exact_staging: bool,
) -> None:
    required = {
        "name",
        "version_endpoint",
        "readiness_endpoint",
        "capabilities_endpoint",
    }
    optional = {"metrics_endpoint", "migration_endpoint"}
    core.ensure_exact_keys(value, required, required | optional, label)
    if value.get("name") != candidate_workload.get("name"):
        raise core.GateError(f"{label}.name does not match candidate workload")
    for key in sorted(required - {"name"}):
        core.validate_https_url(value.get(key), f"{label}.{key}")
    for key in sorted(optional):
        candidate_has = bool(candidate_workload.get(key))
        target_has = key in value and value.get(key) is not None
        if candidate_has != target_has:
            raise core.GateError(
                f"{label}.{key} presence does not match candidate policy"
            )
        if target_has:
            core.validate_https_url(value.get(key), f"{label}.{key}")
    if exact_staging:
        for key in required | optional:
            if key == "name":
                continue
            if value.get(key) != candidate_workload.get(key):
                raise core.GateError(
                    f"{label}.{key} does not match the canonical staging target"
                )


def validate_endpoint_manifest(
    manifest: Mapping[str, Any],
    candidate: Mapping[str, Any],
    expected_environment: str,
) -> None:
    required = {
        "schema",
        "candidate_id",
        "environment",
        "bearer_token_environment",
        "metrics_token_environment",
        "workloads",
        "keycloak",
        "kong",
        "counters",
        "probe",
    }
    core.ensure_exact_keys(manifest, required, required, "endpoint manifest")
    if manifest.get("schema") != core.ENDPOINT_SCHEMA:
        raise core.GateError(
            f"endpoint manifest schema must equal {core.ENDPOINT_SCHEMA}"
        )
    if manifest.get("candidate_id") != candidate.get("candidate_id"):
        raise core.GateError("endpoint manifest is not bound to candidate_id")
    if expected_environment not in EXPECTED_TOKEN_NAMES:
        raise core.GateError("unsupported endpoint environment")
    if manifest.get("environment") != expected_environment:
        raise core.GateError(
            f"endpoint manifest must target {expected_environment}"
        )
    expected_bearer, expected_metrics = EXPECTED_TOKEN_NAMES[expected_environment]
    if manifest.get("bearer_token_environment") != expected_bearer:
        raise core.GateError("read-only bearer environment name is not canonical")
    if manifest.get("metrics_token_environment") != expected_metrics:
        raise core.GateError("metrics bearer environment name is not canonical")
    for name in (expected_bearer, expected_metrics):
        if not os.environ.get(name):
            raise core.GateError(f"required protected credential is not bound: {name}")

    candidate_by_name = {item["name"]: item for item in candidate["workloads"]}
    target_workloads = manifest.get("workloads")
    if not isinstance(target_workloads, list) or len(target_workloads) != len(candidate_by_name):
        raise core.GateError("endpoint workload inventory does not match candidate")
    target_names = [item.get("name") for item in target_workloads if isinstance(item, Mapping)]
    if len(target_names) != len(target_workloads) or set(target_names) != set(candidate_by_name):
        raise core.GateError("endpoint workload names do not match candidate")
    if len(target_names) != len(set(target_names)):
        raise core.GateError("endpoint workload names are duplicated")
    exact_staging = expected_environment == STAGING_ENVIRONMENT
    for index, target in enumerate(target_workloads):
        if not isinstance(target, Mapping):
            raise core.GateError(f"endpoint workloads[{index}] must be an object")
        _validate_target_workload(
            target,
            candidate_by_name[target["name"]],
            f"endpoint workloads[{index}]",
            exact_staging=exact_staging,
        )

    keycloak = manifest.get("keycloak")
    if not isinstance(keycloak, Mapping):
        raise core.GateError("endpoint keycloak target must be an object")
    core.ensure_exact_keys(
        keycloak,
        {"discovery_endpoint", "expected_issuer"},
        {"discovery_endpoint", "expected_issuer"},
        "endpoint keycloak",
    )
    core.validate_https_url(
        keycloak.get("discovery_endpoint"),
        "endpoint keycloak.discovery_endpoint",
    )
    core.validate_https_url(
        keycloak.get("expected_issuer"),
        "endpoint keycloak.expected_issuer",
    )
    if exact_staging and dict(keycloak) != dict(candidate["keycloak"]):
        raise core.GateError("staging Keycloak target differs from candidate")

    kong = manifest.get("kong")
    if not isinstance(kong, Mapping):
        raise core.GateError("endpoint Kong target must be an object")
    core.ensure_exact_keys(
        kong,
        {"smoke_routes"},
        {"smoke_routes"},
        "endpoint kong",
    )
    routes = kong.get("smoke_routes")
    if not isinstance(routes, list) or len(routes) != 29:
        raise core.GateError("endpoint Kong target must contain exactly 29 routes")
    candidate_routes = {
        item["name"]: item for item in candidate["kong"]["smoke_routes"]
    }
    target_route_names: set[str] = set()
    for index, route in enumerate(routes):
        if not isinstance(route, Mapping):
            raise core.GateError(f"endpoint Kong route[{index}] must be an object")
        core.ensure_exact_keys(
            route,
            {"name", "url", "expected_statuses"},
            {"name", "url", "expected_statuses"},
            f"endpoint Kong route[{index}]",
        )
        name = route.get("name")
        if name not in candidate_routes or name in target_route_names:
            raise core.GateError("endpoint Kong route inventory differs from candidate")
        core.validate_https_url(route.get("url"), f"endpoint Kong route[{index}].url")
        if route.get("expected_statuses") != candidate_routes[name]["expected_statuses"]:
            raise core.GateError(
                f"endpoint Kong route {name} changed expected statuses"
            )
        if exact_staging and route.get("url") != candidate_routes[name]["url"]:
            raise core.GateError(
                f"endpoint Kong route {name} differs from canonical staging URL"
            )
        target_route_names.add(name)
    if target_route_names != set(candidate_routes):
        raise core.GateError("endpoint Kong route names do not cover candidate")

    # Reuse the bounded counter and probe validation after removing the v2-only
    # target fields. The protected credential environment is already present.
    v1_view = {
        "schema": manifest["schema"],
        "candidate_id": manifest["candidate_id"],
        "bearer_token_environment": manifest["bearer_token_environment"],
        "metrics_token_environment": manifest["metrics_token_environment"],
        "counters": manifest["counters"],
        "probe": {
            key: value
            for key, value in manifest["probe"].items()
            if key
            in {
                "requests",
                "maximum_error_rate",
                "maximum_p95_ms",
                "maximum_regression_percent",
            }
        },
    }
    core.validate_endpoint_manifest(v1_view, candidate)
    probe = manifest["probe"]
    allowed_probe = {
        "requests",
        "maximum_error_rate",
        "maximum_p95_ms",
        "maximum_regression_percent",
        "baseline_url",
        "canary_url",
    }
    if set(probe) - allowed_probe:
        raise core.GateError("endpoint probe contains unknown keys")
    if expected_environment == CANARY_ENVIRONMENT:
        for key in ("baseline_url", "canary_url"):
            core.validate_https_url(probe.get(key), f"endpoint probe.{key}")
    elif any(key in probe for key in ("baseline_url", "canary_url")):
        raise core.GateError("staging endpoint probe must not define canary URLs")


def effective_candidate(
    candidate: Mapping[str, Any], manifest: Mapping[str, Any]
) -> dict[str, Any]:
    value = copy.deepcopy(candidate)
    targets = {item["name"]: item for item in manifest["workloads"]}
    for workload in value["workloads"]:
        target = targets[workload["name"]]
        for key in (
            "version_endpoint",
            "readiness_endpoint",
            "capabilities_endpoint",
            "metrics_endpoint",
            "migration_endpoint",
        ):
            if key in target:
                workload[key] = target[key]
            else:
                workload.pop(key, None)
    value["keycloak"] = copy.deepcopy(manifest["keycloak"])
    value["kong"] = {
        "expected_route_count": 29,
        "smoke_routes": copy.deepcopy(manifest["kong"]["smoke_routes"]),
    }
    return value


def request(
    url: str,
    *,
    token: str | None,
    method: str = "GET",
    timeout: float = core.DEFAULT_TIMEOUT,
) -> core.HttpResult:
    if method not in core.ALLOWED_METHODS:
        raise core.GateError(
            f"HTTP method prohibited by read-only controller: {method}"
        )
    headers = {
        "Accept": "application/json",
        "User-Agent": "codestra-readonly-certifier/2",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers, method=method)
    context = ssl.create_default_context()
    opener = urllib.request.build_opener(
        _NoRedirectHandler(),
        urllib.request.HTTPSHandler(context=context),
    )
    started = time.monotonic()
    try:
        with opener.open(req, timeout=timeout) as response:
            body = response.read(core.MAX_RESPONSE_BYTES + 1)
            if len(body) > core.MAX_RESPONSE_BYTES:
                raise core.GateError(
                    "endpoint response exceeded the bounded read limit"
                )
            return core.HttpResult(
                status=response.status,
                elapsed_ms=(time.monotonic() - started) * 1000.0,
                body=body,
                headers=dict(response.headers.items()),
            )
    except urllib.error.HTTPError as exc:
        body = exc.read(core.MAX_RESPONSE_BYTES + 1)
        if len(body) > core.MAX_RESPONSE_BYTES:
            body = b""
        return core.HttpResult(
            status=exc.code,
            elapsed_ms=(time.monotonic() - started) * 1000.0,
            body=body,
            headers=dict(exc.headers.items()),
        )
    except (urllib.error.URLError, TimeoutError, ssl.SSLError) as exc:
        raise core.GateError(f"HTTPS request failed for {url}: {exc}") from exc


def _normalize_digest(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip().lower()
    if DIGEST_RE.fullmatch(stripped):
        return stripped
    if core.HASH_RE.fullmatch(stripped):
        return "sha256:" + stripped
    if "@sha256:" in stripped:
        candidate = "sha256:" + stripped.rsplit("@sha256:", 1)[1]
        if DIGEST_RE.fullmatch(candidate):
            return candidate
    return None


def check_workload(
    workload: Mapping[str, Any], bearer: str, metrics: str
) -> dict[str, Any]:
    version = request(workload["version_endpoint"], token=bearer)
    if version.status != 200:
        raise core.GateError(
            f"{workload['name']} version endpoint returned HTTP {version.status}"
        )
    version_json = version.json()
    source_readback = core.find_first(
        version_json,
        {"source_sha", "git_sha", "commit_sha", "revision"},
    )
    if source_readback != workload["source_sha"]:
        raise core.GateError(
            f"{workload['name']} source-version readback mismatch"
        )
    digest_readback = core.find_first(
        version_json,
        {
            "image_digest",
            "container_image_digest",
            "runtime_image_digest",
            "oci_image_digest",
        },
    )
    expected_digest = image_digest(workload["image"])
    if _normalize_digest(digest_readback) != expected_digest:
        raise core.GateError(
            f"{workload['name']} runtime image-digest readback mismatch"
        )

    readiness = request(workload["readiness_endpoint"], token=bearer)
    if readiness.status != 200:
        raise core.GateError(
            f"{workload['name']} readiness endpoint returned HTTP {readiness.status}"
        )
    readiness_json = readiness.json()
    ready = core.find_first(
        readiness_json,
        {"ready", "readiness", "status", "health"},
    )
    if ready is not True and str(ready).lower() not in {
        "ready",
        "ok",
        "pass",
        "healthy",
        "up",
    }:
        raise core.GateError(f"{workload['name']} did not report ready")

    capabilities = request(workload["capabilities_endpoint"], token=bearer)
    if capabilities.status != 200:
        raise core.GateError(
            f"{workload['name']} capabilities endpoint returned HTTP "
            f"{capabilities.status}"
        )
    capabilities_json = capabilities.json()
    false_strings = {str(item).lower() for item in core.FALSE_VALUES}
    for key in core.SAFETY_EXPECTED:
        actual = core.find_first(capabilities_json, {key.lower()})
        if actual is None:
            raise core.GateError(
                f"{workload['name']} capabilities omitted {key}"
            )
        if key == "PRODUCTION_DIALING":
            if str(actual).upper() != "DISABLED":
                raise core.GateError(
                    f"{workload['name']} capability {key} is not disabled"
                )
        elif actual not in core.FALSE_VALUES and str(actual).lower() not in false_strings:
            raise core.GateError(
                f"{workload['name']} capability {key} is live or malformed"
            )

    migration = None
    if workload.get("migration_endpoint"):
        migration_result = request(workload["migration_endpoint"], token=bearer)
        if migration_result.status != 200:
            raise core.GateError(
                f"{workload['name']} migration endpoint returned HTTP "
                f"{migration_result.status}"
            )
        migration = core.find_first(
            migration_result.json(),
            {
                "migration",
                "migration_head",
                "schema_revision",
                "current_revision",
                "head",
            },
        )
        if migration != workload.get("expected_migration"):
            raise core.GateError(
                f"{workload['name']} database migration readback mismatch"
            )
    elif workload.get("expected_migration") is not None:
        raise core.GateError(
            f"{workload['name']} has an expected migration but no migration endpoint"
        )

    metrics_status = None
    if workload.get("metrics_endpoint"):
        anonymous = request(workload["metrics_endpoint"], token=None)
        if anonymous.status not in (401, 403):
            raise core.GateError(
                f"{workload['name']} metrics are not protected"
            )
        authorized = request(workload["metrics_endpoint"], token=metrics)
        if authorized.status != 200:
            raise core.GateError(
                f"{workload['name']} protected metrics returned HTTP "
                f"{authorized.status}"
            )
        metrics_status = authorized.status

    return {
        "name": workload["name"],
        "source_sha": workload["source_sha"],
        "image_digest": expected_digest,
        "version_ms": round(version.elapsed_ms, 3),
        "readiness_ms": round(readiness.elapsed_ms, 3),
        "migration": migration,
        "metrics_status": metrics_status,
    }


def check_keycloak(candidate: Mapping[str, Any], bearer: str) -> None:
    result = request(candidate["keycloak"]["discovery_endpoint"], token=bearer)
    if result.status != 200:
        raise core.GateError(
            f"Keycloak discovery returned HTTP {result.status}"
        )
    payload = result.json()
    issuer = payload.get("issuer") if isinstance(payload, dict) else None
    if issuer != candidate["keycloak"]["expected_issuer"]:
        raise core.GateError("Keycloak issuer mismatch")


def check_kong(
    candidate: Mapping[str, Any], bearer: str
) -> list[dict[str, Any]]:
    routes = candidate["kong"]["smoke_routes"]
    if len(routes) != 29 or candidate["kong"]["expected_route_count"] != 29:
        raise core.GateError("Kong route denominator drifted before smoke test")
    results: list[dict[str, Any]] = []
    for route in routes:
        response = request(route["url"], token=bearer)
        if response.status == 404 or response.status not in route["expected_statuses"]:
            raise core.GateError(
                f"Kong route {route['name']} returned HTTP {response.status}; "
                f"expected one of {route['expected_statuses']}"
            )
        results.append(
            {
                "name": route["name"],
                "status": response.status,
                "elapsed_ms": round(response.elapsed_ms, 3),
            }
        )
    return results


def bearer_tokens(manifest: Mapping[str, Any]) -> tuple[str, str]:
    bearer = os.environ.get(str(manifest["bearer_token_environment"]), "")
    metrics = os.environ.get(str(manifest["metrics_token_environment"]), "")
    if not bearer or not metrics:
        raise core.GateError(
            "protected read-only bearer and metrics credentials are required"
        )
    return bearer, metrics


def read_counters(
    manifest: Mapping[str, Any], token: str
) -> dict[str, int]:
    values: dict[str, int] = {}
    for counter in manifest["counters"]:
        result = request(counter["url"], token=token)
        if result.status != 200:
            raise core.GateError(
                f"counter endpoint {counter['name']} returned HTTP {result.status}"
            )
        value = core.json_pointer(result.json(), counter["json_pointer"])
        if type(value) is not int or value < 0:
            raise core.GateError(
                f"counter {counter['name']} did not return a non-negative integer"
            )
        values[counter["name"]] = value
    return values


def run_all_checks(
    candidate: Mapping[str, Any], manifest: Mapping[str, Any]
) -> dict[str, Any]:
    effective = effective_candidate(candidate, manifest)
    bearer, metrics = bearer_tokens(manifest)
    workloads = [
        check_workload(workload, bearer, metrics)
        for workload in effective["workloads"]
    ]
    check_keycloak(effective, bearer)
    routes = check_kong(effective, bearer)
    return {"workloads": workloads, "kong_routes": routes}


def expected_images(
    candidate: Mapping[str, Any], release: str
) -> list[str]:
    if release == "candidate":
        source = candidate["workloads"]
    elif release == "previous":
        source = candidate["rollback"]["workloads"]
    else:
        raise core.GateError("unknown release image set")
    return sorted(item["image"] for item in source)


def verify_compose_images(
    candidate: Mapping[str, Any], override: Path, release: str
) -> None:
    working = Path(candidate["compose"]["working_directory"])
    rendered = core.run(
        core.compose_command(candidate, override, "config", "--images"),
        cwd=working,
    ).stdout.decode("utf-8", errors="strict").splitlines()
    actual = sorted(line.strip() for line in rendered if line.strip())
    expected = expected_images(candidate, release)
    if actual != expected:
        raise core.GateError(
            f"rendered Compose images do not match the complete {release} "
            f"digest set: expected {expected}, got {actual}"
        )


def deploy(
    candidate: Mapping[str, Any], override: Path, release: str
) -> None:
    working = Path(candidate["compose"]["working_directory"])
    verify_compose_images(candidate, override, release)
    core.run(
        core.compose_command(
            candidate,
            override,
            "up",
            "-d",
            "--no-build",
            "--pull",
            "never",
            "--remove-orphans",
        ),
        cwd=working,
        capture=True,
    )


def _safe_extract(archive_path: Path, destination: Path) -> None:
    with tarfile.open(archive_path, mode="r:gz") as archive:
        members = archive.getmembers()
        if not members:
            raise core.GateError(f"backup archive is empty: {archive_path.name}")
        for member in members:
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts:
                raise core.GateError(
                    f"backup archive contains an unsafe path: {member.name}"
                )
            if member.issym() or member.islnk() or member.isdev():
                raise core.GateError(
                    f"backup archive contains an unsupported special entry: {member.name}"
                )
        archive.extractall(destination, filter="data")


def _directory_hashes(root: Path) -> dict[str, str]:
    output: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise core.GateError(f"recovery tree contains symbolic link: {path}")
        if path.is_file():
            output[str(path.relative_to(root))] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return output


def _normalized_dump(payload: bytes) -> bytes:
    output: list[bytes] = []
    for line in payload.splitlines():
        stripped = line.strip()
        if stripped.startswith(b"--"):
            continue
        if stripped.startswith(b"\\restrict") or stripped.startswith(b"\\unrestrict"):
            continue
        if stripped.startswith(b"SET ") or stripped.startswith(
            b"SELECT pg_catalog.set_config"
        ):
            continue
        if stripped:
            output.append(line.rstrip())
    return b"\n".join(output) + b"\n"


def _pg_dump_plain(
    candidate: Mapping[str, Any],
    override: Path,
    *options: str,
) -> bytes:
    postgres = candidate["backups"]["postgres"]
    return core.run(
        core.compose_command(
            candidate,
            override,
            "exec",
            "-T",
            postgres["service"],
            "pg_dump",
            *options,
            "--no-owner",
            "--no-privileges",
            "-U",
            postgres["username"],
            postgres["database"],
        ),
        cwd=Path(candidate["compose"]["working_directory"]),
        capture=True,
    ).stdout


def _verify_database_restore(
    candidate: Mapping[str, Any],
    override: Path,
    backup_dir: Path,
) -> dict[str, str]:
    postgres = candidate["backups"]["postgres"]
    workload = next(
        (
            item
            for item in candidate["workloads"]
            if item["service"] == postgres["service"]
        ),
        None,
    )
    if workload is None:
        raise core.GateError(
            "PostgreSQL backup service is not represented by an exact workload image"
        )
    source_schema = _normalized_dump(
        _pg_dump_plain(candidate, override, "--schema-only")
    )
    source_data = _normalized_dump(
        _pg_dump_plain(candidate, override, "--data-only")
    )
    if not source_schema:
        raise core.GateError("source database schema fingerprint is empty")

    suffix = hashlib.sha256(
        f"{candidate['candidate_id']}:{time.time_ns()}".encode()
    ).hexdigest()[:12]
    container = f"codestra-pg-restore-{suffix}"
    volume = f"codestra-pg-restore-{suffix}"
    password = secrets.token_urlsafe(32)
    database = "codestra_restore_verify"
    core.run(["docker", "volume", "create", volume], capture=True)
    started = False
    try:
        core.run(
            [
                "docker",
                "run",
                "--detach",
                "--rm",
                "--network",
                "none",
                "--name",
                container,
                "--mount",
                f"type=volume,source={volume},target=/var/lib/postgresql/data",
                "--env",
                f"POSTGRES_PASSWORD={password}",
                workload["image"],
            ],
            capture=True,
        )
        started = True
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            ready = subprocess.run(
                ["docker", "exec", container, "pg_isready", "-U", "postgres"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if ready.returncode == 0:
                break
            time.sleep(2)
        else:
            raise core.GateError("isolated PostgreSQL restore container did not become ready")
        core.run(
            ["docker", "cp", str(backup_dir / "database.dump"), f"{container}:/tmp/database.dump"],
            capture=True,
        )
        core.run(
            [
                "docker",
                "exec",
                container,
                "psql",
                "-v",
                "ON_ERROR_STOP=1",
                "-U",
                "postgres",
                "-c",
                f"CREATE DATABASE {database}",
            ],
            capture=True,
        )
        core.run(
            [
                "docker",
                "exec",
                container,
                "pg_restore",
                "--exit-on-error",
                "--no-owner",
                "--no-privileges",
                "-U",
                "postgres",
                "-d",
                database,
                "/tmp/database.dump",
            ],
            capture=True,
        )
        restored_schema = _normalized_dump(
            core.run(
                [
                    "docker",
                    "exec",
                    container,
                    "pg_dump",
                    "--schema-only",
                    "--no-owner",
                    "--no-privileges",
                    "-U",
                    "postgres",
                    database,
                ],
                capture=True,
            ).stdout
        )
        restored_data = _normalized_dump(
            core.run(
                [
                    "docker",
                    "exec",
                    container,
                    "pg_dump",
                    "--data-only",
                    "--no-owner",
                    "--no-privileges",
                    "-U",
                    "postgres",
                    database,
                ],
                capture=True,
            ).stdout
        )
        if source_schema != restored_schema:
            raise core.GateError(
                "isolated PostgreSQL restore schema fingerprint differs from source"
            )
        if source_data != restored_data:
            raise core.GateError(
                "isolated PostgreSQL restore data fingerprint differs from source"
            )
        return {
            "schema_sha256": hashlib.sha256(source_schema).hexdigest(),
            "data_sha256": hashlib.sha256(source_data).hexdigest(),
        }
    finally:
        if started:
            subprocess.run(
                ["docker", "rm", "--force", container],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        subprocess.run(
            ["docker", "volume", "rm", "--force", volume],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def verify_recovery_point(
    candidate: Mapping[str, Any],
    override: Path,
    backup_dir: Path,
) -> dict[str, Any]:
    core.run(["sha256sum", "--check", "SHA256SUMS"], cwd=backup_dir)
    with tempfile.TemporaryDirectory(prefix="codestra-backup-verify-") as directory:
        root = Path(directory)
        filestore_restore = root / "filestore"
        config_restore = root / "configuration"
        filestore_restore.mkdir()
        config_restore.mkdir()
        _safe_extract(backup_dir / "odoo-filestore.tar.gz", filestore_restore)
        _safe_extract(backup_dir / "configuration.tar.gz", config_restore)
        source_filestore = Path(candidate["backups"]["odoo_filestore"])
        restored_filestore = filestore_restore / source_filestore.name
        if not restored_filestore.is_dir():
            raise core.GateError("restored Odoo filestore root is missing")
        source_hashes = _directory_hashes(source_filestore)
        restored_hashes = _directory_hashes(restored_filestore)
        if source_hashes != restored_hashes:
            raise core.GateError(
                "restored Odoo filestore content differs from source"
            )
        config_hashes = _directory_hashes(config_restore)
        if not config_hashes:
            raise core.GateError("restored configuration archive is empty")
    database = _verify_database_restore(candidate, override, backup_dir)
    return {
        "database": database,
        "filestore_files": len(source_hashes),
        "configuration_files": len(config_hashes),
    }


def create_backup(
    candidate: Mapping[str, Any], override: Path, evidence: Evidence
) -> Path:
    backup_dir = core.create_backup(candidate, override, evidence)
    verification = verify_recovery_point(candidate, override, backup_dir)
    evidence.artifacts.append(
        {
            "type": "recovery-point-verification",
            "path": str(backup_dir),
            **verification,
        }
    )
    return backup_dir


def previous_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(candidate)
    by_service = {
        item["service"]: item for item in candidate["rollback"]["workloads"]
    }
    for workload in value["workloads"]:
        previous = by_service[workload["service"]]
        workload["source_sha"] = previous["source_sha"]
        workload["image"] = previous["image"]
        if "expected_migration" in previous:
            workload["expected_migration"] = previous["expected_migration"]
    return value


def automatic_rollback(
    candidate: Mapping[str, Any], manifest: Mapping[str, Any]
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="codestra-rollback-") as directory:
        override = Path(directory) / "previous.override.yml"
        core.write_override(candidate["rollback"]["workloads"], override)
        started = time.monotonic()
        deploy(candidate, override, "previous")
        results = run_all_checks(previous_candidate(candidate), manifest)
        return {
            "rto_seconds": round(time.monotonic() - started, 3),
            "checks": results,
        }


def previous_image_workloads(
    candidate: Mapping[str, Any],
) -> list[dict[str, str]]:
    current = {item["service"]: item for item in candidate["workloads"]}
    return [
        {
            "name": current[item["service"]]["name"],
            "service": item["service"],
            "repository": current[item["service"]]["repository"],
            "source_sha": item["source_sha"],
            "image": item["image"],
        }
        for item in candidate["rollback"]["workloads"]
    ]


def execute_staging(
    candidate: Mapping[str, Any],
    manifest: Mapping[str, Any],
    evidence: Evidence,
) -> None:
    core.require_tools()
    with tempfile.TemporaryDirectory(prefix="codestra-candidate-") as directory:
        override = Path(directory) / "candidate.override.yml"
        core.write_override(candidate["workloads"], override)
        core.verify_images(candidate["workloads"])
        core.verify_images(previous_image_workloads(candidate))
        evidence.record(
            "immutable-image-source-readback",
            "PASS",
            workloads=len(candidate["workloads"]),
        )
        verify_compose_images(candidate, override, "candidate")
        evidence.record("compose-image-digest-lock", "PASS")
        bearer, _ = bearer_tokens(manifest)
        baseline = read_counters(manifest, bearer)
        core.assert_zero_and_unchanged(baseline, baseline)
        evidence.measurements["baseline_live_effect_counters"] = baseline
        evidence.record("zero-live-effect-baseline", "PASS")
        backup_dir = create_backup(candidate, override, evidence)
        evidence.record(
            "paired-local-off-host-and-restore-verified-backup",
            "PASS",
            recovery_point=str(backup_dir),
        )
        deployment_started = False
        try:
            deployment_started = True
            deploy(candidate, override, "candidate")
            evidence.record("immutable-staging-deployment", "PASS")
            results = run_all_checks(candidate, manifest)
            evidence.measurements["staging_checks"] = results
            evidence.record(
                "source-digest-readiness-capabilities-metrics-migrations",
                "PASS",
                workloads=len(results["workloads"]),
            )
            evidence.record("keycloak-issuer", "PASS")
            evidence.record(
                "kong-29-route-smoke", "PASS", routes=len(results["kong_routes"])
            )
            after = read_counters(manifest, bearer)
            core.assert_zero_and_unchanged(baseline, after)
            evidence.measurements["final_live_effect_counters"] = after
            evidence.record("zero-calls-emails-sms", "PASS")
        except Exception:
            if deployment_started:
                rollback = automatic_rollback(candidate, manifest)
                evidence.rollback_performed = True
                evidence.measurements["automatic_rollback"] = rollback
            raise


def execute_rollback_rehearsal(
    candidate: Mapping[str, Any],
    manifest: Mapping[str, Any],
    evidence: Evidence,
) -> None:
    core.require_tools()
    bearer, _ = bearer_tokens(manifest)
    baseline = read_counters(manifest, bearer)
    core.assert_zero_and_unchanged(baseline, baseline)
    filestore = Path(candidate["backups"]["odoo_filestore"])
    before_integrity = _directory_hashes(filestore)
    with tempfile.TemporaryDirectory(prefix="codestra-rehearsal-") as directory:
        candidate_override = Path(directory) / "candidate.override.yml"
        previous_override = Path(directory) / "previous.override.yml"
        core.write_override(candidate["workloads"], candidate_override)
        core.write_override(candidate["rollback"]["workloads"], previous_override)
        recovery_started = time.monotonic()
        backup_dir = create_backup(candidate, candidate_override, evidence)
        recovery_point_age = time.monotonic() - recovery_started
        rollback_started = time.monotonic()
        deploy(candidate, previous_override, "previous")
        previous_results = run_all_checks(previous_candidate(candidate), manifest)
        previous_rto = time.monotonic() - rollback_started
        redeploy_started = time.monotonic()
        deploy(candidate, candidate_override, "candidate")
        candidate_results = run_all_checks(candidate, manifest)
        candidate_rto = time.monotonic() - redeploy_started
        after_integrity = _directory_hashes(filestore)
        if before_integrity != after_integrity:
            raise core.GateError(
                "Odoo filestore integrity changed during rollback rehearsal"
            )
        after = read_counters(manifest, bearer)
        core.assert_zero_and_unchanged(baseline, after)
        evidence.measurements.update(
            {
                "rto_previous_seconds": round(previous_rto, 3),
                "rto_candidate_seconds": round(candidate_rto, 3),
                "observed_recovery_point_age_seconds": round(
                    recovery_point_age, 3
                ),
                "rpo_statement": (
                    "zero application writes permitted; database, filestore, and "
                    "configuration recovery point restored in isolation"
                ),
                "filestore_files_hashed": len(before_integrity),
                "recovery_point": str(backup_dir),
                "previous_checks": previous_results,
                "candidate_checks": candidate_results,
                "live_effect_counters": after,
            }
        )
        evidence.record(
            "rollback-to-previous-exact-identities",
            "PASS",
            rto_seconds=round(previous_rto, 3),
        )
        evidence.record(
            "candidate-redeployment",
            "PASS",
            rto_seconds=round(candidate_rto, 3),
        )
        evidence.record(
            "database-filestore-configuration-integrity",
            "PASS",
            filestore_files=len(before_integrity),
        )
        evidence.record("rollback-health-readiness-version-digest", "PASS")
        evidence.record("zero-live-effects-during-rehearsal", "PASS")


def _identity_projection(candidate: Mapping[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "name": item["name"],
            "service": item["service"],
            "repository": item["repository"],
            "source_sha": item["source_sha"],
            "image": item["image"],
        }
        for item in candidate["workloads"]
    ]


def validate_run_evidence(
    payload: Mapping[str, Any],
    candidate: Mapping[str, Any],
    candidate_sha256: str,
    *,
    expected_mode: str,
    environment_prefix: str,
    required_gates: set[str],
) -> None:
    if payload.get("candidate_id") != candidate["candidate_id"]:
        raise core.GateError("staging evidence candidate_id mismatch")
    if payload.get("candidate_source_lock_sha") != candidate["candidate_source_lock_sha"]:
        raise core.GateError("staging evidence source-lock mismatch")
    if payload.get("candidate_manifest_sha256") != candidate_sha256:
        raise core.GateError("staging evidence candidate SHA-256 mismatch")
    if payload.get("workload_identities") != _identity_projection(candidate):
        raise core.GateError("staging evidence workload identities mismatch")
    if payload.get("mode") != expected_mode or payload.get("verdict") != "GO":
        raise core.GateError(f"{expected_mode} evidence is not an exact GO result")
    gates = payload.get("gates")
    if not isinstance(gates, list) or not gates or any(
        not isinstance(gate, Mapping) or gate.get("status") != "PASS"
        for gate in gates
    ):
        raise core.GateError(f"{expected_mode} evidence contains an absent or non-PASS gate")
    gate_names = {str(gate.get("gate")) for gate in gates}
    if not required_gates <= gate_names:
        raise core.GateError(
            f"{expected_mode} evidence is missing required gates: "
            + ", ".join(sorted(required_gates - gate_names))
        )
    producer = payload.get("producer")
    if not isinstance(producer, Mapping):
        raise core.GateError("staging evidence producer is absent")
    expected_run = os.environ.get(f"{environment_prefix}_EVIDENCE_RUN_ID")
    expected_attempt = os.environ.get(f"{environment_prefix}_EVIDENCE_RUN_ATTEMPT")
    expected_head = os.environ.get(f"{environment_prefix}_EVIDENCE_HEAD_SHA")
    if not expected_run or producer.get("run_id") != int(expected_run):
        raise core.GateError("staging evidence run ID mismatch")
    if not expected_attempt or producer.get("run_attempt") != int(expected_attempt):
        raise core.GateError("staging evidence run attempt mismatch")
    if not expected_head or producer.get("head_sha") != expected_head:
        raise core.GateError("staging evidence producer head SHA mismatch")
    if producer.get("repository") != "appolon1908-hue/Infustruction-repo":
        raise core.GateError("staging evidence producer repository mismatch")
    if producer.get("workflow") != PRODUCER_WORKFLOW:
        raise core.GateError("staging evidence producer workflow mismatch")


def validate_canary_receipt(
    payload: Any,
    candidate: Mapping[str, Any],
    candidate_sha256: str,
    requested_percent: float,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise core.GateError("canary controller did not return a JSON object")
    required = {
        "schema",
        "candidate_id",
        "source_lock_sha",
        "candidate_manifest_sha256",
        "percent",
        "methods",
        "read_only",
        "workloads",
    }
    core.ensure_exact_keys(payload, required, required, "canary controller receipt")
    if payload.get("schema") != "codestra.readonly-canary-receipt.v1":
        raise core.GateError("canary controller receipt schema mismatch")
    if payload.get("candidate_id") != candidate["candidate_id"]:
        raise core.GateError("canary controller receipt candidate mismatch")
    if payload.get("source_lock_sha") != candidate["candidate_source_lock_sha"]:
        raise core.GateError("canary controller receipt source-lock mismatch")
    if payload.get("candidate_manifest_sha256") != candidate_sha256:
        raise core.GateError("canary controller receipt manifest SHA-256 mismatch")
    percent = payload.get("percent")
    if isinstance(percent, bool) or not isinstance(percent, (int, float)):
        raise core.GateError("canary controller receipt percent is invalid")
    if abs(float(percent) - requested_percent) > 0.000001 or float(percent) > 1:
        raise core.GateError("canary controller applied an unexpected percentage")
    if payload.get("methods") != ["GET", "HEAD"] or payload.get("read_only") is not True:
        raise core.GateError("canary controller did not prove GET/HEAD-only read-only mode")
    expected = [
        {
            "service": item["service"],
            "source_sha": item["source_sha"],
            "image": item["image"],
        }
        for item in candidate["workloads"]
    ]
    if payload.get("workloads") != expected:
        raise core.GateError("canary controller receipt workload identities mismatch")
    return dict(payload)


def validate_rollback_receipt(
    payload: Any,
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise core.GateError("canary rollback controller did not return a JSON object")
    required = {"schema", "candidate_id", "source_lock_sha", "rolled_back"}
    core.ensure_exact_keys(payload, required, required, "canary rollback receipt")
    if payload.get("schema") != "codestra.readonly-canary-rollback.v1":
        raise core.GateError("canary rollback receipt schema mismatch")
    if payload.get("candidate_id") != candidate["candidate_id"]:
        raise core.GateError("canary rollback receipt candidate mismatch")
    if payload.get("source_lock_sha") != candidate["candidate_source_lock_sha"]:
        raise core.GateError("canary rollback receipt source-lock mismatch")
    if payload.get("rolled_back") is not True:
        raise core.GateError("canary rollback receipt did not confirm rollback")
    return dict(payload)


def _parse_controller_json(output: bytes, label: str) -> Any:
    if not output or len(output) > 1024 * 1024:
        raise core.GateError(f"{label} output is absent or oversized")
    try:
        return json.loads(output.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise core.GateError(f"{label} output is not one exact JSON document") from exc


def _probe_samples(
    url: str, token: str, count: int
) -> tuple[list[float], int]:
    latencies: list[float] = []
    errors = 0
    for _ in range(count):
        result = request(url, token=token, method="GET")
        if result.status != 200:
            errors += 1
        latencies.append(result.elapsed_ms)
    return latencies, errors


def execute_canary(
    candidate: Mapping[str, Any],
    manifest: Mapping[str, Any],
    evidence: Evidence,
    staging_evidence_path: Path,
    rollback_evidence_path: Path,
    requested_percent: float,
    candidate_path: Path,
    candidate_sha256: str,
) -> None:
    for tool in ("docker", "sha256sum"):
        if not shutil_which(tool):
            raise core.GateError(f"required host tool is missing: {tool}")
    staging = core.load_json(staging_evidence_path)
    validate_run_evidence(
        staging,
        candidate,
        candidate_sha256,
        expected_mode="staging",
        environment_prefix="STAGING",
        required_gates={
            "paired-local-off-host-and-restore-verified-backup",
            "source-digest-readiness-capabilities-metrics-migrations",
            "keycloak-issuer",
            "kong-29-route-smoke",
            "zero-calls-emails-sms",
        },
    )
    rollback_evidence = core.load_json(rollback_evidence_path)
    validate_run_evidence(
        rollback_evidence,
        candidate,
        candidate_sha256,
        expected_mode="rollback-rehearsal",
        environment_prefix="ROLLBACK",
        required_gates={
            "rollback-to-previous-exact-identities",
            "candidate-redeployment",
            "database-filestore-configuration-integrity",
            "rollback-health-readiness-version-digest",
            "zero-live-effects-during-rehearsal",
        },
    )
    maximum = float(candidate["canary"]["maximum_percent"])
    if requested_percent <= 0 or requested_percent > maximum or requested_percent > 1:
        raise core.GateError(
            "requested canary percentage exceeds the candidate or one-percent ceiling"
        )
    controller = core.validate_path(
        candidate["canary"]["controller"],
        "canary.controller",
        (Path("/srv/codestra/bin"),),
        file_required=True,
    )
    mode = controller.stat().st_mode
    if mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise core.GateError("canary controller is group/world writable")
    if not os.access(controller, os.X_OK):
        raise core.GateError("canary controller is not executable")
    digest = hashlib.sha256(controller.read_bytes()).hexdigest()
    if digest != candidate["canary"]["controller_sha256"]:
        raise core.GateError("canary controller SHA-256 mismatch")
    core.verify_images(candidate["workloads"])
    bearer, _ = bearer_tokens(manifest)
    baseline_counters = read_counters(manifest, bearer)
    core.assert_zero_and_unchanged(baseline_counters, baseline_counters)
    probe = manifest["probe"]
    baseline_latencies, baseline_errors = _probe_samples(
        probe["baseline_url"], bearer, probe["requests"]
    )
    if baseline_errors:
        raise core.GateError("baseline monitoring probe failed before canary apply")
    apply_result = core.run(
        [
            str(controller),
            "apply",
            "--candidate",
            candidate["candidate_id"],
            "--candidate-manifest",
            str(candidate_path),
            "--candidate-sha256",
            candidate_sha256,
            "--source-lock-sha",
            candidate["candidate_source_lock_sha"],
            "--percent",
            f"{requested_percent:.6f}",
            "--methods",
            "GET,HEAD",
            "--read-only",
        ],
        capture=True,
    )
    controller_receipt = validate_canary_receipt(
        _parse_controller_json(apply_result.stdout, "canary controller"),
        candidate,
        candidate_sha256,
        requested_percent,
    )
    canary_applied = True
    try:
        checks = run_all_checks(candidate, manifest)
        canary_latencies, canary_errors = _probe_samples(
            probe["canary_url"], bearer, probe["requests"]
        )
        error_rate = (canary_errors / probe["requests"]) * 100.0
        baseline_p95 = core.percentile(baseline_latencies, 0.95)
        canary_p95 = core.percentile(canary_latencies, 0.95)
        regression = (
            0.0
            if baseline_p95 == 0
            else ((canary_p95 - baseline_p95) / baseline_p95) * 100.0
        )
        if error_rate > probe["maximum_error_rate"]:
            raise core.GateError(
                "canary error rate exceeded the approved ceiling"
            )
        if canary_p95 > probe["maximum_p95_ms"]:
            raise core.GateError(
                "canary p95 latency exceeded the absolute ceiling"
            )
        if regression > probe["maximum_regression_percent"]:
            raise core.GateError(
                "canary p95 latency regression exceeded the approved ceiling"
            )
        after = read_counters(manifest, bearer)
        core.assert_zero_and_unchanged(baseline_counters, after)
        evidence.measurements.update(
            {
                "canary_percent": requested_percent,
                "methods": ["GET", "HEAD"],
                "baseline_p95_ms": round(baseline_p95, 3),
                "canary_p95_ms": round(canary_p95, 3),
                "latency_regression_percent": round(regression, 3),
                "error_rate_percent": round(error_rate, 6),
                "checks": checks,
                "live_effect_counters": after,
                "staging_evidence_run_id": int(
                    os.environ["STAGING_EVIDENCE_RUN_ID"]
                ),
                "rollback_evidence_run_id": int(
                    os.environ["ROLLBACK_EVIDENCE_RUN_ID"]
                ),
                "controller_receipt": controller_receipt,
            }
        )
        evidence.record(
            "production-readonly-canary",
            "PASS",
            percent=requested_percent,
            methods=["GET", "HEAD"],
        )
        evidence.record("latency-error-readiness-monitoring-and-database", "PASS")
        evidence.record("zero-live-effect-counter-movement", "PASS")
    except Exception:
        if canary_applied:
            rollback_result = core.run(
                [
                    str(controller),
                    "rollback",
                    "--candidate",
                    candidate["candidate_id"],
                    "--source-lock-sha",
                    candidate["candidate_source_lock_sha"],
                ],
                capture=True,
            )
            rollback_receipt = validate_rollback_receipt(
                _parse_controller_json(
                    rollback_result.stdout,
                    "canary rollback controller",
                ),
                candidate,
            )
            evidence.measurements["canary_rollback_receipt"] = rollback_receipt
            evidence.rollback_performed = True
        raise


def shutil_which(name: str) -> str | None:
    # Kept behind a tiny wrapper for dependency-free negative tests.
    import shutil

    return shutil.which(name)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--endpoint-manifest", type=Path, required=True)
    parser.add_argument(
        "--mode",
        choices=(
            "validate",
            "staging",
            "rollback-rehearsal",
            "production-readonly-canary",
        ),
        required=True,
    )
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--staging-evidence", type=Path)
    parser.add_argument("--rollback-evidence", type=Path)
    parser.add_argument("--canary-percent", type=float, default=1.0)
    parser.add_argument("--confirm-candidate-id")
    parser.add_argument("--confirm-source-lock-sha")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    candidate: dict[str, Any] = {}
    candidate_sha256 = ""
    evidence = Evidence(
        candidate_id="unloaded",
        candidate_source_lock_sha="",
        candidate_manifest_sha256="",
        workload_identities=[],
        mode=args.mode,
        producer=producer_identity(),
    )
    try:
        candidate_bytes = args.candidate.read_bytes()
        candidate_sha256 = hashlib.sha256(candidate_bytes).hexdigest()
        candidate = json.loads(candidate_bytes.decode("utf-8"))
        if not isinstance(candidate, dict):
            raise core.GateError("candidate must contain a JSON object")
        evidence = new_evidence(candidate, candidate_sha256, args.mode)
        validate_candidate(candidate)
        manifest = core.load_json(args.endpoint_manifest)
        if args.mode == "validate":
            if (
                manifest.get("schema") != core.ENDPOINT_SCHEMA
                or manifest.get("candidate_id") != candidate.get("candidate_id")
            ):
                raise core.GateError(
                    "endpoint manifest structure or candidate binding is invalid"
                )
            evidence.record("release-control-policy", "PASS")
            evidence.finish("GO")
            write_evidence(args.evidence, evidence)
            return 0
        if args.confirm_candidate_id != candidate["candidate_id"]:
            raise core.GateError(
                "--confirm-candidate-id must match the exact candidate"
            )
        if args.confirm_source_lock_sha != candidate["candidate_source_lock_sha"]:
            raise core.GateError(
                "--confirm-source-lock-sha must match the exact source lock"
            )
        expected_environment = (
            CANARY_ENVIRONMENT
            if args.mode == "production-readonly-canary"
            else STAGING_ENVIRONMENT
        )
        validate_endpoint_manifest(
            manifest,
            candidate,
            expected_environment,
        )
        evidence.record(
            "protected-environment-target-manifest-and-credentials",
            "PASS",
            environment=expected_environment,
        )
        if args.mode == "staging":
            execute_staging(candidate, manifest, evidence)
        elif args.mode == "rollback-rehearsal":
            if args.staging_evidence is None:
                raise core.GateError(
                    "rollback rehearsal requires exact staging evidence"
                )
            staging = core.load_json(args.staging_evidence)
            validate_run_evidence(
                staging,
                candidate,
                candidate_sha256,
                expected_mode="staging",
                environment_prefix="STAGING",
                required_gates={
                    "paired-local-off-host-and-restore-verified-backup",
                    "source-digest-readiness-capabilities-metrics-migrations",
                    "keycloak-issuer",
                    "kong-29-route-smoke",
                    "zero-calls-emails-sms",
                },
            )
            evidence.record(
                "exact-successful-staging-prerequisite",
                "PASS",
                run_id=int(os.environ["STAGING_EVIDENCE_RUN_ID"]),
            )
            initial = run_all_checks(candidate, manifest)
            evidence.measurements["initial_candidate_checks"] = initial
            evidence.record("initial-candidate-readback", "PASS")
            execute_rollback_rehearsal(candidate, manifest, evidence)
        else:
            if args.staging_evidence is None or args.rollback_evidence is None:
                raise core.GateError(
                    "production canary requires staging and rollback evidence"
                )
            execute_canary(
                candidate,
                manifest,
                evidence,
                args.staging_evidence,
                args.rollback_evidence,
                args.canary_percent,
                args.candidate,
                candidate_sha256,
            )
        evidence.finish("GO")
        write_evidence(args.evidence, evidence)
        print("CODESTRA_RELEASE_CONTROL=PASS")
        print(f"MODE={args.mode}")
        print(f"CANDIDATE_ID={candidate['candidate_id']}")
        print("VERDICT=GO")
        return 0
    except (
        core.GateError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as exc:
        evidence.error = str(exc)
        evidence.record("release-control", "FAIL", error=str(exc))
        evidence.finish("NO_GO")
        with contextlib.suppress(OSError):
            write_evidence(args.evidence, evidence)
        print(f"CODESTRA_RELEASE_CONTROL=FAIL ERROR={exc}", file=sys.stderr)
        print("VERDICT=NO_GO")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
