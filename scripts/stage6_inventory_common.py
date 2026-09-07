#!/usr/bin/env python3
"""Read-only Stage 6 inventory primitives and exact authority validation."""

from __future__ import annotations

import hashlib
import ipaddress
import json
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUTHORITY = ROOT / "config" / "stage6-inventory-authority.v1.json"
API_ROOT = "https://api.hetzner.cloud/v1"
COLLECTIONS = ("locations", "servers", "networks", "ssh_keys", "firewalls")
FIELDS = (
    "location",
    "network_cidr",
    "staging_subnet_cidr",
    "private_ip",
    "egress_gateway_private_ip",
    "approved_ssh_key_ids",
    "approved_ssh_source_cidrs",
    "approved_egress_fqdns",
    "approved_egress_ports",
    "approved_ntp_fqdns",
    "known_internal_production_deny_cidrs",
)


class InventoryError(RuntimeError):
    """A fail-closed inventory or authority mismatch."""


def fail(message: str) -> None:
    raise InventoryError(message)


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_json(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def sanitized_labels(labels: dict[str, Any]) -> dict[str, str]:
    sensitive_markers = ("secret", "token", "password", "credential", "private_key", "api_key")
    return {
        str(key): "REDACTED" if any(marker in str(key).lower() for marker in sensitive_markers) else str(value)
        for key, value in labels.items()
    }


def get_collection(token: str, collection: str) -> list[dict[str, Any]]:
    if collection not in COLLECTIONS:
        raise SystemExit(f"INVENTORY_ERROR=endpoint_not_allowlisted:{collection}")
    records: list[dict[str, Any]] = []
    page = 1
    while True:
        query = urlencode({"page": page, "per_page": 50})
        request = Request(
            f"{API_ROOT}/{collection}?{query}",
            headers={"Authorization": f"Bearer {token}", "User-Agent": "codestra-stage6-readonly-inventory/2"},
            method="GET",
        )
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
        records.extend(payload.get(collection, []))
        pagination = payload.get("meta", {}).get("pagination", {})
        if not pagination.get("next_page"):
            return records
        page = int(pagination["next_page"])


def labels_equal(value: dict[str, Any], expected: dict[str, str]) -> bool:
    labels = {str(key): str(item).lower() for key, item in value.get("labels", {}).items()}
    return all(labels.get(key) == str(item).lower() for key, item in expected.items())


def exactly_one(records: Iterable[dict[str, Any]], predicate: Callable[[dict[str, Any]], bool], label: str) -> dict[str, Any]:
    matches = [record for record in records if predicate(record)]
    if len(matches) != 1:
        fail(f"{label}:expected_exactly_one:found={len(matches)}")
    return matches[0]


def require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        fail(f"{label}:expected={expected!r}:actual={actual!r}")


def validate_cidr(value: str, label: str) -> str:
    try:
        return str(ipaddress.ip_network(value, strict=False))
    except ValueError as exc:
        fail(f"{label}:invalid_cidr:{exc}")


def validate_ip(value: str, label: str) -> str:
    try:
        return str(ipaddress.ip_address(value))
    except ValueError as exc:
        fail(f"{label}:invalid_ip:{exc}")


def load_authority(path: Path) -> dict[str, Any]:
    try:
        authority = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"authority_load:{exc}")
    if authority.get("schema_version") != "codestra.stage6-inventory-authority.v1":
        fail("authority_schema")
    if authority.get("environment") != "staging" or authority.get("production") is not False:
        fail("authority_environment")
    if authority.get("managed_by") != "opentofu":
        fail("authority_manager")
    resources = authority.get("resources")
    expected_resources = {"runtime_server", "egress_server", "network", "runtime_firewall", "egress_firewall"}
    if not isinstance(resources, dict) or set(resources) != expected_resources:
        fail("authority_resources")

    network_cidr = validate_cidr(resources["network"]["cidr"], "network_cidr")
    subnet_cidr = validate_cidr(resources["network"]["subnet_cidr"], "staging_subnet_cidr")
    if not ipaddress.ip_network(subnet_cidr).subnet_of(ipaddress.ip_network(network_cidr)):
        fail("authority_subnet_outside_network")
    runtime_ip = validate_ip(resources["runtime_server"]["private_ip"], "private_ip")
    gateway_ip = validate_ip(resources["egress_server"]["private_ip"], "egress_gateway_private_ip")
    if runtime_ip == gateway_ip:
        fail("authority_duplicate_private_ip")
    subnet_network = ipaddress.ip_network(subnet_cidr)
    if (
        ipaddress.ip_address(runtime_ip) not in subnet_network
        or ipaddress.ip_address(gateway_ip) not in subnet_network
    ):
        fail("authority_private_ip_outside_subnet")

    list_fields = (
        "approved_ssh_key_ids",
        "approved_ssh_source_cidrs",
        "approved_egress_fqdns",
        "approved_egress_ports",
        "approved_ntp_fqdns",
        "known_internal_production_deny_cidrs",
    )
    for field in list_fields:
        if not isinstance(authority.get(field), list) or not authority[field]:
            fail(f"authority_{field}")
        if len(authority[field]) != len(set(authority[field])):
            fail(f"authority_{field}_duplicates")
    for cidr in authority["approved_ssh_source_cidrs"] + authority["known_internal_production_deny_cidrs"]:
        validate_cidr(cidr, "authority_cidr")
    if any(cidr in {"0.0.0.0/0", "::/0"} for cidr in authority["approved_ssh_source_cidrs"]):
        fail("authority_global_ssh_source")
    if sorted(authority["approved_egress_ports"]) != [80, 443]:
        fail("authority_egress_ports")
    policy = authority.get("evidence_policy") or {}
    require_equal(policy.get("cloud_api_methods"), ["GET"], "authority_cloud_api_methods")
    require_equal(policy.get("require_running_servers"), True, "authority_require_running_servers")
    require_equal(policy.get("require_exact_resource_match"), True, "authority_require_exact_resource_match")
    require_equal(policy.get("allow_unresolved_fields"), False, "authority_allow_unresolved_fields")
    return authority


def server_private_ip(server: dict[str, Any], network_id: int) -> str:
    attachments = [item for item in server.get("private_net", []) if item.get("network") == network_id]
    if len(attachments) != 1 or not attachments[0].get("ip"):
        fail(f"server_network_attachment:{server.get('name')}:found={len(attachments)}")
    return validate_ip(str(attachments[0]["ip"]), f"server_private_ip:{server.get('name')}")


def firewall_rules(firewall: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "direction": rule.get("direction"),
            "protocol": rule.get("protocol"),
            "port": rule.get("port"),
            "source_ips": sorted(rule.get("source_ips") or []),
            "destination_ips": sorted(rule.get("destination_ips") or []),
        }
        for rule in firewall.get("rules", [])
    ]


def _label_selector_matches(selector: str, labels: dict[str, Any]) -> bool:
    """Evaluate the narrow equality-only selector form used by this authority.

    Hetzner supports a broader selector language.  The inventory intentionally
    accepts only comma-separated ``key=value`` clauses so an unsupported or
    ambiguous selector fails closed instead of being treated as authorization.
    """

    clauses = [clause.strip() for clause in selector.split(",") if clause.strip()]
    if not clauses:
        return False
    normalized = {str(key): str(value) for key, value in labels.items()}
    for clause in clauses:
        if clause.count("=") != 1 or "!" in clause:
            return False
        key, expected = (part.strip() for part in clause.split("=", 1))
        if not key or not expected or normalized.get(key) != expected:
            return False
    return True


def firewall_applies_to_server(firewall: dict[str, Any], server: dict[str, Any]) -> bool:
    server_id = int(server["id"])
    for target in firewall.get("applied_to", []):
        if target.get("type") == "server" and int((target.get("server") or {}).get("id", -1)) == server_id:
            return True
        if target.get("type") == "label_selector":
            selector = str((target.get("label_selector") or {}).get("selector", ""))
            if _label_selector_matches(selector, server.get("labels", {})):
                return True
    return False


def require_rule(rules: list[dict[str, Any]], *, direction: str, protocol: str, port: str,
                 source_ips: list[str] | None = None, destination_ips: list[str] | None = None,
                 label: str) -> dict[str, Any]:
    matches = []
    for rule in rules:
        if rule["direction"] != direction or rule["protocol"] != protocol or str(rule["port"]) != port:
            continue
        if source_ips is not None and rule["source_ips"] != sorted(source_ips):
            continue
        if destination_ips is not None and rule["destination_ips"] != sorted(destination_ips):
            continue
        matches.append(rule)
    if len(matches) != 1:
        fail(f"firewall_rule:{label}:found={len(matches)}")
    return matches[0]


def _rule_key(rule: dict[str, Any]) -> tuple[Any, ...]:
    return (
        rule.get("direction"),
        rule.get("protocol"),
        str(rule.get("port")),
        tuple(sorted(rule.get("source_ips") or [])),
        tuple(sorted(rule.get("destination_ips") or [])),
    )


def require_exact_rule_set(actual: list[dict[str, Any]], expected: list[dict[str, Any]], label: str) -> None:
    actual_keys = sorted(_rule_key(rule) for rule in actual)
    expected_keys = sorted(_rule_key(rule) for rule in expected)
    if actual_keys != expected_keys:
        fail(f"firewall_rule_set:{label}:expected={expected_keys!r}:actual={actual_keys!r}")

