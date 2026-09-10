import copy
from pathlib import Path
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_FILE = ROOT / ".github/workflows/reusable-codestra-upstream-deploy-readiness.yml"
text = WORKFLOW_FILE.read_text()
embedded = text.split("# BEGIN CODESTRA_REUSABLE_SIGNING_IDENTITY\n", 1)[1].split("# END CODESTRA_REUSABLE_SIGNING_IDENTITY", 1)[0]
namespace = {"__name__": "signing_identity_test"}
exec(compile(textwrap.dedent(embedded), str(WORKFLOW_FILE), "exec"), namespace)
resolve = namespace["resolve_signing_identity"]
AUTHORITY = namespace["WORKFLOW"]
SHA = "d914fd53a72ffeb57a63ca39ac761abc285e33bf"
PIN = "f509d61a6207c7cd9e5f2562de0c2b32a85b6cca"
REPO = "appolon1908-hue/Codestra-Loki"
RUN = 34478920792


class SigningIdentityTest(unittest.TestCase):
    def setUp(self):
        self.metadata = {
            "id": RUN, "head_sha": SHA, "repository": {"full_name": REPO},
            "referenced_workflows": [{"path": AUTHORITY + "@" + PIN, "sha": PIN}],
        }

    def resolve(self):
        return resolve(self.metadata, REPO, SHA, RUN)

    def test_exact_reusable_identity_from_github_run_evidence(self):
        self.assertEqual(self.resolve(), "https://github.com/" + AUTHORITY + "@" + PIN)

    def test_rejects_other_repository_source_or_run(self):
        for key, value in [
            ("repository", {"full_name": "untrusted/project"}),
            ("head_sha", "a" * 40), ("id", RUN + 1),
        ]:
            with self.subTest(key=key):
                other = copy.deepcopy(self.metadata)
                other[key] = value
                with self.assertRaises(ValueError):
                    resolve(other, REPO, SHA, RUN)

    def test_rejects_missing_workflow_evidence(self):
        self.metadata.pop("referenced_workflows")
        with self.assertRaises(ValueError):
            self.resolve()

    def test_rejects_mutable_reference(self):
        self.metadata["referenced_workflows"][0]["path"] = AUTHORITY + "@refs/heads/main"
        with self.assertRaises(ValueError):
            self.resolve()

    def test_rejects_resolved_sha_disagreement(self):
        self.metadata["referenced_workflows"][0]["sha"] = "b" * 40
        with self.assertRaises(ValueError):
            self.resolve()

    def test_rejects_missing_resolved_sha(self):
        self.metadata["referenced_workflows"][0].pop("sha")
        with self.assertRaises(ValueError):
            self.resolve()

    def test_rejects_other_workflow_or_lookalike_repository(self):
        for authority in [AUTHORITY.replace("Infustruction-repo", "Infustruction-repo-untrusted"),
                          AUTHORITY.replace("upstream-deploy-readiness", "other")]:
            self.metadata["referenced_workflows"][0]["path"] = authority + "@" + PIN
            with self.assertRaises(ValueError):
                self.resolve()

    def test_rejects_ambiguous_workflow_evidence(self):
        self.metadata["referenced_workflows"].append(copy.deepcopy(self.metadata["referenced_workflows"][0]))
        with self.assertRaises(ValueError):
            self.resolve()

    def test_rejects_abbreviated_source_sha(self):
        with self.assertRaises(ValueError):
            resolve(self.metadata, REPO, SHA[:12], RUN)

    def test_workflow_uses_exact_identity_and_fixed_oidc_issuer(self):
        self.assertIn('--certificate-identity "$SOURCE_SIGNING_IDENTITY"', text)
        self.assertNotIn("--certificate-identity-regexp", text)
        self.assertIn('--certificate-oidc-issuer "https://token.actions.githubusercontent.com"', text)
        self.assertIn('"signing_workflow_identity": os.environ["SOURCE_SIGNING_IDENTITY"]', text)


if __name__ == "__main__":
    unittest.main()
