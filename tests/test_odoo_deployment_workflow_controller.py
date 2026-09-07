from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/reusable-codestra-deploy-readiness.yml"


def test_protected_jobs_use_root_controller_without_changing_source_defaults():
    text = WORKFLOW.read_text()
    assert text.count("sudo -n /usr/local/bin/codestra-deploy") == 2
    assert "Runtime deployment authorized by CI: **No**" in text
    assert "External effects authorized by CI: **No**" in text


def test_provider_policy_is_exact_no_arguments():
    policy = (ROOT / "operators/klyrow-odoo-smtp-export.sudoers").read_text()
    assert policy.strip().endswith('/usr/local/sbin/export-odoo-postal-credential ""')
    assert "NOPASSWD: ALL" not in policy
