"""Exercise the workflow's release calls without uploading any real assets."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("exists", [False, True])
def test_source_release_uploads_regular_files_without_runtime_directories(tmp_path, exists):
    workflow = yaml.safe_load((ROOT / ".github/workflows/reusable-codestra-deploy-readiness.yml").read_text())
    step = next(s["run"] for s in workflow["jobs"]["immutable-candidate"]["steps"]
                if s.get("name") == "Build once, scan, publish, sign, and attest")
    script = step.split('tag="deploy-ready-${source_sha}"', 1)[1].split("artifact_kind=source-bundle", 1)[0]
    evidence = tmp_path / "evidence"
    (evidence / "runtime").mkdir(parents=True)
    (evidence / "source.tar.gz").write_text("synthetic-bundle")
    (evidence / "source manifest.json").write_text("{}")
    (evidence / "linked.json").symlink_to(evidence / "source manifest.json")
    capture = tmp_path / "captured.json"
    gh = tmp_path / "gh"
    gh.write_text(f"#!{sys.executable}\n" +
        "import json,os,sys\nfrom pathlib import Path\n" +
        "if sys.argv[2]=='view': sys.exit(0 if os.environ['EXISTS']=='true' else 1)\n" +
        "assets=[a for a in sys.argv[4:] if a.startswith('evidence/')]\n" +
        "Path(os.environ['CAPTURE']).write_text(json.dumps(assets))\n" +
        "sys.exit(9 if any(not Path(a).is_file() or Path(a).is_symlink() for a in assets) else 0)\n")
    gh.chmod(0o755)
    env = os.environ | {"PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
        "EXISTS": str(exists).lower(), "CAPTURE": str(capture), "source_sha": "a" * 40}
    result = subprocess.run(["bash", "-euo", "pipefail", "-c", 'tag=test\n' + script],
                            cwd=tmp_path, env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert sorted(json.loads(capture.read_text())) == ["evidence/source manifest.json", "evidence/source.tar.gz"]
