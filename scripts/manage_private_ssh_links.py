#!/usr/bin/env python3
"""Provision private SSH communication for a dedicated unprivileged account."""
from __future__ import annotations

import argparse
import base64
import grp
import ipaddress
import json
import os
from pathlib import Path
import pwd
import re
import stat
import struct
import subprocess

USER = "codestra-link"
HOME = Path("/var/lib/codestra-link")
STATE = Path("/etc/codestra/ssh/server-links")
NAME = re.compile(r"[a-z][a-z0-9-]{0,31}\Z")
PRIVATE = tuple(ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def address(value):
    ip = ipaddress.ip_address(value)
    require(ip.version == 4 and any(ip in n for n in PRIVATE), "expected an RFC1918 IPv4 address")
    return str(ip)


def public_key(value):
    require(isinstance(value, str) and "\n" not in value and "\r" not in value, "expected one public key")
    parts = value.split()
    require(len(parts) in (2, 3) and parts[0] == "ssh-ed25519", "expected an Ed25519 public key")
    try:
        wire = base64.b64decode(parts[1], validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid public-key encoding") from exc
    prefix = struct.pack(">I", 11) + b"ssh-ed25519" + struct.pack(">I", 32)
    require(len(wire) == len(prefix) + 32 and wire.startswith(prefix), "invalid Ed25519 wire format")
    return " ".join(parts[:2])


def validate_manifest(value):
    require(isinstance(value, dict) and set(value) == {"schema", "node", "private_ip", "peers"}, "invalid manifest fields")
    require(value["schema"] == 1 and isinstance(value["node"], str) and NAME.fullmatch(value["node"]), "invalid node")
    own_ip = address(value["private_ip"])
    require(isinstance(value["peers"], list) and 1 <= len(value["peers"]) <= 16, "expected 1-16 explicit peers")
    peers, names, ips, keys = [], {value["node"]}, {own_ip}, set()
    for peer in value["peers"]:
        require(isinstance(peer, dict) and set(peer) == {"node", "private_ip", "public_key", "host_key"}, "invalid peer fields")
        name = peer["node"]
        require(isinstance(name, str) and NAME.fullmatch(name) and name not in names, "duplicate or invalid peer node")
        ip = address(peer["private_ip"])
        require(ip not in ips, "duplicate or self peer address")
        key = public_key(peer["public_key"])
        require(key not in keys, "each peer requires its own identity key")
        peers.append({"node": name, "private_ip": ip, "public_key": key, "host_key": public_key(peer["host_key"])})
        names.add(name)
        ips.add(ip)
        keys.add(key)
    return {"schema": 1, "node": value["node"], "private_ip": own_ip, "peers": sorted(peers, key=lambda p: p["node"])}


def render(value):
    manifest = validate_manifest(value)
    authorized, known, client = [], [], []
    for peer in manifest["peers"]:
        ip, node = peer["private_ip"], peer["node"]
        authorized.append(f'restrict,from="{ip}" {peer["public_key"]} codestra-link@{node}')
        known.append(f'{ip} {peer["host_key"]}')
        client.extend([
            f"Host codestra-{node}", f"    HostName {ip}", f"    BindAddress {manifest['private_ip']}",
            f"    User {USER}", f"    IdentityFile {HOME}/.ssh/id_ed25519",
            f"    UserKnownHostsFile {HOME}/.ssh/known_hosts", "    GlobalKnownHostsFile /dev/null",
            "    StrictHostKeyChecking yes", "    IdentitiesOnly yes", "    BatchMode yes",
            "    PasswordAuthentication no", "    KbdInteractiveAuthentication no",
            "    ClearAllForwardings yes", "    ForwardAgent no", "    RequestTTY no",
            "    ConnectTimeout 5", "    ConnectionAttempts 1", "",
        ])
    return {"authorized_keys": "\n".join(authorized) + "\n",
            "known_hosts": "\n".join(known) + "\n", "config": "\n".join(client)}


def run(*args):
    return subprocess.check_output(list(args), text=True).strip()


def safe_path(path):
    for parent in [path, *path.parents]:
        require(not parent.is_symlink(), f"refusing symlink: {parent}")


def root_directory(path, mode=0o755):
    safe_path(path)
    path.mkdir(parents=True, exist_ok=True, mode=mode)
    require(path.is_dir() and path.stat().st_uid == 0, f"directory is not root-owned: {path}")
    require(not path.stat().st_mode & 0o022, f"directory is writable by another account: {path}")
    path.chmod(mode)


def write_new(path, content, mode=0o600, uid=0, gid=0):
    safe_path(path)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(descriptor, "w") as handle:
        os.fchown(handle.fileno(), uid, gid)
        os.fchmod(handle.fileno(), mode)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def root_and_address(ip):
    require(os.geteuid() == 0, "root administrative access required")
    expected = address(ip)
    devices = json.loads(run("ip", "-j", "-4", "addr", "show"))
    require(any(a.get("local") == expected for d in devices for a in d.get("addr_info", [])), "target private IP mismatch")
    require("usepam yes" in run("/usr/sbin/sshd", "-T").splitlines(), "this account setup requires PAM-enabled SSH")


def identity(node, ip):
    require(NAME.fullmatch(node), "invalid node")
    root_and_address(ip)
    root_directory(STATE, 0o700)
    marker = STATE / "identity.json"
    expected = {"schema": 1, "node": node, "private_ip": address(ip)}
    try:
        account = pwd.getpwnam(USER)
    except KeyError:
        require(not HOME.exists() and not marker.exists(), "unowned existing account state")
        subprocess.run(["useradd", "--system", "--user-group", "--create-home", "--home-dir", str(HOME),
                        "--shell", "/bin/sh", "--comment", "Codestra private server communication", USER], check=True)
        account = pwd.getpwnam(USER)
        os.chown(HOME, 0, 0)
        HOME.chmod(0o755)
        write_new(marker, json.dumps(expected, sort_keys=True) + "\n")
    require(marker.is_file() and not marker.is_symlink(), "refusing to adopt an existing unmanaged account")
    require(json.loads(marker.read_text()) == expected, "existing identity differs from target")
    require(account.pw_uid != 0 and account.pw_dir == str(HOME) and account.pw_shell == "/bin/sh", "unexpected account attributes")
    require(grp.getgrgid(account.pw_gid).gr_name == USER, "unexpected primary group")
    require(set(os.getgrouplist(USER, account.pw_gid)) == {account.pw_gid}, "communication account has extra groups")
    require(run("passwd", "-S", USER).split()[1] == "L", "communication account password must remain locked")
    root_directory(HOME)
    root_directory(HOME / ".ssh")
    data = HOME / "data"
    safe_path(data)
    if not data.exists():
        data.mkdir(mode=0o700)
        os.chown(data, account.pw_uid, account.pw_gid)
    require(data.stat().st_uid == account.pw_uid and stat.S_IMODE(data.stat().st_mode) == 0o700, "unexpected transfer directory permissions")
    key = HOME / ".ssh/id_ed25519"
    safe_path(key)
    safe_path(Path(str(key) + ".pub"))
    if not key.exists():
        require(not Path(str(key) + ".pub").exists(), "orphaned public key")
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", f"codestra-link@{node}", "-f", str(key)], check=True)
        os.chown(key, account.pw_uid, account.pw_gid)
        key.chmod(0o600)
    require(key.stat().st_uid == account.pw_uid and stat.S_IMODE(key.stat().st_mode) == 0o600, "unexpected private-key ownership or mode")
    # Only public data is returned. The private key stays on the originating server.
    exported = public_key(run("ssh-keygen", "-y", "-P", "", "-f", str(key)))
    require(exported == public_key(Path(str(key) + ".pub").read_text().strip()), "identity public/private mismatch")
    return {**expected, "public_key": exported,
            "host_key": public_key(Path("/etc/ssh/ssh_host_ed25519_key.pub").read_text().strip())}


def authorize(path):
    safe_path(path)
    info = path.stat()
    require(info.st_uid == 0 and not info.st_mode & 0o077, "manifest must be root-owned and private")
    value = validate_manifest(json.loads(path.read_text()))
    own = identity(value["node"], value["private_ip"])
    require(all(p["public_key"] != own["public_key"] for p in value["peers"]), "peer identity duplicates the local key")
    contents = render(value)
    desired = json.dumps(value, sort_keys=True, indent=2) + "\n"
    previous = STATE / "applied.json"
    safe_path(previous)
    if previous.exists():
        require(previous.read_text() == desired, "peer changes require a separately reviewed rotation")
        for name, content in contents.items():
            target = HOME / ".ssh" / name
            safe_path(target)
            require(target.is_file() and target.stat().st_uid == 0 and stat.S_IMODE(target.stat().st_mode) == 0o644
                    and target.read_text() == content, f"managed SSH file drift: {name}")
        return {"status": "UNCHANGED", "node": value["node"], "peers": len(value["peers"])}
    for name in contents:
        target = HOME / ".ssh" / name
        safe_path(target)
        require(not target.exists(), f"refusing to replace existing SSH file: {name}")
    # Install client pins/config first and authorization last, then record exact applied inputs.
    for name in ("known_hosts", "config", "authorized_keys"):
        write_new(HOME / ".ssh" / name, contents[name], 0o644)
    write_new(previous, desired)
    return {"status": "INSTALLED", "node": value["node"], "peers": len(value["peers"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    init = sub.add_parser("identity")
    init.add_argument("--node", required=True)
    init.add_argument("--private-ip", required=True)
    auth = sub.add_parser("authorize")
    auth.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = identity(args.node, args.private_ip) if args.operation == "identity" else authorize(args.manifest)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"PRIVATE_SSH_LINKS_ERROR={exc}") from exc
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
