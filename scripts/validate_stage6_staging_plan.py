#!/usr/bin/env python3
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
LOCK = yaml.safe_load((ROOT / "STAGE6-SOURCE-LOCK.yaml").read_text())
PLAN = yaml.safe_load(
    (ROOT / "releases/STAGE6-STAGING-DEPLOYMENT-PLAN-2026-08-30.yaml").read_text()
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"STAGE6_STAGING_PLAN_ERROR={message}")


require(PLAN["environment"] == "STAGING", "environment")
require(PLAN["status"] == "HELD_SCOPED_PREFLIGHT_FAILED_NOT_EXECUTED", "status")
require(PLAN["production_authorized"] is False, "production_authorized")
require(PLAN["external_writes_enabled"] is False, "external_writes_enabled")
require(PLAN["runtime_preflight"]["source_lock"] == "PASS", "source_lock_gate")
require(
    PLAN["runtime_preflight"]["stage6_preflight"] == "FAIL_SCOPED_RUNTIME_READBACK",
    "preflight_gate",
)
require(
    PLAN["runtime_preflight"]["stage6_path_business_writes"] == "NOT_PROVEN_DISABLED",
    "production_write_gate",
)
require(PLAN["runtime_preflight"]["scoped_runtime_readback"] == "FAIL", "runtime_readback")
require(PLAN["runtime_preflight"]["safety_complete_workloads"] == 0, "safety_complete")
require(PLAN["runtime_preflight"]["in_scope_host"] == "65.109.65.169", "in_scope_host")
require(PLAN["runtime_preflight"]["in_scope_workloads"] == 22, "in_scope_workloads")
require(
    PLAN["runtime_preflight"]["out_of_scope_active_production"]
    == "OUT_OF_SCOPE_ACTIVE_PRODUCTION_DO_NOT_TOUCH",
    "out_of_scope_production",
)
require(PLAN["backup"]["checksums"] == "PASS", "backup_checksums")
require(PLAN["backup"]["postgres_17_archives_readable"] == 24, "database_archive_count")

expected_safety = {
    "LIVE_ADVERTISING_ENABLED": False,
    "EXTERNAL_DELIVERY_ENABLED": False,
    "SOCIAL_PUBLISHING_ENABLED": False,
    "EXTERNAL_MODEL_CALLS_ENABLED": False,
    "LIVE_SMS_DELIVERY": False,
    "LIVE_EMAIL_DELIVERY": False,
    "LIVE_PSTN_DIALING": False,
    "PRODUCTION_DIALING": "DISABLED",
}
for key, value in expected_safety.items():
    require(PLAN["global_safety"].get(key) == value, f"safety_{key}")

batches = PLAN["batches"]
require([batch["id"] for batch in batches] == [0, 1, 2, 3, 4], "batch_order")
planned = [name for batch in batches for name in batch.get("workloads", [])]
frozen = PLAN["frozen_workloads"]
all_planned = planned + frozen
lock_names = set(LOCK["runtime_workloads"])
require(len(all_planned) == len(set(all_planned)), "duplicate_workload")
require(set(all_planned) == lock_names, "workload_coverage")
require(len(lock_names) == 22, "source_lock_workload_count")
require(len(frozen) == 10, "frozen_workload_count")
require(sum(len(b.get("workloads", [])) for b in batches if b["mutation"]) == 7, "mutation_target_count")

for name in frozen:
    disposition = LOCK["runtime_workloads"][name]["disposition"]
    require("FREEZE" in disposition or "UNVERIFIED" in disposition, f"frozen_disposition_{name}")

for batch in batches:
    if not batch["mutation"]:
        continue
    require(isinstance(batch.get("changes_image"), bool), f"changes_image_{batch['name']}")
    for name in batch["workloads"]:
        require("rollback_digest" in LOCK["runtime_workloads"][name], f"rollback_{name}")
    if batch["changes_image"]:
        require("expected_digest" in batch, f"expected_digest_{batch['name']}")
        require("rollback_digest" in batch, f"rollback_digest_{batch['name']}")
        require(
            batch["expected_digest"] != batch["rollback_digest"],
            f"image_rollback_must_precede_replacement_{batch['name']}",
        )

middleware = next(batch for batch in batches if batch["name"] == "middleware")
middleware_lock = LOCK["runtime_workloads"][middleware["workloads"][0]]
for field in ("expected_sha", "expected_digest", "rollback_digest"):
    require(middleware[field] == middleware_lock[field], f"middleware_{field}")
require(PLAN["unknown_workload"]["disposition"] == "UNVERIFIED_DO_NOT_TOUCH", "unknown_gateway")
print("STAGE6_STAGING_PLAN=PASS")
print("PLANNED_RELEASE_WORKLOADS=22")
print("MUTATION_TARGETS=7")
print("RETAIN_ONLY_WORKLOADS=5")
print("FROZEN_WORKLOADS=10")
print("PRODUCTION_AUTHORIZED=NO")
print("EXTERNAL_WRITES_ENABLED=NO")
print("STAGING_RECONCILIATION_AUTHORIZED=NO")
print("IMAGE_REPLACEMENT_ROLLBACK_DISTINCT=YES")
