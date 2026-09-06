#!/usr/bin/env python3
import json
from pathlib import Path

import yaml


root = Path(__file__).resolve().parents[1] / "production-green-evidence"
bom = yaml.safe_load((root / "PLATFORM_WORKLOAD_BOM_20260902.yaml").read_text())
matrix = json.loads((root / "API_COMPLETION_MATRIX_20260902.json").read_text())
markdown = (root / "API_COMPLETION_MATRIX_20260902.md").read_text()

workloads = bom["workloads"]
assert len(workloads) == matrix["denominator"] == 15
assert len({item["name"] for item in workloads}) == 15
assert {item["name"] for item in workloads} == {
    item["name"] for item in matrix["workloads"]
}
for item in workloads:
    assert len(item["source_sha"]) == 40
    assert item["digest"] == "UNKNOWN" or item["digest"].startswith("sha256:")
    assert item["business_writes"] is False
    assert item["repository"] in bom["production_prs_by_repository"]
for item in matrix["workloads"]:
    assert f"| {item['name']} | {item['health']} | {item['ready']} | {item['version']} | {item['capabilities']} |" in markdown
for key, label in (("health", "HEALTH_ENDPOINTS"), ("ready", "READINESS_ENDPOINTS"), ("version", "VERSION_ENDPOINTS"), ("capabilities", "CAPABILITY_ENDPOINTS")):
    certified = sum(1 for item in matrix["workloads"] if item[key] == "PASS")
    assert matrix["counts"][key] == certified
    assert f"`{label}={matrix['counts'][key]}/15`" in markdown
assert bom["production_business_writes_enabled"] is False
assert matrix["production_business_writes_enabled"] is False
print("PLATFORM_WORKLOAD_BOM=PASS")
print("API_COMPLETION_MATRIX_AGREEMENT=PASS")
