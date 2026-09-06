#!/usr/bin/env python3
"""Generate sanitized, fail-closed Server B observability authority evidence."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
GENERATED_AT = "2026-09-02T17:02:17Z"
SERVER = "37.27.128.39"
REGISTRY = ROOT.parents[2] / "config/observability/repository-registry.v1.json"
DISPLAY_NAMES = {
    "grafana": "Grafana", "prometheus": "Prometheus", "alertmanager": "Alertmanager",
    "loki": "Loki", "tempo": "Tempo", "opentelemetry": "OpenTelemetry Collector",
    "superset": "Superset", "node-exporter": "Node Exporter", "cadvisor": "cAdvisor",
    "postgres-exporter": "PostgreSQL Exporter", "redis-exporter": "Redis Exporter",
    "blackbox-exporter": "Blackbox Exporter", "alloy": "Alloy", "openbao": "OpenBao",
}


def canonical_registry() -> dict:
    data = json.loads(REGISTRY.read_text())
    rows = data["repositories"]
    result = {row["component"]: row for row in rows}
    if len(result) != len(rows) or set(result) != set(DISPLAY_NAMES):
        raise ValueError("canonical observability component inventory mismatch")
    return result


COMPONENTS = [
    {
        "component": "Loki",
        "repository": "https://github.com/appolon1908-hue/Codestra-Loki",
        "production_sha": "c17b93282086a433439c695ed77a1ebdb0a944c0",
        "staging_sha": "a3dbac8cc945d6f3d1725839964ab42360181bcf",
        "production_branch_protected": False,
        "production_contains_staging": False,
        "api_pr": "https://github.com/appolon1908-hue/Codestra-Loki/pull/17",
        "promotion_pr": "https://github.com/appolon1908-hue/Codestra-Loki/pull/16",
        "runtime_state": "ABSENT",
        "runtime_image_digest": None,
    },
    {
        "component": "Prometheus",
        "repository": "https://github.com/appolon1908-hue/Codestra-Prometheus",
        "production_sha": "7b7a4b8880bb2d3c6bbb2d33bd23b23bd5c63284",
        "staging_sha": "b74f9432b2e4103b72c66aac62e7ccb7bd3617de",
        "production_branch_protected": False,
        "production_contains_staging": False,
        "api_pr": "https://github.com/appolon1908-hue/Codestra-Prometheus/pull/29",
        "promotion_pr": "https://github.com/appolon1908-hue/Codestra-Prometheus/pull/25",
        "runtime_state": "PRESENT_IN_TWO_BUSINESS_APPLICATION_STACKS_NOT_HOST_AUTHORITY",
        "runtime_image_digest": "sha256:63805ebb8d2b3920190daf1cb14a60871b16fd38bed42b857a3182bc621f4996",
    },
    {
        "component": "Grafana",
        "repository": "https://github.com/appolon1908-hue/Codestra-Grafana-",
        "production_sha": "e88307dbfdaaebc4a3b09b90eed1494579755e6a",
        "staging_sha": "42a2f75e4993349e654da5994d3b061b7e6219d5",
        "production_branch_protected": False,
        "production_contains_staging": True,
        "api_pr": "https://github.com/appolon1908-hue/Codestra-Grafana-/pull/17",
        "promotion_pr": None,
        "runtime_state": "PRESENT_IN_KLYROW_STACK_NOT_HOST_AUTHORITY",
        "runtime_image_digest": "sha256:9b58461280b4d2992d4399823c9427d0fcf5f0fd7f376c93f2dea876158b867b",
    },
    {
        "component": "Tempo",
        "repository": "https://github.com/appolon1908-hue/Codestra-Tempo",
        "production_sha": "c34a86e325cf5dc34533f721b03a8d0422e2086e",
        "staging_sha": "870b131d75b3fef2ac22eb7174542a2bded102f4",
        "production_branch_protected": False,
        "production_contains_staging": False,
        "api_pr": "https://github.com/appolon1908-hue/Codestra-Tempo/pull/15",
        "promotion_pr": "https://github.com/appolon1908-hue/Codestra-Tempo/pull/14",
        "runtime_state": "ABSENT",
        "runtime_image_digest": None,
    },
    {
        "component": "OpenTelemetry Collector",
        "repository": "https://github.com/appolon1908-hue/Codestra-Telemetry",
        "production_sha": "cb1e628913378886859b463844ba82c5222a833a",
        "staging_sha": "f8ac9417fc27473f04c58722fb2ec990072762ef",
        "production_branch_protected": False,
        "production_contains_staging": False,
        "api_pr": "https://github.com/appolon1908-hue/Codestra-Telemetry/pull/17",
        "promotion_pr": "https://github.com/appolon1908-hue/Codestra-Telemetry/pull/16",
        "runtime_state": "ABSENT",
        "runtime_image_digest": None,
    },
    {
        "component": "Alloy",
        "repository": "https://github.com/appolon1908-hue/Codestra-Alloy",
        "production_sha": "6e74e00ed24b927255766938f16416bfefb24223",
        "staging_sha": "f976f69d4bc8fd4e5e5fc0f5eb8e9c659f50ebde",
        "production_branch_protected": False,
        "production_contains_staging": True,
        "api_pr": "https://github.com/appolon1908-hue/Codestra-Alloy/pull/17",
        "promotion_pr": None,
        "runtime_state": "ABSENT",
        "runtime_image_digest": None,
    },
    {
        "component": "Node Exporter",
        "repository": "https://github.com/appolon1908-hue/Codestra-Node-Exporter",
        "production_sha": "c1b84bc9f455c269dece1e58d67812d61a9856e9",
        "staging_sha": "95e24dff0450c202aa03fd3e2b81ac9ae82b14a7",
        "production_branch_protected": False,
        "production_contains_staging": False,
        "api_pr": "https://github.com/appolon1908-hue/Codestra-Node-Exporter/pull/21",
        "promotion_pr": "https://github.com/appolon1908-hue/Codestra-Node-Exporter/pull/20",
        "runtime_state": "PRESENT_AS_HOST_SYSTEMD_AND_TWO_BUSINESS_STACKS_NOT_HOST_AUTHORITY",
        "runtime_image_digest": "sha256:d00a542e409ee618a4edc67da14dd48c5da66726bbd5537ab2af9c1dfc442c8a",
    },
    {
        "component": "cAdvisor",
        "repository": "https://github.com/appolon1908-hue/Codestra-cAdvisor",
        "production_sha": "69d6119176f408601b6bf3384bae6257890747b0",
        "staging_sha": "97927343014f73cd4c388a1fcdd92ee483fa2b33",
        "production_branch_protected": False,
        "production_contains_staging": False,
        "api_pr": "https://github.com/appolon1908-hue/Codestra-cAdvisor/pull/18",
        "promotion_pr": "https://github.com/appolon1908-hue/Codestra-cAdvisor/pull/17",
        "runtime_state": "ABSENT",
        "runtime_image_digest": None,
    },
    {
        "component": "Redis Exporter",
        "repository": "https://github.com/appolon1908-hue/Codestra-Redis-Exporter",
        "production_sha": "c6e4dbc0243e5c3736df7ba34d8c0db8a3228332",
        "staging_sha": "0c051b670c308186494e4e09d9c116a7b54fdf23",
        "production_branch_protected": False,
        "production_contains_staging": False,
        "api_pr": "https://github.com/appolon1908-hue/Codestra-Redis-Exporter/pull/18",
        "promotion_pr": "https://github.com/appolon1908-hue/Codestra-Redis-Exporter/pull/17",
        "runtime_state": "ABSENT",
        "runtime_image_digest": None,
    },
    {
        "component": "Blackbox Exporter",
        "repository": "https://github.com/appolon1908-hue/Codestra-Blackbox-Exporter",
        "production_sha": "ab3ff59b92a90c405d9eee43b4e97b3394ef347c",
        "staging_sha": "f303beea84acca2335a0a0f311fefca933404178",
        "production_branch_protected": False,
        "production_contains_staging": False,
        "api_pr": "https://github.com/appolon1908-hue/Codestra-Blackbox-Exporter/pull/18",
        "promotion_pr": "https://github.com/appolon1908-hue/Codestra-Blackbox-Exporter/pull/17",
        "runtime_state": "ABSENT",
        "runtime_image_digest": None,
    },
    {
        "component": "Superset",
        "repository": "https://github.com/appolon1908-hue/Superset",
        "production_sha": "f12bc1cdf4d1c7bb0636fa27c69dd6f99c6acf0e",
        "staging_sha": "e64f83889fed203bf51f925adacfdca82a25c0b8",
        "production_branch_protected": False,
        "production_contains_staging": False,
        "api_pr": "https://github.com/appolon1908-hue/Superset/pull/17",
        "promotion_pr": "https://github.com/appolon1908-hue/Superset/pull/16",
        "runtime_state": "ABSENT",
        "runtime_image_digest": None,
    },
    {
        "component": "OpenBao",
        "repository": "https://github.com/appolon1908-hue/Codestra-OpenBao",
        "production_sha": "38ff3f3d7a2dcd9f03455415c26b2562a50adb34",
        "staging_sha": "6e092ce5cf8e1cd76587118103653ebb7e7620b0",
        "production_branch_protected": True,
        "production_contains_staging": False,
        "api_pr": "https://github.com/appolon1908-hue/Codestra-OpenBao/pull/30",
        "promotion_pr": "https://github.com/appolon1908-hue/Codestra-OpenBao/pull/28",
        "runtime_state": "PRESENT_UNINITIALIZED_AND_SEALED",
        "runtime_image_digest": "sha256:5b2486ab0fb90bbc788cc345b0a08616dfb375873ee8be5df3a2fd4d378a67e0",
    },
]

DNS_NAMES = [
    "graf.codestra.media",
    "prom.codestra.media",
    "loki.codestra.media",
    "temp.codestra.media",
    "otel.codestra.media",
    "allo.codestra.media",
    "node.codestra.media",
    "cadv.codestra.media",
    "rdex.codestra.media",
    "blac.codestra.media",
    "supe.codestra.media",
    "bao.codestra.media",
]


def write_json(name: str, value: object) -> None:
    (ROOT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main() -> None:
    # Extend scope from canonical source, not invented production/runtime observations.
    registry = canonical_registry()
    components = [dict(row, source_evidence_status="HISTORICAL_20260902") for row in COMPONENTS]
    for key in ("alertmanager", "postgres-exporter"):
        canonical = registry[key]
        components.append({
            "component": DISPLAY_NAMES[key],
            "repository": "https://github.com/" + canonical["repository"],
            "production_sha": None,
            "staging_sha": None,
            "production_branch_protected": None,
            "production_contains_staging": None,
            "api_pr": None,
            "promotion_pr": None,
            "runtime_state": "NOT_CAPTURED",
            "runtime_image_digest": None,
            "source_evidence_status": "NOT_CAPTURED",
            "canonical_candidate_sha": canonical["candidate"]["headSha"],
            "canonical_candidate_branch": canonical["candidate"]["branch"],
        })
    common = {
        "generated_at": GENERATED_AT,
        "server": SERVER,
        "phase": "SERVER_B_CODESTRA_OBSERVABILITY_14_AUTHORITY_REVIEW",
        "historical_observed_at": GENERATED_AT,
        "scope_corrected_at": "2026-09-06",
        "runtime_revalidated": False,
    }
    write_json(
        "repository-inventory.json",
        {
            **common,
            "host_authority_repository": "https://github.com/appolon1908-hue/Infustruction-repo",
            "host_authority_base_branch": "development",
            "host_authority_base_sha": "e00cf3298bd5b7775a06707693f547ba704ac728",
            "components": components,
        },
    )
    write_json(
        "production-source-lock.json",
        {
            **common,
            "lock_status": "FAIL",
            "components": [
                {
                    "component": row["component"],
                    "repository": row["repository"],
                    "branch": "production",
                    "source_sha": row["production_sha"],
                    "staging_sha": row["staging_sha"],
                    "source_evidence_status": row["source_evidence_status"],
                    "branch_protected": row["production_branch_protected"],
                    "production_contains_staging": row["production_contains_staging"],
                    "exact_head_ci": "FAIL",
                    "release_evidence_complete": False,
                    "activation_allowed": False,
                }
                for row in components
            ],
        },
    )
    write_json(
        "production-image-lock.json",
        {
            **common,
            "lock_status": "FAIL",
            "components": [
                {
                    "component": row["component"],
                    "runtime_image_digest": row["runtime_image_digest"],
                    "source_aligned": False,
                    "sbom": "FAIL",
                    "provenance": "FAIL",
                    "signature": "FAIL",
                    "vulnerability_gate": "FAIL",
                    "activation_allowed": False,
                }
                for row in components
            ],
        },
    )
    write_json(
        "runtime-inventory.json",
        {
            **common,
            "running_required_components": sum(row["runtime_state"].startswith("PRESENT_") for row in components),
            "absent_required_components": sum(row["runtime_state"] == "ABSENT" for row in components),
            "not_captured_required_components": sum(row["runtime_state"] == "NOT_CAPTURED" for row in components),
            "running_unhealthy_containers": 0,
            "restarting_containers": 0,
            "critical_alerts": [
                "KlyrowEventDeliveryStalled",
                "KlyrowUsageDeliveryStalled",
            ],
            "prometheus_targets": {"total": 5, "up": 5, "down": 0},
            "host_node_exporter": {
                "service": "prometheus-node-exporter.service",
                "version": "1.3.1",
                "bind_address": "127.0.0.1:9100",
                "http_status": 200,
                "enabled_collectors": 46,
                "collector_allowlist_gate": "FAIL",
                "reason": "DEFAULT_COLLECTOR_SET_IS_ENABLED_WITHOUT_REVIEWED_HOST_AUTHORITY",
                "sensitive_pattern_metric_families": ["node_systemd_unit_state"],
                "secret_value_evidence": "NOT_COLLECTED",
            },
            "components": [
                {
                    "component": row["component"],
                    "runtime_state": row["runtime_state"],
                    "runtime_image_digest": row["runtime_image_digest"],
                    "host_authority_managed": False,
                    "activation_certified": False,
                }
                for row in components
            ],
        },
    )
    write_json(
        "network-inventory.json",
        {
            **common,
            "dns": [
                {"hostname": host, "a_records": [SERVER], "exclusive": True}
                for host in DNS_NAMES
            ],
            "tls": [
                {
                    "hostname": host,
                    "status": "PASS" if host == "bao.codestra.media" else "FAIL",
                    "reason": "MATCHING_CERTIFICATE"
                    if host == "bao.codestra.media"
                    else "KLYROW_CERTIFICATE_NAME_MISMATCH",
                }
                for host in DNS_NAMES
            ],
            "browser_endpoints": [
                "graf.codestra.media",
                "supe.codestra.media",
                "bao.codestra.media",
            ],
            "restricted_endpoints": [
                host
                for host in DNS_NAMES
                if host
                not in {
                    "graf.codestra.media",
                    "supe.codestra.media",
                    "bao.codestra.media",
                }
            ],
            "components": [
                {
                    "component": DISPLAY_NAMES[key],
                    "repository": row["repository"],
                    "intended_hostname": row.get("hostname"),
                    "private_service_identity": row.get("privateServiceIdentity"),
                    "evidence_status": "NOT_CAPTURED" if key in {"alertmanager", "postgres-exporter"} else "HISTORICAL_20260902",
                    "activation_allowed": False,
                }
                for key, row in registry.items()
            ],
            "network_gate": "FAIL",
        },
    )
    write_json(
        "api-certification.json",
        {
            **common,
            "api_contracts_complete": 0,
            "apis_runtime_verified": 0,
            "unexpected_404s": 0,
            "unexpected_5xxs": 0,
            "authentication": "FAIL",
            "authorization_negative_tests": "FAIL",
            "tenant_isolation": "FAIL",
            "cross_business_denial": "FAIL",
            "components": [
                {
                    "component": row["component"],
                    "api_contract_pr": row["api_pr"],
                    "contract_state": "DRAFT_OR_UNMERGED",
                    "runtime_verified": False,
                    "activation_allowed": False,
                }
                for row in components
            ],
        },
    )
    write_json(
        "backup-restore-matrix.json",
        {
            **common,
            "backup_gate": "FAIL",
            "restore_gate": "FAIL",
            "components": [
                {
                    "component": row["component"],
                    "stateful": row["component"]
                    in {
                        "Loki",
                        "Alertmanager",
                        "Prometheus",
                        "Grafana",
                        "Tempo",
                        "Superset",
                        "OpenBao",
                    },
                    "backup": "FAIL",
                    "off_host_backup": "FAIL",
                    "isolated_restore": "FAIL",
                    "rpo_seconds": None,
                    "rto_seconds": None,
                }
                for row in components
            ],
        },
    )
    write_json(
        "rollback-matrix.json",
        {
            **common,
            "rollback_gate": "FAIL",
            "production_changed": False,
            "components": [
                {
                    "component": row["component"],
                    "before_source_sha": row["production_sha"],
                    "before_image_digest": row["runtime_image_digest"],
                    "after_source_sha": None,
                    "after_image_digest": None,
                    "state_snapshot": "MISSING",
                    "rollback_command": None,
                    "rollback_duration_seconds": None,
                    "rollback_health": "FAIL",
                }
                for row in components
            ],
        },
    )
    (ROOT / "authority-matrix.yaml").write_text(
        "\n".join(
            [
                "schema_version: 1",
                f"generated_at: {GENERATED_AT}",
                f"server: {SERVER}",
                "activation_allowed: false",
                "gates:",
                "  repository_branches: FAIL",
                "  exact_head_ci: FAIL",
                "  reviews: FAIL",
                "  api_contracts: FAIL",
                "  tls: FAIL",
                "  mtls: FAIL",
                "  immutable_images: FAIL",
                "  supply_chain: FAIL",
                "  backup: FAIL",
                "  restore: FAIL",
                "  rollback: FAIL",
                "  critical_alerts: FAIL",
                "  source_runtime_alignment: FAIL",
                "overall_verdict: NOT_PRODUCTION_CERTIFIED",
                "",
            ]
        )
    )
    (ROOT / "certification-report.md").write_text(
        """# Server B observability production certification

Status: **NOT_PRODUCTION_CERTIFIED**

This is a sanitized, fail-closed pre-change record for `37.27.128.39`. No
component was installed, recreated, restarted, or activated. SSH, firewall,
DNS, reverse-proxy, identity, and secret authorities were not changed.

The historical twelve probed DNS names resolved exclusively to the intended server. Eleven names
served an unrelated Klyrow certificate; only `bao.codestra.media` has a matching
certificate. Two critical Klyrow delivery alerts are firing. Only Prometheus,
Grafana, Node Exporter, and OpenBao have existing runtimes, none controlled by
this host authority. OpenBao is uninitialized and sealed. The host package Node
Exporter is healthy and loopback-only, but its broad default collector set is
not controlled by the reviewed host authority. The required API, release,
runtime, backup, restore, rollback, SBOM, provenance, and signature evidence is
not present on the protected product production branches.

The scope now includes all fourteen canonical components. Alertmanager and
PostgreSQL Exporter were missing from this record; their production/staging
heads and runtime/network/recovery evidence remain explicitly NOT_CAPTURED.
Canonical candidate references do not substitute for protected production
heads. No new DNS, service, or runtime probe was run for this source repair.

Activation remains prohibited until every JSON/YAML gate in this directory is
regenerated from reviewed protected release heads and validates PASS.
"""
    )
    (ROOT / "current-blockers.md").write_text(
        """# Current blockers

1. Independent reviewers must approve the product API and promotion PRs.
2. Repository owners must protect the complete release branch chain and attach
   exact-production-head CI; local validation is not a substitute.
3. The proxy/TLS owner must publish reviewed matching certificates and private
   access boundaries for the eleven failing hostnames.
4. The Klyrow owner must resolve the two firing critical delivery alerts.
5. Release owners must publish digest-only signed images with SBOM, provenance,
   clean vulnerability evidence, and exact source revision labels.
6. Recovery owners must provide state snapshots, encrypted off-host backups,
   isolated restores, and measured rollback for every stateful component.
7. OpenBao recovery custodians must approve an initialization or recovery
   ceremony; no unseal shares or root authority may be invented.
8. Identity owners must provide approved OIDC/mTLS service and canary identities
   for negative and cross-business tests without exposing their values.
9. Alertmanager and PostgreSQL Exporter require complete protected source,
   image, runtime, network, API, recovery, and rollback evidence; registry
   membership alone does not establish any of those operational gates.
10. The Node Exporter owner must replace or formally retire the unmanaged host
   package service and approve an explicit collector allowlist.
"""
    )
    write_json(
        "release-layout.json",
        {
            **common,
            "components": sorted(DISPLAY_NAMES.values()),
            "release_root": "/opt/codestra/releases/observability/<component>/<production-sha>/",
            "current_link": "/opt/codestra/current/observability/<component>",
            "rollback_root": "/opt/codestra/rollback/observability/<component>/",
            "state_root": "/var/lib/codestra/<component>/",
            "backup_root": "/var/backups/codestra/<component>/",
            "activation_allowed": False,
        },
    )


if __name__ == "__main__":
    main()
