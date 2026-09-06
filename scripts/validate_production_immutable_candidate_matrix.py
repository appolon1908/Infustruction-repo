#!/usr/bin/env python3
import re
from pathlib import Path

import yaml

PATH = Path("PRODUCTION-IMMUTABLE-CANDIDATE-MATRIX.yaml")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
SHA = re.compile(r"[0-9a-f]{40}")
IMAGE_REF = re.compile(r"[^@\s]+@sha256:[0-9a-f]{64}")
CAPABILITIES = {
    "advertising_write", "external_delivery", "social_publish",
    "external_model_call", "sms_delivery", "email_delivery",
    "pstn_dialing", "n8n_provider_write",
}

document = yaml.safe_load(PATH.read_text(encoding="utf-8"))
assert document["source_authority_ready"] is True
assert document["source_ownership_proven"] == "23/23"
assert document["capability_matrix_coverage"] == "64/64"
assert document["capability_unknown_fields"] == 0
assert document["build_authority_ready"] == "12/12"
assert document["production_business_writes_enabled"] is False

candidates = document["candidates"]
assert len(candidates) == 21
custom_builds = 0
for workload, candidate in candidates.items():
    assert SHA.fullmatch(candidate["source_sha"]), workload
    for field in ("current_runtime_image_id", "candidate_image_digest", "rollback_digest"):
        assert DIGEST.fullmatch(candidate[field]), (workload, field)
    assert IMAGE_REF.fullmatch(candidate["candidate_image_ref"]), workload
    assert candidate["candidate_image_ref"].endswith("@" + candidate["candidate_image_digest"])
    assert candidate["migration_required"] is False
    assert candidate["restart_required"] is True
    assert set(candidate["capabilities"]) == CAPABILITIES
    assert all(type(value) is bool for value in candidate["capabilities"].values())
    evidence = candidate["build_evidence"]
    if "sbom" in evidence:
        custom_builds += 1
        assert all(value == "PASS" for value in evidence.values())
    else:
        assert evidence == {
            "vendor_digest_pin": "PASS",
            "codestra_config_authority": "PASS",
            "runtime_repo_digest_verified": "PASS",
        }

assert custom_builds == 14  # 12 artifacts cover 14 workload instances.
print("IMMUTABLE_CANDIDATE_MATRIX=PASS")
print("CANDIDATE_WORKLOADS=21/21")
print("BUILD_AUTHORITY_READY=12/12")
