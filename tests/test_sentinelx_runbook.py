"""Offline regressions for the blocked SentinelX installation runbook."""
import hashlib
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "hosts/65.21.67.207/sentinelx"


class SentinelXRunbookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (HOST / "README.md").read_text(encoding="utf-8")
        cls.blocks = re.findall(r"```bash\n(.*?)```", cls.text, re.S)

    def test_installation_stays_blocked_until_immutable_bundle_review(self):
        for required in (
            "INSTALLATION_AUTHORIZED=false", "Do not execute the historical installer",
            "Immutable offline bundle gate", "independently approved, authenticated bundle manifest",
            "all transitive Python and", "--no-index", "--find-links", "--require-hashes",
            "--no-deps", "Recheck the authenticated manifest and all hashes immediately",
            "Do not enable or start the service", "separate owner authorization",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.text)

    def test_no_executable_historical_installer_recipe(self):
        for block in self.blocks:
            self.assertNotRegex(block, r"(?:bash|sh)\s+\S*install\.sh")
            self.assertNotRegex(block, r"(?:curl|wget|git\s+clone|pip\s+install)")
            self.assertNotRegex(block, r"systemctl\s+(?:enable|start|restart|reload)\b")

    def test_sudo_probe_originates_from_agent_context(self):
        self.assertIn("runuser -u sentinelx -- sudo -n -u root -- /usr/bin/true", self.text)
        self.assertIn('test "$(runuser -u sentinelx -- id -un)" = sentinelx', self.text)
        self.assertNotIn("sudo -u sentinelx -n true", self.text)
        self.assertIn("sudo -n -l -U sentinelx", self.text)
        self.assertIn("Do not treat a probe execution error", self.text)

    def test_shell_examples_parse_without_running_them(self):
        self.assertEqual(len(self.blocks), 2)
        for block in self.blocks:
            result = subprocess.run(["bash", "-n"], input=block, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_historical_evidence_is_not_rewritten_as_fresh_success(self):
        data = (HOST / "evidence-20260905.yaml").read_bytes()
        blob = b"blob " + str(len(data)).encode() + b"\0" + data
        self.assertEqual(hashlib.sha1(blob).hexdigest(), "e75c011690e7b66eb9f34d8090e741451ba4b042")
        template = (HOST / "config.yaml.blocked-template").read_text(encoding="utf-8")
        self.assertIn("REVIEW-ONLY", template)
        self.assertIn("allowed_commands: []", template)
        self.assertIn("services: {}", template)


if __name__ == "__main__":
    unittest.main()
