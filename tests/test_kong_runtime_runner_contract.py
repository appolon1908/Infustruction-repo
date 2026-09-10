from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class KongRuntimeRunnerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(
            (ROOT / "operations/kong-runtime/runner-contract.v1.json").read_text(
                encoding="utf-8"
            )
        )
        cls.installer = (ROOT / "scripts/install_kong_actions_runner.sh").read_text(
            encoding="utf-8"
        )
        cls.controller = (ROOT / "scripts/configure_kong_runtime_runner.sh").read_text(
            encoding="utf-8"
        )
        cls.workflow = (
            ROOT / ".github/workflows/kong-runtime-runner-bootstrap.yml"
        ).read_text(encoding="utf-8")

    def test_exact_runner_binary_is_pinned(self) -> None:
        app = self.contract["runner_application"]
        self.assertEqual(app["version"], "2.337.0")
        self.assertEqual(
            app["sha256"],
            "70920811a4f8ad4328818682bca5c6469c1c942fab52448868071d0063816613",
        )
        self.assertIn(app["sha256"], self.installer)
        self.assertIn("--disableupdate", self.installer)
        self.assertIn("--ephemeral", self.installer)
        self.assertTrue(os.access(ROOT / "scripts/install_kong_actions_runner.sh", os.X_OK))

    def test_bootstrap_is_staging_only_and_job_bound(self) -> None:
        target = self.contract["target"]
        self.assertEqual(target["environment"], "staging")
        self.assertEqual(
            target["required_labels"], ["self-hosted", "linux", "kong-runtime"]
        )
        self.assertIn("branches/staging", self.controller)
        self.assertIn('head_branch == "staging"', self.controller)
        self.assertIn("runtime_job_not_waiting_for_exact_runner", self.controller)
        self.assertIn('(.status == "queued" or .status == "in_progress")', self.controller)
        self.assertLess(
            self.controller.index("runtime_job_not_waiting_for_exact_runner"),
            self.controller.index("actions/runners/registration-token"),
        )

    def test_bootstrap_never_grants_docker_or_root_runner_access(self) -> None:
        self.assertIn("docker_authorization_missing", self.installer)
        self.assertIn("runner_identity_missing", self.installer)
        self.assertNotIn("useradd", self.installer)
        self.assertNotIn("usermod -aG docker", self.installer)
        self.assertNotIn("RUNNER_ALLOW_RUNASROOT=1", self.installer)
        self.assertNotIn("NOPASSWD: /usr/bin/docker", self.installer)
        self.assertFalse(
            self.contract["security_invariants"][
                "docker_authorization_created_by_bootstrap"
            ]
        )

    def test_runtime_readback_matches_kong_release_gate(self) -> None:
        for container in self.contract["runtime_readback"]["containers"]:
            self.assertIn(container, self.installer)
        self.assertEqual(
            self.contract["runtime_readback"]["required_networks"],
            {
                "caddy_kong": "codestra_edge",
                "kong_middleware": "codestra_edge",
                "kong_redis": "codestra_backend",
                "middleware_redis": "codestra_backend",
            },
        )

    def test_registration_token_is_stdin_only_and_not_persisted(self) -> None:
        self.assertIn("--registration-token-stdin", self.installer)
        self.assertIn("actions/runners/registration-token", self.controller)
        self.assertNotIn("registration-token.txt", self.installer)
        self.assertNotIn("registration-token.txt", self.controller)
        self.assertFalse(
            self.contract["security_invariants"]["registration_token_persisted"]
        )

    def test_explicit_stale_replacement_reaches_unregistered_local_state(self) -> None:
        replacement = '"$REPLACE_STALE" && replace_arg=(--replace-stale-registration)'
        self.assertIn(replacement, self.controller)
        self.assertLess(
            self.controller.index(replacement),
            self.controller.index('if [[ -n "$runner_matches" ]]'),
        )

    def test_controller_is_fail_closed_ssh(self) -> None:
        for token in ("StrictHostKeyChecking=yes", "UserKnownHostsFile=", "BatchMode=yes"):
            self.assertIn(token, self.controller)
        self.assertNotIn("StrictHostKeyChecking=no", self.controller)

    def test_controller_does_not_fabricate_release_evidence(self) -> None:
        self.assertNotIn("gh variable set", self.controller)
        self.assertNotIn("gh secret set", self.controller)
        self.assertIn('"certification_claimed": False', self.controller)
        self.assertIn('"runtime_changed_by_bootstrap": False', self.controller)
        self.assertFalse(
            self.contract["completion"]["runner_bootstrap_is_certification"]
        )

    def test_protected_workflow_is_manual_exact_job_bootstrap(self) -> None:
        bootstrap = self.contract["bootstrap"]
        self.assertEqual(
            bootstrap["workflow"], ".github/workflows/kong-runtime-runner-bootstrap.yml"
        )
        self.assertEqual(
            bootstrap["environment"], "kong-staging-runtime-runner-bootstrap"
        )
        self.assertEqual(
            bootstrap["confirmation"], "BOOTSTRAP_KONG_STAGING_RUNTIME_RUNNER"
        )
        for token in (
            "workflow_dispatch:",
            "runtime_run_id:",
            "BOOTSTRAP_KONG_STAGING_RUNTIME_RUNNER",
            "environment: kong-staging-runtime-runner-bootstrap",
            "GITHUB_REF_PROTECTED",
            "scripts/configure_kong_runtime_runner.sh",
        ):
            self.assertIn(token, self.workflow)
        self.assertNotIn("pull_request_target", self.workflow)
        self.assertIn("permissions:\n  contents: read", self.workflow)

    def test_workflow_uses_dedicated_kong_bootstrap_inputs(self) -> None:
        for token in (
            "CODESTRA_REPOSITORY_ADMIN_TOKEN",
            "KONG_RUNTIME_RUNNER_SSH_PRIVATE_KEY",
            "KONG_RUNTIME_RUNNER_KNOWN_HOSTS",
            "KONG_RUNTIME_RUNNER_HOST",
            "KONG_RUNTIME_RUNNER_SSH_USER",
            "KONG_RUNTIME_RUNNER_SSH_PORT",
        ):
            self.assertIn(token, self.workflow)
        self.assertNotIn("secrets.CADDY_RUNNER_SSH_PRIVATE_KEY", self.workflow)
        self.assertNotIn("vars.CADDY_RUNNER_HOST", self.workflow)
        self.assertNotIn("gh variable set", self.workflow)
        self.assertNotIn("gh secret set", self.workflow)
        self.assertNotIn("KONG_IMAGE_DIGEST", self.workflow)

    def test_workflow_revalidates_contract_before_remote_bootstrap(self) -> None:
        contract_validation = "python3 scripts/validate_kong_runtime_runner_contract.py"
        remote_bootstrap = "bash scripts/configure_kong_runtime_runner.sh"
        self.assertIn(contract_validation, self.workflow)
        self.assertIn(remote_bootstrap, self.workflow)
        self.assertLess(
            self.workflow.index(contract_validation),
            self.workflow.index(remote_bootstrap),
        )
        self.assertIn("if-no-files-found: error", self.workflow)

    def test_issue_closure_remains_runtime_gated(self) -> None:
        self.assertEqual(
            self.contract["completion"]["issues_close_only_after_required_runtime_evidence"],
            [58, 52, 49],
        )
        self.assertTrue(
            self.contract["completion"]["runtime_topology_job_must_succeed"]
        )


if __name__ == "__main__":
    unittest.main()
