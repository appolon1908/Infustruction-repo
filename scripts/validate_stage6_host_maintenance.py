#!/usr/bin/env python3
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PLAN = yaml.safe_load(
    (ROOT / "operations" / "stage6-host-seccomp-maintenance.yaml").read_text()
)


def require(condition: bool, label: str) -> None:
    if not condition:
        raise SystemExit(f"STAGE6_HOST_MAINTENANCE_ERROR={label}")


require(PLAN["status"] == "WITHDRAWN_NOT_EXECUTED", "status")
require(
    PLAN["superseded_by"]
    == "operations/stage6-container-runtime-rollback-experiment.yaml",
    "superseded_by",
)
require(PLAN["host"]["current_kernel"] == "5.15.0-187-generic", "current_kernel")
require(PLAN["host"]["target_kernel"] == "5.15.0-190-generic", "target_kernel")
require(PLAN["host"]["rollback_kernel"] == "5.15.0-187-generic", "rollback_kernel")
require(PLAN["preflight"]["running_containers_observed"] == 101, "container_count")
require(PLAN["preflight"]["frozen_workloads_present"] == 10, "frozen_count")
require(PLAN["impact"]["host_reboot_required"] is True, "reboot_disclosed")
require(PLAN["impact"]["frozen_workloads_will_restart"] is True, "frozen_disclosed")
require(PLAN["authorization"]["source_pr_merge_authorizes_execution"] is False, "merge_auth")
require(PLAN["authorization"]["execution_authorized"] is False, "execution_auth")
require(PLAN["runtime_mutation_permitted_before_approval"] is False, "runtime_mutation")
require(PLAN["staging_apply_authorized"] is False, "staging_apply")
require(PLAN["production_deployment_authorized"] is False, "production")

security = PLAN["security_invariants"]
require(security["seccomp_disabled"] is False, "seccomp")
for field in (
    "privileged_allowed",
    "capability_relaxation_allowed",
    "no_new_privileges_relaxation_allowed",
    "readonly_root_relaxation_allowed",
):
    require(security[field] is False, field)

require(PLAN["rollback"]["boot_target"].endswith("5.15.0-187-generic"), "rollback_target")
require(len(PLAN["post_change_gates"]) >= 9, "post_change_gates")

print("STAGE6_HOST_MAINTENANCE_PLAN=WITHDRAWN_NOT_EXECUTED")
print("EXECUTION_AUTHORIZED=NO")
print("SECCOMP_DISABLED=NO")
print("STAGING_APPLY=NO")
print("PRODUCTION_DEPLOYMENT=NO")
