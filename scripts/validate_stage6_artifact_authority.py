#!/usr/bin/env python3
"""Verify a reviewed GitHub Actions artifact without exposing credentials."""

from __future__ import annotations

import json
import os
import urllib.request


def require(condition: bool, label: str) -> None:
    if not condition:
        raise SystemExit(f"STAGE6_ARTIFACT_AUTHORITY_ERROR={label}")


repo = os.environ["GITHUB_REPOSITORY"]
run_id = os.environ["PLAN_RUN_ID"]
expected_sha = os.environ["PLAN_SHA"]
expected_name = os.environ["PLAN_ARTIFACT_NAME"]
expected_digest = os.environ["PLAN_ARTIFACT_DIGEST"]
token = os.environ["GH_TOKEN"]

request = urllib.request.Request(
    f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100",
    headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    },
)
with urllib.request.urlopen(request, timeout=30) as response:
    payload = json.load(response)

matches = [item for item in payload.get("artifacts", []) if item.get("name") == expected_name]
require(len(matches) == 1, "artifact_name_not_unique")
artifact = matches[0]
require(not artifact.get("expired", True), "artifact_expired")
require(str(artifact.get("workflow_run", {}).get("id")) == run_id, "source_run")
require(artifact.get("workflow_run", {}).get("head_sha") == expected_sha, "source_sha")
require(artifact.get("digest") == expected_digest, "outer_digest")

print("SOURCE_ARTIFACT_DIGEST=PASS")
print(f"SOURCE_PLAN_RUN_ID={run_id}")
print(f"SOURCE_PLAN_SHA={expected_sha}")
