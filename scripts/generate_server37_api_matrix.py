#!/usr/bin/env python3
"""Generate the Server 37 API classification and candidate rollback evidence.

This script consumes the already-reviewed, current-host endpoint evidence.  It
does not contact services and must never read runtime credentials.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
SOURCE_MATRIX = ROOT / "PRODUCTION-API-MATRIX.yaml"
CERTIFICATION = ROOT / "FULL-PLATFORM-PRODUCTION-CERTIFICATION.yaml"
OUTPUT_MATRIX = ROOT / "SERVER-37-PRODUCTION-API-MATRIX.yaml"
OUTPUT_ROLLBACK = ROOT / "SERVER-37-PRODUCTION-ROLLBACK.yaml"
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


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text())
    if not isinstance(value, dict):
        raise RuntimeError(f"{path.name} is not a YAML object")
    return value


def endpoint_key(service: str, method: str, path: str) -> tuple[str, str, str]:
    return service, method.upper(), path


def main() -> None:
    source = load_yaml(SOURCE_MATRIX)
    certification = load_yaml(CERTIFICATION)
    source_sha256 = hashlib.sha256(SOURCE_MATRIX.read_bytes()).hexdigest()
    endpoint_index = {
        endpoint_key(row["service"], row["method"], row["path"]): row
        for row in source["endpoints"]
    }

    # The private email command is not part of the mission's required private
    # gateway contract.  The crawler command remains required because it is the
    # canonical replacement for the dead legacy Kyqra job-intake route.
    required = [
        dict(row)
        for row in source["required_contracts"]
        if endpoint_key(row["service"], row["method"], row["path"])
        != ("PRIVATE_GATEWAY", "POST", "/v1/integrations/email/commands")
    ]

    # The original contract covered Telnexa SMS submission and operation
    # control.  Add the families explicitly required by the Server 37 mission.
    telnexa_additions = (
        ("POST", "/api/v1/messages/bulk"),
        ("GET", "/api/v1/messages/{message_id}/events"),
        ("GET", "/api/v1/senders"),
        ("POST", "/api/v1/senders"),
        ("GET", "/api/v1/routing/routes"),
        ("GET", "/api/v1/tenants"),
        ("GET", "/api/v1/tenants/{requested_tenant_id}"),
        ("GET", "/api/v1/api-keys"),
        ("POST", "/api/v1/api-keys"),
        ("DELETE", "/api/v1/api-keys/{key_id}"),
        ("GET", "/api/v1/webhooks"),
        ("POST", "/api/v1/webhooks"),
        ("DELETE", "/api/v1/webhooks/{webhook_id}"),
        ("GET", "/api/v1/audit"),
        ("GET", "/api/v1/usage"),
    )
    for method, path in telnexa_additions:
        row = endpoint_index[endpoint_key("TELNEXA", method, path)]
        required.append(
            {
                "service": "TELNEXA",
                "method": method,
                "path": path,
                "implementation_status": row["implementation_status"],
                "runtime_verification": row["runtime_verification"],
            }
        )

    classified_required: list[dict[str, Any]] = []
    for row in required:
        live = row["runtime_verification"] == "LIVE_OPENAPI_MATCH"
        classified_required.append(
            {
                "service": row["service"],
                "method": row["method"],
                "path": row["path"],
                "classification": "REQUIRED_LIVE" if live else "MISSING_REQUIRED",
                "source_implemented": row["implementation_status"] != "MISSING",
                "runtime_verified": live,
                "evidence": row["runtime_verification"],
            }
        )

    missing_required = sum(
        row["classification"] == "MISSING_REQUIRED" for row in classified_required
    )
    required_live = len(classified_required) - missing_required
    required_by_service = {
        service: sum(
            row["service"] == service and row["classification"] == "REQUIRED_LIVE"
            for row in classified_required
        )
        for service in ("KLYROW", "TELNEXA")
    }

    live_groups = [
        {
            "service": "KLYROW_GATEWAY",
            "authority": "RUNNING_OPENAPI_AND_NGINX",
            "operation_count": required_by_service["KLYROW"],
            "classification": "REQUIRED_LIVE",
            "notes": "Canonical required operations are present in the protected production runtime.",
        },
        {
            "service": "KLYROW_GATEWAY",
            "authority": "RUNNING_OPENAPI_AND_NGINX",
            "operation_count": 324 - required_by_service["KLYROW"],
            "classification": "OPTIONAL_LIVE",
            "notes": "Live protected-source application operations outside the bounded required contract.",
        },
        {
            "service": "KLYROW_GATEWAY",
            "authority": "RUNNING_OPENAPI_AND_NGINX",
            "operation_count": 1,
            "classification": "LEGACY_COMPATIBILITY",
            "notes": "GET /v1/legacy/billing/usage.",
        },
        {
            "service": "TELNEXA_API",
            "authority": "RUNNING_OPENAPI_AND_NGINX",
            "operation_count": required_by_service["TELNEXA"],
            "classification": "REQUIRED_LIVE",
            "notes": "Required Telnexa operations already present in the old runtime.",
        },
        {
            "service": "TELNEXA_API",
            "authority": "RUNNING_OPENAPI_AND_NGINX",
            "operation_count": 39 - required_by_service["TELNEXA"],
            "classification": "OPTIONAL_LIVE",
            "notes": "Live public Telnexa operations outside the exact current contract, including contract-drifted paths.",
        },
        {
            "service": "KYQRA_API",
            "authority": "RUNNING_SOURCE_ROUTES_AND_NGINX",
            "operation_count": 9,
            "classification": "LEGACY_COMPATIBILITY",
            "notes": "Functional legacy paths; they do not establish reviewed-source parity.",
        },
        {
            "service": "NGINX_HEALTH",
            "authority": "RUNNING_NGINX",
            "operation_count": 2,
            "classification": "REQUIRED_LIVE",
            "notes": "sms.telnexa.co and status.telnexa.co health responders.",
        },
        {
            "service": "JASMIN_HTTP",
            "authority": "RUNNING_JASMIN_CONFIGURATION",
            "operation_count": 7,
            "classification": "UPSTREAM_PRODUCT_API",
        },
        {
            "service": "KEYCLOAK_PROTOCOL",
            "authority": "RUNNING_KEYCLOAK_REGISTRY_AND_NGINX",
            "operation_count": 139,
            "classification": "UPSTREAM_PRODUCT_API",
        },
        {
            "service": "GRAFANA",
            "authority": "RUNNING_GRAFANA_REGISTRY_AND_OPENAPI",
            "operation_count": 741,
            "classification": "UPSTREAM_PRODUCT_API",
            "notes": "443 classic, 291 unified, and 7 schema/health/metrics operations.",
        },
        {
            "service": "OPENBAO",
            "authority": "RUNNING_OPENBAO_PATH_CATALOG",
            "operation_count": 276,
            "classification": "UPSTREAM_PRODUCT_API",
            "notes": "Registered operations; authority remains uninitialized and sealed.",
        },
        {
            "service": "KLYROW_BILLING",
            "authority": "RUNNING_PRIVATE_OPENAPI",
            "operation_count": 214,
            "classification": "INTERNAL_ONLY",
        },
        {
            "service": "KLYROW_WORKER_HEALTH",
            "authority": "RUNNING_PRIVATE_ROUTES",
            "operation_count": 3,
            "classification": "INTERNAL_ONLY",
        },
        {
            "service": "POSTAL_PROVISIONER",
            "authority": "RUNNING_PRIVATE_ROUTES",
            "operation_count": 4,
            "classification": "INTERNAL_ONLY",
        },
        {
            "service": "PRIVATE_INTEGRATION_GATEWAY",
            "authority": "RUNNING_PROTECTED_SOURCE_OPENAPI",
            "operation_count": 20,
            "classification": "INTERNAL_ONLY",
            "notes": "Signed shared-mode protected release is deployed; the separately governed middleware-mode ingress contract is not deployed.",
        },
        {
            "service": "PROMETHEUS",
            "authority": "RUNNING_PROMETHEUS_API",
            "operation_count": 66,
            "classification": "INTERNAL_ONLY",
        },
        {
            "service": "NODE_EXPORTER",
            "authority": "RUNNING_METRICS_LISTENERS",
            "operation_count": 3,
            "classification": "INTERNAL_ONLY",
        },
        {
            "service": "RABBITMQ_METRICS",
            "authority": "RUNNING_METRICS_LISTENERS",
            "operation_count": 7,
            "classification": "INTERNAL_ONLY",
        },
        {
            "service": "KEYCLOAK_ADMIN",
            "authority": "RUNNING_KEYCLOAK_REGISTRY",
            "operation_count": 450,
            "classification": "INTERNAL_ONLY",
            "notes": "Public /auth/admin/ remains blocked by Nginx.",
        },
        {
            "service": "KEYCLOAK_MANAGEMENT",
            "authority": "RUNNING_KEYCLOAK_MANAGEMENT_LISTENER",
            "operation_count": 5,
            "classification": "INTERNAL_ONLY",
        },
        {
            "service": "POSTAL_HEALTH_CONTROL",
            "authority": "RUNNING_POSTAL_LISTENERS",
            "operation_count": 6,
            "classification": "INTERNAL_ONLY",
        },
        {
            "service": "POSTAL_LEGACY_API",
            "authority": "RUNNING_RAILS_ROUTES",
            "operation_count": 16,
            "classification": "LEGACY_COMPATIBILITY",
            "notes": "Private compatibility surface pending dependency retirement evidence.",
        },
        {
            "service": "MAUTIC",
            "authority": "RUNNING_ROUTER_AND_NGINX_PRIVATE_API_DENY",
            "operation_count": 781,
            "classification": "INTERNAL_ONLY",
            "notes": "Mautic router is live; API and OAuth are private-network only and use the dedicated Klyrow OAuth2 identity.",
        },
        {
            "service": "TELNEXA_ADMIN_SIMULATOR_METRICS",
            "authority": "RUNNING_OPENAPI_AND_NGINX_DENY_RULES",
            "operation_count": 7,
            "classification": "INTERNAL_ONLY",
            "notes": "Explicitly blocked at the public edge.",
        },
    ]
    live_counts: dict[str, int] = {name: 0 for name in ALLOWED_CLASSIFICATIONS}
    for group in live_groups:
        live_counts[group["classification"]] += group["operation_count"]
    if sum(live_counts.values()) != 3120:
        raise RuntimeError(f"live classification total is {sum(live_counts.values())}, expected 3120")

    source_only_groups = [
        {
            "service": "KEYCLOAK_EXPERIMENTAL_EXTENSIONS",
            "operation_count": 26,
            "classification": "DISABLED_BY_DESIGN",
        },
        {
            "service": "JASMIN_REST_V1",
            "operation_count": 5,
            "classification": "N/A",
            "notes": "Telnexa uses the private Jasmin HTTP submission adapter; REST-v1 is not required.",
        },
        {
            "service": "PRIVATE_GATEWAY_LEGACY_KYQRA_JOB_INTAKE",
            "operation_count": 1,
            "classification": "N/A",
            "notes": "Dead/deprecated route; canonical crawler command intake is a separate missing requirement.",
        },
    ]
    if sum(row["operation_count"] for row in source_only_groups) != 32:
        raise RuntimeError("source-only classification does not reconcile to 32")

    documented_not_implemented = [
        {
            "service": "MAUTIC_GENERATED_METADATA",
            "operation_count": 4,
            "classification": "N/A",
            "notes": "Upstream explicitly marks these generated metadata operations non-exposed.",
        }
    ]

    integration_contracts = [
        {
            "service": "MAUTIC",
            "required_domains": [
                "contacts",
                "companies",
                "segments",
                "tags",
                "campaigns",
                "campaign_membership",
                "emails",
                "forms",
                "form_submissions",
                "webhooks",
                "reports",
                "service_identity",
            ],
            "classification": "REQUIRED_LIVE",
            "reason": "Dedicated private OAuth2 identity, scheduler file mounts, users/self, contact CRUD, segment membership, campaign membership, and cleanup passed; public API/OAuth routes remain denied.",
        },
        {
            "service": "KEYCLOAK",
            "required_protocols": [
                "discovery",
                "authorization",
                "token",
                "jwks",
                "userinfo",
                "logout",
                "refresh",
                "introspection_where_used",
                "pkce",
                "mfa",
                "service_accounts",
                "roles",
                "scopes",
                "brute_force_protection",
                "session_expiry",
            ],
            "classification": "MISSING_REQUIRED",
            "reason": "No enabled service accounts; refresh-token revocation and admin event audit are disabled in the running realm.",
        },
        {
            "service": "PRIVATE_GATEWAY",
            "required_capabilities": [
                "health",
                "readiness",
                "metrics",
                "capabilities",
                "kyqra_integration",
                "telnexa_integration",
                "operation_lookup",
                "events",
                "cancel",
                "reconcile",
            ],
            "classification": "MISSING_REQUIRED",
            "reason": "Reviewed candidate and positive mTLS/provider E2E are not deployed.",
        },
    ]

    for collection in (
        live_groups,
        source_only_groups,
        documented_not_implemented,
        classified_required,
        integration_contracts,
    ):
        for row in collection:
            if row["classification"] not in ALLOWED_CLASSIFICATIONS:
                raise RuntimeError(f"invalid classification: {row['classification']}")

    matrix = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "phase": "SERVER_37_PRODUCTION_REMEDIATION_AND_CERTIFICATION",
        "server": "37.27.128.39",
        "scope": "THIS_SERVER_ONLY",
        "authoritative_baseline": {
            "total_running_services": 72,
            "total_live_api_endpoints": 3120,
            "total_internal_api_endpoints": 1582,
            "total_source_implemented_not_deployed": 32,
            "api_inventory_complete": True,
            "source_matrix": SOURCE_MATRIX.name,
            "source_matrix_sha256": source_sha256,
        },
        "authority_order": [
            "RUNNING_REVERSE_PROXY_CONFIGURATION",
            "KONG_ROUTES_SERVICES_IF_PRESENT",
            "RUNNING_CADDY_OR_NGINX_ROUTES",
            "FASTAPI_DJANGO_OPENAPI",
            "ODOO_CONTROLLERS",
            "N8N_WEBHOOKS_API",
            "KEYCLOAK_ENDPOINTS",
            "PROMETHEUS_GRAFANA_APIS",
            "SERVICE_SOURCE_ROUTES",
            "CONTAINER_LABELS_RUNTIME_CONFIGURATION",
        ],
        "classification_definitions": {
            "REQUIRED_LIVE": "Required operation is registered in the current runtime.",
            "OPTIONAL_LIVE": "Live operation outside the bounded production-required set.",
            "INTERNAL_ONLY": "Live operation restricted to private/container/management access.",
            "LEGACY_COMPATIBILITY": "Live compatibility operation retained for an existing dependency.",
            "UPSTREAM_PRODUCT_API": "Framework/product-native surface; not custom Codestra API work.",
            "DISABLED_BY_DESIGN": "Source capability intentionally not registered or enabled.",
            "N/A": "Explicitly not required by the approved architecture.",
            "MISSING_REQUIRED": "Required canonical operation or integration capability is not live.",
        },
        "live_runtime_classification_counts": {
            key: value for key, value in live_counts.items() if value
        },
        "live_runtime_groups": live_groups,
        "baseline_source_implemented_not_deployed_groups": source_only_groups,
        "documented_not_implemented": documented_not_implemented,
        "canonical_custom_contract": {
            "total_operations": len(classified_required),
            "required_live": required_live,
            "missing_required": missing_required,
            "operations": sorted(
                classified_required,
                key=lambda row: (row["service"], row["path"], row["method"]),
            ),
        },
        "required_integration_capabilities": integration_contracts,
        "candidate_source_authority": {
            "KLYROW": {
                "repository": "https://github.com/appolon1908-hue/klyrow.com",
                "source_sha": certification["KLYROW_SOURCE_SHA"],
                "review": "DEPLOYED_PROTECTED_MAIN_PR_76_APPROVED_AND_MERGED",
            },
            "TELNEXA": {
                "repository": "https://github.com/appolon1908-hue/telnexa",
                "source_sha": certification["TELNEXA_SOURCE_SHA"],
                "review": "PR_27_REVIEW_REQUIRED",
            },
            "KYQRA": {
                "repository": "https://github.com/appolon1908-hue/kyqra-crawler",
                "source_sha": certification["KYQRA_SOURCE_SHA"],
                "review": "PR_38_REVIEW_REQUIRED",
            },
            "PRIVATE_GATEWAY": {
                "repository": "https://github.com/appolon1908-hue/codestra-production-platform",
                "source_sha": certification["PRIVATE_GATEWAY_SOURCE_SHA"],
                "review": "PROTECTED_RELEASE_SIGNED_AND_DEPLOYED",
            },
        },
        "missing_required_endpoints": missing_required,
        "completion_rule": "PASS_ONLY_WHEN_MISSING_REQUIRED_IS_ZERO_AND_REVIEWED_SOURCE_EQUALS_RUNTIME",
    }
    OUTPUT_MATRIX.write_text(yaml.safe_dump(matrix, sort_keys=False, width=120))

    rollback = {
        "schema_version": 1,
        "generated_at": matrix["generated_at"],
        "phase": matrix["phase"],
        "server": matrix["server"],
        "production_changed": True,
        "rollback_gate": "FAIL",
        "reason": "Klyrow, its private Mautic integration, and the shared private gateway are deployed with tested rollback controls; Telnexa and Kyqra candidates remain review-gated, so the platform rollback gate remains fail-closed.",
        "production_configuration_changes": [
            {
                "service": "MAUTIC_API",
                "before_state": "GLOBAL_API_DISABLED",
                "temporary_state": "OAUTH2_API_ENABLED_FOR_BOUNDED_VALIDATION",
                "after_state": "OAUTH2_API_ENABLED_PRIVATE_EDGE_DENIED",
                "rollback_procedure": "Restore api_enabled=false, clear and warm the production cache without restarting services, and verify public API requests fail closed while application health remains green.",
                "rollback_status": "PASS",
            },
            {
                "service": "TELNEXA_ADMIN_DENY_EDGE",
                "before_state": "HTTP_403_VHOST_WITH_DNS_ABSENT",
                "after_state": "DNS_AND_DEDICATED_TLS_PRESENT_HTTPS_403",
                "rollback_procedure": "Restore the recorded Nginx and TLS-monitor units, verify the exact A/admin value, then delete only that GoDaddy record. Retain the issued certificate on disk.",
                "rollback_status": "PASS",
                "evidence": "SERVER-37-TELNEXA-ADMIN-DENY-EVIDENCE.md",
            },
        ],
        "candidate_promotions": [
            {
                "service": "KLYROW_GATEWAY_AND_WORKER",
                "before_source_sha": "UNVERIFIED_RUNTIME_DRIFT",
                "before_image_digest": "sha256:7cb3769eceb3339dbbd4392580fceaa4ff285dbec3721fbb4dd2763a00e27d7f",
                "after_source_sha": "da9d85891a4e313748e309aed86662d6c03d26bb",
                "after_image_digest": "sha256:1b0caed0283f03bf3e1f05e8411ca7e28f30ab42c4b854b570471a22671a740b",
                "database_migration": "2026090208_runtime_database_least_privilege.sql",
                "rollback_procedure": "Run the root-gated Klyrow rollback operator, restoring all recorded prior service digests and the prior fixed boot inventory.",
                "status": "DEPLOYED_PASS",
            },
            {
                "service": "KLYROW_WEB",
                "before_source_sha": "UNVERIFIED_RUNTIME_DRIFT",
                "before_image_digest": "sha256:dd4a20b1c80f206ffb471bffaff5024f426e03f47ba9787e060933d65fb27019",
                "after_source_sha": "da9d85891a4e313748e309aed86662d6c03d26bb",
                "after_image_digest": "sha256:7227cf01cf5ac998bf15321c70546c2c8e1e25e9ca2b37f31cb8151f8aa6a6c1",
                "database_migration": "NONE",
                "rollback_procedure": "Restore the recorded before digest at the same Nginx route, then execute browser and authentication smoke tests.",
                "status": "DEPLOYED_PASS",
            },
            {
                "service": "POSTAL_PROVISIONER",
                "before_source_sha": "UNKNOWN",
                "before_image_digest": "sha256:82910d20b3cabd293d2bd896ee4b32cb5edf8c45412f44fd7800d86e18aefeb8",
                "after_source_sha": "da9d85891a4e313748e309aed86662d6c03d26bb",
                "after_image_digest": "sha256:d30d3065c5f4a87fc793a422dfd4e66d938b83d9562f9f9b0cb247cf3c704cd8",
                "database_migration": "NONE",
                "rollback_procedure": "Restore the recorded before digest and verify idempotent read-only provisioner health before allowing reconciliation.",
                "status": "DEPLOYED_PASS",
            },
            {
                "service": "KYQRA_API_AND_WORKERS",
                "before_source_sha": "DIRTY_WORKTREE_AT_45b388fed2f9424c296ca74e19404b383cafeee4",
                "before_image_digests": [
                    "sha256:4921a6e4540288f54ef414bdac5a131bcb39192179bd7449f11ed37f2a563f75",
                    "sha256:f1c8f7baef701e2f6b36122a5ad788f1afc7dc3aed872cacaf00bfbc1fa7adb5",
                    "sha256:b60792f7c6791b4b7c912d17c3c7151310c5c7cbc252b5c04e92ccfeb56b9d4f",
                    "sha256:369bf4c01a1fe87ae3f03c8d5be1728c022304ccbc0dcc5c50e85ea2ad5fdfbc",
                ],
                "after_source_sha": "37cb0bfc1b5366629eefdfbfcf822520bdf2617b",
                "after_image_digest": "sha256:e384651f9b5539b972ffb85e037e0f00fc63d77e442339dba8d46dde4acdc45d",
                "database_migration": "REVIEWED_FORWARD_AND_BACKWARD_MIGRATION_REQUIRED",
                "rollback_procedure": "Restore all four recorded before digests together and restore the isolated pre-migration database snapshot if compatibility checks fail.",
                "status": "NOT_DEPLOYED_REVIEW_REQUIRED",
            },
            {
                "service": "TELNEXA_BILLING_API_AND_WORKER",
                "before_source_sha": "4dbd67190ccc0fb2be52ec700882178e29c6ff27",
                "before_image_digest": "sha256:e92ec02857ac67c15030b26ca464ac07966b8bd0162c9dbd424844e42683012c",
                "after_source_sha": "e0474ecb9c6b52b9340aece4a446d63f2dd1b6ac",
                "after_image_digest": "sha256:f410f43f9253271d10144c6a80a40ab7b6296470b6357be5176edabb56d796b7",
                "database_migration": "REVIEWED_FORWARD_AND_BACKWARD_MIGRATION_REQUIRED",
                "rollback_procedure": "Stop intake, drain workers, restore the recorded before digest, and restore the isolated pre-migration billing snapshot when schema compatibility requires it.",
                "status": "NOT_DEPLOYED_REVIEW_REQUIRED",
            },
            {
                "service": "TELNEXA_KEYCLOAK",
                "before_source_sha": "UNATTRIBUTED_TELNEXA_WRAPPER",
                "before_image_digest": "sha256:03f6ec1f3754e4a448d1a5008bc6521d08b26bbf27407f0acf5b0a99180adfaa",
                "after_source_sha": "e0474ecb9c6b52b9340aece4a446d63f2dd1b6ac",
                "after_image_digest": "sha256:960b8833992d02b3f39fb3dfa25ace03de9b1e3682307c8cebb4e150b6efa17c",
                "database_migration": "KEYCLOAK_SCHEMA_UPGRADE_REQUIRES_ISOLATED_RESTORE_PROOF",
                "rollback_procedure": "Restore the isolated pre-upgrade Keycloak database and recorded before digest as one atomic rollback unit.",
                "status": "NOT_DEPLOYED_REVIEW_REQUIRED",
            },
            {
                "service": "TELNEXA_JASMIN",
                "before_source_sha": "WRAPPER_TAG_4b4e5c73463d",
                "before_image_digest": "sha256:16585e89840fdd972d9483c0e45d5fad694df28922562f74fb05d540a6893cf4",
                "after_source_sha": "e0474ecb9c6b52b9340aece4a446d63f2dd1b6ac",
                "after_image_digest": "sha256:90995aaefd0fc72641d988acba08b3830d4f3ced80ea656c70ce197813f44824",
                "database_migration": "JASMIN_TOPOLOGY_MIGRATION_REQUIRES_ISOLATED_ROUNDTRIP",
                "rollback_procedure": "Quiesce submission, snapshot broker/Jasmin state, restore the before digest and topology snapshot, then prove no-effect SMPP and DLR handling.",
                "status": "NOT_DEPLOYED_REVIEW_REQUIRED",
            },
            {
                "service": "TELNEXA_WEBHOOK_RELAY",
                "before_source_sha": "NOT_RUNNING",
                "after_source_sha": "e0474ecb9c6b52b9340aece4a446d63f2dd1b6ac",
                "after_image_digest": "sha256:3d3a03fc8a10989ed986fc1d614ea18c737bddef57d2dcadb19c0a5d99da5640",
                "database_migration": "NONE",
                "rollback_procedure": "Remove the candidate relay from the reviewed Compose graph and restore the prior direct private event path.",
                "status": "NOT_DEPLOYED_REVIEW_REQUIRED",
            },
            {
                "service": "TELNEXA_CONTAINER_NGINX",
                "before_source_sha": "HOST_NGINX_AUTHORITY",
                "after_source_sha": "e0474ecb9c6b52b9340aece4a446d63f2dd1b6ac",
                "after_image_digest": "sha256:791e66955c7a6d34f8172cfeeff1715b8ecb067d6ebba5efa78d28250fa39953",
                "database_migration": "NONE",
                "rollback_procedure": "Restore the reviewed host-Nginx route snapshot and remove the container edge from the upstream graph.",
                "status": "NOT_DEPLOYED_REVIEW_REQUIRED",
            },
            {
                "service": "PRIVATE_INTEGRATION_GATEWAY",
                "before_source_sha": "a3dbfd6b464d2ba4c130e360f8ad73338bdd9fbb",
                "before_image_digest": "sha256:6d6d8cefa4a32796c85a1d6505d74fefdd2e1646421f387f126a2d0ecd03ed88",
                "after_source_sha": "9ec227d6a2b5c14217d88c33a8cfd4e057486c56",
                "after_image_digest": "sha256:8f963929c600baa03435e9c5d7bc7bfa9af152fe26736ca201c586a7b6c0db6b",
                "database_migration": "NONE_APPLICATION_BYTES_IDENTICAL_SQLITE_INTEGRITY_VERIFIED",
                "rollback_procedure": "Use the root-only private-gateway rollout bundle to restore the prior digest; the rollback and forward recovery rehearsal both returned healthy with SQLite integrity preserved.",
                "rollback_evidence": "SERVER-37-PRIVATE-GATEWAY-RELEASE-EVIDENCE.md",
                "status": "DEPLOYED_PASS",
            },
        ],
        "required_next_action": "Independent reviewers approve the remaining exact Telnexa and Kyqra heads; release owners publish signed digests and perform isolated rollback rehearsals before production promotion.",
    }
    rollback["production_configuration_changes"].extend(
        [{'service': 'PRIVATE_GATEWAY_NGINX_EDGE',
          'before_state': '390839d0d142e335e722d7127e30eebc68c32314849ff145468a28794bdafca3',
          'after_state': '66c66dab3d1e67c230687af6d58e2fefe32d85e2ec9d44c2d0de9ea5b2d05231',
          'rollback_bundle': '/var/backups/codestra-operators/private-gateway-edge-20260903T002126Z',
          'rollback_procedure': 'Authorized operator must restore the recorded prior Nginx configuration, '
                                'verify its checksum and nginx -t, reload, then restore the protected '
                                'configuration and verify its checksum, certificate denial and gateway '
                                'health. This rehearsal is not evidenced.',
          'rollback_status': 'FAIL',
          'evidence': 'SERVER-37-PRIVATE-GATEWAY-RELEASE-EVIDENCE.md',
          'evidence_sha256': 'da8ed21364a61ed81a1a2e72caa7b1785858b17e5bef6821c40519d1155993f4'},
         {'service': 'KLYROW_EVENT_CONFIGURATION_BRIDGE',
          'before_state': 'LEGACY_BASE_GUARD_NOT_BOUND_TO_APPROVED_MTLS_AUTHORITY',
          'after_state': 'GATEWAY_AND_WORKER_LEGACY_BASE_GUARD_BOUND_TO_APPROVED_MTLS_AUTHORITY',
          'rollback_bundle': '/var/backups/codestra-operators/klyrow-event-bridge-20260903T004520Z',
          'rollback_procedure': 'Authorized operator restores the gateway and delivery-worker '
                                'configuration together from the recorded bundle, recreates both at the '
                                'unchanged image digest, and verifies isolation and no-send controls; '
                                'forward recovery reapplies the bridge to both services. The cited '
                                'historical report records rollback and forward recovery PASS.',
          'rollback_status': 'PASS',
          'evidence': 'SERVER-37-KLYROW-EVENT-DELIVERY-EVIDENCE.md',
          'evidence_sha256': '0c9df7c43e2eb2d2fd7d62ac6bee0c1fb0443f56ad367ba9569d904a003a3c78'}]
    )
    rollback["reason"] = 'Historical image rollback controls do not certify later configuration changes. The private Nginx edge rollback rehearsal is not evidenced; Telnexa and Kyqra remain review-gated. Platform rollback remains FAIL.'
    OUTPUT_ROLLBACK.write_text(yaml.safe_dump(rollback, sort_keys=False, width=120))

    print(
        yaml.safe_dump(
            {
                "output": OUTPUT_MATRIX.name,
                "live_operations_classified": sum(live_counts.values()),
                "required_contract_operations": len(classified_required),
                "missing_required_endpoints": missing_required,
                "rollback_output": OUTPUT_ROLLBACK.name,
            },
            sort_keys=False,
        ).strip()
    )


if __name__ == "__main__":
    main()
