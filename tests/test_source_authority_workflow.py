from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "source-authority-matrix.yml"


class SourceAuthorityWorkflowTests(unittest.TestCase):
    def test_required_pull_request_checks_are_not_path_filtered(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        pull_request_block = text.split("pull_request:", 1)[1].split(
            "permissions:", 1
        )[0]
        self.assertNotIn("paths:", pull_request_block)
        self.assertIn("validate-source:", text)
        self.assertIn("validate-merge-result:", text)


if __name__ == "__main__":
    unittest.main()
