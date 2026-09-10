"""Offline tests for independent review identity and complete source binding."""
import copy
import importlib.util
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("policy_review", ROOT / "scripts/validate_release_policy_review.py")
policy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(policy)


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.head = "a" * 40
        self.base = "b" * 40
        self.pr = {
            "number": 108, "state": "open", "draft": False, "user": {"id": 275410064},
            "base": {"ref": "main", "sha": self.base,
                     "repo": {"id": policy.REPOSITORY_ID, "full_name": policy.REPOSITORY}},
            "head": {"sha": self.head},
        }
        self.review = {
            "id": 12, "user": {"id": policy.REVIEWER_ID}, "state": "APPROVED",
            "commit_id": self.head, "author_association": "COLLABORATOR",
        }

    def test_exact_independent_approval(self):
        self.assertEqual(policy.validate_subject(self.pr, 108, self.base), self.head)
        self.assertEqual(policy.validate_review(self.pr, [self.review], self.head), 12)

    def test_missing_approval(self):
        with self.assertRaises(policy.ReviewError):
            policy.validate_review(self.pr, [], self.head)

    def test_stale_approval(self):
        self.review["commit_id"] = "c" * 40
        with self.assertRaises(policy.ReviewError):
            policy.validate_review(self.pr, [self.review], self.head)

    def test_substitute_reviewer(self):
        self.review["user"]["id"] += 1
        with self.assertRaises(policy.ReviewError):
            policy.validate_review(self.pr, [self.review], self.head)

    def test_self_review(self):
        self.pr["user"]["id"] = policy.REVIEWER_ID
        with self.assertRaises(policy.ReviewError):
            policy.validate_review(self.pr, [self.review], self.head)

    def test_reviewer_must_be_collaborator(self):
        self.review["author_association"] = "NONE"
        with self.assertRaises(policy.ReviewError):
            policy.validate_review(self.pr, [self.review], self.head)

    def test_withdrawn_or_changes_requested(self):
        for state in ("DISMISSED", "CHANGES_REQUESTED"):
            later = {**self.review, "id": 13, "state": state}
            with self.subTest(state=state), self.assertRaises(policy.ReviewError):
                policy.validate_review(self.pr, [later, self.review], self.head)

    def test_comment_does_not_replace_approval(self):
        comment = {**self.review, "id": 13, "state": "COMMENTED"}
        self.assertEqual(policy.validate_review(self.pr, [self.review, comment], self.head), 12)

    def test_duplicate_review_identity(self):
        with self.assertRaises(policy.ReviewError):
            policy.validate_review(self.pr, [self.review, self.review], self.head)

    def test_unknown_review_state(self):
        self.review["state"] = "UNKNOWN"
        with self.assertRaises(policy.ReviewError):
            policy.validate_review(self.pr, [self.review], self.head)

    def test_repository_and_branch_binding(self):
        for field, value in (("sha", "c" * 40), ("ref", "other"), ("repo", {"id": 1, "full_name": policy.REPOSITORY})):
            changed = copy.deepcopy(self.pr)
            changed["base"][field] = value
            with self.subTest(field=field), self.assertRaises(policy.ReviewError):
                policy.validate_subject(changed, 108, self.base)

    def test_closed_draft_and_wrong_pr(self):
        for field, value in (("state", "closed"), ("draft", True), ("number", 109)):
            with self.subTest(field=field), self.assertRaises(policy.ReviewError):
                policy.validate_subject({**self.pr, field: value}, 108, self.base)

    def test_invalid_candidate_sha(self):
        self.pr["head"]["sha"] = "main"
        with self.assertRaises(policy.ReviewError):
            policy.validate_subject(self.pr, 108, self.base)


class SourceTests(unittest.TestCase):
    def test_closure_values_and_test_inputs_remain_bound_without_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            def git(*args):
                return subprocess.check_output(["git", "-C", directory, *args], stderr=subprocess.DEVNULL).decode().strip()
            git("init", "-q")
            git("config", "user.name", "Policy test")
            git("config", "user.email", "policy-test@example.invalid")
            source = root / "validator.py"
            source.write_text("raise RuntimeError('candidate must never execute')\nclosure = 'original'\n")
            git("add", ".")
            git("commit", "-qm", "fixture")
            first = git("rev-parse", "HEAD")
            initial = policy.source_fingerprint(root, first)
            source.write_text(source.read_text().replace("'original'", "'changed'"))
            git("add", ".")
            git("commit", "-qm", "change closure value")
            second = git("rev-parse", "HEAD")
            changed = policy.source_fingerprint(root, second)
            self.assertNotEqual(initial, changed)
            with self.assertRaises(policy.ReviewError):
                policy.source_fingerprint(root, first)
            (root / "test-input.json").write_text('{"expected": "different"}\n')
            git("add", ".")
            git("commit", "-qm", "change test input")
            self.assertNotEqual(changed, policy.source_fingerprint(root, git("rev-parse", "HEAD")))


if __name__ == "__main__":
    unittest.main()
