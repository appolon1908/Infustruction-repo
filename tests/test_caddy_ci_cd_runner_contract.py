from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CaddyCICDRunnerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(
            (ROOT / "operations/caddy-ci-cd/runner-contract.v1.json").read_text(
                encoding="utf-8"
            )
        )
        cls.installer = (
            ROOT / "scripts/install_caddy_actions_runner.sh"
        ).read_text(encoding="utf-8")
        cls.controller = (
            ROOT / "scripts/configure_caddy_ci_cd_runner.sh"
        ).read_text(encoding="utf-8")
        cls.workflow = (
            ROOT / ".github/workflows/caddy-ci-cd-runner-bootstrap.yml"
        ).read_text(encoding="utf-8")

    def test_runner_binary_is_exactly_pinned(self) -> None:
        application = self.contract["runner_application"]
        self.assertEqual(application["version"], "2.337.0")
        self.assertEqual(
            application["sha256"],
            "70920811a4f8ad4328818682bca5c6469c1c942fab52448868071d0063816613",
        )
        self.assertIn(application["sha256"], self.installer)
        self.assertIn("--disableupdate", self.installer)

    def test_staging_and_production_are_separate_one_job_runners(self) -> None:
        targets = self.contract["targets"]
        self.assertEqual(
            targets["staging"]["required_labels"],
            ["self-hosted", "codestra-staging"],
        )
        self.assertEqual(
            targets["production-readonly-canary"]["required_labels"],
            ["self-hosted", "codestra-production-canary"],
        )
        self.assertNotEqual(
            targets["staging"]["runner_name"],
            targets["production-readonly-canary"]["runner_name"],
        )
        self.assertIn("--ephemeral", self.installer)

    def test_bootstrap_does_not_grant_docker_or_root_runner_access(self) -> None:
        self.assertIn("docker_authorization_missing", self.installer)
        self.assertNotIn("usermod -aG docker", self.installer)
        self.assertNotIn("RUNNER_ALLOW_RUNASROOT=1", self.installer)
        self.assertNotIn("NOPASSWD: /usr/bin/docker", self.installer)

    def test_registration_token_is_short_lived_and_stdin_only(self) -> None:
        self.assertIn("actions/runners/registration-token", self.controller)
        self.assertIn("--registration-token-stdin", self.installer)
        self.assertIn(
            'printf \'%s\\n\' "$registration_token" | ssh',
            self.controller,
        )
        self.assertNotIn("registration-token.txt", self.controller)
        self.assertNotIn("set -x", self.controller)

    def test_ssh_is_fail_closed(self) -> None:
        self.assertIn("StrictHostKeyChecking=yes", self.controller)
        self.assertIn("UserKnownHostsFile=", self.controller)
        self.assertIn("BatchMode=yes", self.controller)
        self.assertNotIn("StrictHostKeyChecking=no", self.controller)

    def test_runner_is_bound_to_exact_queued_job_before_registration(self) -> None:
        self.assertIn("--bounded-runtime-run-id", self.controller)
        self.assertIn(
            '.path == ".github/workflows/bounded-runtime-certification.yml"',
            self.controller,
        )
        self.assertIn('.head_branch == "production"', self.controller)
        self.assertIn('.status == "queued"', self.controller)
        self.assertIn("bounded_job_not_waiting_for_exact_runner", self.controller)
        self.assertIn("bounded_job_not_assigned_to_exact_runner", self.controller)
        self.assertIn("bounded_job_assigned_to_different_runner", self.controller)
        self.assertLess(
            self.controller.index("bounded_job_not_waiting_for_exact_runner"),
            self.controller.index("actions/runners/registration-token"),
        )
        self.assertLess(
            self.controller.index("bounded_job_not_waiting_for_exact_runner"),
            self.controller.index("install-codestra-caddy-actions-runner"),
        )
        self.assertIn("bounded_runtime_run_id:", self.workflow)
        self.assertTrue(
            self.contract["security_invariants"][
                "queued_job_identity_verified_before_registration"
            ]
        )
        self.assertFalse(
            self.contract["security_invariants"]["runner_registered_speculatively"]
        )

    def test_environment_writes_are_read_back_before_host_install(self) -> None:
        self.assertIn("environment_branch_policy_readback", self.controller)
        self.assertIn("environment_variable_readback", self.controller)
        self.assertLess(
            self.controller.index("environment_variable_readback"),
            self.controller.index("install-codestra-caddy-actions-runner"),
        )

    def test_staging_runner_receives_only_the_secret_file_path(self) -> None:
        token = "CADDY_STAGING_N8N_CLIENT_SECRET_FILE"
        self.assertIn(token, self.workflow)
        self.assertIn(
            "/etc/codestra/caddy/secrets/n8n-automation-client-secret",
            self.workflow,
        )
        self.assertIn(
            f'--environment-variable "{token}=${token}"',
            self.workflow,
        )
        self.assertNotIn("N8N_CLIENT_SECRET:", self.workflow)
        self.assertNotIn("client_secret=", self.workflow)

    def test_governance_is_verified_but_never_mutated(self) -> None:
        self.assertLess(
            self.controller.index("protected-branches-ruleset.json"),
            self.controller.index("actions/runners/registration-token"),
        )
        for token in (
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
        ):
            self.assertIn(token, self.controller)
        self.assertNotIn("AI automated production gates", self.controller)
        self.assertNotIn("Protect main", self.controller)
        self.assertNotIn("canonical_ruleset_applied", self.controller)
        self.assertNotIn("legacy_rulesets_retired", self.controller)
        self.assertEqual(
            self.contract["bootstrap"]["governance_effect"],
            "verify-canonical-ruleset-readback-no-mutation",
        )
        self.assertFalse(
            self.contract["security_invariants"][
                "canonical_ruleset_mutated_by_bootstrap"
            ]
        )
        self.assertFalse(
            self.contract["security_invariants"][
                "unrelated_rulesets_changed_by_bootstrap"
            ]
        )

    def test_workflow_has_protected_separate_environments(self) -> None:
        self.assertIn("environment: caddy-staging-runner-bootstrap", self.workflow)
        self.assertIn(
            "environment: caddy-production-canary-runner-bootstrap",
            self.workflow,
        )
        self.assertIn("BOOTSTRAP_CADDY_STAGING_RUNNER", self.workflow)
        self.assertIn(
            "BOOTSTRAP_CADDY_PRODUCTION_CANARY_RUNNER",
            self.workflow,
        )
        self.assertIn("CODESTRA_REPOSITORY_ADMIN_TOKEN", self.workflow)
        self.assertNotIn("CODESTRA_GITHUB_ADMIN_TOKEN", self.workflow)
        self.assertNotIn("pull_request_target", self.workflow)

    def test_production_canary_remains_read_only(self) -> None:
        security = self.contract["security_invariants"]
        self.assertEqual(security["production_methods"], ["GET", "HEAD"])
        self.assertFalse(security["production_candidate_start_allowed"])
        self.assertFalse(security["live_runtime_mutation_allowed"])
        self.assertTrue(security["production_job_depends_on_staging_evidence"])


if __name__ == "__main__":
    unittest.main()
