#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
COLLECTOR_PATH = SCRIPTS / "collect_stage6_hetzner_inventory.py"
spec = importlib.util.spec_from_file_location("stage6_inventory", COLLECTOR_PATH)
assert spec and spec.loader
collector = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = collector
spec.loader.exec_module(collector)


def rule(direction: str, protocol: str, port: str, *, source=None, destination=None):
    return {
        "direction": direction,
        "protocol": protocol,
        "port": port,
        "source_ips": source or [],
        "destination_ips": destination or [],
    }


def fixture_raw() -> dict:
    common = {"environment": "staging", "production": "false", "klyrow": "false", "postal": "false", "managed-by": "opentofu"}
    runtime_labels = {**common, "role": "stage6-runtime"}
    egress_labels = {**common, "role": "stage6-egress-gateway"}
    ssh = ["179.53.46.159/32"]
    runtime_ip = "10.250.6.10"
    gateway_ip = "10.250.6.2"
    return {
        "locations": [{"id": 1, "name": "hel1", "city": "Helsinki", "country": "FI"}],
        "servers": [
            {
                "id": 164156679,
                "name": "codestra-stage6-staging-01",
                "status": "running",
                "labels": runtime_labels,
                "server_type": {"name": "cx43"},
                "image": {"name": "ubuntu-24.04"},
                "backup_window": "22-02",
                "protection": {"delete": True, "rebuild": True},
                "datacenter": {"location": {"name": "hel1"}},
                "public_net": {"ipv4": {"ip": "192.0.2.10"}, "ipv6": None},
                "private_net": [{"network": 12602071, "ip": runtime_ip, "alias_ips": []}],
            },
            {
                "id": 164156658,
                "name": "codestra-stage6-egress-01",
                "status": "running",
                "labels": egress_labels,
                "server_type": {"name": "cx23"},
                "image": {"name": "ubuntu-24.04"},
                "backup_window": "22-02",
                "protection": {"delete": True, "rebuild": True},
                "datacenter": {"location": {"name": "hel1"}},
                "public_net": {"ipv4": {"ip": "192.0.2.20"}, "ipv6": None},
                "private_net": [{"network": 12602071, "ip": gateway_ip, "alias_ips": []}],
            },
        ],
        "networks": [
            {
                "id": 12602071,
                "name": "codestra-stage6-staging-net",
                "labels": common,
                "ip_range": "10.250.0.0/16",
                "subnets": [{"type": "cloud", "ip_range": "10.250.6.0/24", "network_zone": "eu-central", "gateway": "10.250.0.1"}],
                "routes": [],
            }
        ],
        "ssh_keys": [{"id": 118172836, "name": "codestra-stage6-admin", "labels": {"stage6": "approved"}}],
        "firewalls": [
            {
                "id": 11551910,
                "name": "codestra-stage6-staging-01-deny-default",
                "labels": runtime_labels,
                "applied_to": [{"type": "server", "server": {"id": 164156679}}],
                "rules": [
                    rule("in", "tcp", "22", source=ssh),
                    rule("out", "tcp", "3128", destination=[gateway_ip + "/32"]),
                    rule("out", "tcp", "53", destination=[gateway_ip + "/32"]),
                    rule("out", "udp", "53", destination=[gateway_ip + "/32"]),
                    rule("out", "udp", "123", destination=[gateway_ip + "/32"]),
                    rule("out", "tcp", "1-65535", destination=["10.250.6.0/24"]),
                ],
            },
            {
                "id": 11551911,
                "name": "codestra-stage6-egress-01-boundary",
                "labels": egress_labels,
                "applied_to": [{"type": "server", "server": {"id": 164156658}}],
                "rules": [
                    rule("in", "tcp", "22", source=ssh),
                    rule("in", "tcp", "3128", source=[runtime_ip + "/32"]),
                    rule("in", "tcp", "53", source=[runtime_ip + "/32"]),
                    rule("in", "udp", "53", source=[runtime_ip + "/32"]),
                    rule("in", "udp", "123", source=[runtime_ip + "/32"]),
                    rule("out", "tcp", "80", destination=["0.0.0.0/0"]),
                    rule("out", "tcp", "443", destination=["0.0.0.0/0"]),
                    rule("out", "tcp", "53", destination=["0.0.0.0/0"]),
                    rule("out", "udp", "53", destination=["0.0.0.0/0"]),
                    rule("out", "udp", "123", destination=["0.0.0.0/0"]),
                ],
            },
        ],
    }


class ResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.authority = collector.load_authority(ROOT / "config" / "stage6-inventory-authority.v1.json")

    def test_resolves_all_fields_from_exact_live_and_git_authority(self):
        result = collector.resolve_authority(fixture_raw(), self.authority)
        self.assertTrue(result["complete"])
        self.assertEqual(result["unresolved"], [])
        self.assertEqual(set(result["fields"]), set(collector.FIELDS))
        self.assertEqual(result["fields"]["private_ip"], "10.250.6.10")
        self.assertEqual(result["fields"]["approved_egress_ports"], [80, 443])
        self.assertEqual(result["resource_ids"]["runtime_server_id"], 164156679)
        self.assertEqual(result["cloud_api_methods"], ["GET"])
        self.assertFalse(result["cloud_mutation"])
        self.assertFalse(result["production_changed"])

    def test_duplicate_runtime_authority_fails_closed(self):
        raw = fixture_raw()
        raw["servers"].append(copy.deepcopy(raw["servers"][0]))
        with self.assertRaisesRegex(collector.InventoryError, "runtime_server:expected_exactly_one"):
            collector.resolve_authority(raw, self.authority)

    def test_stopped_runtime_fails_closed(self):
        raw = fixture_raw()
        raw["servers"][0]["status"] = "off"
        with self.assertRaisesRegex(collector.InventoryError, "runtime_status"):
            collector.resolve_authority(raw, self.authority)

    def test_private_ip_drift_fails_closed(self):
        raw = fixture_raw()
        raw["servers"][0]["private_net"][0]["ip"] = "10.250.6.11"
        with self.assertRaisesRegex(collector.InventoryError, "runtime_private_ip"):
            collector.resolve_authority(raw, self.authority)

    def test_ssh_firewall_drift_fails_closed(self):
        raw = fixture_raw()
        raw["firewalls"][0]["rules"][0]["source_ips"] = ["0.0.0.0/0"]
        with self.assertRaisesRegex(collector.InventoryError, "runtime_ssh"):
            collector.resolve_authority(raw, self.authority)

    def test_missing_approved_ssh_key_fails_closed(self):
        raw = fixture_raw()
        raw["ssh_keys"] = []
        with self.assertRaisesRegex(collector.InventoryError, "approved_ssh_keys_missing"):
            collector.resolve_authority(raw, self.authority)

    def test_extra_firewall_rule_fails_closed(self):
        raw = fixture_raw()
        raw["firewalls"][0]["rules"].append(rule("in", "tcp", "443", source=["0.0.0.0/0"]))
        with self.assertRaisesRegex(collector.InventoryError, "firewall_rule_set:runtime"):
            collector.resolve_authority(raw, self.authority)

    def test_server_type_drift_fails_closed(self):
        raw = fixture_raw()
        raw["servers"][0]["server_type"]["name"] = "cx53"
        with self.assertRaisesRegex(collector.InventoryError, "runtime_server_type"):
            collector.resolve_authority(raw, self.authority)

    def test_missing_server_protection_fails_closed(self):
        raw = fixture_raw()
        raw["servers"][0]["protection"]["delete"] = False
        with self.assertRaisesRegex(collector.InventoryError, "runtime_delete_protection"):
            collector.resolve_authority(raw, self.authority)

    def test_unsupported_label_selector_does_not_authorize_firewall(self):
        raw = fixture_raw()
        raw["firewalls"][0]["applied_to"] = [
            {"type": "label_selector", "label_selector": {"selector": "environment in (staging)"}}
        ]
        with self.assertRaisesRegex(collector.InventoryError, "runtime_firewall_not_applied"):
            collector.resolve_authority(raw, self.authority)

    def test_exact_label_selector_can_authorize_firewall_attachment(self):
        raw = fixture_raw()
        raw["firewalls"][0]["applied_to"] = [
            {"type": "label_selector", "label_selector": {"selector": "environment=staging,role=stage6-runtime"}}
        ]
        result = collector.resolve_authority(raw, self.authority)
        self.assertTrue(result["complete"])

    def test_sanitized_inventory_redacts_sensitive_label_values(self):
        raw = fixture_raw()
        raw["servers"][0]["labels"]["api_token"] = "do-not-export"
        inventory = collector.sanitized_inventory(raw)
        runtime = next(item for item in inventory["servers"] if item["name"] == "codestra-stage6-staging-01")
        self.assertEqual(runtime["labels"]["api_token"], "REDACTED")
        self.assertNotIn("do-not-export", json.dumps(inventory))


if __name__ == "__main__":
    unittest.main()
