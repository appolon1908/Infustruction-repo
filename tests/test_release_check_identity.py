"""Regression tests for PR 116: required checks must retain workflow identity."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("release_intent", ROOT / ".codestra/validate-release-intent.py")
policy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(policy)


class CheckIdentityTests(unittest.TestCase):
    def setUp(self):
        self.repo = "appolon1908-hue/Infustruction-repo"
        self.sha = "a" * 40
        self.name = "orchestrator-contract"
        self.check = {
            "id": 30, "name": self.name, "app": {"id": 15368}, "conclusion": "success",
            "details_url": f"https://github.com/{self.repo}/actions/runs/100/job/1000",
        }
        self.run = {
            "path": ".github/workflows/production-orchestrator-contract.yml",
            "head_sha": self.sha, "head_branch": "main", "event": "push",
        }
        self.job = {"id": 1000, "run_id": 100, "run_attempt": 1,
                    "name": self.name, "head_sha": self.sha}

    def conclusions(self, check=None, run=None, job=None):
        return policy.workflow_bound_check_conclusions(
            [{"check_runs": [self.check if check is None else check]}], self.repo,
            self.sha, [self.name], {self.name: 15368},
            {100: self.run if run is None else run},
            {1000: self.job if job is None else job}, "main",
        )

    def test_exact_workflow_run_job_and_source(self):
        self.assertEqual(self.conclusions(), {(self.name, 15368): "success"})

    def test_same_name_from_another_workflow_is_not_authoritative(self):
        self.assertEqual(self.conclusions(run={**self.run, "path": ".github/workflows/other.yml"}), {})

    def test_shared_actions_app_is_not_sufficient(self):
        for url in ("https://example.invalid/check", f"https://github.com/other/repo/actions/runs/100/job/1000"):
            with self.subTest(url=url):
                self.assertEqual(self.conclusions(check={**self.check, "details_url": url}), {})

    def test_another_app_is_not_authoritative(self):
        self.assertEqual(self.conclusions(check={**self.check, "app": {"id": 1}}), {})

    def test_stale_source_wrong_branch_and_wrong_event_fail(self):
        for key, value in (("head_sha", "b" * 40), ("head_branch", "other"), ("event", "pull_request")):
            with self.subTest(key=key), self.assertRaises(policy.PolicyError):
                self.conclusions(run={**self.run, key: value})

    def test_job_identity_mismatch_fails(self):
        for key, value in (("id", 1001), ("run_id", 101), ("name", "other"),
                           ("head_sha", "b" * 40), ("run_attempt", 0)):
            with self.subTest(key=key), self.assertRaises(policy.PolicyError):
                self.conclusions(job={**self.job, key: value})

    def test_incomplete_run_or_job_evidence_does_not_pass(self):
        for runs, jobs in (({}, {1000: self.job}), ({100: self.run}, {})):
            self.assertEqual(policy.workflow_bound_check_conclusions(
                [{"check_runs": [self.check]}], self.repo, self.sha, [self.name],
                {self.name: 15368}, runs, jobs, "main"), {})

    def test_pending_authoritative_check_stays_pending(self):
        self.assertEqual(self.conclusions(check={**self.check, "conclusion": None}),
                         {(self.name, 15368): None})


if __name__ == "__main__":
    unittest.main()
