"""Exercise the embedded production resolvers and exact pinned-version delta."""
import copy
import hashlib
import json
from pathlib import Path
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
VERSIONED = "reusable-codestra-deploy-readiness-pinned-v1.yml"
UPSTREAM = "reusable-codestra-upstream-deploy-readiness.yml"


class CanonicalSigningIdentityTest(unittest.TestCase):
    def test_both_resolvers_accept_only_exact_canonical_immutable_evidence(self):
        for filename in (VERSIONED, UPSTREAM):
            with self.subTest(filename=filename):
                text = (ROOT / ".github/workflows" / filename).read_text()
                code = text.split("# BEGIN CODESTRA_REUSABLE_SIGNING_IDENTITY\n", 1)[1].split("# END CODESTRA_REUSABLE_SIGNING_IDENTITY", 1)[0]
                namespace = {"__name__": "resolver_test"}
                exec(compile(textwrap.dedent(code), filename, "exec"), namespace)
                authority = "appolon1908/Infustruction-repo/.github/workflows/" + filename
                self.assertEqual(namespace["WORKFLOW"], authority)
                resolve = namespace["resolve_signing_identity"]
                pin, source, repository, run = "a" * 40, "b" * 40, "appolon1908/example", 123
                metadata = {"id": run, "head_sha": source, "repository": {"full_name": repository}, "referenced_workflows": [{"path": authority + "@" + pin, "sha": pin}]}
                self.assertEqual(resolve(metadata, repository, source, run), "https://github.com/" + authority + "@" + pin)
                invalid = []
                for replacement in ("appolon1908-hue", "ingtrader21-spec", "appolon1908-attacker"):
                    wrong = copy.deepcopy(metadata)
                    wrong["referenced_workflows"][0]["path"] = authority.replace("appolon1908/", replacement + "/") + "@" + pin
                    invalid.append(wrong)
                for replacement in ("refs/heads/main", pin[:12], "A" * 40):
                    wrong = copy.deepcopy(metadata)
                    wrong["referenced_workflows"][0]["path"] = authority + "@" + replacement
                    invalid.append(wrong)
                for field, value in (("id", 124), ("head_sha", "c" * 40), ("repository", {"full_name": "other/repo"}), ("referenced_workflows", []), ("referenced_workflows", None)):
                    wrong = copy.deepcopy(metadata)
                    wrong[field] = value
                    invalid.append(wrong)
                wrong = copy.deepcopy(metadata)
                wrong["referenced_workflows"][0]["sha"] = "c" * 40
                invalid.append(wrong)
                wrong = copy.deepcopy(metadata)
                wrong["referenced_workflows"].append(copy.deepcopy(wrong["referenced_workflows"][0]))
                invalid.append(wrong)
                for wrong in invalid:
                    with self.assertRaises(ValueError):
                        resolve(wrong, repository, source, run)
                self.assertNotIn("--certificate-identity-regexp", text)
                self.assertIn('--certificate-identity "$SOURCE_SIGNING_IDENTITY"', text)
                self.assertIn('--certificate-oidc-issuer "https://token.actions.githubusercontent.com"', text)
                proof = 'test "$(gh api repos/appolon1908/Infustruction-repo --jq .id)" = "1350724865"'
                self.assertIn(proof, text)
                self.assertLess(text.index(proof), text.index('gh api "repos/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}"'))

    def test_versioned_workflow_reconstructs_exact_approved_consumer_blob(self):
        text = (ROOT / ".github/workflows" / VERSIONED).read_text()
        delta = json.loads((ROOT / "tests/fixtures/pinned_v1_signing_delta.json").read_text())
        start = text.index("      - name: Bind signature verification to the exact reusable workflow\n")
        end = text.index("      - name: Build once, scan, publish, sign, and attest\n", start)
        binding = text[start:end]
        self.assertEqual(hashlib.sha256(binding.encode()).hexdigest(), delta["binding_step_sha256"])
        self.assertEqual(text.count('--certificate-identity "$SOURCE_SIGNING_IDENTITY"'), 4)
        text = text[:start] + text[end:]
        text = text.replace("      packages: write\n      actions: read\n      id-token: write", "      packages: write\n      id-token: write")
        exact = '--certificate-identity "$SOURCE_SIGNING_IDENTITY"'
        text = text.replace(exact, '--certificate-identity-regexp "^(${caller_identity}|${called_identity_pattern#^})"', 3)
        text = text.replace(exact, '--certificate-identity-regexp "$identity_pattern"')
        caller, called, blob = delta["removed_lines"]
        text = text.replace('            "$RUNNER_TEMP/cosign" sign --yes "$subject"\n', '            "$RUNNER_TEMP/cosign" sign --yes "$subject"\n' + caller + called)
        text = text.replace('            "$RUNNER_TEMP/cosign" sign-blob --yes', blob + '            "$RUNNER_TEMP/cosign" sign-blob --yes')
        encoded = text.encode()
        actual = hashlib.sha1(b"blob " + str(len(encoded)).encode() + b"\0" + encoded).hexdigest()
        self.assertEqual(actual, "c4ed9cf0b68669ff12f88c7de35d5c954d04f736")


if __name__ == "__main__":
    unittest.main()
