#!/usr/bin/env python3
"""Sanitize and persist Stage 6 inventory evidence."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from stage6_inventory_common import fail, firewall_rules, sanitized_labels


def sanitized_inventory(raw: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    locations = [
        {"id": item["id"], "name": item["name"], "city": item.get("city"), "country": item.get("country")}
        for item in raw["locations"]
    ]
    servers = []
    for server in raw["servers"]:
        public_net = server.get("public_net", {})
        servers.append({
            "id": server["id"],
            "name": server["name"],
            "status": server.get("status"),
            "labels": sanitized_labels(server.get("labels", {})),
            "location": (server.get("datacenter") or {}).get("location", {}).get("name"),
            "public_ipv4": (public_net.get("ipv4") or {}).get("ip"),
            "public_ipv6": (public_net.get("ipv6") or {}).get("ip"),
            "private_network_attachments": [
                {"network_id": item.get("network"), "private_ip": item.get("ip"), "aliases": item.get("alias_ips", [])}
                for item in server.get("private_net", [])
            ],
        })
    networks = [
        {
            "id": item["id"],
            "name": item["name"],
            "labels": sanitized_labels(item.get("labels", {})),
            "ip_range": item.get("ip_range"),
            "subnets": [
                {"type": subnet.get("type"), "ip_range": subnet.get("ip_range"), "network_zone": subnet.get("network_zone"), "gateway": subnet.get("gateway")}
                for subnet in item.get("subnets", [])
            ],
            "routes": [{"destination": route.get("destination"), "gateway": route.get("gateway")} for route in item.get("routes", [])],
        }
        for item in raw["networks"]
    ]
    ssh_keys = [
        {"id": item["id"], "name": item["name"], "labels": sanitized_labels(item.get("labels", {}))}
        for item in raw["ssh_keys"]
    ]
    firewalls = [
        {
            "id": item["id"],
            "name": item["name"],
            "labels": sanitized_labels(item.get("labels", {})),
            "applied_to": item.get("applied_to", []),
            "rules": firewall_rules(item),
        }
        for item in raw["firewalls"]
    ]
    return {
        "schema_version": "2.0",
        "source": "Hetzner Cloud API GET-only",
        "locations": locations,
        "servers": servers,
        "networks": networks,
        "ssh_keys": ssh_keys,
        "firewalls": firewalls,
    }


def write_new(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        fail(f"output_exists:{path}")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())

