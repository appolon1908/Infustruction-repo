"""Execute both workflow build paths with a synthetic checkout and fake Docker."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/reusable-codestra-deploy-readiness.yml"
DOCUMENT = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def step_script(job, name):
    script = next(step["run"] for step in DOCUMENT["jobs"][job]["steps"] if step.get("name") == name)
    return script.replace("${{ github.event.pull_request.head.sha || github.sha }}", "${GITHUB_SHA}")


SCRIPTS = {
    "source-ci": step_script("source-ci", "Build primary container without publishing"),
    "immutable-candidate": step_script("immutable-candidate", "Build once, scan, publish, sign, and attest").split(
        '"$RUNNER_TEMP/trivy" image', 1
    )[0] + "\nfi\n",
}


class BuildContextRegression(unittest.TestCase):
    def run_fixture(self, job, context=".", dockerfile="vicidial/docker/Dockerfile"):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            root = parent / "checkout"
            nested = root / "vicidial/docker"
            nested.mkdir(parents=True)
            (nested / "Dockerfile").write_text("FROM scratch\nCOPY vicidial /vicidial\n", encoding="utf-8")
            (root / "escape").symlink_to(parent, target_is_directory=True)
            env = os.environ | {
                "GIT_AUTHOR_NAME": "Synthetic", "GIT_AUTHOR_EMAIL": "test@example.invalid",
                "GIT_COMMITTER_NAME": "Synthetic", "GIT_COMMITTER_EMAIL": "test@example.invalid",
                "GIT_AUTHOR_DATE": "2026-09-05T07:04:08-04:00",
                "GIT_COMMITTER_DATE": "2026-09-05T07:04:08-04:00",
            }
            for args in (["init", "-q"], ["add", "."], ["commit", "-qm", "fixture"]):
                subprocess.run(["git", *args], cwd=root, env=env, check=True, capture_output=True)
            sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            fake = parent / "docker"
            fake.write_text(
                f"#!{sys.executable}\nimport json,os,sys\nfrom pathlib import Path\n"
                "Path(os.environ['CAPTURE']).write_text(json.dumps(sys.argv[1:]))\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            (parent / "python").symlink_to(sys.executable)
            capture = parent / "capture.json"
            env.update({
                "PATH": str(parent) + os.pathsep + os.environ["PATH"],
                "CONFIGURED_DOCKERFILE": dockerfile,
                "CONFIGURED_BUILD_CONTEXT": context,
                "GITHUB_SHA": sha,
                "GITHUB_REPOSITORY": "synthetic/repo",
                "GITHUB_RUN_ID": "1", "GITHUB_RUN_ATTEMPT": "1",
                "ARTIFACT_STRATEGY": "oci", "REPOSITORY_CLASS": "service",
                "CAPTURE": str(capture),
            })
            result = subprocess.run(["bash", "-c", SCRIPTS[job]], cwd=root, env=env, text=True, capture_output=True)
            args = json.loads(capture.read_text()) if capture.exists() else None
            return result, args, sha

    def test_both_paths_use_root_context_and_utc_metadata(self):
        for job in SCRIPTS:
            result, args, sha = self.run_fixture(job)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(args[-1], ".")
            self.assertEqual(args[args.index("-f") + 1], "vicidial/docker/Dockerfile")
            self.assertIn("SOURCE_SHA=" + sha, args)
            build_date = next(value for value in args if value.startswith("BUILD_DATE="))
            self.assertEqual(build_date, "BUILD_DATE=2026-09-05T11:04:08Z")

    def test_both_paths_preserve_default_layout(self):
        for job in SCRIPTS:
            result, args, _ = self.run_fixture(job, context="", dockerfile="")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(args[-1], "vicidial/docker")

    def test_both_paths_reject_invalid_paths_before_build(self):
        for job in SCRIPTS:
            for context in ("../", "escape", "missing", "https://example.invalid/repo", "$(touch unexpected)"):
                result, args, _ = self.run_fixture(job, context=context)
                self.assertNotEqual(result.returncode, 0)
                self.assertIsNone(args)
            result, args, _ = self.run_fixture(job, dockerfile="missing/Dockerfile")
            self.assertNotEqual(result.returncode, 0)
            self.assertIsNone(args)


if __name__ == "__main__":
    unittest.main()
