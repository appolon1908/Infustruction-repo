#!/usr/bin/env python3
"""Fail closed unless a saved Stage 6 plan matches the owner-reviewed authority."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def require(condition: bool, label: str) -> None:
    if not condition:
        raise SystemExit(f"STAGE6_REVIEWED_PLAN_ERROR={label}")


allowed = {
    "hcloud_firewall.egress",
    "hcloud_firewall.runtime",
    "hcloud_network.stage6",
    "hcloud_network_subnet.stage6",
    "hcloud_server.egress",
    "hcloud_server.stage6",
    "hcloud_server_network.egress",
    "hcloud_server_network.stage6",
}
plan = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
changes = plan.get("resource_changes", [])
addresses = {change.get("address") for change in changes}
actions = {change["address"]: change.get("change", {}).get("actions", []) for change in changes}

require(addresses == allowed, "resource_addresses")
require(all(action == ["create"] for action in actions.values()), "create_only")
require(len(changes) == 8, "create_count")

variables = plan.get("variables", {})
value = lambda name: variables.get(name, {}).get("value")
require(value("approved_ssh_source_cidrs") == ["148.101.227.238/32"], "ssh_source")
require(value("network_cidr") == "10.250.0.0/16", "network_cidr")
require(value("staging_subnet_cidr") == "10.250.6.0/24", "subnet_cidr")
require(value("private_ip") == "10.250.6.10", "runtime_ip")
require(value("egress_gateway_private_ip") == "10.250.6.2", "gateway_ip")

runtime_firewall = next(change for change in changes if change["address"] == "hcloud_firewall.runtime")
runtime_rules = runtime_firewall["change"]["after"]["rule"]
ssh_rules = [rule for rule in runtime_rules if rule["direction"] == "in" and rule["port"] == "22"]
require(len(ssh_rules) == 1, "runtime_ssh_rule")
require(ssh_rules[0]["source_ips"] == ["148.101.227.238/32"], "runtime_ssh_cidr")
require(all("0.0.0.0/0" not in rule.get("destination_ips", []) for rule in runtime_rules), "runtime_public_egress")
for port in ("53", "123", "3128"):
    matching = [rule for rule in runtime_rules if rule["direction"] == "out" and rule["port"] == port]
    require(matching and all(rule["destination_ips"] == ["10.250.6.2/32"] for rule in matching), f"gateway_port_{port}")

for change in changes:
    labels = change.get("change", {}).get("after", {}).get("labels")
    if labels is not None:
        require(labels.get("production") == "false", "production_label")
        require(labels.get("klyrow") == "false", "klyrow_label")
        require(labels.get("postal") == "false", "postal_label")

prior_resources = (
    plan.get("prior_state", {}).get("values", {}).get("root_module", {}).get("resources", [])
)
require(len(prior_resources) == 0, "prior_resources_present")

print("PLAN_CREATE_COUNT=8")
print("PLAN_UPDATE_COUNT=0")
print("PLAN_DELETE_COUNT=0")
print("APPROVED_RESOURCE_ADDRESSES_ONLY=YES")
print("SSH_POLICY=PASS")
print("NETWORK_POLICY=PASS")
print("DNS_NTP_POLICY=PASS")
print("DEFAULT_DENY_EGRESS=YES")
print("PRODUCTION_RESOURCES_TOUCHED=0")
