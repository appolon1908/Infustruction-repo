#!/usr/bin/env python3
"""Static fail-closed checks for the Stage 6 read-only inventory authority."""

from __future__ import annotations

import ast
import ipaddress
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "stage6-readonly-inventory.yml"
COLLECTOR = ROOT / "scripts" / "collect_stage6_hetzner_inventory.py"
COMMON = ROOT / "scripts" / "stage6_inventory_common.py"
RESOLUTION = ROOT / "scripts" / "stage6_inventory_resolution.py"
OUTPUT = ROOT / "scripts" / "stage6_inventory_output.py"
TESTS = ROOT / "scripts" / "test_stage6_hetzner_inventory_resolution.py"
AUTHORITY = ROOT / "config" / "stage6-inventory-authority.v1.json"
VARIABLES = ROOT / "infra" / "hetzner" / "stage6-staging" / "variables.tf"
MAIN_TF = ROOT / "infra" / "hetzner" / "stage6-staging" / "main.tf"
ACCESS = ROOT / "infra" / "hetzner" / "stage6-staging" / "access-authority.tfvars.json"

EXPECTED_FIELDS = {
    "location": "hel1",
    "network_cidr": "10.250.0.0/16",
    "staging_subnet_cidr": "10.250.6.0/24",
    "private_ip": "10.250.6.10",
    "egress_gateway_private_ip": "10.250.6.2",
    "approved_ssh_key_ids": [118172836],
    "approved_ssh_source_cidrs": ["179.53.46.159/32"],
    "approved_egress_fqdns": [
        "api.github.com",
        "archive.ubuntu.com",
        "github.com",
        "ghcr.io",
        "objects.githubusercontent.com",
        "pkg-containers.githubusercontent.com",
        "release-assets.githubusercontent.com",
        "security.ubuntu.com",
    ],
    "approved_egress_ports": [80, 443],
    "approved_ntp_fqdns": ["ntp.ubuntu.com"],
    "known_internal_production_deny_cidrs": [
        "10.40.0.0/24",
        "37.27.128.39/32",
        "65.109.65.169/32",
    ],
}
EXPECTED_RESOURCES = {
    "runtime_server": {
        "name": "codestra-stage6-staging-01",
        "role": "stage6-runtime",
        "location": "hel1",
        "server_type": "cx43",
        "operating_system": "ubuntu-24.04",
        "private_ip": "10.250.6.10",
    },
    "egress_server": {
        "name": "codestra-stage6-egress-01",
        "role": "stage6-egress-gateway",
        "location": "hel1",
        "server_type": "cx23",
        "operating_system": "ubuntu-24.04",
        "private_ip": "10.250.6.2",
    },
    "network": {
        "name": "codestra-stage6-staging-net",
        "cidr": "10.250.0.0/16",
        "subnet_cidr": "10.250.6.0/24",
    },
    "runtime_firewall": {"name": "codestra-stage6-staging-01-deny-default"},
    "egress_firewall": {"name": "codestra-stage6-egress-01-boundary"},
}


def require(condition: bool, label: str) -> None:
    if not condition:
        raise SystemExit(f"STAGE6_READONLY_INVENTORY_ERROR={label}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"STAGE6_READONLY_INVENTORY_ERROR=invalid_json:{path}:{exc}") from exc
    require(isinstance(value, dict), f"json_object:{path}")
    return value


for path in (WORKFLOW, COLLECTOR, COMMON, RESOLUTION, OUTPUT, TESTS, AUTHORITY, VARIABLES, MAIN_TF, ACCESS):
    require(path.is_file() and not path.is_symlink(), f"required_regular_file:{path.relative_to(ROOT)}")

workflow = WORKFLOW.read_text(encoding="utf-8")
collector = COLLECTOR.read_text(encoding="utf-8")
common = COMMON.read_text(encoding="utf-8")
resolution = RESOLUTION.read_text(encoding="utf-8")
output = OUTPUT.read_text(encoding="utf-8")
collector_sources = {
    "collector": collector,
    "common": common,
    "resolution": resolution,
    "output": output,
}
combined_collector = "\n".join(collector_sources.values())
tests = TESTS.read_text(encoding="utf-8")
variables = VARIABLES.read_text(encoding="utf-8")
main_tf = MAIN_TF.read_text(encoding="utf-8")

require(re.search(r"(?m)^on:\n  workflow_dispatch:\s*$", workflow) is not None, "dispatch_only")
require("pull_request:" not in workflow and "push:" not in workflow and "schedule:" not in workflow, "automatic_trigger")
require("environment: stage6-infrastructure-provisioning" in workflow, "protected_environment")
require("github.ref_protected" in workflow and "refs/heads/main" in workflow, "protected_main")
require("secrets.HETZNER_CLOUD_TOKEN" in workflow, "token_source")
require("permissions:\n  contents: read" in workflow, "permissions")
require("persist-credentials: false" in workflow, "checkout_credentials")
require("python -m unittest scripts/test_stage6_hetzner_inventory_resolution.py" in workflow, "resolution_regressions")
require("--authority config/stage6-inventory-authority.v1.json" in workflow, "explicit_authority")
require(".complete == true" in workflow and ".unresolved == []" in workflow, "complete_resolution_gate")
require(".cloud_mutation == false" in workflow and ".production_changed == false" in workflow, "no_effect_result_gate")
require("retention-days: 30" in workflow, "evidence_retention")

for target_name, target in (("workflow", workflow), *collector_sources.items()):
    require(
        re.search(
            r"(?i)\bhcloud\s+(server|network|firewall|ssh-key)\s+"
            r"(create|update|delete|attach|detach|power|reboot|reset|rebuild)",
            target,
        )
        is None,
        f"hcloud_mutation_{target_name}",
    )
    require(
        re.search(r"(?i)curl[^\n]*(--request|-X)\s*(POST|PUT|PATCH|DELETE)", target) is None,
        f"curl_mutation_{target_name}",
    )

request_methods: list[str] = []
for source_name, source in collector_sources.items():
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Request":
            method = next((kw.value for kw in node.keywords if kw.arg == "method"), None)
            require(isinstance(method, ast.Constant) and method.value == "GET", f"request_not_explicit_get:{source_name}")
            request_methods.append(str(method.value))
require(request_methods == ["GET"], "request_count")
require('COLLECTIONS = ("locations", "servers", "networks", "ssh_keys", "firewalls")' in common, "endpoint_allowlist")
for marker in (
    "DEFAULT_AUTHORITY",
    "resolve_authority",
    "authority_sha256",
    "allow_unresolved_fields",
    "require_exact_rule_set",
    "expected_exactly_one",
    "cloud_api_methods",
    "O_EXCL",
    "0o600",
):
    require(marker in combined_collector, f"collector_control:{marker}")
for field in EXPECTED_FIELDS:
    require(f'"{field}"' in combined_collector, f"current_schema:{field}")
require(re.search(r"print\([^\n]*HETZNER_CLOUD_TOKEN", combined_collector) is None, "token_print")
require("print(token" not in combined_collector, "token_export")
require("STAGE6_TFVARS_JSON" not in workflow, "incomplete_tfvars_write")
require("class ResolutionTests" in tests and tests.count("def test_") >= 12, "regression_count")

authority = load_json(AUTHORITY)
require(authority.get("schema_version") == "codestra.stage6-inventory-authority.v1", "authority_schema")
require(authority.get("environment") == "staging", "authority_environment")
require(authority.get("production") is False, "authority_production")
require(authority.get("managed_by") == "opentofu", "authority_manager")
require(authority.get("resources") == EXPECTED_RESOURCES, "authority_resources")
for key in (
    "approved_ssh_key_ids",
    "approved_ssh_source_cidrs",
    "approved_egress_fqdns",
    "approved_egress_ports",
    "approved_ntp_fqdns",
    "known_internal_production_deny_cidrs",
):
    require(authority.get(key) == EXPECTED_FIELDS[key], f"authority_field:{key}")
policy = authority.get("evidence_policy") or {}
require(policy.get("cloud_api_methods") == ["GET"], "authority_get_only")
require(policy.get("require_running_servers") is True, "authority_running")
require(policy.get("require_exact_resource_match") is True, "authority_exact_match")
require(policy.get("allow_unresolved_fields") is False, "authority_unresolved")
require(
    set(policy.get("git_authority_fields") or [])
    == {"approved_egress_fqdns", "approved_ntp_fqdns", "known_internal_production_deny_cidrs"},
    "authority_git_fields",
)

access = load_json(ACCESS)
require(access.get("approved_ssh_source_cidrs") == EXPECTED_FIELDS["approved_ssh_source_cidrs"], "ssh_access_authority")
for value in (
    *EXPECTED_RESOURCES["runtime_server"].values(),
    *EXPECTED_RESOURCES["egress_server"].values(),
    *EXPECTED_RESOURCES["network"].values(),
):
    require(str(value) in main_tf or str(value) in variables, f"iac_value:{value}")
for exact_name, template, local_binding in (
    (
        EXPECTED_RESOURCES["runtime_firewall"]["name"],
        '${local.runtime_name}-deny-default',
        'runtime_name = "codestra-stage6-staging-01"',
    ),
    (
        EXPECTED_RESOURCES["egress_firewall"]["name"],
        '${local.gateway_name}-boundary',
        'gateway_name = "codestra-stage6-egress-01"',
    ),
):
    require(
        exact_name in main_tf or (template in main_tf and local_binding in main_tf),
        f"iac_firewall_name:{exact_name}",
    )
for values in (
    EXPECTED_FIELDS["approved_ssh_key_ids"],
    EXPECTED_FIELDS["approved_egress_fqdns"],
    EXPECTED_FIELDS["approved_egress_ports"],
    EXPECTED_FIELDS["approved_ntp_fqdns"],
    EXPECTED_FIELDS["known_internal_production_deny_cidrs"],
):
    for value in values:
        require(str(value) in variables, f"iac_catalog_value:{value}")

network = ipaddress.ip_network(EXPECTED_FIELDS["network_cidr"])
subnet = ipaddress.ip_network(EXPECTED_FIELDS["staging_subnet_cidr"])
require(subnet.subnet_of(network), "authority_subnet")
require(ipaddress.ip_address(EXPECTED_FIELDS["private_ip"]) in subnet, "authority_runtime_ip")
require(ipaddress.ip_address(EXPECTED_FIELDS["egress_gateway_private_ip"]) in subnet, "authority_gateway_ip")

print("STAGE6_READONLY_INVENTORY_STATIC=PASS")
print("STAGE6_AUTHORITY_BINDING=PASS")
print("RESOLUTION_REGRESSION_TESTS=12")
print("API_METHODS=GET_ONLY")
print("CLOUD_MUTATION=NO")
print("PRODUCTION_CHANGED=NO")
