from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_release_environment_contract_requires_independent_review() -> None:
    contract = json.loads(
        (
            ROOT
            / "operations/staging-readonly/github-environment-contract.json"
        ).read_text(encoding="utf-8")
    )

    for environment in ("staging-readonly", "production-readonly-canary"):
        policy = contract["environments"][environment]
        assert policy["protected_branches_only"] is True
        assert policy["can_admins_bypass"] is False
        assert policy["prevent_self_review"] is True
        assert policy["minimum_required_reviewers"] == 1


def test_provisioner_installs_and_rechecks_environment_review_policy() -> None:
    source = (
        ROOT / "operations/staging-readonly/configure_github_environments.sh"
    ).read_text(encoding="utf-8")

    for marker in (
        "--reviewer-user LOGIN",
        'reviewers: [{type: "User", id: $reviewer_id}]',
        "prevent_self_review: true",
        "can_admins_bypass: false",
        ".deployment_branch_policy.protected_branches == true",
        ".deployment_branch_policy.custom_branch_policies == false",
        '.reviewer.id == $reviewer_id',
    ):
        assert marker in source
