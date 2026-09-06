#!/usr/bin/env python3
"""Fail-closed Codestra immutable staging, rollback, and read-only canary controller.

This controller never builds or tags an image. It accepts only digest-qualified
images, applies a generated Compose override, records sanitized evidence, and
rolls back automatically when a post-change gate fails.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import ssl
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SCHEMA = "codestra.release-control.v1"
ENDPOINT_SCHEMA = "codestra.staging-endpoints.v1"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
IMAGE_RE = re.compile(r"^[^@\s]+@sha256:[0-9a-f]{64}$")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
PLACEHOLDER_RE = re.compile(r"(?i)(replace_with|placeholder|example|todo|tbd|change_me)")
ALLOWED_METHODS = ("GET", "HEAD")
FALSE_VALUES = {False, 0, "0", "false", "disabled", "off", "no", "none"}
SAFETY_EXPECTED: dict[str, Any] = {
    "LIVE_WRITE": False,
    "ODOO_WRITE": False,
    "ENABLE_EXTERNAL_DELIVERY": False,
    "N8N_DELIVERY_ENABLED": False,
    "LIVE_EMAIL_DELIVERY": False,
    "LIVE_SMS_DELIVERY": False,
    "LIVE_PSTN_DIALING": False,
    "PRODUCTION_DIALING": "DISABLED",
    "CAMPAIGN_ACTIVATION": False,
    "PROVIDER_DELIVERY": False,
}
REQUIRED_TOOLS = ("docker", "tar", "sha256sum", "restic")
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
DEFAULT_TIMEOUT = 15.0


class GateError(RuntimeError):
    """A fail-closed gate was not satisfied."""


@dataclasses.dataclass(frozen=True)
class HttpResult:
    status: int
    elapsed_ms: float
    body: bytes
    headers: Mapping[str, str]

    def json(self) -> Any:
        try:
            return json.loads(self.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GateError("endpoint did not return valid UTF-8 JSON") from exc


@dataclasses.dataclass
class Evidence:
    candidate_id: str
    mode: str
    started_at: str = dataclasses.field(default_factory=lambda: utc_now())
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
        self.completed_at = utc_now()
        self.verdict = verdict

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GateError(f"cannot load JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GateError(f"{path} must contain a JSON object")
    return value


def ensure_exact_keys(value: Mapping[str, Any], required: set[str], allowed: set[str], label: str) -> None:
    missing = required - set(value)
    extra = set(value) - allowed
    if missing:
        raise GateError(f"{label} missing keys: {', '.join(sorted(missing))}")
    if extra:
        raise GateError(f"{label} unknown keys: {', '.join(sorted(extra))}")


def no_placeholder(value: Any, label: str) -> None:
    if isinstance(value, str) and (not value.strip() or PLACEHOLDER_RE.search(value)):
        raise GateError(f"{label} contains a placeholder or empty value")


def validate_https_url(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise GateError(f"{label} must be a string")
    no_placeholder(value, label)
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise GateError(f"{label} must be an HTTPS URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise GateError(f"{label} must not contain credentials, query, or fragment")
    if parsed.port not in (None, 443):
        raise GateError(f"{label} may use only the HTTPS default port")
    return value


def validate_path(value: Any, label: str, prefixes: Sequence[Path], *, file_required: bool = False) -> Path:
    if not isinstance(value, str):
        raise GateError(f"{label} must be a path string")
    no_placeholder(value, label)
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise GateError(f"{label} must be an absolute non-traversing path")
    resolved = path.resolve(strict=file_required)
    if not any(resolved == prefix or prefix in resolved.parents for prefix in prefixes):
        raise GateError(f"{label} is outside the approved filesystem roots")
    if file_required:
        if path.is_symlink() or not resolved.is_file():
            raise GateError(f"{label} must be a regular non-symlink file")
    return resolved


def validate_candidate(candidate: Mapping[str, Any]) -> None:
    required = {
        "schema", "candidate_id", "candidate_source_lock_sha", "environment",
        "compose", "workloads", "safety", "keycloak", "kong", "backups",
        "rollback", "canary",
    }
    ensure_exact_keys(candidate, required, required, "candidate")
    if candidate.get("schema") != SCHEMA:
        raise GateError(f"candidate.schema must equal {SCHEMA}")
    candidate_id = candidate.get("candidate_id")
    if not isinstance(candidate_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,127}", candidate_id):
        raise GateError("candidate_id is invalid")
    if not SHA_RE.fullmatch(str(candidate.get("candidate_source_lock_sha", ""))):
        raise GateError("candidate_source_lock_sha must be an exact 40-hex SHA")
    if candidate.get("environment") != "staging-readonly":
        raise GateError("candidate environment must equal staging-readonly")

    compose = candidate.get("compose")
    if not isinstance(compose, dict):
        raise GateError("compose must be an object")
    ensure_exact_keys(compose, {"project_name", "files", "working_directory"}, {"project_name", "files", "working_directory"}, "compose")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{2,62}", str(compose.get("project_name", ""))):
        raise GateError("compose.project_name is invalid")
    files = compose.get("files")
    if not isinstance(files, list) or not files or len(files) != len(set(files)):
        raise GateError("compose.files must be a unique non-empty list")
    for index, value in enumerate(files):
        validate_path(value, f"compose.files[{index}]", (Path("/srv/codestra"),), file_required=False)
    validate_path(compose.get("working_directory"), "compose.working_directory", (Path("/srv/codestra"),), file_required=False)

    workloads = candidate.get("workloads")
    if not isinstance(workloads, list) or not workloads:
        raise GateError("workloads must be a non-empty list")
    names: set[str] = set()
    services: set[str] = set()
    images: set[str] = set()
    workload_required = {
        "name", "service", "repository", "source_sha", "image",
        "version_endpoint", "readiness_endpoint", "capabilities_endpoint",
        "expected_migration",
    }
    workload_allowed = workload_required | {"metrics_endpoint", "migration_endpoint"}
    for index, workload in enumerate(workloads):
        if not isinstance(workload, dict):
            raise GateError(f"workloads[{index}] must be an object")
        ensure_exact_keys(workload, workload_required, workload_allowed, f"workloads[{index}]")
        name = str(workload.get("name", ""))
        service = str(workload.get("service", ""))
        repository = str(workload.get("repository", ""))
        source_sha = str(workload.get("source_sha", ""))
        image = str(workload.get("image", ""))
        if not NAME_RE.fullmatch(name) or name in names:
            raise GateError(f"workloads[{index}].name is invalid or duplicated")
        if not NAME_RE.fullmatch(service) or service in services:
            raise GateError(f"workloads[{index}].service is invalid or duplicated")
        if not REPOSITORY_RE.fullmatch(repository):
            raise GateError(f"workloads[{index}].repository is invalid")
        if not SHA_RE.fullmatch(source_sha):
            raise GateError(f"workloads[{index}].source_sha is invalid")
        if not IMAGE_RE.fullmatch(image) or image in images:
            raise GateError(f"workloads[{index}].image is mutable, invalid, or duplicated")
        for endpoint_name in ("version_endpoint", "readiness_endpoint", "capabilities_endpoint"):
            validate_https_url(workload.get(endpoint_name), f"workloads[{index}].{endpoint_name}")
        for endpoint_name in ("metrics_endpoint", "migration_endpoint"):
            if endpoint_name in workload:
                validate_https_url(workload.get(endpoint_name), f"workloads[{index}].{endpoint_name}")
        migration = workload.get("expected_migration")
        if migration is not None:
            if not isinstance(migration, str) or not migration.strip() or len(migration) > 128:
                raise GateError(f"workloads[{index}].expected_migration is invalid")
        names.add(name)
        services.add(service)
        images.add(image)

    safety = candidate.get("safety")
    if safety != SAFETY_EXPECTED:
        raise GateError("candidate safety controls must be the complete reviewed all-off contract")

    keycloak = candidate.get("keycloak")
    if not isinstance(keycloak, dict):
        raise GateError("keycloak must be an object")
    ensure_exact_keys(keycloak, {"discovery_endpoint", "expected_issuer"}, {"discovery_endpoint", "expected_issuer"}, "keycloak")
    validate_https_url(keycloak.get("discovery_endpoint"), "keycloak.discovery_endpoint")
    validate_https_url(keycloak.get("expected_issuer"), "keycloak.expected_issuer")

    kong = candidate.get("kong")
    if not isinstance(kong, dict):
        raise GateError("kong must be an object")
    ensure_exact_keys(kong, {"expected_route_count", "smoke_routes"}, {"expected_route_count", "smoke_routes"}, "kong")
    if kong.get("expected_route_count") != 29:
        raise GateError("Kong expected_route_count must equal 29")
    routes = kong.get("smoke_routes")
    if not isinstance(routes, list) or len(routes) != 29:
        raise GateError("Kong smoke_routes must contain exactly 29 routes")
    route_names: set[str] = set()
    route_urls: set[str] = set()
    for index, route in enumerate(routes):
        if not isinstance(route, dict):
            raise GateError(f"kong.smoke_routes[{index}] must be an object")
        ensure_exact_keys(route, {"name", "url", "expected_statuses"}, {"name", "url", "expected_statuses"}, f"kong.smoke_routes[{index}]")
        name = str(route.get("name", ""))
        url = validate_https_url(route.get("url"), f"kong.smoke_routes[{index}].url")
        statuses = route.get("expected_statuses")
        if not NAME_RE.fullmatch(name) or name in route_names or url in route_urls:
            raise GateError("Kong smoke route name or URL is invalid or duplicated")
        if not isinstance(statuses, list) or not statuses or any(type(item) is not int or item < 200 or item > 499 for item in statuses):
            raise GateError(f"kong.smoke_routes[{index}].expected_statuses is invalid")
        route_names.add(name)
        route_urls.add(url)

    backups = candidate.get("backups")
    if not isinstance(backups, dict):
        raise GateError("backups must be an object")
    ensure_exact_keys(backups, {"directory", "postgres", "odoo_filestore", "configuration", "off_host"}, {"directory", "postgres", "odoo_filestore", "configuration", "off_host"}, "backups")
    validate_path(backups.get("directory"), "backups.directory", (Path("/var/backups/codestra"),), file_required=False)
    validate_path(backups.get("odoo_filestore"), "backups.odoo_filestore", (Path("/srv/codestra"),), file_required=False)
    configuration = backups.get("configuration")
    if not isinstance(configuration, list) or not configuration or len(configuration) != len(set(configuration)):
        raise GateError("backups.configuration must be a unique non-empty list")
    for index, value in enumerate(configuration):
        validate_path(value, f"backups.configuration[{index}]", (Path("/srv/codestra"),), file_required=False)
    postgres = backups.get("postgres")
    if not isinstance(postgres, dict):
        raise GateError("backups.postgres must be an object")
    ensure_exact_keys(postgres, {"service", "database", "username"}, {"service", "database", "username"}, "backups.postgres")
    for key in ("service", "database", "username"):
        if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,62}", str(postgres.get(key, ""))):
            raise GateError(f"backups.postgres.{key} is invalid")
    off_host = backups.get("off_host")
    if off_host != {"required": True, "restic_repository_environment": "RESTIC_REPOSITORY"}:
        raise GateError("off-host restic backup must be required")

    rollback = candidate.get("rollback")
    if not isinstance(rollback, dict):
        raise GateError("rollback must be an object")
    ensure_exact_keys(rollback, {"previous_source_lock_sha", "workloads"}, {"previous_source_lock_sha", "workloads"}, "rollback")
    if not SHA_RE.fullmatch(str(rollback.get("previous_source_lock_sha", ""))):
        raise GateError("rollback.previous_source_lock_sha is invalid")
    previous = rollback.get("workloads")
    if not isinstance(previous, list) or len(previous) != len(workloads):
        raise GateError("rollback.workloads must cover every candidate workload")
    previous_services: set[str] = set()
    for index, workload in enumerate(previous):
        if not isinstance(workload, dict):
            raise GateError(f"rollback.workloads[{index}] must be an object")
        ensure_exact_keys(workload, {"service", "source_sha", "image"}, {"service", "source_sha", "image"}, f"rollback.workloads[{index}]")
        service = str(workload.get("service", ""))
        if service not in services or service in previous_services:
            raise GateError("rollback service set does not match candidate service set")
        if not SHA_RE.fullmatch(str(workload.get("source_sha", ""))) or not IMAGE_RE.fullmatch(str(workload.get("image", ""))):
            raise GateError(f"rollback.workloads[{index}] has invalid immutable identity")
        previous_services.add(service)
    if previous_services != services:
        raise GateError("rollback workloads do not cover the exact candidate services")

    canary = candidate.get("canary")
    if not isinstance(canary, dict):
        raise GateError("canary must be an object")
    ensure_exact_keys(canary, {"maximum_percent", "methods", "controller", "controller_sha256"}, {"maximum_percent", "methods", "controller", "controller_sha256"}, "canary")
    percent = canary.get("maximum_percent")
    if isinstance(percent, bool) or not isinstance(percent, (int, float)) or percent <= 0 or percent > 1:
        raise GateError("canary.maximum_percent must be greater than zero and no more than one")
    if canary.get("methods") != ["GET", "HEAD"]:
        raise GateError("canary methods must be exactly GET and HEAD")
    controller = validate_path(canary.get("controller"), "canary.controller", (Path("/srv/codestra/bin"),), file_required=False)
    if not HASH_RE.fullmatch(str(canary.get("controller_sha256", ""))):
        raise GateError("canary.controller_sha256 is invalid")
    if controller.name in {"sh", "bash", "python", "python3", "env"}:
        raise GateError("canary controller must be a dedicated reviewed executable")


def validate_endpoint_manifest(manifest: Mapping[str, Any], candidate: Mapping[str, Any]) -> None:
    required = {"schema", "candidate_id", "bearer_token_environment", "metrics_token_environment", "counters", "probe"}
    ensure_exact_keys(manifest, required, required, "endpoint manifest")
    if manifest.get("schema") != ENDPOINT_SCHEMA:
        raise GateError(f"endpoint manifest schema must equal {ENDPOINT_SCHEMA}")
    if manifest.get("candidate_id") != candidate.get("candidate_id"):
        raise GateError("endpoint manifest is not bound to the candidate_id")
    for key in ("bearer_token_environment", "metrics_token_environment"):
        value = manifest.get(key)
        if not isinstance(value, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{2,63}", value):
            raise GateError(f"endpoint manifest {key} is invalid")
        if not os.environ.get(value):
            raise GateError(f"required protected credential is not bound: {value}")
    counters = manifest.get("counters")
    if not isinstance(counters, list) or len(counters) < 3:
        raise GateError("endpoint manifest must contain calls, emails, and SMS counters")
    names: set[str] = set()
    required_counters = {"calls", "emails", "sms"}
    for index, counter in enumerate(counters):
        if not isinstance(counter, dict):
            raise GateError(f"counters[{index}] must be an object")
        ensure_exact_keys(counter, {"name", "url", "json_pointer", "expected"}, {"name", "url", "json_pointer", "expected"}, f"counters[{index}]")
        name = str(counter.get("name", ""))
        if not NAME_RE.fullmatch(name) or name in names:
            raise GateError("counter name is invalid or duplicated")
        validate_https_url(counter.get("url"), f"counters[{index}].url")
        pointer = counter.get("json_pointer")
        if not isinstance(pointer, str) or not pointer.startswith("/") or ".." in pointer:
            raise GateError(f"counters[{index}].json_pointer is invalid")
        if counter.get("expected") != 0:
            raise GateError(f"counters[{index}] must have expected zero")
        names.add(name)
    if not required_counters <= names:
        raise GateError("endpoint manifest is missing calls, emails, or SMS counter")
    probe = manifest.get("probe")
    if not isinstance(probe, dict):
        raise GateError("probe must be an object")
    ensure_exact_keys(probe, {"requests", "maximum_error_rate", "maximum_p95_ms", "maximum_regression_percent"}, {"requests", "maximum_error_rate", "maximum_p95_ms", "maximum_regression_percent"}, "probe")
    requests = probe.get("requests")
    if type(requests) is not int or requests < 10 or requests > 1000:
        raise GateError("probe.requests must be between 10 and 1000")
    for key in ("maximum_error_rate", "maximum_regression_percent"):
        value = probe.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 or value > 100:
            raise GateError(f"probe.{key} must be between 0 and 100")
    p95 = probe.get("maximum_p95_ms")
    if isinstance(p95, bool) or not isinstance(p95, (int, float)) or p95 <= 0:
        raise GateError("probe.maximum_p95_ms must be positive")


def run(command: Sequence[str], *, cwd: Path | None = None, input_bytes: bytes | None = None, capture: bool = True, env: Mapping[str, str] | None = None) -> subprocess.CompletedProcess[bytes]:
    if not command or any(not isinstance(part, str) or not part for part in command):
        raise GateError("invalid subprocess command")
    completed = subprocess.run(
        list(command),
        cwd=cwd,
        input=input_bytes,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        env=dict(env) if env is not None else None,
        check=False,
    )
    if completed.returncode:
        stderr = (completed.stderr or b"").decode("utf-8", errors="replace")[-1500:]
        raise GateError(f"command failed ({command[0]}): {stderr.strip()}")
    return completed


def compose_command(candidate: Mapping[str, Any], override: Path, *arguments: str) -> list[str]:
    compose = candidate["compose"]
    command = ["docker", "compose", "--project-name", compose["project_name"]]
    for value in compose["files"]:
        command.extend(["--file", value])
    command.extend(["--file", str(override)])
    command.extend(arguments)
    return command


def write_override(workloads: Iterable[Mapping[str, Any]], path: Path) -> None:
    lines = ["services:"]
    for workload in sorted(workloads, key=lambda item: item["service"]):
        service = workload["service"]
        image = workload["image"]
        if not NAME_RE.fullmatch(service) or not IMAGE_RE.fullmatch(image):
            raise GateError("unsafe workload identity while generating Compose override")
        lines.extend([f"  {service}:", f"    image: {image}"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.chmod(0o600)


def require_tools() -> None:
    missing = [name for name in REQUIRED_TOOLS if shutil.which(name) is None]
    if missing:
        raise GateError("required host tools are missing: " + ", ".join(missing))


def verify_images(workloads: Iterable[Mapping[str, Any]]) -> None:
    for workload in workloads:
        image = workload["image"]
        run(["docker", "pull", image], capture=True)
        revision = run(
            ["docker", "image", "inspect", image, "--format", "{{ index .Config.Labels \"org.opencontainers.image.revision\" }}"],
            capture=True,
        ).stdout.decode("utf-8", errors="strict").strip()
        if revision != workload["source_sha"]:
            raise GateError(
                f"image source revision mismatch for {workload['service']}: "
                f"expected {workload['source_sha']}, got {revision or 'absent'}"
            )
        repo_label = run(
            ["docker", "image", "inspect", image, "--format", "{{ index .Config.Labels \"org.opencontainers.image.source\" }}"],
            capture=True,
        ).stdout.decode("utf-8", errors="strict").strip()
        if workload["repository"].lower() not in repo_label.lower():
            raise GateError(f"image source repository label mismatch for {workload['service']}")


def request(url: str, *, token: str | None, method: str = "GET", timeout: float = DEFAULT_TIMEOUT) -> HttpResult:
    if method not in ALLOWED_METHODS:
        raise GateError(f"HTTP method prohibited by read-only controller: {method}")
    headers = {"Accept": "application/json", "User-Agent": "codestra-readonly-certifier/1"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers, method=method)
    context = ssl.create_default_context()
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=context) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise GateError("endpoint response exceeded the bounded read limit")
            return HttpResult(
                status=response.status,
                elapsed_ms=(time.monotonic() - started) * 1000.0,
                body=body,
                headers=dict(response.headers.items()),
            )
    except urllib.error.HTTPError as exc:
        body = exc.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            body = b""
        return HttpResult(
            status=exc.code,
            elapsed_ms=(time.monotonic() - started) * 1000.0,
            body=body,
            headers=dict(exc.headers.items()),
        )
    except (urllib.error.URLError, TimeoutError, ssl.SSLError) as exc:
        raise GateError(f"HTTPS request failed for {url}: {exc}") from exc


def json_pointer(value: Any, pointer: str) -> Any:
    current = value
    for raw in pointer.lstrip("/").split("/"):
        part = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError) as exc:
                raise GateError(f"JSON pointer not found: {pointer}") from exc
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise GateError(f"JSON pointer not found: {pointer}")
    return current


def find_first(value: Any, keys: set[str]) -> Any:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in keys:
                return child
        for child in value.values():
            found = find_first(child, keys)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_first(child, keys)
            if found is not None:
                return found
    return None


def bearer_tokens(manifest: Mapping[str, Any]) -> tuple[str, str]:
    bearer = os.environ.get(manifest["bearer_token_environment"], "")
    metrics = os.environ.get(manifest["metrics_token_environment"], "")
    if not bearer or not metrics:
        raise GateError("protected read-only bearer and metrics credentials are required")
    return bearer, metrics


def read_counters(manifest: Mapping[str, Any], token: str) -> dict[str, int]:
    values: dict[str, int] = {}
    for counter in manifest["counters"]:
        result = request(counter["url"], token=token)
        if result.status != 200:
            raise GateError(f"counter endpoint {counter['name']} returned HTTP {result.status}")
        value = json_pointer(result.json(), counter["json_pointer"])
        if type(value) is not int or value < 0:
            raise GateError(f"counter {counter['name']} did not return a non-negative integer")
        values[counter["name"]] = value
    return values


def assert_zero_and_unchanged(before: Mapping[str, int], after: Mapping[str, int]) -> None:
    if set(before) != set(after):
        raise GateError("live-effect counter inventory changed")
    for name in sorted(before):
        if before[name] != 0 or after[name] != 0:
            raise GateError(f"live-effect counter moved or is nonzero: {name} {before[name]}->{after[name]}")


def check_workload(workload: Mapping[str, Any], bearer: str, metrics: str) -> dict[str, Any]:
    version = request(workload["version_endpoint"], token=bearer)
    if version.status != 200:
        raise GateError(f"{workload['name']} version endpoint returned HTTP {version.status}")
    version_json = version.json()
    readback = find_first(version_json, {"source_sha", "git_sha", "commit_sha", "revision"})
    if readback != workload["source_sha"]:
        raise GateError(f"{workload['name']} source-version readback mismatch")

    readiness = request(workload["readiness_endpoint"], token=bearer)
    if readiness.status != 200:
        raise GateError(f"{workload['name']} readiness endpoint returned HTTP {readiness.status}")
    readiness_json = readiness.json()
    ready = find_first(readiness_json, {"ready", "readiness", "status"})
    if ready not in (True, "ready", "ok", "pass", "healthy"):
        raise GateError(f"{workload['name']} did not report ready")

    capabilities = request(workload["capabilities_endpoint"], token=bearer)
    if capabilities.status != 200:
        raise GateError(f"{workload['name']} capabilities endpoint returned HTTP {capabilities.status}")
    capabilities_json = capabilities.json()
    for key, expected in SAFETY_EXPECTED.items():
        actual = find_first(capabilities_json, {key.lower()})
        if actual is None:
            raise GateError(f"{workload['name']} capabilities omitted {key}")
        if key == "PRODUCTION_DIALING":
            if str(actual).upper() != "DISABLED":
                raise GateError(f"{workload['name']} capability {key} is not disabled")
        elif actual not in FALSE_VALUES and str(actual).lower() not in {str(item).lower() for item in FALSE_VALUES}:
            raise GateError(f"{workload['name']} capability {key} is live or malformed")

    migration = None
    if workload.get("migration_endpoint"):
        migration_result = request(workload["migration_endpoint"], token=bearer)
        if migration_result.status != 200:
            raise GateError(f"{workload['name']} migration endpoint returned HTTP {migration_result.status}")
        migration = find_first(migration_result.json(), {"migration", "migration_head", "schema_revision", "current_revision", "head"})
        if migration != workload.get("expected_migration"):
            raise GateError(f"{workload['name']} database migration readback mismatch")
    elif workload.get("expected_migration") is not None:
        raise GateError(f"{workload['name']} has an expected migration but no migration endpoint")

    metrics_status = None
    if workload.get("metrics_endpoint"):
        anonymous = request(workload["metrics_endpoint"], token=None)
        if anonymous.status not in (401, 403):
            raise GateError(f"{workload['name']} metrics are not protected")
        authorized = request(workload["metrics_endpoint"], token=metrics)
        if authorized.status != 200:
            raise GateError(f"{workload['name']} protected metrics returned HTTP {authorized.status}")
        metrics_status = authorized.status

    return {
        "name": workload["name"],
        "source_sha": workload["source_sha"],
        "version_ms": round(version.elapsed_ms, 3),
        "readiness_ms": round(readiness.elapsed_ms, 3),
        "migration": migration,
        "metrics_status": metrics_status,
    }


def check_keycloak(candidate: Mapping[str, Any], bearer: str) -> None:
    result = request(candidate["keycloak"]["discovery_endpoint"], token=bearer)
    if result.status != 200:
        raise GateError(f"Keycloak discovery returned HTTP {result.status}")
    issuer = result.json().get("issuer") if isinstance(result.json(), dict) else None
    if issuer != candidate["keycloak"]["expected_issuer"]:
        raise GateError("Keycloak issuer mismatch")


def check_kong(candidate: Mapping[str, Any], bearer: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    routes = candidate["kong"]["smoke_routes"]
    if len(routes) != candidate["kong"]["expected_route_count"]:
        raise GateError("Kong route denominator drifted before smoke test")
    for route in routes:
        response = request(route["url"], token=bearer)
        if response.status not in route["expected_statuses"]:
            raise GateError(
                f"Kong route {route['name']} returned HTTP {response.status}; "
                f"expected one of {route['expected_statuses']}"
            )
        results.append({"name": route["name"], "status": response.status, "elapsed_ms": round(response.elapsed_ms, 3)})
    return results


def run_all_checks(candidate: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, Any]:
    bearer, metrics = bearer_tokens(manifest)
    workload_results = [check_workload(workload, bearer, metrics) for workload in candidate["workloads"]]
    check_keycloak(candidate, bearer)
    route_results = check_kong(candidate, bearer)
    return {"workloads": workload_results, "kong_routes": route_results}


def create_backup(candidate: Mapping[str, Any], override: Path, evidence: Evidence) -> Path:
    backup_root = Path(candidate["backups"]["directory"])
    backup_dir = backup_root / f"{candidate['candidate_id']}-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    backup_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
    working = Path(candidate["compose"]["working_directory"])
    postgres = candidate["backups"]["postgres"]
    database_path = backup_dir / "database.dump"
    dump = run(
        compose_command(
            candidate,
            override,
            "exec", "-T", postgres["service"],
            "pg_dump", "-Fc", "-U", postgres["username"], postgres["database"],
        ),
        cwd=working,
        capture=True,
    )
    if not dump.stdout:
        raise GateError("PostgreSQL backup is empty")
    database_path.write_bytes(dump.stdout)
    database_path.chmod(0o600)

    filestore = Path(candidate["backups"]["odoo_filestore"])
    if not filestore.exists() or filestore.is_symlink():
        raise GateError("Odoo filestore path is missing or symbolic")
    run(["tar", "--numeric-owner", "--xattrs", "--acls", "-C", str(filestore.parent), "-czf", str(backup_dir / "odoo-filestore.tar.gz"), filestore.name])

    config_archive = backup_dir / "configuration.tar.gz"
    config_paths = [Path(item) for item in candidate["backups"]["configuration"]]
    for path in config_paths:
        if not path.exists() or path.is_symlink():
            raise GateError(f"configuration backup path is missing or symbolic: {path}")
    run(["tar", "--numeric-owner", "--xattrs", "--acls", "-czf", str(config_archive), *[str(path) for path in config_paths]])

    metadata = {
        "schema": "codestra.recovery-point.v1",
        "candidate_id": candidate["candidate_id"],
        "candidate_source_lock_sha": candidate["candidate_source_lock_sha"],
        "created_at": utc_now(),
        "database": postgres["database"],
        "filestore": str(filestore),
        "configuration": [str(path) for path in config_paths],
    }
    (backup_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checksum_lines: list[str] = []
    for path in sorted(backup_dir.iterdir()):
        if path.is_file() and path.name != "SHA256SUMS":
            checksum_lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")
    (backup_dir / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    run(["sha256sum", "--check", "SHA256SUMS"], cwd=backup_dir)

    restic_environment = dict(os.environ)
    if not restic_environment.get("RESTIC_REPOSITORY"):
        raise GateError("RESTIC_REPOSITORY is not bound for required off-host backup")
    if not (restic_environment.get("RESTIC_PASSWORD_FILE") or restic_environment.get("RESTIC_PASSWORD_COMMAND")):
        raise GateError("restic password must be supplied through a protected file or command")
    restic = run(
        ["restic", "backup", "--json", "--tag", candidate["candidate_id"], str(backup_dir)],
        capture=True,
        env=restic_environment,
    )
    snapshot_id = None
    for line in restic.stdout.decode("utf-8", errors="replace").splitlines():
        with contextlib.suppress(json.JSONDecodeError):
            item = json.loads(line)
            if isinstance(item, dict) and item.get("message_type") == "summary":
                snapshot_id = item.get("snapshot_id")
    if not isinstance(snapshot_id, str) or not snapshot_id:
        raise GateError("off-host restic backup did not return a snapshot identity")
    evidence.artifacts.append({"type": "recovery-point", "path": str(backup_dir), "restic_snapshot": snapshot_id})
    return backup_dir


def verify_compose_images(candidate: Mapping[str, Any], override: Path) -> None:
    working = Path(candidate["compose"]["working_directory"])
    rendered = run(compose_command(candidate, override, "config", "--images"), cwd=working).stdout.decode("utf-8", errors="strict").splitlines()
    expected = sorted(workload["image"] for workload in candidate["workloads"])
    actual = sorted(line.strip() for line in rendered if line.strip())
    if actual != expected:
        raise GateError(f"rendered Compose images do not exactly match candidate digests: expected {expected}, got {actual}")


def deploy(candidate: Mapping[str, Any], override: Path) -> None:
    working = Path(candidate["compose"]["working_directory"])
    verify_compose_images(candidate, override)
    run(compose_command(candidate, override, "up", "-d", "--no-build", "--pull", "never", "--remove-orphans"), cwd=working, capture=True)


def integrity_manifest(path: Path) -> dict[str, str]:
    results: dict[str, str] = {}
    for child in sorted(path.rglob("*")):
        if child.is_file() and not child.is_symlink():
            results[str(child.relative_to(path))] = hashlib.sha256(child.read_bytes()).hexdigest()
    return results


def rollback_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="codestra-rollback-") as directory:
        override = Path(directory) / "rollback.override.yml"
        write_override(candidate["rollback"]["workloads"], override)
        started = time.monotonic()
        deploy(candidate, override)
        return {"rto_seconds": round(time.monotonic() - started, 3)}


def execute_staging(candidate: Mapping[str, Any], manifest: Mapping[str, Any], evidence: Evidence) -> None:
    require_tools()
    with tempfile.TemporaryDirectory(prefix="codestra-candidate-") as directory:
        override = Path(directory) / "candidate.override.yml"
        write_override(candidate["workloads"], override)
        verify_images(candidate["workloads"])
        evidence.record("immutable-image-source-readback", "PASS", workloads=len(candidate["workloads"]))
        verify_compose_images(candidate, override)
        evidence.record("compose-image-digest-lock", "PASS")
        bearer, _ = bearer_tokens(manifest)
        baseline = read_counters(manifest, bearer)
        assert_zero_and_unchanged(baseline, baseline)
        evidence.measurements["baseline_live_effect_counters"] = baseline
        evidence.record("zero-live-effect-baseline", "PASS")
        backup_dir = create_backup(candidate, override, evidence)
        evidence.record("paired-local-and-off-host-backup", "PASS", recovery_point=str(backup_dir))
        deployment_started = False
        try:
            deployment_started = True
            deploy(candidate, override)
            evidence.record("immutable-staging-deployment", "PASS")
            results = run_all_checks(candidate, manifest)
            evidence.measurements["staging_checks"] = results
            evidence.record("source-readiness-capabilities-metrics-migrations", "PASS", workloads=len(results["workloads"]))
            evidence.record("keycloak-issuer", "PASS")
            evidence.record("kong-29-route-smoke", "PASS", routes=len(results["kong_routes"]))
            after = read_counters(manifest, bearer)
            assert_zero_and_unchanged(baseline, after)
            evidence.measurements["final_live_effect_counters"] = after
            evidence.record("zero-calls-emails-sms", "PASS")
        except Exception:
            if deployment_started:
                rollback = rollback_candidate(candidate)
                evidence.rollback_performed = True
                evidence.measurements["automatic_rollback"] = rollback
            raise


def execute_rollback_rehearsal(candidate: Mapping[str, Any], manifest: Mapping[str, Any], evidence: Evidence) -> None:
    require_tools()
    bearer, _ = bearer_tokens(manifest)
    baseline = read_counters(manifest, bearer)
    assert_zero_and_unchanged(baseline, baseline)
    filestore = Path(candidate["backups"]["odoo_filestore"])
    before_integrity = integrity_manifest(filestore)
    recovery_point_started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="codestra-rehearsal-") as directory:
        candidate_override = Path(directory) / "candidate.override.yml"
        previous_override = Path(directory) / "previous.override.yml"
        write_override(candidate["workloads"], candidate_override)
        write_override(candidate["rollback"]["workloads"], previous_override)
        backup_dir = create_backup(candidate, candidate_override, evidence)
        recovery_point_age = time.monotonic() - recovery_point_started
        rollback_started = time.monotonic()
        deploy(candidate, previous_override)
        previous_rto = time.monotonic() - rollback_started
        previous_results = run_all_checks(
            {
                **candidate,
                "workloads": [
                    {
                        **next(item for item in candidate["workloads"] if item["service"] == previous["service"]),
                        "source_sha": previous["source_sha"],
                        "image": previous["image"],
                    }
                    for previous in candidate["rollback"]["workloads"]
                ],
            },
            manifest,
        )
        redeploy_started = time.monotonic()
        deploy(candidate, candidate_override)
        candidate_results = run_all_checks(candidate, manifest)
        candidate_rto = time.monotonic() - redeploy_started
        after_integrity = integrity_manifest(filestore)
        if before_integrity != after_integrity:
            raise GateError("Odoo filestore integrity changed during read-only rollback rehearsal")
        after = read_counters(manifest, bearer)
        assert_zero_and_unchanged(baseline, after)
        evidence.measurements.update(
            {
                "rto_previous_seconds": round(previous_rto, 3),
                "rto_candidate_seconds": round(candidate_rto, 3),
                "observed_recovery_point_age_seconds": round(recovery_point_age, 3),
                "rpo_statement": "zero application writes permitted; recovery point age recorded above",
                "filestore_files_hashed": len(before_integrity),
                "recovery_point": str(backup_dir),
                "previous_checks": previous_results,
                "candidate_checks": candidate_results,
                "live_effect_counters": after,
            }
        )
        evidence.record("rollback-to-previous-exact-identities", "PASS", rto_seconds=round(previous_rto, 3))
        evidence.record("candidate-redeployment", "PASS", rto_seconds=round(candidate_rto, 3))
        evidence.record("data-integrity", "PASS", filestore_files=len(before_integrity))
        evidence.record("rollback-health-readiness-version", "PASS")
        evidence.record("zero-live-effects-during-rehearsal", "PASS")


def percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        raise GateError("cannot calculate percentile of empty sample")
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * fraction)))
    return ordered[index]


def execute_canary(candidate: Mapping[str, Any], manifest: Mapping[str, Any], evidence: Evidence, staging_evidence_path: Path, requested_percent: float) -> None:
    require_tools()
    staging = load_json(staging_evidence_path)
    if staging.get("candidate_id") != candidate["candidate_id"] or staging.get("mode") != "staging" or staging.get("verdict") != "GO":
        raise GateError("production canary requires a GO staging evidence file for the exact candidate")
    if any(gate.get("status") != "PASS" for gate in staging.get("gates", [])):
        raise GateError("staging evidence contains a non-PASS gate")
    maximum = float(candidate["canary"]["maximum_percent"])
    if requested_percent <= 0 or requested_percent > maximum or requested_percent > 1:
        raise GateError("requested canary percentage exceeds the candidate or one-percent ceiling")
    controller = validate_path(candidate["canary"]["controller"], "canary.controller", (Path("/srv/codestra/bin"),), file_required=True)
    mode = controller.stat().st_mode
    if mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise GateError("canary controller is group/world writable")
    digest = hashlib.sha256(controller.read_bytes()).hexdigest()
    if digest != candidate["canary"]["controller_sha256"]:
        raise GateError("canary controller SHA-256 mismatch")
    bearer, _ = bearer_tokens(manifest)
    baseline_counters = read_counters(manifest, bearer)
    assert_zero_and_unchanged(baseline_counters, baseline_counters)
    baseline_latencies: list[float] = []
    canary_latencies: list[float] = []
    errors = 0
    probe = manifest["probe"]
    primary = candidate["workloads"][0]["readiness_endpoint"]
    for _ in range(probe["requests"]):
        result = request(primary, token=bearer, method="GET")
        if result.status != 200:
            errors += 1
        baseline_latencies.append(result.elapsed_ms)
    run(
        [str(controller), "apply", "--candidate", candidate["candidate_id"], "--percent", f"{requested_percent:.6f}", "--methods", "GET,HEAD", "--read-only"],
        capture=True,
    )
    canary_applied = True
    try:
        checks = run_all_checks(candidate, manifest)
        for _ in range(probe["requests"]):
            result = request(primary, token=bearer, method="GET")
            if result.status != 200:
                errors += 1
            canary_latencies.append(result.elapsed_ms)
        total = probe["requests"] * 2
        error_rate = (errors / total) * 100.0
        baseline_p95 = percentile(baseline_latencies, 0.95)
        canary_p95 = percentile(canary_latencies, 0.95)
        regression = 0.0 if baseline_p95 == 0 else ((canary_p95 - baseline_p95) / baseline_p95) * 100.0
        if error_rate > probe["maximum_error_rate"]:
            raise GateError("canary error rate exceeded the approved ceiling")
        if canary_p95 > probe["maximum_p95_ms"]:
            raise GateError("canary p95 latency exceeded the absolute ceiling")
        if regression > probe["maximum_regression_percent"]:
            raise GateError("canary p95 latency regression exceeded the approved ceiling")
        after = read_counters(manifest, bearer)
        assert_zero_and_unchanged(baseline_counters, after)
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
            }
        )
        evidence.record("production-readonly-canary", "PASS", percent=requested_percent, methods=["GET", "HEAD"])
        evidence.record("latency-and-error-budget", "PASS")
        evidence.record("zero-live-effect-counter-movement", "PASS")
    except Exception:
        if canary_applied:
            run([str(controller), "rollback", "--candidate", candidate["candidate_id"]], capture=True)
            evidence.rollback_performed = True
        raise


def write_evidence(path: Path, evidence: Evidence) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(evidence.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--endpoint-manifest", type=Path, required=True)
    parser.add_argument("--mode", choices=("validate", "staging", "rollback-rehearsal", "production-readonly-canary"), required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--staging-evidence", type=Path)
    parser.add_argument("--canary-percent", type=float, default=1.0)
    parser.add_argument("--confirm-candidate-id")
    parser.add_argument("--confirm-source-lock-sha")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    candidate: dict[str, Any] = {}
    evidence = Evidence(candidate_id="unloaded", mode=args.mode)
    try:
        candidate = load_json(args.candidate)
        evidence.candidate_id = str(candidate.get("candidate_id", "invalid"))
        validate_candidate(candidate)
        manifest = load_json(args.endpoint_manifest)
        if args.mode == "validate":
            # Structural validation does not require credentials; execution does.
            if manifest.get("schema") != ENDPOINT_SCHEMA or manifest.get("candidate_id") != candidate.get("candidate_id"):
                raise GateError("endpoint manifest structure or candidate binding is invalid")
            evidence.record("release-control-policy", "PASS")
            evidence.finish("GO")
            write_evidence(args.evidence, evidence)
            return 0
        if args.confirm_candidate_id != candidate["candidate_id"]:
            raise GateError("--confirm-candidate-id must match the exact candidate")
        if args.confirm_source_lock_sha != candidate["candidate_source_lock_sha"]:
            raise GateError("--confirm-source-lock-sha must match the exact source lock")
        validate_endpoint_manifest(manifest, candidate)
        evidence.record("protected-endpoint-manifest-and-credentials", "PASS")
        if args.mode == "staging":
            execute_staging(candidate, manifest, evidence)
        elif args.mode == "rollback-rehearsal":
            execute_rollback_rehearsal(candidate, manifest, evidence)
        else:
            if args.staging_evidence is None:
                raise GateError("production canary requires --staging-evidence")
            execute_canary(candidate, manifest, evidence, args.staging_evidence, args.canary_percent)
        evidence.finish("GO")
        write_evidence(args.evidence, evidence)
        print("CODESTRA_RELEASE_CONTROL=PASS")
        print(f"MODE={args.mode}")
        print(f"CANDIDATE_ID={candidate['candidate_id']}")
        print("VERDICT=GO")
        return 0
    except (GateError, OSError, subprocess.SubprocessError) as exc:
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
