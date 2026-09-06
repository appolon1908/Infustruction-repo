#!/usr/bin/env python3
"""Resolve exact Stage 6 deployment inputs from live GET evidence plus Git authority."""

from __future__ import annotations

from typing import Any

from stage6_inventory_common import (
    COLLECTIONS, FIELDS, exactly_one, fail, firewall_applies_to_server,
    firewall_rules, labels_equal, require_equal, require_exact_rule_set,
    require_rule, server_private_ip, sha256_json,
)


def resolve_authority(raw: dict[str, list[dict[str, Any]]], authority: dict[str, Any]) -> dict[str, Any]:
    if set(raw) != set(COLLECTIONS):
        fail("raw_collection_set")
    resources = authority["resources"]
    common_labels = {
        "environment": authority["environment"],
        "production": "false",
        "klyrow": "false",
        "postal": "false",
        "managed-by": authority["managed_by"],
    }
    runtime_labels = {**common_labels, "role": resources["runtime_server"]["role"]}
    egress_labels = {**common_labels, "role": resources["egress_server"]["role"]}

    runtime = exactly_one(
        raw["servers"],
        lambda item: item.get("name") == resources["runtime_server"]["name"] and labels_equal(item, runtime_labels),
        "runtime_server",
    )
    egress = exactly_one(
        raw["servers"],
        lambda item: item.get("name") == resources["egress_server"]["name"] and labels_equal(item, egress_labels),
        "egress_server",
    )
    if authority["evidence_policy"]["require_running_servers"]:
        require_equal(runtime.get("status"), "running", "runtime_status")
        require_equal(egress.get("status"), "running", "egress_status")

    for label, server, expected in (
        ("runtime", runtime, resources["runtime_server"]),
        ("egress", egress, resources["egress_server"]),
    ):
        require_equal((server.get("server_type") or {}).get("name"), expected["server_type"], f"{label}_server_type")
        require_equal((server.get("image") or {}).get("name"), expected["operating_system"], f"{label}_operating_system")
        require_equal(server.get("backup_window") is not None, True, f"{label}_backups_enabled")
        protection = server.get("protection") or {}
        require_equal(protection.get("delete"), True, f"{label}_delete_protection")
        require_equal(protection.get("rebuild"), True, f"{label}_rebuild_protection")
        public_net = server.get("public_net") or {}
        require_equal(bool((public_net.get("ipv4") or {}).get("ip")), True, f"{label}_public_ipv4_present")
        require_equal(bool((public_net.get("ipv6") or {}).get("ip")), False, f"{label}_public_ipv6_absent")

    location = exactly_one(
        raw["locations"],
        lambda item: item.get("name") == resources["runtime_server"]["location"],
        "stage6_location",
    )
    require_equal(location.get("name"), resources["egress_server"]["location"], "location_authority_alignment")

    network = exactly_one(
        raw["networks"],
        lambda item: item.get("name") == resources["network"]["name"] and labels_equal(item, common_labels),
        "stage6_network",
    )
    network_id = int(network["id"])
    require_equal(str(network.get("ip_range")), resources["network"]["cidr"], "network_cidr")
    subnets = [
        item for item in network.get("subnets", [])
        if item.get("type") == "cloud" and item.get("ip_range") == resources["network"]["subnet_cidr"]
    ]
    if len(subnets) != 1:
        fail(f"stage6_subnet:found={len(subnets)}")
    require_equal(network.get("routes") or [], [], "stage6_network_routes")

    runtime_private_ip = server_private_ip(runtime, network_id)
    egress_private_ip = server_private_ip(egress, network_id)
    require_equal(runtime_private_ip, resources["runtime_server"]["private_ip"], "runtime_private_ip")
    require_equal(egress_private_ip, resources["egress_server"]["private_ip"], "egress_private_ip")

    runtime_location = (runtime.get("datacenter") or {}).get("location", {}).get("name")
    egress_location = (egress.get("datacenter") or {}).get("location", {}).get("name")
    require_equal(runtime_location, resources["runtime_server"]["location"], "runtime_location")
    require_equal(egress_location, resources["egress_server"]["location"], "egress_location")
    require_equal(runtime_location, egress_location, "server_location_alignment")

    actual_key_ids = {int(item["id"]) for item in raw["ssh_keys"]}
    approved_key_ids = sorted(int(item) for item in authority["approved_ssh_key_ids"])
    missing_keys = sorted(set(approved_key_ids) - actual_key_ids)
    if missing_keys:
        fail(f"approved_ssh_keys_missing:{missing_keys}")

    runtime_fw = exactly_one(
        raw["firewalls"],
        lambda item: item.get("name") == resources["runtime_firewall"]["name"] and labels_equal(item, runtime_labels),
        "runtime_firewall",
    )
    egress_fw = exactly_one(
        raw["firewalls"],
        lambda item: item.get("name") == resources["egress_firewall"]["name"] and labels_equal(item, egress_labels),
        "egress_firewall",
    )
    if not firewall_applies_to_server(runtime_fw, runtime):
        fail("runtime_firewall_not_applied")
    if not firewall_applies_to_server(egress_fw, egress):
        fail("egress_firewall_not_applied")

    approved_ssh_sources = sorted(authority["approved_ssh_source_cidrs"])
    runtime_rules = firewall_rules(runtime_fw)
    egress_rules = firewall_rules(egress_fw)
    require_rule(runtime_rules, direction="in", protocol="tcp", port="22", source_ips=approved_ssh_sources, label="runtime_ssh")
    require_rule(egress_rules, direction="in", protocol="tcp", port="22", source_ips=approved_ssh_sources, label="egress_ssh")
    require_rule(runtime_rules, direction="out", protocol="tcp", port="3128", destination_ips=[f"{egress_private_ip}/32"], label="runtime_proxy")
    require_rule(runtime_rules, direction="out", protocol="tcp", port="53", destination_ips=[f"{egress_private_ip}/32"], label="runtime_dns_tcp")
    require_rule(runtime_rules, direction="out", protocol="udp", port="53", destination_ips=[f"{egress_private_ip}/32"], label="runtime_dns_udp")
    require_rule(runtime_rules, direction="out", protocol="udp", port="123", destination_ips=[f"{egress_private_ip}/32"], label="runtime_ntp")
    require_rule(runtime_rules, direction="out", protocol="tcp", port="1-65535", destination_ips=[resources["network"]["subnet_cidr"]], label="runtime_private")
    require_rule(egress_rules, direction="in", protocol="tcp", port="3128", source_ips=[f"{runtime_private_ip}/32"], label="egress_proxy")
    for port in authority["approved_egress_ports"]:
        require_rule(egress_rules, direction="out", protocol="tcp", port=str(port), destination_ips=["0.0.0.0/0"], label=f"egress_{port}")

    expected_runtime_rules = [
        {"direction": "in", "protocol": "tcp", "port": "22", "source_ips": approved_ssh_sources, "destination_ips": []},
        {"direction": "out", "protocol": "tcp", "port": "3128", "source_ips": [], "destination_ips": [f"{egress_private_ip}/32"]},
        {"direction": "out", "protocol": "tcp", "port": "53", "source_ips": [], "destination_ips": [f"{egress_private_ip}/32"]},
        {"direction": "out", "protocol": "udp", "port": "53", "source_ips": [], "destination_ips": [f"{egress_private_ip}/32"]},
        {"direction": "out", "protocol": "udp", "port": "123", "source_ips": [], "destination_ips": [f"{egress_private_ip}/32"]},
        {"direction": "out", "protocol": "tcp", "port": "1-65535", "source_ips": [], "destination_ips": [resources["network"]["subnet_cidr"]]},
    ]
    expected_egress_rules = [
        {"direction": "in", "protocol": "tcp", "port": "22", "source_ips": approved_ssh_sources, "destination_ips": []},
        {"direction": "in", "protocol": "tcp", "port": "3128", "source_ips": [f"{runtime_private_ip}/32"], "destination_ips": []},
        {"direction": "in", "protocol": "tcp", "port": "53", "source_ips": [f"{runtime_private_ip}/32"], "destination_ips": []},
        {"direction": "in", "protocol": "udp", "port": "53", "source_ips": [f"{runtime_private_ip}/32"], "destination_ips": []},
        {"direction": "in", "protocol": "udp", "port": "123", "source_ips": [f"{runtime_private_ip}/32"], "destination_ips": []},
        {"direction": "out", "protocol": "tcp", "port": "53", "source_ips": [], "destination_ips": ["0.0.0.0/0"]},
        {"direction": "out", "protocol": "udp", "port": "53", "source_ips": [], "destination_ips": ["0.0.0.0/0"]},
        {"direction": "out", "protocol": "udp", "port": "123", "source_ips": [], "destination_ips": ["0.0.0.0/0"]},
    ] + [
        {"direction": "out", "protocol": "tcp", "port": str(port), "source_ips": [], "destination_ips": ["0.0.0.0/0"]}
        for port in authority["approved_egress_ports"]
    ]
    require_exact_rule_set(runtime_rules, expected_runtime_rules, "runtime")
    require_exact_rule_set(egress_rules, expected_egress_rules, "egress")

    fields = {
        "location": runtime_location,
        "network_cidr": resources["network"]["cidr"],
        "staging_subnet_cidr": resources["network"]["subnet_cidr"],
        "private_ip": runtime_private_ip,
        "egress_gateway_private_ip": egress_private_ip,
        "approved_ssh_key_ids": approved_key_ids,
        "approved_ssh_source_cidrs": approved_ssh_sources,
        "approved_egress_fqdns": sorted(authority["approved_egress_fqdns"]),
        "approved_egress_ports": sorted(authority["approved_egress_ports"]),
        "approved_ntp_fqdns": sorted(authority["approved_ntp_fqdns"]),
        "known_internal_production_deny_cidrs": sorted(authority["known_internal_production_deny_cidrs"]),
    }
    unresolved = [name for name in FIELDS if fields.get(name) is None]
    if unresolved and not authority["evidence_policy"]["allow_unresolved_fields"]:
        fail(f"unresolved_fields:{','.join(unresolved)}")
    field_sources = {
        "location": "hetzner-api:servers.datacenter.location",
        "network_cidr": "hetzner-api:networks.ip_range+git-authority",
        "staging_subnet_cidr": "hetzner-api:networks.subnets+git-authority",
        "private_ip": "hetzner-api:servers.private_net+git-authority",
        "egress_gateway_private_ip": "hetzner-api:servers.private_net+git-authority",
        "approved_ssh_key_ids": "hetzner-api:ssh_keys+git-authority",
        "approved_ssh_source_cidrs": "hetzner-api:firewalls.rules+git-authority",
        "approved_egress_fqdns": "git-authority:egress-cloud-init",
        "approved_egress_ports": "hetzner-api:firewalls.rules+git-authority",
        "approved_ntp_fqdns": "git-authority:egress-cloud-init",
        "known_internal_production_deny_cidrs": "git-authority:network-isolation",
    }
    return {
        "schema_version": "2.0",
        "authority_sha256": sha256_json(authority),
        "fields": fields,
        "field_sources": field_sources,
        "resource_ids": {
            "runtime_server_id": runtime["id"],
            "egress_server_id": egress["id"],
            "network_id": network["id"],
            "runtime_firewall_id": runtime_fw["id"],
            "egress_firewall_id": egress_fw["id"],
        },
        "resource_status": {
            "runtime": runtime.get("status"),
            "egress": egress.get("status"),
            "runtime_backups_enabled": runtime.get("backup_window") is not None,
            "egress_backups_enabled": egress.get("backup_window") is not None,
            "delete_and_rebuild_protection": True,
            "public_ipv6": False,
        },
        "unresolved": unresolved,
        "complete": not unresolved,
        "cloud_api_methods": ["GET"],
        "cloud_mutation": False,
        "production_changed": False,
    }

