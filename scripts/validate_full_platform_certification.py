#!/usr/bin/env python3
"""Validate the committed, secret-free full-platform certification evidence."""

from __future__ import annotations

import re
import hashlib
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "PRODUCTION-RUNTIME-INVENTORY.yaml"
API_PATH = ROOT / "PRODUCTION-API-MATRIX.yaml"
INTEGRATION_PATH = ROOT / "PRODUCTION-INTEGRATION-MATRIX.yaml"
SUMMARY_PATH = ROOT / "FULL-PLATFORM-CERTIFICATION-SUMMARY.yaml"
CERTIFICATION_PATH = ROOT / "FULL-PLATFORM-PRODUCTION-CERTIFICATION.yaml"
GATE_EVIDENCE_PATH = ROOT / "SERVER-37-PRODUCTION-GATE-EVIDENCE.yaml"

ALLOWED_STAGES = {
    "PRODUCTION",
    "PRODUCTION_CANDIDATE",
    "STAGING",
    "LEGACY",
    "TOOLING",
}
ALLOWED_ENDPOINT_STATUSES = {"IMPLEMENTED", "PARTIAL", "MISSING", "DEPRECATED", "N/A"}
ALLOWED_CLASSIFICATIONS = {"PASS", "WARNING", "FAIL", "N/A"}
SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
GIT_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def load(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), f"{path.name}: expected a YAML mapping"
    return value


def assert_no_forbidden_states(paths: list[Path]) -> None:
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "UNKNOWN" not in text, f"{path.name}: forbidden UNKNOWN state"
        assert "NOT VERIFIED" not in text, f"{path.name}: forbidden NOT VERIFIED state"
        assert "NOT_VERIFIED" not in text, f"{path.name}: forbidden NOT_VERIFIED state"


def validate_inventory(inventory: dict[str, Any]) -> int:
    assert inventory["server_scope"] == "CURRENT_SERVER_ONLY"
    workloads = inventory["workloads"]
    host_services = inventory["host_services"]
    assert isinstance(workloads, list) and workloads, "inventory has no workloads"
    assert isinstance(host_services, list) and host_services, "inventory has no host services"
    required_fields = {
        "software",
        "container_or_service",
        "image",
        "image_digest",
        "version",
        "source_repository",
        "source_sha",
        "deployment_file",
        "ports",
        "public_url",
        "private_url",
        "networks",
        "volumes",
        "databases",
        "health",
        "stage",
    }
    names: set[str] = set()
    for row in workloads + host_services:
        missing = required_fields - row.keys()
        assert not missing, f"{row.get('container_or_service', 'unnamed')}: missing {sorted(missing)}"
        name = row["container_or_service"]
        assert name not in names, f"duplicate inventory service: {name}"
        names.add(name)
        assert row["stage"] in ALLOWED_STAGES, f"{name}: invalid stage {row['stage']}"
        assert isinstance(row["ports"], list) and row["ports"], f"{name}: ports must be explicit"
        assert isinstance(row["networks"], list) and row["networks"], f"{name}: networks must be explicit"
        assert isinstance(row["volumes"], list) and row["volumes"], f"{name}: volumes must be explicit"
        assert row["health"], f"{name}: health must be explicit"
    for row in workloads:
        assert SHA256_PATTERN.fullmatch(row["image_digest"]), (
            f"{row['container_or_service']}: invalid runtime image digest"
        )
        assert row["image_reference_digest_pinned"] in {"YES", "NO"}
    dispositions = inventory["scope_dispositions"]
    for component in (
        "CADDY",
        "KONG",
        "ODOO",
        "N8N",
        "LOKI",
        "TEMPO",
        "ALLOY",
        "VICIDIAL",
        "ASTERISK",
        "CENTRIFUGO",
        "CELERY",
    ):
        assert component in dispositions, f"missing scope disposition for {component}"
    return sum(row["stage"] == "PRODUCTION" for row in workloads + host_services)


def validate_api(api: dict[str, Any]) -> tuple[int, dict[str, int]]:
    assert api["server_scope"] == "CURRENT_SERVER_ONLY"
    assert set(api["source_authority"]) == {"KLYROW", "TELNEXA", "KYQRA", "PRIVATE_GATEWAY"}
    for service, authority in api["source_authority"].items():
        assert authority["repository"] == api["source_repositories"][service]
        assert GIT_SHA_PATTERN.fullmatch(authority["source_sha"]), (
            f"{service}: invalid source authority SHA"
        )
    required = api["required_contracts"]
    endpoints = api["endpoints"]
    required_keys: set[tuple[str, str, str]] = set()
    for row in required:
        key = (row["service"], row["method"], row["path"])
        assert key not in required_keys, f"duplicate required API contract: {key}"
        required_keys.add(key)
        assert row["implementation_status"] in ALLOWED_ENDPOINT_STATUSES
        assert row["runtime_verification"], f"{key}: missing runtime verification"
    endpoint_keys: set[tuple[str, str, str]] = set()
    required_endpoint_fields = {
        "service",
        "method",
        "path",
        "public_url",
        "private_url",
        "authentication",
        "authorization",
        "tenant_model",
        "idempotency",
        "request_model",
        "response_model",
        "external_effect",
        "implementation_status",
        "runtime_verification",
        "stage",
    }
    for row in endpoints:
        missing = required_endpoint_fields - row.keys()
        assert not missing, f"API row missing fields: {sorted(missing)}"
        key = (row["service"], row["method"], row["path"])
        assert key not in endpoint_keys, f"duplicate API endpoint row: {key}"
        endpoint_keys.add(key)
        assert row["implementation_status"] in ALLOWED_ENDPOINT_STATUSES
        assert row["stage"] in ALLOWED_STAGES
        assert row["runtime_verification"], f"{key}: missing runtime verification"
    for key in (
        ("TELNEXA", "POST", "/v1/smpp/accounts"),
        ("TELNEXA", "PATCH", "/v1/smpp/accounts/{id}"),
    ):
        contract = next(
            row
            for row in required
            if (row["service"], row["method"], row["path"]) == key
        )
        assert contract["implementation_status"] == "IMPLEMENTED", f"{key}: incomplete"
    for key in (
        ("TELNEXA", "POST", "/api/v1/smpp/accounts"),
        ("TELNEXA", "PATCH", "/api/v1/smpp/accounts/{account_id}"),
    ):
        endpoint = next(
            row
            for row in endpoints
            if (row["service"], row["method"], row["path"]) == key
        )
        assert endpoint["idempotency"] == "DURABLE", f"{key}: idempotency not durable"
        assert endpoint["implementation_status"] == "IMPLEMENTED", f"{key}: incomplete"
    counts = {
        status: sum(row["implementation_status"] == status for row in required)
        for status in ("IMPLEMENTED", "PARTIAL", "MISSING")
    }
    return len(endpoints), counts


def validate_integrations(integration: dict[str, Any]) -> None:
    assert integration["server_scope"] == "CURRENT_SERVER_ONLY"
    required_fields = {
        "source",
        "destination",
        "protocol",
        "auth",
        "authorization",
        "network",
        "timeout_seconds",
        "retry",
        "idempotency",
        "health",
        "external_effect",
        "failure_mode",
    }
    expected_edges = {
        ("KLYROW", "POSTAL"),
        ("KLYROW", "MAUTIC"),
        ("KLYROW", "OPENBAO"),
        ("KLYROW", "PRIVATE_GATEWAY"),
        ("TELNEXA", "KEYCLOAK"),
        ("TELNEXA", "JASMIN"),
        ("TELNEXA", "RABBITMQ"),
        ("TELNEXA", "REDIS"),
        ("TELNEXA", "OPENBAO"),
        ("TELNEXA", "PRIVATE_GATEWAY"),
        ("KYQRA", "REDIS"),
        ("KYQRA", "POSTGRESQL"),
        ("KYQRA", "OPENBAO"),
        ("KYQRA", "PRIVATE_GATEWAY"),
        ("PRIVATE_GATEWAY", "TELNEXA"),
        ("PRIVATE_GATEWAY", "KYQRA"),
        ("PROMETHEUS_KLYROW", "APPROVED_KLYROW_TARGETS"),
        ("PROMETHEUS_TELNEXA", "APPROVED_TELNEXA_TARGETS"),
        ("GRAFANA_KLYROW", "PROMETHEUS_KLYROW"),
    }
    actual_edges: set[tuple[str, str]] = set()
    for row in integration["edges"]:
        missing = required_fields - row.keys()
        assert not missing, f"integration edge missing fields: {sorted(missing)}"
        key = (row["source"], row["destination"])
        assert key not in actual_edges, f"duplicate integration edge: {key}"
        actual_edges.add(key)
        assert isinstance(row["timeout_seconds"], int) and row["timeout_seconds"] > 0
    assert expected_edges <= actual_edges, f"missing integration edges: {sorted(expected_edges - actual_edges)}"


def validate_gate_evidence(gates: dict[str, Any]) -> None:
    assert gates["server"] == "37.27.128.39"
    required = {
        "OFF_HOST_BACKUP", "ISOLATED_RESTORE",
        "POSITIVE_AND_NEGATIVE_MTLS_E2E", "CONTROLLED_EMAIL_E2E",
        "CONTROLLED_SMS_E2E", "CONTROLLED_KYQRA_E2E",
        "CONTROLLED_PRIVATE_INTEGRATION_E2E", "KEYCLOAK_AUTH_E2E",
        "MAUTIC_KLYROW_E2E", "ALERT_AND_RETENTION_E2E",
    }
    assert set(gates["gates"]) == required
    for name, record in gates["gates"].items():
        assert record["status"] in {"PASS", "FAIL"}, f"{name}: invalid gate status"
        assert record["reason"], f"{name}: reason is required"
        evidence = record["evidence"]
        assert evidence, f"{name}: evidence authority is required"
        if evidence == "EXTERNAL_AUTHORITY_REQUIRED":
            assert record["status"] == "FAIL", f"{name}: missing authority cannot pass"
        else:
            assert (ROOT / evidence).is_file(), f"{name}: evidence file is missing"


def validate_certification(
    certification: dict[str, Any],
    summary: dict[str, Any],
    production_services: int,
    endpoint_total: int,
    api_counts: dict[str, int],
) -> None:
    assert certification["PHASE"] == "FULL_PLATFORM_API_INTEGRATION_AND_PRODUCTION_CERTIFICATION"
    assert certification["PRODUCTION_SERVICES"] == production_services
    assert summary["production_services"] == production_services
    assert summary["api_endpoints"] == endpoint_total
    assert certification["TOTAL_REQUIRED_ENDPOINTS"] == summary["required_endpoints"]
    for status, report_key, summary_key in (
        ("IMPLEMENTED", "IMPLEMENTED_ENDPOINTS", "implemented_required_endpoints"),
        ("PARTIAL", "PARTIAL_ENDPOINTS", "partial_required_endpoints"),
        ("MISSING", "MISSING_ENDPOINTS", "missing_required_endpoints"),
    ):
        assert certification[report_key] == summary[summary_key] == api_counts[status]
    for key in (
        "KLYROW_SOURCE_SHA",
        "TELNEXA_SOURCE_SHA",
        "KYQRA_SOURCE_SHA",
        "PRIVATE_GATEWAY_SOURCE_SHA",
    ):
        assert GIT_SHA_PATTERN.fullmatch(certification[key]), f"{key}: invalid Git SHA"
    assert certification["ALL_IMAGES_DIGEST_PINNED"] in {"YES", "NO"}
    assert isinstance(certification["SOURCE_RUNTIME_DRIFT"], int)
    classifications = certification["CLASSIFICATIONS"]
    assert classifications
    assert set(classifications.values()) <= ALLOWED_CLASSIFICATIONS
    verdict = certification["OVERALL_VERDICT"]
    assert verdict in {"PRODUCTION_CERTIFIED", "PRODUCTION_BLOCKED"}
    if verdict == "PRODUCTION_CERTIFIED":
        assert certification["MISSING_ENDPOINTS"] == 0
        assert certification["PARTIAL_ENDPOINTS"] == 0
        assert certification["ALL_IMAGES_DIGEST_PINNED"] == "YES"
        assert certification["SOURCE_RUNTIME_DRIFT"] == 0
        assert set(classifications.values()) <= {"PASS", "N/A"}
        assert all(
            certification[key] == "PASS"
            for key in (
                "KLYROW_OPENAPI",
                "TELNEXA_OPENAPI",
                "KYQRA_OPENAPI",
                "PRIVATE_GATEWAY_OPENAPI",
                "OPENBAO",
                "KEYCLOAK",
                "POSTAL",
                "MAUTIC",
                "JASMIN",
                "MTLS",
                "POSTGRES",
                "MARIADB",
                "REDIS",
                "RABBITMQ",
                "PROMETHEUS",
                "GRAFANA",
                "BACKUPS",
                "RESTORE",
                "SECURITY",
                "ROLLBACK",
                "KLYROW_EMAIL_E2E",
                "TELNEXA_SMS_E2E",
                "KYQRA_E2E",
                "PRIVATE_INTEGRATION_E2E",
            )
        )
    else:
        blockers = certification["BLOCKERS"]
        assert blockers, "blocked certification must include blockers"
        required_blocker_fields = {
            "blocker",
            "owner",
            "repository",
            "component",
            "required_action",
            "validation_after_action",
        }
        for blocker in blockers:
            missing = required_blocker_fields - blocker.keys()
            assert not missing, f"blocker missing fields: {sorted(missing)}"
            assert all(blocker[field] for field in required_blocker_fields)


def main() -> None:
    paths = [INVENTORY_PATH, API_PATH, INTEGRATION_PATH, SUMMARY_PATH, CERTIFICATION_PATH, GATE_EVIDENCE_PATH]
    assert_no_forbidden_states(paths)
    inventory = load(INVENTORY_PATH)
    api = load(API_PATH)
    integration = load(INTEGRATION_PATH)
    summary = load(SUMMARY_PATH)
    certification = load(CERTIFICATION_PATH)
    gates = load(GATE_EVIDENCE_PATH)
    delivery = gates["gates"]["CONTROLLED_PRIVATE_INTEGRATION_E2E"]
    assert delivery["status"] == "FAIL"
    assert delivery["evidence"] == "SERVER-37-KLYROW-EVENT-DELIVERY-EVIDENCE.md"
    assert hashlib.sha256((ROOT / delivery["evidence"]).read_bytes()).hexdigest() == delivery["evidence_sha256"]
    production_services = validate_inventory(inventory)
    endpoint_total, api_counts = validate_api(api)
    validate_integrations(integration)
    validate_gate_evidence(gates)
    validate_certification(certification, summary, production_services, endpoint_total, api_counts)
    print("FULL_PLATFORM_CERTIFICATION_EVIDENCE=PASS")


if __name__ == "__main__":
    main()
