#!/usr/bin/env python3
"""Static policy for the exact reviewed-plan apply workflow."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
workflow = (ROOT / ".github/workflows/stage6-apply-reviewed-plan.yml").read_text(encoding="utf-8")


def require(condition: bool, label: str) -> None:
    if not condition:
        raise SystemExit(f"STAGE6_APPLY_REVIEWED_PLAN_ERROR={label}")


for input_name in (
    "mode:",
    "plan_run_id:",
    "plan_sha:",
    "plan_artifact_name:",
    "plan_artifact_digest:",
    "confirmation:",
):
    require(input_name in workflow, f"input_{input_name[:-1]}")

require("APPLY_REVIEWED_STAGE6_PLAN" in workflow, "mode")
require("APPLY_EXACT_REVIEWED_STAGE6_PLAN" in workflow, "confirmation")
require("contents: read" in workflow and "actions: read" in workflow, "read_permissions")
require(not re.search(r"(?m)^\s+[a-z-]+:\s+write\s*$", workflow), "write_permission")
require(workflow.count("environment: stage6-infrastructure-provisioning") == 2, "two_protected_stages")
require(
    workflow.count("github.ref == 'refs/heads/main' && github.ref_protected == true") == 2,
    "protected_main_only",
)
require("run-id: ${{ inputs.plan_run_id }}" in workflow, "cross_run_download")
require("github-token: ${{ github.token }}" in workflow, "artifact_read_token")
require(workflow.count("ref: ${{ github.sha }}") == 2, "protected_validator_checkout")
require(workflow.count("ref: ${{ inputs.plan_sha }}") == 2, "exact_plan_source_checkout")
require(workflow.count("path: plan-source") == 2, "separate_plan_source_checkout")
require("IAC_DIR: plan-source/infra/hetzner/stage6-staging" in workflow, "plan_source_iac")
require(workflow.count('test "$GITHUB_REF" = refs/heads/main') == 2, "runtime_main_assertion")
require(workflow.count('test "$GITHUB_REF_PROTECTED" = true') == 2, "runtime_protection_assertion")
require(workflow.count('test "$(git rev-parse HEAD)" = "$GITHUB_SHA"') == 2, "validator_sha")
require(
    workflow.count('test "$(git -C plan-source rev-parse HEAD)" = "$REVIEWED_PLAN_SHA"') == 2,
    "plan_source_sha",
)
require("git merge-base --is-ancestor" in workflow, "protected_main_ancestry")
require("sha256sum -c stage6-plan.SHA256SUMS" in workflow, "internal_checksums")
require("validate_stage6_artifact_authority.py" in workflow, "outer_digest")
require("validate_stage6_reviewed_plan.py" in workflow, "plan_policy")
require("validate_stage6_state_currency.py" in workflow, "state_currency")
require(not re.search(r"(?m)^\s*(?:tofu|terraform)(?:\s+-chdir=\S+)?\s+plan(?:\s|$)", workflow), "plan_regeneration")
require(workflow.count(" apply -input=false /tmp/stage6-reviewed-plan/stage6.tfplan") == 1, "saved_plan_apply_only")
require("-var-file" not in workflow and "-target" not in workflow and "-refresh-only" not in workflow, "apply_flags")
require("STAGE6_TFVARS_JSON" not in workflow, "tfvars_forbidden")
require("cancel-in-progress: false" in workflow, "no_cancellation")

print("STAGE6_APPLY_REVIEWED_PLAN_STATIC=PASS")
print("PLAN_REGENERATION=NO")
print("APPLY_SAVED_PLAN_ONLY=YES")
print("PROTECTED_MAIN_DISPATCH_ONLY=YES")
print("TRUSTED_VALIDATOR_SOURCE_SEPARATE=YES")
print("PRODUCTION_CHANGED=NO")
