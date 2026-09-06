"""Regression coverage for PR 30's historical evidence and retry boundaries."""

from hashlib import sha1
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports/runtime-reconciliation"
README = REPORTS / "pr-30-runtime-certification-20260831/README.md"
HISTORY = "## Historical report (superseded; retained verbatim)\n\n"
ORIGINAL_BLOBS = {
    "STAGE6-RUNTIME-RECONCILIATION-DECISION.md": "e1bf8e0bc959d138b7213036c40c120356ff522c",
    "STAGE6-SOURCE-LOCK-REMEDIATION-EVIDENCE.md": "6e0f0fa746b91637d13201780089fdd664b1f351",
}


class HistoricalEvidenceAuthorityTests(unittest.TestCase):
    def test_prior_pass_reports_are_explicitly_superseded(self):
        for filename in ORIGINAL_BLOBS:
            with self.subTest(filename=filename):
                text = (REPORTS / filename).read_text(encoding="utf-8")
                notice, separator, _ = text.partition(HISTORY)
                self.assertTrue(separator, "Missing historical boundary")
                self.assertIn("Status: **SUPERSEDED_DO_NOT_EXECUTE**", notice)
                self.assertIn("backup-preparation authorization are superseded", notice)
                self.assertIn("No backup or runtime action", notice)
                self.assertIn("../../STAGE6-SOURCE-LOCK.yaml", notice)
                self.assertIn("../../STAGE6-STAGING-CERTIFICATION.md", notice)
                self.assertIn("OUT_OF_SCOPE_ACTIVE_PRODUCTION_DO_NOT_TOUCH", notice)
                self.assertIn("#retry-prerequisites-not-execution-authorization", notice)

    def test_original_report_bodies_remain_byte_identical(self):
        for filename, expected in ORIGINAL_BLOBS.items():
            with self.subTest(filename=filename):
                data = (REPORTS / filename).read_bytes()
                title = data.split(b"\n\n", 1)[0]
                _, separator, historical = data.partition(HISTORY.encode())
                self.assertTrue(separator, "Missing historical boundary")
                original = title + b"\n\n" + historical
                digest = sha1(b"blob " + str(len(original)).encode() + b"\0" + original)
                self.assertEqual(digest.hexdigest(), expected)

    def test_retry_requires_complete_immutable_artifact_resolution(self):
        text = README.read_text(encoding="utf-8")
        retry = text.split("## Retry prerequisites (not execution authorization)\n", 1)[1]
        for requirement in (
            "Resolve the immutable artifact lock", "five missing application digests",
            "four\n   unresolved infrastructure runtime images", "Kong, Keycloak, OpenBao, shared observability stack",
            "reviewed immutable image digest", "vendor/config provenance",
            "compatible rollback identity", "Never invent digests",
            "any narrower scope requires its own explicit approval",
        ):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, retry)

    def test_retry_retains_access_safety_and_separate_authorization_gates(self):
        text = README.read_text(encoding="utf-8")
        retry = text.split("## Retry prerequisites (not execution authorization)\n", 1)[1]
        for requirement in (
            "approved read-only core-server access", "fresh runtime read-back",
            "negative probes", "Missing safety evidence remains a failure",
            "OUT_OF_SCOPE_ACTIVE_PRODUCTION_DO_NOT_TOUCH",
            "separate reviewed operation", "NEXT_ALLOWED_STAGE=STOP",
            "runtime_mutation_authorized=false", "production_write_activation=false",
            "Merging this PR does not authorize", "Preserve separate verified backup evidence",
        ):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, retry)

    def test_readme_preserves_historical_and_canonical_authority_distinction(self):
        text = README.read_text(encoding="utf-8")
        for requirement in (
            "HISTORICAL_EVIDENCE_ONLY_DO_NOT_DEPLOY", "SUPERSEDED_DO_NOT_EXECUTE",
            "STAGE6_PREFLIGHT=FAIL_SCOPED_RUNTIME_READBACK",
            "STAGE6_PATH_BUSINESS_WRITES=NOT_PROVEN_DISABLED",
            "repository evidence\nvalues, not a fresh runtime read-back",
            "STAGE6-RUNTIME-RECONCILIATION-DECISION.md",
            "STAGE6-SOURCE-LOCK-REMEDIATION-EVIDENCE.md",
        ):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, text)


if __name__ == "__main__":
    unittest.main()
