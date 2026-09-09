#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "operations/kong-runtime/runner-contract.v1.json"
INSTALLER_PATH = ROOT / "scripts/install_kong_actions_runner.sh"
CONTROLLER_PATH = ROOT / "scripts/configure_kong_runtime_runner.sh"

EXPECTED_VERSION = "2.337.0"
EXPECTED_SHA256 = "70920811a4f8ad4328818682bca5c6469c1c942fab52448868071d0063816613"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"KONG_RUNTIME_RUNNER_CONTRACT=FAIL:{message}")


def main() -> int:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    installer = INSTALLER_PATH.read_text(encoding="utf-8")
    controller = CONTROLLER_PATH.read_text(encoding="utf-8")

    require(contract["schema"] == "codestra.kong-runtime-runner-contract.v1", "schema")
    require(contract["repository"] == "appolon1908-hue/Kong", "repository")

    target = contract["target"]
    require(target["environment"] == "staging", "environment")
    require(target["runner_name"] == "codestra-kong-staging-01", "runner_name")
    require(
        target["required_labels"] == ["self-hosted", "linux", "kong-runtime"],
        "labels",
    )
    require(target["workflow"] == ".github/workflows/release.yml", "workflow")
    require(target["workflow_name"] == "Generate immutable Kong release evidence", "workflow_name")
    require(target["job_name"] == "runtime-topology", "job_name")

    app = contract["runner_application"]
    require(app["version"] == EXPECTED_VERSION, "runner_version")
    require(app["sha256"] == EXPECTED_SHA256, "runner_sha256")
    require(EXPECTED_VERSION in installer, "installer_version")
    require(EXPECTED_SHA256 in installer, "installer_sha")
    require("--ephemeral" in installer, "installer_ephemeral")
    require("--disableupdate" in installer, "installer_disableupdate")
    require("--registration-token-stdin" in installer, "installer_token_stdin")

    for source, label in ((installer, "installer"), (controller, "controller")):
        require("set -Eeuo pipefail" in source, f"{label}_strict_shell")
        require("set -x" not in source, f"{label}_xtrace")
        require("eval " not in source, f"{label}_eval")
        require("curl -k" not in source and "--insecure" not in source, f"{label}_tls")
        require("RUNNER_ALLOW_RUNASROOT=1" not in source, f"{label}_root_runner")
        require("usermod -aG docker" not in source, f"{label}_docker_group")
        require("NOPASSWD: /usr/bin/docker" not in source, f"{label}_docker_sudo")

    for token in (
        "codestra-caddy-upstream-gateway",
        "codestra-kong-kong-gateway-1",
        "codestra-middleware-integration-api-1",
        "codestra-redis-1",
        "docker_authorization_missing",
        "RUNTIME_MUTATION=NONE",
    ):
        require(token in installer, f"installer_runtime_token:{token}")

    for token in (
        "StrictHostKeyChecking=yes",
        "UserKnownHostsFile=",
        "BatchMode=yes",
        "repository_administration_required",
        "branches/staging",
        "staging_not_protected",
        "Generate immutable Kong release evidence",
        ".github/workflows/release.yml",
        "runtime-topology",
        "runtime_job_not_waiting_for_exact_runner",
        "actions/runners/registration-token",
        "stale_runner_not_safe_to_replace",
        "exact_runner_assignment_timeout",
        '"certification_claimed": False',
        '"runtime_changed_by_bootstrap": False',
    ):
        require(token in controller, f"controller_token:{token}")

    require(
        controller.index("runtime_job_not_waiting_for_exact_runner")
        < controller.index("actions/runners/registration-token"),
        "job_identity_before_token",
    )
    require(
        controller.index("runtime_job_not_waiting_for_exact_runner")
        < controller.index("REMOTE_INSTALLER"),
        "job_identity_before_remote_install",
    )
    require("gh variable set" not in controller, "no_release_variable_write")
    require("gh secret set" not in controller, "no_secret_write")

    security = contract["security_invariants"]
    for key in (
        "runner_repository_scoped",
        "runner_ephemeral",
        "runner_accepts_one_job",
        "runner_update_disabled",
        "registration_token_stdin_only",
        "queued_job_identity_verified_before_registration",
        "docker_authorization_must_preexist",
    ):
        require(security[key] is True, f"security_{key}")
    for key in (
        "registration_token_persisted",
        "registration_token_logged",
        "docker_authorization_created_by_bootstrap",
        "runtime_container_mutation_allowed",
        "runtime_network_mutation_allowed",
        "kong_admin_mutation_allowed",
        "production_traffic_authorized",
        "external_effects_authorized",
        "workflow_gate_weakening_allowed",
    ):
        require(security[key] is False, f"security_{key}")

    completion = contract["completion"]
    require(completion["runner_bootstrap_is_certification"] is False, "no_false_certification")
    require(completion["runtime_topology_job_must_succeed"] is True, "runtime_gate")
    require(completion["issues_close_only_after_required_runtime_evidence"] == [58, 52, 49], "issues")

    print("KONG_RUNTIME_RUNNER_CONTRACT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
