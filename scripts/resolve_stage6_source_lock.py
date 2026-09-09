#!/usr/bin/env python3
"""Resolve Stage 6 source, artifact, runtime, and activation gates independently."""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "STAGE6-SOURCE-LOCK.yaml"
OUTPUT = ROOT / "STAGE6-SOURCE-LOCK.RESOLVED.yaml"
CHECKOUT_ROOT = Path("/root/stage6-source-lock-checkouts")
MIDDLEWARE_RELEASE_MANIFEST = (
    ROOT
    / "reports/runtime-reconciliation/middleware-release-9152a0/release-manifest.v1.json"
)
MIDDLEWARE_VERIFIER = ROOT / "scripts/verify_stage6_middleware_artifact.py"
SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
SAFE_VALUES = {"false", "disabled", "0", "off", "no"}
SAFETY_KEYS = (
    "LIVE_ADVERTISING_ENABLED",
    "EXTERNAL_DELIVERY_ENABLED",
    "SOCIAL_PUBLISHING_ENABLED",
    "EXTERNAL_MODEL_CALLS_ENABLED",
    "LIVE_SMS_DELIVERY",
    "LIVE_EMAIL_DELIVERY",
    "LIVE_PSTN_DIALING",
    "PRODUCTION_DIALING",
    "ENABLE_EXTERNAL_DELIVERY",
    "LIVE_WRITE",
    "LIVE_WRITES",
)
# Image names are reviewed authority, not inferred from arbitrary component names.
IMAGE_REFERENCES = {
    "middleware": "ghcr.io/appolon1908-hue/codestra-middleware",
    "odoo": "docker.io/library/odoo",
    "n8n": "docker.io/n8nio/n8n",
    "openbao": "ghcr.io/openbao/openbao",
    "social_runtime": "ghcr.io/appolon1908-hue/social.codestra.co",
    "kong": "docker.io/kong/kong-gateway",
    "keycloak": "quay.io/keycloak/keycloak",
}
UPSTREAM_COMPONENTS = {"odoo", "n8n", "openbao", "kong", "keycloak"}
CORE_COMPONENTS = {"middleware", "odoo", "n8n"}
MIDDLEWARE_RUN_ID = 33427334862
INSPECTION_HOST = "37.27.128.39"
DOCKER_ENDPOINT = "unix:///var/run/docker.sock"


def run(*args: str, cwd: Path | None = None) -> str:
    return subprocess.check_output(
        list(args), cwd=cwd, text=True, stderr=subprocess.STDOUT
    ).strip()


def file_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def middleware_artifact_verification() -> dict:
    try:
        result = json.loads(run(sys.executable, str(MIDDLEWARE_VERIFIER), "--json"))
        if not isinstance(result, dict):
            raise ValueError("artifact verifier returned a non-object result")
        return result
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        return {
            "status": "FAIL",
            "error": (getattr(exc, "output", None) or str(exc))[-2000:],
            "checks": {},
        }


def registry_resolution(reference: str, digest: str) -> dict:
    result = {
        "reference": f"{reference}@{digest}",
        "resolved_digest": None,
        "registry_resolution": "FAIL",
    }
    try:
        with tempfile.TemporaryDirectory(prefix="stage6-docker-config-") as config:
            output = run(
                "docker", "--config", config, "--host", DOCKER_ENDPOINT,
                "buildx", "imagetools", "inspect", result["reference"],
            )
        match = re.search(r"^Digest:\s+(sha256:[0-9a-f]{64})$", output, re.MULTILINE)
        result["resolved_digest"] = match.group(1) if match else None
        result["registry_resolution"] = (
            "PASS" if result["resolved_digest"] == digest else "FAIL_DIGEST_MISMATCH"
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        result["error"] = (getattr(exc, "output", None) or str(exc))[-1000:]
    return result


def local_image_labels(reference: str) -> dict:
    try:
        image = json.loads(
            run("docker", "--host", DOCKER_ENDPOINT, "image", "inspect", reference)
        )[0]
        return image["Config"].get("Labels") or {}
    except (OSError, subprocess.CalledProcessError, ValueError, KeyError, IndexError, TypeError):
        return {}


def docker_runtime() -> list[dict]:
    ids = run("docker", "--host", DOCKER_ENDPOINT, "ps", "-q").split()
    if not ids:
        return []
    containers = json.loads(
        run("docker", "--host", DOCKER_ENDPOINT, "inspect", *ids)
    )
    image_ids = sorted({container["Image"] for container in containers})
    images = json.loads(
        run("docker", "--host", DOCKER_ENDPOINT, "image", "inspect", *image_ids)
    )
    image_by_id = {image["Id"]: image for image in images}
    rows = []
    for container in sorted(containers, key=lambda item: item["Name"]):
        labels = container["Config"].get("Labels") or {}
        environment = {
            item.split("=", 1)[0]: item.split("=", 1)[1]
            for item in container["Config"].get("Env", [])
            if "=" in item
        }
        configured_image = container["Config"].get("Image", "")
        configured_digest = (
            configured_image.split("@", 1)[1]
            if "@sha256:" in configured_image
            else None
        )
        image = image_by_id.get(container["Image"], {})
        rows.append(
            {
                "name": container["Name"].lstrip("/"),
                "container_id": container["Id"],
                "configured_image": configured_image,
                "configured_digest": configured_digest,
                "local_image_id": container["Image"],
                "repo_digests": image.get("RepoDigests") or [],
                "image_revision": labels.get("org.opencontainers.image.revision")
                or labels.get("io.codestra.build.revision")
                or labels.get("build.revision"),
                "image_source": labels.get("org.opencontainers.image.source"),
                "compose_project": labels.get("com.docker.compose.project"),
                "compose_service": labels.get("com.docker.compose.service"),
                "started_at": container["State"].get("StartedAt"),
                "networks": sorted(container["NetworkSettings"]["Networks"]),
                "safety_flags": {
                    key: environment[key] for key in SAFETY_KEYS if key in environment
                },
            }
        )
    return rows


def verify_inspection_host() -> dict:
    docker_host_environment = os.environ.get("DOCKER_HOST", "")
    if docker_host_environment and docker_host_environment != DOCKER_ENDPOINT:
        raise RuntimeError(
            f"refusing Docker evidence: DOCKER_HOST is {docker_host_environment!r}"
        )
    try:
        interfaces = json.loads(run("ip", "-json", "address", "show"))
        addresses = sorted(
            address["local"]
            for interface in interfaces
            for address in interface.get("addr_info", [])
            if address.get("family") in {"inet", "inet6"}
            and isinstance(address.get("local"), str)
        )
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as exc:
        raise RuntimeError("cannot verify the Docker inspection host identity") from exc
    if INSPECTION_HOST not in addresses:
        raise RuntimeError(
            f"refusing Docker evidence: expected host address {INSPECTION_HOST} is absent"
        )
    try:
        context_name = run("docker", "context", "show")
        context = json.loads(run("docker", "context", "inspect", context_name))[0]
        context_endpoint = context["Endpoints"]["docker"]["Host"]
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as exc:
        raise RuntimeError("cannot verify the active Docker context") from exc
    if context_endpoint != DOCKER_ENDPOINT:
        raise RuntimeError(
            f"refusing Docker evidence: active context endpoint is {context_endpoint!r}"
        )
    return {
        "expected_address": INSPECTION_HOST,
        "address_present": True,
        "hostname": socket.gethostname(),
        "docker_endpoint": DOCKER_ENDPOINT,
        "docker_context": context_name,
        "docker_host_environment": docker_host_environment or "UNSET",
    }


def source_evidence(component: str, definition: dict) -> dict:
    checkout = CHECKOUT_ROOT / component
    expected = definition["revision"]
    try:
        head = run("git", "rev-parse", "HEAD", cwd=checkout)
        authority_head = run(
            "git", "rev-parse", "refs/remotes/origin/main", cwd=checkout
        )
        tree = run("git", "rev-parse", "HEAD^{tree}", cwd=checkout)
        dirty = run(
            "git", "status", "--porcelain", "--untracked-files=all", cwd=checkout
        )
    except (OSError, subprocess.CalledProcessError):
        head, authority_head, tree, dirty = None, None, None, "UNAVAILABLE"
    exact = bool(
        head == expected
        and authority_head == expected
        and dirty == ""
        and SHA.fullmatch(head or "")
    )
    return {
        "repository": definition["repository"],
        "locked_revision": expected,
        "authoritative_main_head": authority_head,
        "checkout_head": head,
        "checkout_tree": tree,
        "exact_head_match": head == expected,
        "authoritative_head_match": authority_head == expected,
        "clean_worktree": dirty == "",
        "status": "PASS" if exact else "FAIL",
    }


def artifact_evidence(component: str, definition: dict, source: dict) -> dict:
    """Resolve known artifact classes; unsupported provenance is a failure, not a crash."""
    artifact_class = definition["artifact_class"]
    digest = definition["image_digest"]
    result = {
        "classification": artifact_class,
        "locked_digest": digest,
        "status": "FAIL",
    }
    if artifact_class == "source_only":
        result.update(
            {
                "runtime_image_required": False,
                "status": "PASS_SOURCE_ONLY" if source["status"] == "PASS" else "FAIL_SOURCE",
            }
        )
        return result
    if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
        result["status"] = "FAIL_UNRESOLVED_BLOCKING_ARTIFACT"
        return result

    reference = IMAGE_REFERENCES.get(component)
    if reference is None:
        result["status"] = "FAIL_UNREVIEWED_IMAGE_REFERENCE"
        result["error"] = "A reviewed registry reference and artifact verifier are required."
        return result

    expected_class = (
        "custom_signed_image" if component == "middleware"
        else "custom_attested_image" if component == "social_runtime"
        else "official_upstream_image_plus_codestra_config"
    )
    if artifact_class != expected_class:
        result["status"] = "FAIL_ARTIFACT_CLASS_MISMATCH"
        result["expected_classification"] = expected_class
        return result

    registry = registry_resolution(reference, digest)
    result.update(registry)
    if component == "social_runtime":
        # A resolvable custom image is NOT an official upstream artifact. The
        # historical SBOM/provenance claim is not a cryptographic verification
        # performed by this resolver, nor is it rollback/runtime authorization.
        result["runtime_image_required"] = True
        result["cryptographic_verification"] = {
            "status": "FAIL",
            "reason": "No reviewed Social Runtime attestation verifier is configured.",
        }
        result["status"] = (
            "FAIL_ATTESTATION_VERIFICATION_REQUIRED"
            if registry["registry_resolution"] == "PASS"
            else "FAIL_REGISTRY_RESOLUTION"
        )
        return result
    if component == "middleware":
        labels = local_image_labels(registry["reference"])
        verification = middleware_artifact_verification()
        try:
            manifest = json.loads(MIDDLEWARE_RELEASE_MANIFEST.read_text())
            if not isinstance(manifest, dict):
                raise ValueError("release manifest must be an object")
            manifest_source = manifest.get("source") or {}
            manifest_image = manifest.get("image") or {}
            if not isinstance(manifest_source, dict) or not isinstance(manifest_image, dict):
                raise ValueError("release manifest source and image must be objects")
        except (OSError, ValueError):
            result["status"] = "FAIL_INVALID_RELEASE_MANIFEST"
            return result
        result.update(
            {
                "oci_revision": labels.get("org.opencontainers.image.revision"),
                "oci_source": labels.get("org.opencontainers.image.source"),
                "verified_source_revision": verification.get("source_sha"),
                "release_workflow_run": f"https://github.com/appolon1908-hue/Middleware-/actions/runs/{MIDDLEWARE_RUN_ID}",
                "release_manifest_sha256": file_sha256(MIDDLEWARE_RELEASE_MANIFEST),
                "release_manifest_source_sha": manifest_source.get("git_sha"),
                "release_manifest_image_digest": manifest_image.get("digest"),
                "cryptographic_verification": verification,
            }
        )
        exact = (
            registry["registry_resolution"] == "PASS"
            and verification.get("status") == "PASS"
            and result["verified_source_revision"] == definition["revision"]
            and result["release_manifest_source_sha"] == definition["revision"]
            and result["release_manifest_image_digest"] == digest
            and result["release_manifest_sha256"] is not None
        )
        result["status"] = "PASS" if exact else "FAIL_CRYPTOGRAPHIC_PROVENANCE"
        return result

    if component not in UPSTREAM_COMPONENTS:
        result["status"] = "FAIL_UNSUPPORTED_PROVENANCE_MODEL"
        return result
    result["codestra_config_revision"] = definition["revision"]
    result["image_not_built_from_codestra_config"] = True
    labels = local_image_labels(registry["reference"])
    result["upstream_image_revision"] = labels.get("org.opencontainers.image.revision")
    result["status"] = (
        "PASS_OFFICIAL_DIGEST_WITH_SEPARATE_CONFIG"
        if registry["registry_resolution"] == "PASS"
        else "FAIL_REGISTRY_RESOLUTION"
    )
    if component == "openbao":
        result["provenance_statement"] = (
            "The official OpenBao image digest is upstream runtime provenance; "
            "the Codestra SHA is configuration authority only and is not its build revision."
        )
    return result


def runtime_evidence(component: str, definition: dict, runtime: list[dict], lock: dict) -> dict:
    expected_digest = definition["image_digest"]
    if component == "openbao":
        matches = [row for row in runtime if row["name"] == "codestra-openbao"]
        if not matches:
            return {"status": "NOT_OBSERVED", "containers": [], "digest_match": False}
        row = matches[0]
        digest_match = (
            DIGEST.fullmatch(expected_digest) is not None
            and row["configured_digest"] == expected_digest
            and any(item.endswith("@" + expected_digest) for item in row["repo_digests"])
        )
        return {
            "status": "DRIFT_CODESTRA_CONFIG_BINDING_UNPROVEN",
            "host": INSPECTION_HOST,
            "containers": [row],
            "digest_match": digest_match,
            "upstream_image_revision": row["image_revision"],
            "codestra_config_revision": definition["revision"],
            "codestra_config_runtime_binding": False,
            "rollback_target": {
                "state": "ABSENT_RUNTIME",
                "nginx_backup": "/root/openbao-runtime-backups/20260831T120111Z",
            },
        }
    if component in CORE_COMPONENTS:
        historical = []
        for name, workload in lock["runtime_workloads"].items():
            belongs = (
                component == "middleware" and "middleware-staging" in name
                or component == "n8n" and "n8n-staging" in name
                or component == "odoo" and "odoo19-staging" in name
            )
            if belongs:
                historical.append(
                    {
                        "name": name,
                        "classification": "frozen_observed_digest",
                        "historical_digest": workload["image_digest"],
                        "historical_rollback_digest": workload["rollback_digest"],
                        "container_id": "HISTORICAL_CONTAINER_ID_NOT_RECORDED",
                        "host": "65.109.65.169",
                    }
                )
        return {
            "status": "FAIL_REQUIRED_COMPONENTS_ABSENT_OR_UNBOUND",
            "host": "65.109.65.169",
            "containers": historical,
            "digest_match": False,
            "read_only_probe": "RECORDED_READBACK_SUCCEEDED_RUNTIME_DRIFT",
            "evidence": "STAGE6-RUNTIME-PROVENANCE.md",
            "observed_at": "2026-08-31T22:10:00Z",
            "fresh_runtime_verification_performed": False,
        }
    return {
        "status": "NOT_OBSERVED_ON_INSPECTED_HOST",
        "host": INSPECTION_HOST,
        "containers": [],
        "digest_match": False,
    }


def isolation_evidence(runtime: list[dict]) -> dict:
    compose = yaml.safe_load(
        (ROOT / "deploy/staging/intake-observability/compose.yaml").read_text()
    )
    runtime_lock = json.loads(
        (ROOT / "deploy/staging/intake-observability/runtime-lock.v1.json").read_text()
    )
    klyrow = [row for row in runtime if row["name"].startswith("klyrow-")]
    middleware = compose["services"]["middleware"]
    host_ports = middleware.get("ports") or []
    no_host_ports = host_ports == [] and middleware.get("expose") == ["8080"]
    private_internal = compose["networks"]["private"].get("internal") is True
    lock_text = json.dumps(runtime_lock).lower()
    no_klyrow_endpoint = all(
        token not in lock_text for token in ("37.27.128.39", "postal", "smtp://", "klyrow")
    )
    isolation_pass = all(
        (
            private_internal,
            no_host_ports,
            no_klyrow_endpoint,
            runtime_lock["external_effects_enabled"] is False,
            runtime_lock["activation"]["production_authorized"] is False,
        )
    )
    return {
        "status": (
            "PASS_SOURCE_ISOLATION_RUNTIME_NOT_ACTIVATED"
            if isolation_pass
            else "FAIL_SOURCE_ISOLATION"
        ),
        "stage6_host": "65.109.65.169",
        "klyrow_postal_host": INSPECTION_HOST,
        "distinct_hosts": True,
        "stage6_compose_project": "codestra-intake-observability-staging",
        "stage6_private_network_internal": private_internal,
        "stage6_middleware_host_ports": host_ports,
        "stage6_no_host_ports": no_host_ports,
        "stage6_external_effects_enabled": runtime_lock["external_effects_enabled"],
        "stage6_production_authorized": runtime_lock["activation"]["production_authorized"],
        "stage6_outbound_klyrow_postal_endpoint_declared": not no_klyrow_endpoint,
        "inbound_klyrow_webhook_secret_name_exists_but_no_egress_route": True,
        "klyrow_postal_classification": "out_of_batch",
        "klyrow_postal_mutation_performed": False,
        "observed_klyrow_containers": [
            {
                "name": row["name"],
                "container_id": row["container_id"],
                "started_at": row["started_at"],
            }
            for row in klyrow
        ],
    }


def main() -> None:
    original_bytes = LOCK.read_bytes()
    original = yaml.safe_load(original_bytes)
    resolved = json.loads(json.dumps(original))
    inspection_host = verify_inspection_host()
    runtime = docker_runtime()

    components = {}
    source_pass = 0
    artifact_pass = 0
    runtime_matches = 0
    class_counts = Counter()
    for component, definition in original["repositories"].items():
        source = source_evidence(component, definition)
        artifact = artifact_evidence(component, definition, source)
        observed = runtime_evidence(component, definition, runtime, original)
        source_pass += int(source["status"] == "PASS")
        artifact_pass += int(artifact["status"].startswith("PASS"))
        runtime_matches += int(observed.get("digest_match") is True)
        class_counts[definition["artifact_class"]] += 1
        components[component] = {
            "classification": definition["artifact_class"],
            "repository_integrity": source,
            "artifact_provenance": artifact,
            "runtime_readback": observed,
            "activation_eligible": False,
        }

    class_counts["source_only"] += 1  # Infrastructure evidence repository.
    class_counts["frozen_observed_digest"] += 1  # Historical core runtime set.
    class_counts["out_of_batch"] += 1  # Klyrow/Postal.
    isolation = isolation_evidence(runtime)
    expected_private_digest = original["repositories"]["middleware"]["image_digest"]
    private_lock = json.loads(
        (ROOT / "deploy/staging/intake-observability/runtime-lock.v1.json").read_text()
    )
    private_digest = private_lock["middleware"]["image_digest"]

    resolution = {
        "schema": "codestra.stage6.source-lock-resolution.v2",
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "authoritative_lock_path": str(LOCK),
        "authoritative_lock_sha256": file_sha256(LOCK),
        "infrastructure_evidence_base_sha": "244a743a771d1f93c1445392bb45f8325908ca72",
        "runtime_mutation_performed": False,
        "source_lock": "FAIL",
        "summary": {
            "repository_components": len(components),
            "exact_authority_head_and_clean_checkout": source_pass,
            "artifact_provenance_pass": artifact_pass,
            "fresh_verified_digest_matches": runtime_matches,
            "minimum_verified_digest_matches": 1,
            "activation_eligible_components": 0,
            "classification_counts": dict(sorted(class_counts.items())),
        },
        "component_catalog_extensions": {
            "infrastructure_evidence": {
                "classification": "source_only",
                "base_sha": "244a743a771d1f93c1445392bb45f8325908ca72",
            },
            "legacy_stage6_core_runtime": {
                "classification": "frozen_observed_digest",
                "workloads": 22,
                "recorded_readback": "SUCCEEDED_RUNTIME_DRIFT",
            },
            "klyrow_postal": {
                "classification": "out_of_batch",
                "host": INSPECTION_HOST,
                "disposition": "DO_NOT_TOUCH",
            },
        },
        "gates": {
            "repository_integrity": {
                "status": "PASS" if source_pass == len(components) else "FAIL",
                "passed": source_pass,
                "required": len(components),
            },
            "artifact_provenance": {
                "status": "FAIL_PARTIAL",
                "passed": artifact_pass,
                "required": len(components),
            },
            "runtime_readback": {
                "status": "FAIL_REQUIRED_COMPONENTS_ABSENT_OR_UNBOUND",
                "fresh_verified_digest_matches": runtime_matches,
                "nonzero_match_requirement": "PASS" if runtime_matches > 0 else "FAIL",
                "core_host_readback": "RECORDED_READBACK_SUCCEEDED_RUNTIME_DRIFT",
            },
            "activation_eligibility": {
                "status": "FAIL",
                "private_middleware_staging": "FAIL_STALE_ARTIFACT_AND_RUNTIME_SAFETY_UNVERIFIED",
                "prometheus_staging_target": "PENDING_SEPARATE_REVIEW",
                "blackbox_staging_target": "PENDING",
                "production": "DISABLED_NOT_AUTHORIZED",
            },
        },
        "private_middleware_staging": {
            "status": "HELD",
            "locked_source_digest": expected_private_digest,
            "deployment_lock_digest": private_digest,
            "artifact_gate": (
                "PASS" if private_digest == expected_private_digest else "FAIL_STALE_DEPLOYMENT_LOCK"
            ),
            "scoped_safety_gate": "FAIL_RUNTIME_READBACK_UNAVAILABLE",
            "resume_authorized": False,
        },
        "bounded_inventory": {
            "host": INSPECTION_HOST,
            "host_identity": inspection_host,
            "running_containers_inspected": len(runtime),
            "fresh_verified_digest_matches": runtime_matches,
            "minimum_required": 1,
            "result": "PASS_NONZERO_PARTIAL" if runtime_matches > 0 else "FAIL_ZERO_MATCHES",
            "core_host": "65.109.65.169",
            "core_result": "RECORDED_READBACK_SUCCEEDED_RUNTIME_DRIFT",
        },
        "stage6_klyrow_postal_isolation": isolation,
        "components": components,
        "decision": (
            "SOURCE_LOCK remains FAIL. Repository integrity passes independently, but "
            "artifact provenance is partial, recorded core read-back shows absent or unbound components, private "
            "Middleware staging is stale and held, Stage 7 activation is pending review, "
            "and production activation remains prohibited."
        ),
    }
    resolved["runtime_resolution"] = resolution
    OUTPUT.write_text(yaml.safe_dump(resolved, sort_keys=False, width=120))
    print(f"RESOLVED_LOCK={OUTPUT}")
    print(f"REPOSITORY_INTEGRITY={source_pass}/{len(components)}")
    print(f"ARTIFACT_PROVENANCE={artifact_pass}/{len(components)}")
    print(f"RUNTIME_DIGEST_MATCH={runtime_matches}")
    print("ACTIVATION_ELIGIBILITY=FAIL")
    print("SOURCE_LOCK=FAIL")


if __name__ == "__main__":
    main()
