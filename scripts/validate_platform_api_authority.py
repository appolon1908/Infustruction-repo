#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = ROOT / "contracts/platform-api"
AUTHORITY = CONTRACT_DIR / "authority.json"

COLUMNS = [
    "operation_id", "owner_repository", "runtime_service", "method", "path",
    "visibility", "client", "audience", "scope", "tenant_required",
    "idempotency_required", "correlation_required", "durability",
    "external_effect", "safety_flag", "kong_route", "sdk_method",
    "implementation_status",
]
METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
VISIBILITY = {"public", "gateway", "private", "private_gateway", "internal"}
REQUIRED_AUTOMATION = {
    ("POST", "/v2/automation/jobs/claim"),
    ("GET", "/v2/automation/jobs/{job_id}"),
    ("POST", "/v2/automation/jobs/{job_id}/heartbeat"),
    ("POST", "/v2/automation/jobs/{job_id}/steps"),
    ("POST", "/v2/automation/jobs/{job_id}/complete"),
    ("POST", "/v2/automation/jobs/{job_id}/fail"),
    ("POST", "/v2/automation/commands"),
    ("GET", "/v2/automation/commands/{command_id}"),
    ("POST", "/v2/automation/approvals"),
    ("GET", "/v2/automation/approvals/{approval_id}"),
    ("POST", "/v2/automation/dead-letters/{dead_letter_id}/replay"),
    ("POST", "/v2/automation/jobs/reconcile"),
    ("GET", "/v2/automation/capabilities/{capability}"),
}
REQUIRED_PROVIDER = {
    ("POST", "/api/v1/control/ai/inference-requests"),
    ("POST", "/api/v1/control/communications/email"),
    ("POST", "/api/v1/control/communications/sms"),
    ("POST", "/api/v1/control/marketing/campaigns"),
    ("POST", "/api/v1/odoo/events"),
    ("POST", "/api/v1/control/social/publications"),
}
REQUIRED_INCIDENT = {
    ("POST", "/v1/observability/alerts"),
    ("GET", "/v1/observability/incidents"),
    ("GET", "/v1/observability/incidents/{incident_id}"),
    ("POST", "/v1/observability/incidents/{incident_id}/acknowledge"),
    ("POST", "/v1/observability/incidents/{incident_id}/resolve"),
}
OPERATION_ID = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$")


def fail(reason: str) -> None:
    raise SystemExit(f"PLATFORM_API_AUTHORITY=FAIL reason={reason}")


def read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        fail(f"not_object_{path.name}")
    return value


def main() -> None:
    doc = read(AUTHORITY)
    if doc.get("schema_version") != "2.0" or doc.get("operation_columns") != COLUMNS:
        fail("authority_schema")

    authority = doc.get("authority", {})
    for key, value in {
        "production_authorized": False,
        "external_effects_enabled": False,
        "new_prometheus_targets": "pending",
        "blackbox_target": "pending",
    }.items():
        if authority.get(key) != value:
            fail(f"unsafe_authority_{key}")

    rules = doc.get("rules", {})
    for key in (
        "one_repository_per_layer",
        "middleware_only_cross_system_write_authority",
        "n8n_orchestration_only",
        "odoo_is_crm_system_of_record",
        "provider_writes_default_disabled",
        "production_activation_separate",
    ):
        if rules.get(key) is not True:
            fail(f"rule_{key}")

    owners = set(doc.get("owners", {}))
    declared_scopes = set(doc.get("declared_scopes", []))
    operations: list[list] = []
    operation_files = sorted(CONTRACT_DIR.glob("operations-*.json"))
    if len(operation_files) < 9:
        fail("operation_files")

    for path in operation_files:
        part = read(path)
        if part.get("schema_version") != "2.0" or part.get("operation_columns") != COLUMNS:
            fail(f"part_schema_{path.name}")
        rows = part.get("operations")
        if not isinstance(rows, list) or not rows:
            fail(f"empty_part_{path.name}")
        operations.extend(rows)

    if len(operations) < 120:
        fail("operation_count")

    ids: set[str] = set()
    service_routes: set[tuple[str, str, str]] = set()
    route_pairs: set[tuple[str, str]] = set()
    used_scopes: set[str] = set()
    statuses: Counter[str] = Counter()

    for index, row in enumerate(operations):
        if not isinstance(row, list) or len(row) != len(COLUMNS):
            fail(f"operation_row_{index}")

        operation = dict(zip(COLUMNS, row, strict=True))
        operation_id = operation["operation_id"]
        if (
            not isinstance(operation_id, str)
            or not OPERATION_ID.fullmatch(operation_id)
            or operation_id in ids
        ):
            fail(f"operation_id_{index}")
        ids.add(operation_id)

        method = operation["method"]
        path = operation["path"]
        if method not in METHODS or not isinstance(path, str) or not path.startswith("/"):
            fail(f"route_{operation_id}")

        service_route = (operation["runtime_service"], method, path)
        if service_route in service_routes:
            fail(f"duplicate_service_route_{operation_id}")
        service_routes.add(service_route)
        route_pairs.add((method, path))

        if (
            operation["owner_repository"] not in owners
            or operation["visibility"] not in VISIBILITY
        ):
            fail(f"ownership_visibility_{operation_id}")

        if not all(
            isinstance(operation[name], str) and operation[name]
            for name in ("client", "audience", "scope")
        ):
            fail(f"auth_{operation_id}")

        used_scopes.add(operation["scope"])
        if "*" in operation["scope"] or operation["scope"] in {
            "all",
            "full",
            "full_scope",
        }:
            fail(f"wildcard_scope_{operation_id}")

        if (
            method in {"POST", "PUT", "PATCH", "DELETE"}
            and operation["correlation_required"] is not True
        ):
            fail(f"correlation_{operation_id}")

        if operation["external_effect"]:
            if operation["safety_flag"] in {"", "NOT_APPLICABLE", None}:
                fail(f"safety_flag_{operation_id}")
            if operation["durability"] not in {
                "transactional_outbox",
                "database_then_middleware_operation",
                "middleware_operation",
            }:
                fail(f"durability_{operation_id}")

        if (
            path.startswith("/api/v1/control/")
            and operation["visibility"] != "internal"
        ):
            fail(f"provider_control_visibility_{operation_id}")

        if (
            path.startswith("/codestra/middleware/")
            and operation["visibility"] != "internal"
        ):
            fail(f"odoo_visibility_{operation_id}")

        if path in {"/v1/crm/leads", "/v1/workflow/runs"}:
            fail(f"prohibited_path_{path}")

        statuses[str(operation["implementation_status"])] += 1

    for name, required in {
        "automation": REQUIRED_AUTOMATION,
        "provider": REQUIRED_PROVIDER,
        "incident": REQUIRED_INCIDENT,
    }.items():
        missing = required - route_pairs
        if missing:
            fail(f"missing_{name}_{sorted(missing)}")

    if used_scopes - declared_scopes:
        fail("undeclared_scopes")

    constraints = doc.get("scope_constraints", {})
    if constraints.get("wildcard_scopes_allowed") is not False:
        fail("wildcard_scope_constraint")
    if constraints.get("sole_provider_dispatch_client") != "middleware-worker":
        fail("provider_dispatch_client")

    if len(set(doc.get("event_types", []))) < 10:
        fail("event_catalogue")

    forbidden = set(doc.get("forbidden_metric_labels", []))
    required_forbidden = {
        "tenant_id",
        "email",
        "phone",
        "correlation_id",
        "trace_id",
        "token",
        "secret",
    }
    if not required_forbidden <= forbidden:
        fail("metric_privacy")

    print(
        "PLATFORM_API_AUTHORITY=PASS "
        f"operations={len(operations)} "
        f"owners={len(owners)} "
        f"scopes={len(declared_scopes)} "
        f"events={len(set(doc['event_types']))} "
        f"statuses={dict(sorted(statuses.items()))}"
    )


if __name__ == "__main__":
    main()
