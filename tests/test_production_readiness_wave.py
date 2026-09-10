"""Regression coverage for the umbrella production-certification contract."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ProductionReadinessWaveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT / "CODESTRA_PRODUCTION_READINESS_WAVE_20260901.md").read_text()

    def test_platform_authority_is_in_core_denominator_once(self):
        core = self.text.split("## Core repositories in this wave\n", 1)[1].split("\n## ", 1)[0]
        self.assertEqual(re.findall(r"^- codestra-production-platform$", core, re.M), ["- codestra-production-platform"])
        self.assertIn("appolon1908-hue", core)

    def test_invariant_names_real_effect_controls_not_aliases(self):
        safety = self.text.split("## Global safety invariants\n", 1)[1].split("\n## ", 1)[0]
        names = set(re.findall(r"\b[A-Z][A-Z0-9_]+\b", safety))
        required = {"LIVE_EMAIL_DELIVERY", "LIVE_SMS_DELIVERY", "LIVE_PSTN_DIALING", "PRODUCTION_DIALING", "CALLBACK_DISPATCH", "ODOO_WRITE", "LIVE_WRITE", "N8N_EXTERNAL_EFFECTS", "SOCIAL_PUBLISHING_ENABLED", "LIVE_ADVERTISING_ENABLED", "EXTERNAL_DELIVERY_ENABLED", "EXTERNAL_MODEL_CALLS_ENABLED"}
        self.assertTrue(required <= names, required - names)
        self.assertFalse({"SOCIAL_PUBLISHING", "LIVE_ADVERTISING"} & names)
        self.assertIn("disabled until separately certified", safety)

    def test_scope_and_no_go_are_preserved(self):
        self.assertIn("Status: ACTIVE / NOT PRODUCTION CERTIFIED", self.text)
        self.assertIn("OUT_OF_SCOPE_ACTIVE_PRODUCTION_DO_NOT_TOUCH", self.text)
        self.assertIn("Never bypass branch protection", self.text)
        self.assertIn("PRODUCTION_READ_ONLY_CANARY=PASS", self.text)
        self.assertIn("only when every production-critical gate is PASS or explicitly justified N/A", self.text)


if __name__ == "__main__":
    unittest.main()
