#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REQUEST_PATH = ROOT / "config" / "stage6-staging-host-provisioning-request.v1.json"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ALLOWED_STATES = {
    "BLOCKED_ACCOUNT_CREDENTIALS_REQUIRED",
    "PROVISIONED_PENDING_CURRENT_VERIFICATION",
    "CREATED_AND_VERIFIED",
}
PENDING = "PENDING_CURRENT_VERIFICATION"


class ValidationError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise ValidationError(message)


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot parse {label}: {exc}")
    if not isinstance(value, dict):
        fail(f"{label} must contain an object")
    return value


def evidence_from_reference(reference: dict[str, Any]) -> dict[str, Any]:
    relative = reference.get("path")
    digest = str(reference.get("sha256", ""))
    if not isinstance(relative, str) or not relative.startswith("evidence/stage6/"):
        fail("observed evidence path must stay under evidence/stage6")
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        fail("observed evidence path is unsafe")
    full = ROOT / path
    if not full.is_file() or full.is_symlink():
        fail("observed evidence must be a regular non-symlink file")
    if not DIGEST_RE.fullmatch(digest):
        fail("observed evidence digest must be sha256")
    actual = "sha256:" + hashlib.sha256(full.read_bytes()).hexdigest()
    if actual != digest:
        fail("observed evidence digest mismatch")
    return load_json(full, "observed evidence")


def validate_request(request: dict[str, Any]) -> None:
    if request.get("schema_version") != 1:
        fail("schema_version must be 1")
    if request.get("repository") != "appolon1908-hue/Infustruction-repo":
        fail("repository authority mismatch")
    if request.get("workflow") != ".github/workflows/stage6-provision-staging-host.yml":
        fail("provisioning workflow authority mismatch")
    if request.get("protected_environment") != "stage6-infrastructure-provisioning":
        fail("protected environment mismatch")
    if request.get("network_class") != "isolated-private-staging":
        fail("staging host must use the isolated private network class")
    status = request.get("status")
    if status not in ALLOWED_STATES:
        fail("unsupported request status")
    if request.get("deployment_authorized") is not False:
        fail("host request cannot authorize workload deployment")
    if request.get("production_certified") is not False:
        fail("host request cannot certify production")

    source = request.get("required_source")
    if not isinstance(source, dict):
        fail("required_source is missing")
    if source.get("production_platform_repository") != "appolon1908-hue/codestra-production-platform":
        fail("production platform source authority mismatch")
    if source.get("production_platform_branch") != "release/production-activation":
        fail("production platform protected branch mismatch")
    if source.get("source_lock_status") != "PASS":
        fail("runtime deployment may require only a PASS production source lock")
    if source.get("candidate_matrix_deployment_authorized") is not True:
        fail("runtime deployment must require an authorized immutable candidate matrix")
    if source.get("endpoint_manifest_checksum_required") is not True:
        fail("endpoint manifest checksum must be required")

    outputs = request.get("required_provisioning_outputs")
    verification = request.get("required_verification")
    forbidden = request.get("forbidden_actions")
    for label, values, minimum in (
        ("required_provisioning_outputs", outputs, 10),
        ("required_verification", verification, 10),
        ("forbidden_actions", forbidden, 8),
    ):
        if not isinstance(values, list) or len(values) < minimum:
            fail(f"{label} is incomplete")
        if len(values) != len(set(values)):
            fail(f"{label} contains duplicates")

    for required in (
        "provider_resource_id", "private_ip", "ssh_host_key_fingerprint",
        "workflow_run_id", "workflow_source_sha", "configuration_checksum",
    ):
        if required not in outputs:
            fail(f"provisioning output missing: {required}")
    for required in (
        "private_network_only", "public_native_service_ports_absent",
        "operator_identity_least_privilege", "failed_systemd_units_zero",
        "destruction_and_recreation_test",
    ):
        if required not in verification:
            fail(f"verification control missing: {required}")

    safety = request.get("safety_controls")
    if not isinstance(safety, dict) or not safety:
        fail("safety_controls must be a non-empty object")
    enabled = sorted(name for name, value in safety.items() if value is not False)
    if enabled:
        fail(f"all safety controls must remain false: {enabled}")

    created = request.get("host_created")
    verified = request.get("host_verified")
    reference = request.get("observed_evidence")

    if status == "BLOCKED_ACCOUNT_CREDENTIALS_REQUIRED":
        if created is not False or verified is not False or reference is not None:
            fail("blocked request cannot claim creation, verification, or evidence")
        return

    if created is not True:
        fail("provisioned status requires host_created=true")
    if not isinstance(reference, dict):
        fail("provisioned status requires observed evidence reference")
    evidence = evidence_from_reference(reference)
    if evidence.get("schema_version") != "codestra.stage6-provisioning-evidence.v1":
        fail("observed evidence schema mismatch")
    workflow = evidence.get("workflow") or {}
    if workflow.get("repository") != request["repository"] or workflow.get("path") != request["workflow"]:
        fail("observed workflow authority mismatch")
    if not isinstance(workflow.get("run_id"), int) or workflow["run_id"] <= 0:
        fail("observed workflow run ID is invalid")
    if not SHA_RE.fullmatch(str(workflow.get("source_sha", ""))):
        fail("observed workflow_source_sha must be a full Git SHA")
    if workflow.get("conclusion") != "success":
        fail("observed provisioning workflow was not successful")
    if workflow.get("environment") != request["protected_environment"]:
        fail("observed protected environment mismatch")

    observed_outputs = evidence.get("provisioning_outputs")
    if not isinstance(observed_outputs, dict) or set(observed_outputs) != set(outputs):
        fail("observed provisioning output field set mismatch")
    verification_results = evidence.get("verification_results")
    if not isinstance(verification_results, dict) or set(verification_results) != set(verification):
        fail("verification result field set mismatch")
    invalid_results = sorted(name for name, value in verification_results.items() if value not in {"PASS", PENDING})
    if invalid_results:
        fail(f"unsupported verification results: {invalid_results}")
    safety_evidence = evidence.get("safety") or {}
    if safety_evidence.get("secret_values_recorded") is not False or safety_evidence.get("production_changed") is not False:
        fail("observed evidence safety state is invalid")

    missing_outputs = sorted(name for name in outputs if observed_outputs.get(name) in (None, ""))
    pending_checks = sorted(name for name in verification if verification_results.get(name) != "PASS")

    if status == "PROVISIONED_PENDING_CURRENT_VERIFICATION":
        if verified is not False:
            fail("pending status requires host_verified=false")
        if evidence.get("evidence_class") != "PROVISIONED_CLOUD_RESOURCES_OBSERVED_PENDING_CURRENT_VERIFICATION":
            fail("pending evidence class mismatch")
        if evidence.get("current_verification_required") is not True:
            fail("pending evidence must require current verification")
        if not missing_outputs and not pending_checks:
            fail("pending status must retain explicit unfinished evidence")
        return

    if verified is not True:
        fail("CREATED_AND_VERIFIED requires host_verified=true")
    if missing_outputs:
        fail(f"verified host provisioning outputs are incomplete: {missing_outputs}")
    if pending_checks:
        fail(f"host verification is incomplete: {pending_checks}")
    if evidence.get("current_verification_required") is not False:
        fail("verified evidence cannot remain pending")


def main() -> None:
    try:
        request = load_json(REQUEST_PATH, "request")
        validate_request(request)
    except ValidationError as exc:
        print(f"STAGE6_STAGING_HOST_REQUEST_ERROR={exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print("STAGE6_STAGING_HOST_REQUEST_AUTHORITY=PASS")
    print(f"STAGE6_STAGING_HOST_STATUS={request.get('status')}")
    print(f"STAGE6_HOST_CREATED={'YES' if request.get('host_created') else 'NO'}")
    print(f"STAGE6_HOST_VERIFIED={'YES' if request.get('host_verified') else 'NO'}")
    print("PRODUCTION_CERTIFIED=NO")


if __name__ == "__main__":
    main()
