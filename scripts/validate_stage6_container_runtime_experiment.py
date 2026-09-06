#!/usr/bin/env python3
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PLAN = yaml.safe_load(
    (ROOT / "operations" / "stage6-container-runtime-rollback-experiment.yaml").read_text()
)


def require(value: bool, label: str) -> None:
    if not value:
        raise SystemExit(f"STAGE6_RUNTIME_EXPERIMENT_ERROR={label}")


require(PLAN["status"] == "REVIEW_REQUIRED_NOT_EXECUTED", "status")
require(PLAN["causality_status"] == "UNPROVEN_REVERSIBLE_EXPERIMENT", "causality")
require(PLAN["evidence"]["running_containers_started_before_upgrade"] == 0, "control")
require(PLAN["evidence"]["current_runc_bundled_by"] == "containerd.io", "runc_owner")
require(PLAN["candidate_runtime"]["runc"] == "1.3.6", "candidate_runc")
require(PLAN["rollback_runtime"]["runc"] == "1.4.3", "rollback_runc")

candidate = PLAN["candidate_packages"]
rollback = PLAN["rollback_packages"]
require(set(candidate) == set(rollback) and len(candidate) == 6, "package_tuple")
for package in candidate:
    require(candidate[package]["version"] != rollback[package]["version"], f"version_{package}")
    for side in (candidate, rollback):
        digest = side[package]["sha256"]
        require(isinstance(digest, str) and len(digest) == 64, f"digest_{package}")

impact = PLAN["impact"]
require(impact["host_reboot_required"] is False, "reboot")
require(impact["docker_daemon_restart_expected"] is True, "daemon_restart")
require(impact["all_running_containers_may_be_interrupted"] is True, "impact")
require(impact["workload_recreation_authorized"] is False, "recreation")
require(impact["staging_reconciliation_authorized"] is False, "staging")
require(impact["production_deployment_authorized"] is False, "production")

security = PLAN["security_invariants"]
require(security["seccomp_disabled"] is False, "seccomp")
for key, value in security.items():
    if key != "seccomp_disabled":
        require(value is False, key)

authorization = PLAN["authorization"]
require(authorization["source_pr_merge_authorizes_execution"] is False, "merge_auth")
require(authorization["execution_authorized"] is False, "execution_auth")
require(PLAN["runtime_mutation_permitted_before_approval"] is False, "runtime_mutation")
require(PLAN["production_business_writes_enabled"] is False, "business_writes")
require(len(PLAN["experiment"]["decisive_positive_canaries"]) == 2, "canaries")

print("STAGE6_CONTAINER_RUNTIME_EXPERIMENT=PASS")
print("CAUSALITY=UNPROVEN_TESTABLE")
print("HOST_REBOOT=NO")
print("DAEMON_RESTART_EXPECTED=YES")
print("EXECUTION_AUTHORIZED=NO")
print("PRODUCTION_CHANGED=NO")
