from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_release_uses_verified_checkout_identity_everywhere():
    workflow=(ROOT/".github/workflows/release-codestra-deploy-controller.yml").read_text()
    assert '--source-sha "$VERIFIED_SOURCE_SHA"' in workflow
    assert 'codestra-deploy-controller-${{ inputs.source_sha }}' in workflow
    assert '--source-sha "$GITHUB_SHA"' not in workflow
    assert 'codestra-deploy-controller-${{ github.sha }}' not in workflow

def test_pr_workflow_executes_adapter_regressions():
    workflow=(ROOT/".github/workflows/test-odoo-deploy-adapter.yml").read_text()
    assert "pull_request:" in workflow
    assert "test_codestra_deploy_odoo_adapter.py" in workflow
