#!/usr/bin/env python3
"""Validate the fail-closed Server 37 API and rollback evidence."""

from __future__ import annotations

import hashlib

import hashlib
import re
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "SERVER-37-PRODUCTION-API-MATRIX.yaml"
ROLLBACK_PATH = ROOT / "SERVER-37-PRODUCTION-ROLLBACK.yaml"
ALLOWED_CLASSIFICATIONS = {
    "REQUIRED_LIVE",
    "OPTIONAL_LIVE",
    "INTERNAL_ONLY",
    "LEGACY_COMPATIBILITY",
    "UPSTREAM_PRODUCT_API",
    "DISABLED_BY_DESIGN",
    "N/A",
    "MISSING_REQUIRED",
}
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
IMAGE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def load(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text())
    assert isinstance(value, dict), f"{path.name}: expected a mapping"
    return value


def main() -> None:
    matrix = load(MATRIX_PATH)
    rollback = load(ROLLBACK_PATH)
    assert matrix["server"] == rollback["server"] == "37.27.128.39"
    assert matrix["scope"] == "THIS_SERVER_ONLY"
    baseline = matrix["authoritative_baseline"]
    assert baseline["source_matrix_sha256"] == hashlib.sha256(
        (ROOT / "PRODUCTION-API-MATRIX.yaml").read_bytes()
    ).hexdigest()
    assert baseline["total_running_services"] > 0
    assert baseline["total_live_api_endpoints"] > 0
    assert baseline["total_internal_api_endpoints"] > 0
    assert baseline["total_source_implemented_not_deployed"] > 0
    assert baseline["api_inventory_complete"] is True

    classifications = matrix["live_runtime_classification_counts"]
    assert set(classifications) <= ALLOWED_CLASSIFICATIONS
    assert sum(classifications.values()) == baseline["total_live_api_endpoints"]
    internal_count = sum(
        row["operation_count"]
        for row in matrix["live_runtime_groups"]
        if row["classification"] == "INTERNAL_ONLY"
        or row["service"] == "POSTAL_LEGACY_API"
    )
    assert internal_count == baseline["total_internal_api_endpoints"]
    assert sum(
        row["operation_count"]
        for row in matrix["baseline_source_implemented_not_deployed_groups"]
    ) == baseline["total_source_implemented_not_deployed"]
    assert sum(
        row["operation_count"] for row in matrix["documented_not_implemented"]
    ) == 4

    contract = matrix["canonical_custom_contract"]
    operations = contract["operations"]
    keys = {(row["service"], row["method"], row["path"]) for row in operations}
    assert len(keys) == len(operations) == contract["total_operations"]
    assert all(row["classification"] in ALLOWED_CLASSIFICATIONS for row in operations)
    live = sum(row["classification"] == "REQUIRED_LIVE" for row in operations)
    missing = sum(row["classification"] == "MISSING_REQUIRED" for row in operations)
    assert live == contract["required_live"]
    assert missing == contract["missing_required"] == matrix["missing_required_endpoints"]

    for service, row in matrix["candidate_source_authority"].items():
        assert GIT_SHA.fullmatch(row["source_sha"])
        if service == "KLYROW":
            assert row["review"] == "DEPLOYED_PROTECTED_MAIN_PR_76_APPROVED_AND_MERGED"
        elif service == "PRIVATE_GATEWAY":
            assert row["review"] == "PROTECTED_RELEASE_SIGNED_AND_DEPLOYED"
        else:
            assert "REVIEW_REQUIRED" in row["review"]

    assert rollback["production_changed"] is True
    assert rollback["rollback_gate"] == "FAIL"
    configuration_changes = {
        row["service"]: row for row in rollback["production_configuration_changes"]
    }
    assert set(configuration_changes) == {"MAUTIC_API", "TELNEXA_ADMIN_DENY_EDGE", "PRIVATE_GATEWAY_NGINX_EDGE", "KLYROW_EVENT_CONFIGURATION_BRIDGE"}
    configuration_change = configuration_changes["MAUTIC_API"]
    assert configuration_change["before_state"] == "GLOBAL_API_DISABLED"
    assert (
        configuration_change["temporary_state"]
        == "OAUTH2_API_ENABLED_FOR_BOUNDED_VALIDATION"
    )
    assert configuration_change["after_state"] == "OAUTH2_API_ENABLED_PRIVATE_EDGE_DENIED"
    assert configuration_change["rollback_procedure"]
    assert configuration_change["rollback_status"] == "PASS"
    admin_deny = configuration_changes["TELNEXA_ADMIN_DENY_EDGE"]
    assert admin_deny["before_state"] == "HTTP_403_VHOST_WITH_DNS_ABSENT"
    assert admin_deny["after_state"] == "DNS_AND_DEDICATED_TLS_PRESENT_HTTPS_403"
    assert admin_deny["rollback_procedure"]
    assert admin_deny["rollback_status"] == "PASS"
    for service in ("PRIVATE_GATEWAY_NGINX_EDGE", "KLYROW_EVENT_CONFIGURATION_BRIDGE"):
        row = configuration_changes[service]
        assert row["before_state"] and row["after_state"] and row["rollback_bundle"]
        assert row["rollback_procedure"]
        assert hashlib.sha256((ROOT / row["evidence"]).read_bytes()).hexdigest() == row["evidence_sha256"]
    assert configuration_changes["PRIVATE_GATEWAY_NGINX_EDGE"]["rollback_status"] == "FAIL"
    assert rollback["candidate_promotions"]
    deployed = {
        "KLYROW_GATEWAY_AND_WORKER",
        "KLYROW_WEB",
        "POSTAL_PROVISIONER",
        "PRIVATE_INTEGRATION_GATEWAY",
    }
    for row in rollback["candidate_promotions"]:
        digests = []
        if "before_image_digest" in row:
            digests.append(row["before_image_digest"])
        digests.extend(row.get("before_image_digests", []))
        digests.append(row["after_image_digest"])
        assert all(IMAGE_DIGEST.fullmatch(value) for value in digests)
        if row["service"] in deployed:
            assert row["status"] == "DEPLOYED_PASS"
        else:
            assert row["status"] == "NOT_DEPLOYED_REVIEW_REQUIRED"
        assert row["rollback_procedure"]

    print(
        "server37_api_matrix=PASS "
        f"live={sum(classifications.values())} required={len(operations)} missing={missing}"
    )


if __name__ == "__main__":
    main()
