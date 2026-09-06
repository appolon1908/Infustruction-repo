#!/usr/bin/env python3
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PLAN = yaml.safe_load(
    (ROOT / "operations" / "stage6-bpf-jit-limit-canary.yaml").read_text()
)


def require(condition: bool, label: str) -> None:
    if not condition:
        raise SystemExit(f"STAGE6_BPF_CANARY_ERROR={label}")


require(PLAN["status"] == "REVIEW_REQUIRED_NOT_EXECUTED", "status")
require(PLAN["diagnosis"]["config_bpf_jit_always_on"] is True, "always_on")
require(PLAN["diagnosis"]["bpf_jit_enabled"] is True, "jit_enabled")
require(PLAN["canary"]["persistence"] == "NONE", "persistence")
require(PLAN["canary"]["proposed_bpf_jit_limit"] > PLAN["diagnosis"]["current_bpf_jit_limit"], "increase")
require(PLAN["canary"]["proposed_bpf_jit_limit"] < PLAN["diagnosis"]["x86_64_modules_len"], "modules_ceiling")
require(PLAN["rollback"]["command"].endswith(str(PLAN["diagnosis"]["current_bpf_jit_limit"])), "rollback")
require(len(PLAN["canary"]["probes"]) == 2, "probes")
require(PLAN["authorization"]["source_pr_merge_authorizes_execution"] is False, "merge_auth")
require(PLAN["authorization"]["execution_authorized"] is False, "execution_auth")
require(PLAN["risk"]["accepted"] is False, "risk_acceptance")
require(PLAN["risk"]["unprivileged_bpf_disabled"] == 2, "unprivileged_bpf")
for label, allowed in PLAN["prohibitions"].items():
    require(allowed is False, label)
require(PLAN["runtime_mutation"] is False, "runtime")
require(PLAN["production_changed"] is False, "production")

print("STAGE6_BPF_JIT_LIMIT_CANARY=PASS")
print("EXECUTION_AUTHORIZED=NO")
print("PERSISTENT_SYSCTL_CHANGE=NO")
print("CONTAINER_RESTART=NO")
print("PRODUCTION_CHANGED=NO")
