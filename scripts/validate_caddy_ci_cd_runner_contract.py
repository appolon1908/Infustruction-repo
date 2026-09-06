#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "operations/caddy-ci-cd/runner-contract.v1.json"
INSTALLER_PATH = ROOT / "scripts/install_caddy_actions_runner.sh"
CONTROLLER_PATH = ROOT / "scripts/configure_caddy_ci_cd_runner.sh"
WORKFLOW_PATH = ROOT / ".github/workflows/caddy-ci-cd-runner-bootstrap.yml"

EXPECTED_RUNNER_SHA256 = "70920811a4f8ad4328818682bca5c6469c1c942fab52448868071d0063816613"
EXPECTED_VERSION = "2.337.0"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"CADDY_CI_CD_RUNNER_CONTRACT=FAIL:{message}")


def main() -> int:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    installer = INSTALLER_PATH.read_text(encoding="utf-8")
    controller = CONTROLLER_PATH.read_text(encoding="utf-8")
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    require(contract["schema"] == "codestra.caddy-ci-cd-runner-contract.v1", "schema")
    require(contract["repository"] == "appolon1908-hue/Caddy", "repository")
    require(contract["bootstrap"]["admin_secret"] == "CODESTRA_REPOSITORY_ADMIN_TOKEN", "admin_secret")
    require(
        contract["bootstrap"]["governance_effect"]
        == "verify-canonical-ruleset-readback-no-mutation",
        "governance_effect",
    )

    application = contract["runner_application"]
    require(application["version"] == EXPECTED_VERSION, "runner_version")
    require(application["sha256"] == EXPECTED_RUNNER_SHA256, "runner_sha256")
    require(
        application["download_url"].startswith(
            "https://github.com/actions/runner/releases/"
        ),
        "runner_url",
    )

    expected_targets = {
        "staging": (
            "codestra-staging",
            "staging-readonly",
            "codestra-caddy-staging-01",
        ),
        "production-readonly-canary": (
            "codestra-production-canary",
            "production-readonly-canary",
            "codestra-caddy-production-canary-01",
        ),
    }
    require(set(contract["targets"]) == set(expected_targets), "targets")
    for target, (label, environment, name) in expected_targets.items():
        value = contract["targets"][target]
        require(value["custom_label"] == label, f"{target}_label")
        require(value["environment"] == environment, f"{target}_environment")
        require(value["runner_name"] == name, f"{target}_name")
        require(
            value["required_labels"] == ["self-hosted", label],
            f"{target}_labels",
        )

    security = contract["security_invariants"]
    for key in (
        "registration_token_persisted",
        "registration_token_logged",
        "docker_authorization_created_by_bootstrap",
        "live_runtime_mutation_allowed",
        "canonical_ruleset_mutated_by_bootstrap",
        "unrelated_rulesets_changed_by_bootstrap",
    ):
        require(security[key] is False, f"security_{key}")
    for key in (
        "runner_ephemeral",
        "runner_accepts_one_job",
        "runner_repository_scoped",
        "strict_ssh_host_key_checking",
        "docker_authorization_must_preexist",
        "production_job_depends_on_staging_evidence",
        "queued_job_identity_verified_before_registration",
    ):
        require(security[key] is True, f"security_{key}")

    for source, label in ((installer, "installer"), (controller, "controller")):
        require("set -Eeuo pipefail" in source, f"{label}_strict_shell")
        require("set -x" not in source, f"{label}_xtrace")
        require("eval " not in source, f"{label}_eval")
        require(
            "curl -k" not in source and "--insecure" not in source,
            f"{label}_insecure_tls",
        )

    require("--ephemeral" in installer, "installer_ephemeral")
    require("--disableupdate" in installer, "installer_update_lock")
    require("--registration-token-stdin" in installer, "installer_token_stdin")
    require(EXPECTED_RUNNER_SHA256 in installer, "installer_runner_digest")
    require("docker_authorization_missing" in installer, "installer_docker_fail_closed")
    require("RUNNER_ALLOW_RUNASROOT=1" not in installer, "installer_root_runner")
    require("usermod -aG docker" not in installer, "installer_docker_group")
    require("NOPASSWD: /usr/bin/docker" not in installer, "installer_docker_sudo")

    for token in (
        "StrictHostKeyChecking=yes",
        "UserKnownHostsFile=",
        "actions/runners/registration-token",
        "printf '%s\\n' \"$registration_token\" | ssh",
        "gh variable set",
        "environment_variable_readback",
        "environment_branch_policy_readback",
        "deployment_branch_policy",
        "actions/runners/$runner_id",
        "runner_busy",
        "bounded-runtime-certification.yml",
        "bounded_job_not_waiting_for_exact_runner",
        "bounded_job_not_assigned_to_exact_runner",
        "bounded_job_assigned_to_different_runner",
        "protected-branches-ruleset.json",
        "Protect Caddy promotion branches",
        "required_approving_review_count",
        "dismiss_stale_reviews_on_push",
        "require_last_push_approval",
        "required_review_thread_resolution",
        "allowed_merge_methods",
        "required_linear_history",
        "CADDY_CANONICAL_RULESET_READBACK=PASS",
        "CADDY_CANONICAL_RULESET_MUTATION_FORBIDDEN=PASS",
        '"canonical_ruleset_mutated": False',
        '"unrelated_rulesets_changed": False',
        '"runtime_changed_by_bootstrap": False',
    ):
        require(token in controller, f"controller_token:{token}")

    require(
        controller.index("bounded_job_not_waiting_for_exact_runner")
        < controller.index("install-codestra-caddy-actions-runner"),
        "controller_no_remote_install_before_job_validation",
    )
    require("runner_registered_speculatively" not in controller, "controller_no_bad_flag")
    require("AI automated production gates" not in controller, "controller_no_legacy_policy_name")
    require("Protect main" not in controller, "controller_no_legacy_main_policy_name")
    require("rulesets/$canonical_id\" --input" not in controller, "controller_no_ruleset_update")
    require("canonical_ruleset_applied" not in controller, "controller_no_ruleset_apply_claim")
    require("legacy_rulesets_retired" not in controller, "controller_no_ruleset_retirement_claim")

    permissions = contract["bootstrap"]["admin_token_repository_permissions"]
    require(
        permissions
        == {
            "Actions": "read",
            "Administration": "read-and-write",
            "Environments": "read-and-write",
        },
        "admin_token_permissions",
    )

    for token in (
        "name: Caddy CI/CD runner bootstrap",
        "workflow_dispatch:",
        "caddy-staging-runner-bootstrap",
        "caddy-production-canary-runner-bootstrap",
        "CODESTRA_REPOSITORY_ADMIN_TOKEN",
        "CADDY_RUNNER_SSH_PRIVATE_KEY",
        "CADDY_RUNNER_KNOWN_HOSTS",
        "bounded_runtime_run_id:",
        "scripts/validate_caddy_ci_cd_runner_contract.py",
        "scripts/configure_caddy_ci_cd_runner.sh",
        "if-no-files-found: error",
    ):
        require(token in workflow, f"workflow_token:{token}")
    require("CODESTRA_GITHUB_ADMIN_TOKEN" not in workflow, "workflow_old_admin_secret")
    require("pull_request_target" not in workflow, "workflow_pull_request_target")
    require("permissions:\n  contents: read" in workflow, "workflow_permissions")
    require(
        re.search(r"runs-on:\s+ubuntu-24\.04", workflow) is not None,
        "workflow_runner",
    )

    print("CADDY_CI_CD_RUNNER_CONTRACT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
