import os
import subprocess
import sys
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "reusable-codestra-deploy-readiness.yml"


def resolver_sources() -> list[str]:
    text = WORKFLOW.read_text(encoding="utf-8")
    sources = []
    cursor = 0
    while True:
        marker = text.find("readarray -t container_paths", cursor)
        if marker < 0:
            return sources
        start = text.index("          import os\n", marker)
        end = text.index("          PY\n", start)
        sources.append(textwrap.dedent(text[start:end]))
        cursor = end + 1


def resolve(tmp_path: Path, source: str, dockerfile: str = "", context: str = ""):
    env = os.environ | {
        "CONFIGURED_DOCKERFILE": dockerfile,
        "CONFIGURED_BUILD_CONTEXT": context,
    }
    return subprocess.run(
        [sys.executable, "-c", source], cwd=tmp_path, env=env,
        check=False, capture_output=True, text=True,
    )


def test_explicit_root_context_supports_nested_dockerfile(tmp_path):
    dockerfile = tmp_path / "vicidial" / "docker" / "Dockerfile"
    dockerfile.parent.mkdir(parents=True)
    dockerfile.write_text("FROM scratch\n", encoding="utf-8")

    assert len(resolver_sources()) == 2
    for source in resolver_sources():
        result = resolve(tmp_path, source, "vicidial/docker/Dockerfile", ".")
        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == ["vicidial/docker/Dockerfile", "."]


def test_default_layout_keeps_dockerfile_directory_context(tmp_path):
    dockerfile = tmp_path / "service" / "Dockerfile"
    dockerfile.parent.mkdir()
    dockerfile.write_text("FROM scratch\n", encoding="utf-8")

    for source in resolver_sources():
        result = resolve(tmp_path, source)
        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == ["service/Dockerfile", "service"]


def test_container_paths_reject_traversal(tmp_path):
    for source in resolver_sources():
        result = resolve(tmp_path, source, "../Dockerfile", ".")
        assert result.returncode != 0
        assert "must be repository-relative" in result.stderr


def test_container_paths_reject_missing_and_symlink_escape(tmp_path):
    outside = tmp_path.parent / "outside"
    outside.mkdir(exist_ok=True)
    (tmp_path / "escape").symlink_to(outside, target_is_directory=True)
    for source in resolver_sources():
        for dockerfile, context in (("missing/Dockerfile", "."), ("Dockerfile", "missing"), ("escape/Dockerfile", "."), ("Dockerfile", "escape")):
            result = resolve(tmp_path, source, dockerfile, context)
            assert result.returncode != 0


def test_release_passes_verified_metadata_as_build_arguments():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert '--build-arg "SOURCE_SHA=${source_sha}"' in text
    assert '--build-arg "BUILD_DATE=${build_date}"' in text
    assert 'source_sha="$(git rev-parse HEAD)"' in text
    assert 'commit_epoch="$(git show -s --format=%ct "$source_sha")"' in text
    assert "date --utc" in text
    assert "'+%Y-%m-%dT%H:%M:%SZ'" in text
    assert text.count('--build-arg "SOURCE_SHA=${source_sha}"') == 2
    assert text.count('--build-arg "BUILD_DATE=${build_date}"') == 2


def test_source_bundle_is_scanned_fail_closed_before_publication():
    text = WORKFLOW.read_text(encoding="utf-8")
    branch = text[text.index('          else\n            "$RUNNER_TEMP/trivy" fs'):text.index("            artifact_kind=source-bundle")]
    assert "--severity HIGH,CRITICAL" in branch
    assert "--exit-code 1" in branch
    assert "test -s evidence/vulnerability-report.json" in branch
    assert "test -s evidence/sbom.spdx.json" in branch
    assert branch.index('"$RUNNER_TEMP/trivy" fs') < branch.index("git archive")


def test_node_audits_match_lockfile_package_manager():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "auditor=(npm audit --omit=dev --audit-level=high)" in text
    assert "auditor=(pnpm audit --prod --audit-level high)" in text
    assert "auditor=(yarn npm audit --environment production --severity high)" in text
    assert "auditor=(yarn audit --groups dependencies --level high)" in text
    assert '"${auditor[@]}"' in text


def test_deployment_confirmations_are_data_not_shell_source():
    for name in (
        "reusable-codestra-deploy-readiness.yml",
        "reusable-codestra-upstream-deploy-readiness.yml",
    ):
        text = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
        assert 'test "${{ inputs.confirmation }}"' not in text
        assert 'case "${{ inputs.operation }}:${{ inputs.confirmation }}"' not in text
        assert "CONFIRMATION: ${{ inputs.confirmation }}" in text


def test_explicit_dockerfile_enables_source_container_check():
    text = WORKFLOW.read_text(encoding="utf-8")
    detector = text[text.index("      - name: Detect source stacks"):text.index("      - name: Set up Node.js")]
    assert "CONFIGURED_DOCKERFILE: ${{ inputs.dockerfile_path }}" in detector
    assert '[[ -n "$CONFIGURED_DOCKERFILE" ]] && has_docker=true' in detector


def test_upstream_production_requires_manual_dispatch():
    text = (ROOT / ".github/workflows/reusable-codestra-upstream-deploy-readiness.yml").read_text(encoding="utf-8")
    job = text[text.index("  production-readonly-canary:"):]
    assert "github.event_name == 'workflow_dispatch'" in job.split("runs-on:", 1)[0]
