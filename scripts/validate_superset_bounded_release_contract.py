#!/usr/bin/env python3
"""Validate the fail-closed Superset release/staging/canary authority."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "operations/superset-bounded-release/contract.v1.json"
SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
IMAGE = re.compile(
    r"^ghcr\.io/appolon1908-hue/superset-superset@sha256:[0-9a-f]{64}$"
)
EVIDENCE_SHA = re.compile(r"^[0-9a-f]{64}$")
TAG = re.compile(r"^codestra-superset-v[0-9]+\.[0-9]+\.[0-9]+$")

EXTERNAL_BINDING_KEYS = {
    "stage6_host_created",
    "codestra_staging_runner_registered",
    "codestra_production_canary_runner_registered",
    "staging_readonly_environment_configured",
    "production_readonly_canary_environment_configured",
    "superset_canary_controller_installed",
    "superset_canary_controller_checksum_bound",
}
SAFETY_KEYS = {
    "deployment_authorized",
    "production_certified",
    "live_write",
    "odoo_write",
    "external_delivery",
    "email_delivery",
    "sms_delivery",
    "pstn_dialing",
    "provider_delivery",
    "campaign_activation",
    "payment_execution",
    "financial_trading",
}
LIVE_EFFECT_KEYS = SAFETY_KEYS - {"production_certified", "deployment_authorized"}
CANDIDATE_IDENTITY_FIELDS = (
    "source_sha",
    "release_tag",
    "image",
    "image_digest",
    "release_run_id",
    "release_evidence_sha256",
    "hosted_staging_evidence_sha256",
    "bounded_staging_evidence_sha256",
    "production_canary_evidence_sha256",
)
CANDIDATE_STATES = {
    "PENDING_PROTECTED_SUPERSET_RELEASE",
    "SIGNED_RELEASE_READY",
    "HOSTED_STAGING_CERTIFIED",
    "BOUNDED_STAGING_CERTIFIED",
    "PRODUCTION_READONLY_CERTIFIED",
}


def fail(message: str) -> None:
    raise SystemExit(f"SUPERSET_BOUNDED_RELEASE_CONTRACT=FAIL reason={message}")


def require_equal(actual: object, expected: object, name: str) -> None:
    if actual != expected:
        fail(f"{name}_mismatch")


def require_boolean_map(value: object, expected_keys: set[str], name: str) -> dict[str, bool]:
    if not isinstance(value, dict):
        fail(f"{name}_not_object")
    if set(value) != expected_keys:
        fail(f"{name}_keys_mismatch")
    if any(type(item) is not bool for item in value.values()):
        fail(f"{name}_contains_non_boolean")
    return value


def require_sha256(value: object, name: str) -> str:
    text = str(value or "")
    if not EVIDENCE_SHA.fullmatch(text):
        fail(f"{name}_invalid")
    return text


def require_null(candidate: dict[str, Any], fields: tuple[str, ...], state: str) -> None:
    for field in fields:
        if candidate.get(field) is not None:
            fail(f"{state.lower()}_{field}_must_be_null")


def require_release_identity(candidate: dict[str, Any]) -> None:
    if not SHA.fullmatch(str(candidate.get("source_sha", ""))):
        fail("candidate_source_sha_invalid")
    if not TAG.fullmatch(str(candidate.get("release_tag", ""))):
        fail("candidate_release_tag_invalid")
    if not IMAGE.fullmatch(str(candidate.get("image", ""))):
        fail("candidate_image_invalid")
    if not DIGEST.fullmatch(str(candidate.get("image_digest", ""))):
        fail("candidate_image_digest_invalid")
    if candidate["image"].rsplit("@", 1)[1] != candidate["image_digest"]:
        fail("candidate_image_digest_mismatch")
    if not isinstance(candidate.get("release_run_id"), int) or candidate["release_run_id"] <= 0:
        fail("candidate_release_run_id_invalid")
    require_sha256(candidate.get("release_evidence_sha256"), "candidate_release_evidence")


def validate(data: dict[str, Any], serialized: str) -> str:
    require_equal(data.get("schema"), "codestra.superset-bounded-release-contract.v1", "schema")
    require_equal(data.get("workload"), "superset", "workload")
    require_equal(data.get("source_repository"), "appolon1908-hue/Superset", "source_repository")
    require_equal(
        data.get("infrastructure_repository"),
        "appolon1908-hue/Infustruction-repo",
        "infrastructure_repository",
    )
    require_equal(
        data.get("promotion_chain"),
        ["development", "test", "staging", "production", "main"],
        "promotion_chain",
    )

    release = data.get("release")
    if not isinstance(release, dict):
        fail("release_not_object")
    require_equal(release.get("workflow"), ".github/workflows/release-image.yml", "release_workflow")
    require_equal(
        release.get("bounded_workflow"),
        ".github/workflows/bounded-runtime-certification.yml",
        "bounded_workflow",
    )
    require_equal(
        release.get("reusable_build_authority"),
        "appolon1908-hue/Codestra-Telemetry/.github/workflows/reusable-release-image.yml@9a6aebb849bbc068105c10d9d1dfd39ebf6f78bd",
        "reusable_build_authority",
    )
    require_equal(
        release.get("image_repository"),
        "ghcr.io/appolon1908-hue/superset-superset",
        "image_repository",
    )
    require_equal(release.get("source_branch"), "production", "release_source_branch")
    if release.get("runtime_activation_by_release") is not False:
        fail("release_may_not_activate_runtime")
    required_release = {
        "exact_protected_source_sha",
        "exact_image_digest",
        "oci_source_label",
        "oci_revision_label",
        "nonroot_user_10001_10001",
        "high_critical_vulnerability_gate",
        "sbom",
        "image_provenance",
        "cosign_signature",
        "spdx_attestation",
        "github_build_provenance",
    }
    require_equal(set(release.get("required_evidence", [])), required_release, "release_evidence")

    staging = data.get("staging")
    if not isinstance(staging, dict):
        fail("staging_not_object")
    require_equal(staging.get("hosted_artifact_job"), "artifact-staging-certification", "hosted_job")
    require_equal(staging.get("bounded_job"), "bounded-staging-runtime", "bounded_job")
    require_equal(staging.get("environment"), "staging-readonly", "staging_environment")
    require_equal(staging.get("runner_labels"), ["self-hosted", "codestra-staging"], "staging_runner_labels")
    if staging.get("public_traffic_changed") is not False:
        fail("staging_public_traffic_may_not_change")
    if staging.get("production_runtime_changed") is not False:
        fail("staging_may_not_change_production")
    required_staging = {
        "signed_image_identity",
        "migration",
        "role_bootstrap_idempotency",
        "metadata_readiness",
        "metadata_backup_integrity",
        "metadata_restore",
        "runtime_restart_rollback",
        "database_native_rls",
        "cross_business_denial",
        "write_attempt_denied",
        "zero_live_effects",
    }
    require_equal(set(staging.get("required_gates", [])), required_staging, "staging_gates")

    canary = data.get("production_readonly_canary")
    if not isinstance(canary, dict):
        fail("canary_not_object")
    require_equal(canary.get("job"), "production-readonly-canary", "canary_job")
    require_equal(canary.get("environment"), "production-readonly-canary", "canary_environment")
    require_equal(
        canary.get("runner_labels"),
        ["self-hosted", "codestra-production-canary"],
        "canary_runner_labels",
    )
    require_equal(canary.get("maximum_percent"), 1, "maximum_percent")
    require_equal(canary.get("methods"), ["GET", "HEAD"], "canary_methods")
    if canary.get("read_only") is not True:
        fail("canary_not_read_only")
    if canary.get("runtime_must_be_restored_after_canary") is not True:
        fail("canary_rollback_not_mandatory")

    controller = canary.get("controller")
    if not isinstance(controller, dict):
        fail("controller_not_object")
    expected_controller = {
        "path_variable": "SUPERSET_CANARY_CONTROLLER",
        "sha256_variable": "SUPERSET_CANARY_CONTROLLER_SHA256",
        "required_owner_uid": 0,
        "group_world_writable": False,
        "apply_receipt_schema": "codestra.superset-readonly-canary-receipt.v1",
        "rollback_receipt_schema": "codestra.superset-readonly-canary-rollback.v1",
        "status_schema": "codestra.superset-readonly-canary-status.v1",
    }
    require_equal(controller, expected_controller, "controller")
    required_stops = {
        "source_or_digest_mismatch",
        "missing_staging_evidence",
        "readiness_failure",
        "oidc_failure",
        "runtime_state_drift",
        "write_counter_movement",
        "external_delivery_counter_movement",
        "method_outside_get_head",
        "percentage_above_one",
        "controller_checksum_mismatch",
        "rollback_failure",
    }
    require_equal(
        set(canary.get("required_stop_conditions", [])),
        required_stops,
        "canary_stop_conditions",
    )

    bindings = require_boolean_map(
        data.get("required_external_bindings"), EXTERNAL_BINDING_KEYS, "external_bindings"
    )
    safety = require_boolean_map(data.get("safety_state"), SAFETY_KEYS, "safety_state")
    if safety["deployment_authorized"] is not False:
        fail("read_only_certification_may_not_authorize_full_deployment")
    if any(safety[key] is not False for key in LIVE_EFFECT_KEYS):
        fail("live_effects_not_fail_closed")

    candidate = data.get("candidate")
    if not isinstance(candidate, dict):
        fail("candidate_not_object")
    if set(candidate) != {"status", *CANDIDATE_IDENTITY_FIELDS}:
        fail("candidate_keys_mismatch")
    status = candidate.get("status")
    if status not in CANDIDATE_STATES:
        fail("candidate_status_invalid")

    if status == "PENDING_PROTECTED_SUPERSET_RELEASE":
        require_null(candidate, CANDIDATE_IDENTITY_FIELDS, status)
        if any(bindings.values()):
            fail("pending_release_contains_external_binding_claim")
    else:
        require_release_identity(candidate)

        if status == "SIGNED_RELEASE_READY":
            require_null(
                candidate,
                (
                    "hosted_staging_evidence_sha256",
                    "bounded_staging_evidence_sha256",
                    "production_canary_evidence_sha256",
                ),
                status,
            )
        elif status == "HOSTED_STAGING_CERTIFIED":
            require_sha256(
                candidate.get("hosted_staging_evidence_sha256"),
                "hosted_staging_evidence",
            )
            require_null(
                candidate,
                ("bounded_staging_evidence_sha256", "production_canary_evidence_sha256"),
                status,
            )
        elif status == "BOUNDED_STAGING_CERTIFIED":
            require_sha256(
                candidate.get("hosted_staging_evidence_sha256"),
                "hosted_staging_evidence",
            )
            require_sha256(
                candidate.get("bounded_staging_evidence_sha256"),
                "bounded_staging_evidence",
            )
            require_null(candidate, ("production_canary_evidence_sha256",), status)
            for binding in (
                "stage6_host_created",
                "codestra_staging_runner_registered",
                "staging_readonly_environment_configured",
            ):
                if bindings[binding] is not True:
                    fail(f"bounded_staging_without_{binding}")
        elif status == "PRODUCTION_READONLY_CERTIFIED":
            require_sha256(
                candidate.get("hosted_staging_evidence_sha256"),
                "hosted_staging_evidence",
            )
            require_sha256(
                candidate.get("bounded_staging_evidence_sha256"),
                "bounded_staging_evidence",
            )
            require_sha256(
                candidate.get("production_canary_evidence_sha256"),
                "production_canary_evidence",
            )
            if any(value is not True for value in bindings.values()):
                fail("production_certified_without_external_bindings")

    expected_certified = status == "PRODUCTION_READONLY_CERTIFIED"
    if safety["production_certified"] is not expected_certified:
        fail("production_certified_flag_state_mismatch")

    lowered = serialized.lower()
    for forbidden in (
        "begin openssh private key",
        "begin rsa private key",
        "bearer eyj",
        "password=",
        "client_secret=",
    ):
        if forbidden in lowered:
            fail("secret_material_detected")

    return str(status)


def main() -> None:
    serialized = CONTRACT.read_text(encoding="utf-8")
    status = validate(json.loads(serialized), serialized)
    print("SUPERSET_BOUNDED_RELEASE_CONTRACT=PASS")
    print(f"CANDIDATE_STATUS={status}")
    print("LIVE_EFFECTS=DISABLED")


if __name__ == "__main__":
    main()
