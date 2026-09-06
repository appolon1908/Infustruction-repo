from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "one-click-go-live.yml"


def test_one_click_infrastructure_wrapper_only_runs_the_certified_readonly_chain() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    required = (
        "name: ONE CLICK — Go live read-only",
        "workflow_dispatch:",
        "GO_LIVE_READONLY",
        "full-readonly-release-chain.yml",
        "environment: staging-readonly",
        "environment: production-readonly-canary",
        "needs: [staging, rollback-rehearsal]",
        "0 < value <= 1",
        "gh run watch",
        "Allowed production traffic: GET/HEAD only",
        "Live writes, messages, calls, payments, withdrawals, and provider execution remain disabled.",
    )
    for value in required:
        assert value in text, value

    forbidden = (
        "pull_request_target:",
        "contents: write",
        "packages: write",
        "id-token: write",
        ":latest",
        "ssh ",
        "docker compose up",
        "tofu apply",
        "enable-production-web-traffic",
        "continue-on-error: true",
    )
    for value in forbidden:
        assert value not in text, value

    assert "permissions:\n  contents: read" in text
    assert "actions: write" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert "-f ref=main" in text
    assert "inputs[canary_percent]" in text


if __name__ == "__main__":
    test_one_click_infrastructure_wrapper_only_runs_the_certified_readonly_chain()
    print("ONE_CLICK_GO_LIVE_INFRASTRUCTURE_POLICY=PASS")
