#!/usr/bin/env python3
import base64
import copy
import importlib.util
import os
from pathlib import Path
import struct
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / "scripts/manage_private_ssh_links.py"
SPEC = importlib.util.spec_from_file_location("private_ssh_links", PATH)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def key(byte):
    wire = struct.pack(">I", 11) + b"ssh-ed25519" + struct.pack(">I", 32) + bytes([byte]) * 32
    return "ssh-ed25519 " + base64.b64encode(wire).decode()


def manifest():
    return {"schema": 1, "node": "core", "private_ip": "10.20.0.1", "peers": [
        {"node": "web", "private_ip": "10.20.0.2", "public_key": key(1), "host_key": key(2)},
        {"node": "providers", "private_ip": "10.20.0.3", "public_key": key(3), "host_key": key(4)},
    ]}


class PrivateSSHLinksTests(unittest.TestCase):
    def test_authorization_restricts_each_identity_to_its_source(self):
        rendered = module.render(manifest())
        lines = rendered["authorized_keys"].splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(all(line.startswith('restrict,from="10.20.0.') for line in lines))
        self.assertIn(f'from="10.20.0.2" {key(1)}', rendered["authorized_keys"])
        self.assertIn(f'from="10.20.0.3" {key(3)}', rendered["authorized_keys"])

    def test_client_pins_host_keys_and_uses_no_password_or_forwarding(self):
        rendered = module.render(manifest())
        self.assertIn("10.20.0.2 " + key(2), rendered["known_hosts"])
        for directive in ("StrictHostKeyChecking yes", "IdentitiesOnly yes", "BatchMode yes",
                          "PasswordAuthentication no", "KbdInteractiveAuthentication no",
                          "ClearAllForwardings yes", "ForwardAgent no", "RequestTTY no",
                          "User codestra-link", "BindAddress 10.20.0.1"):
            self.assertEqual(rendered["config"].count(directive), 2)
        self.assertNotIn("User root", rendered["config"])

    def test_public_loopback_multicast_and_unspecified_addresses_fail(self):
        for ip in ("203.0.113.1", "127.0.0.1", "0.0.0.0", "::1", "224.0.0.1"):
            with self.subTest(ip=ip):
                value = manifest()
                value["peers"][0]["private_ip"] = ip
                with self.assertRaises(ValueError):
                    module.render(value)

    def test_duplicate_self_and_shared_identity_peers_fail(self):
        for field, invalid in (("node", "core"), ("private_ip", "10.20.0.1"),
                               ("node", "providers"), ("private_ip", "10.20.0.3"),
                               ("public_key", key(3))):
            with self.subTest(field=field, invalid=invalid):
                value = manifest()
                value["peers"][0][field] = invalid
                with self.assertRaises(ValueError):
                    module.render(value)

    def test_configuration_injection_fails(self):
        for field, invalid in (("node", "web\nProxyCommand bad"), ("private_ip", '10.20.0.2",command="bad'),
                               ("public_key", key(1) + "\n" + key(3)),
                               ("host_key", key(2) + "\nHost *")):
            with self.subTest(field=field):
                value = manifest()
                value["peers"][0][field] = invalid
                with self.assertRaises(ValueError):
                    module.render(value)

    def test_invalid_public_key_wire_format_fails(self):
        invalid = ("ssh-rsa AAAA", "ssh-ed25519 !!!", "ssh-ed25519 AAAA",
                   "ssh-ed25519 " + base64.b64encode(b"x" * 51).decode())
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.public_key(value)

    def test_unknown_fields_and_unbounded_peer_lists_fail(self):
        values = []
        value = manifest()
        value["private_key"] = "must-not-be-accepted"
        values.append(value)
        value = manifest()
        value["peers"][0]["command"] = "bad"
        values.append(value)
        value = manifest()
        value["peers"] = []
        values.append(value)
        value = manifest()
        value["peers"] *= 9
        values.append(value)
        for value in values:
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.render(value)

    def test_render_does_not_mutate_input_and_has_stable_order(self):
        value = manifest()
        before = copy.deepcopy(value)
        first = module.render(value)
        self.assertEqual(value, before)
        value["peers"].reverse()
        self.assertEqual(module.render(value), first)

    def test_requested_modes_are_independent_of_administrator_umask(self):
        for mask in (0o027, 0o077, 0o777):
            for mode in (0o600, 0o644):
                with self.subTest(umask=oct(mask), mode=oct(mode)), tempfile.TemporaryDirectory() as tmp:
                    target = Path(tmp) / "managed"
                    previous = os.umask(mask)
                    try:
                        module.write_new(target, "data", mode=mode, uid=os.getuid(), gid=os.getgid())
                    finally:
                        os.umask(previous)
                    self.assertEqual(target.stat().st_mode & 0o777, mode)

    def test_write_refuses_existing_files_and_symlinked_parents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            existing = root / "existing"
            existing.write_text("preserved")
            with self.assertRaises(FileExistsError):
                module.write_new(existing, "replacement", uid=os.getuid(), gid=os.getgid())
            self.assertEqual(existing.read_text(), "preserved")
            (root / "real").mkdir()
            (root / "link").symlink_to(root / "real", target_is_directory=True)
            with self.assertRaises(ValueError):
                module.write_new(root / "link" / "new", "rejected", uid=os.getuid(), gid=os.getgid())
            self.assertFalse((root / "real" / "new").exists())


if __name__ == "__main__":
    unittest.main()
