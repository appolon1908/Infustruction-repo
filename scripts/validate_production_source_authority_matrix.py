#!/usr/bin/env python3
import pathlib
import re
import yaml

path = pathlib.Path("PRODUCTION-SOURCE-AUTHORITY-MATRIX.yaml")
data = yaml.safe_load(path.read_text())
workloads = data["workloads"]
assert len(workloads) == 23
statuses = {"PROVEN", "AMBIGUOUS", "SOURCE_AUTHORITY_ABSENT", "VENDOR_ONLY", "DIVERGENT", "INVALID_REVISION_METADATA"}
remediations = set("ABCDEF")
expected = {"PROVEN": 23, "AMBIGUOUS": 0, "SOURCE_AUTHORITY_ABSENT": 0, "VENDOR_ONLY": 0, "DIVERGENT": 0, "INVALID_REVISION_METADATA": 0}
actual = {status: 0 for status in statuses}
for name, item in workloads.items():
    assert item["status"] in statuses, name
    assert item["remediation_type"] in remediations, name
    actual[item["status"]] += 1
    sha = str(item.get("source_sha", "UNKNOWN"))
    assert sha == "UNKNOWN" or re.fullmatch(r"[0-9a-f]{40}", sha), (name, sha)
    if item["status"] == "PROVEN":
        for field in ("runtime_image", "runtime_image_id", "compose_file", "build_context", "dockerfile", "repository", "protected_branch", "source_sha"):
            assert item.get(field) not in (None, "", "UNKNOWN"), (name, field)
        assert re.fullmatch(r"[0-9a-f]{40}", item["source_sha"])
assert actual == expected, (actual, expected)
assert data["source_ownership_proven"] == "23/23"
assert data["source_ownership_ambiguous"] == 0
assert data["source_authority_ready"] is True
assert data["acceptance_rule"] == "runtime_to_compose_to_build_context_to_dockerfile_to_protected_git_exact_sha"
print("SOURCE_AUTHORITY_MATRIX=PASS")
