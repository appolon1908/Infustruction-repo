#!/usr/bin/env python3
"""Collect redacted, read-only staging inventory evidence.

The collector never uses sudo, never reads process/container environments, never
reads logs or configuration contents, and never changes host, network, runtime,
or service state. Failed permission-sensitive probes are recorded as unavailable.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

CANONICAL_HOSTS = [
    "graf.codestra.media",
    "prom.codestra.media",
    "aler.codestra.media",
    "loki.codestra.media",
    "temp.codestra.media",
    "otel.codestra.media",
    "supe.codestra.media",
    "node.codestra.media",
    "cadv.codestra.media",
    "rdex.codestra.media",
    "blac.codestra.media",
    "allo.codestra.media",
    "bao.codestra.media",
]
PRIVATE_SERVICE_IDENTITIES = {
    "postgres-exporter": "postgres-exporter:9187",
}

DOCKER_CONTAINER_FORMAT = (
    '{"id":{{json .ID}},"image":{{json .Image}},"names":{{json .Names}},'
    '"state":{{json .State}},"status":{{json .Status}},'
    '"ports":{{json .Ports}},"networks":{{json .Networks}}}'
)
DOCKER_NETWORK_FORMAT = (
    '{"id":{{json .ID}},"name":{{json .Name}},"driver":{{json .Driver}},'
    '"scope":{{json .Scope}},"ipv6":{{json .IPv6}},"internal":{{json .Internal}}}'
)
DOCKER_VOLUME_FORMAT = (
    '{"name":{{json .Name}},"driver":{{json .Driver}},"scope":{{json .Scope}}}'
)


@dataclass(frozen=True)
class Probe:
    name: str
    argv: tuple[str, ...]
    timeout: int = 15


PROBES = (
    Probe("kernel", ("uname", "-a")),
    Probe("identity", ("id",)),
    Probe("filesystems", ("df", "-PT")),
    Probe("inodes", ("df", "-Pi")),
    Probe("listeners", ("ss", "-H", "-lntup")),
    Probe("time", ("timedatectl", "show", "--no-pager")),
    Probe("docker_version", ("docker", "version", "--format", "{{json .}}"), 30),
    Probe(
        "docker_containers",
        (
            "docker",
            "ps",
            "-a",
            "--format",
            DOCKER_CONTAINER_FORMAT,
        ),
        30,
    ),
    Probe("docker_networks", ("docker", "network", "ls", "--format", DOCKER_NETWORK_FORMAT), 30),
    Probe("docker_volumes", ("docker", "volume", "ls", "--format", DOCKER_VOLUME_FORMAT), 30),
    Probe(
        "systemd_services",
        (
            "systemctl",
            "list-units",
            "--type=service",
            "--all",
            "--no-pager",
            "--no-legend",
        ),
        30,
    ),
    Probe("caddy_version", ("caddy", "version")),
    Probe("ufw_status", ("ufw", "status", "verbose")),
    Probe("nftables_rules", ("nft", "--numeric", "list", "ruleset"), 30),
    Probe("iptables_rules", ("iptables-save",), 30),
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def minimal_environment() -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"),
        "LANG": "C",
        "LC_ALL": "C",
    }


def run_probe(probe: Probe) -> dict[str, Any]:
    executable = shutil.which(probe.argv[0], path=minimal_environment()["PATH"])
    if executable is None:
        return {
            "status": "unavailable",
            "reason": "command_not_found",
            "exitCode": None,
            "stdout": "",
            "stderr": "",
        }

    argv = (executable, *probe.argv[1:])
    try:
        completed = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=probe.timeout,
            env=minimal_environment(),
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "unavailable",
            "reason": "timeout",
            "exitCode": None,
            "stdout": "",
            "stderr": "",
        }
    except OSError as exc:
        return {
            "status": "unavailable",
            "reason": f"execution_error:{type(exc).__name__}",
            "exitCode": None,
            "stdout": "",
            "stderr": "",
        }

    status = "collected" if completed.returncode == 0 else "unavailable"
    reason = None if completed.returncode == 0 else "permission_or_runtime_unavailable"
    return {
        "status": status,
        "reason": reason,
        "exitCode": completed.returncode,
        "stdout": completed.stdout.rstrip(),
        "stderr": completed.stderr.rstrip(),
    }


def read_os_release() -> dict[str, str]:
    path = pathlib.Path("/etc/os-release")
    values: dict[str, str] = {}
    try:
        for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key] = value.strip().strip('"')
    except OSError:
        return {}
    return values


def resolve_host(host: str) -> dict[str, Any]:
    try:
        answers = socket.getaddrinfo(host, None, family=socket.AF_INET, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        return {"status": "unresolved", "addresses": [], "reason": str(exc)}
    addresses = sorted({answer[4][0] for answer in answers})
    return {"status": "resolved", "addresses": addresses, "reason": None}


def sha256_file(path: pathlib.Path) -> dict[str, Any]:
    resolved = path.expanduser()
    if resolved.is_symlink():
        return {"status": "rejected", "reason": "symlink", "sha256": None, "size": None}
    if not resolved.is_file():
        return {"status": "unavailable", "reason": "not_regular_file", "sha256": None, "size": None}
    digest = hashlib.sha256()
    try:
        with resolved.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        return {
            "status": "unavailable",
            "reason": f"read_error:{type(exc).__name__}",
            "sha256": None,
            "size": None,
        }
    return {
        "status": "collected",
        "reason": None,
        "sha256": f"sha256:{digest.hexdigest()}",
        "size": resolved.stat().st_size,
    }


def write_new_file(path: pathlib.Path, payload: bytes) -> None:
    path = path.expanduser().resolve(strict=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            path.unlink(missing_ok=True)
        finally:
            raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=pathlib.Path(f"/tmp/codestra-observability-readonly-inventory-{utc_now().replace(':', '')}.json"),
    )
    parser.add_argument(
        "--hash-file",
        action="append",
        default=[],
        type=pathlib.Path,
        help="Hash a known configuration file without recording its contents; may be repeated.",
    )
    args = parser.parse_args()

    inventory: dict[str, Any] = {
        "schemaVersion": "1.0",
        "evidenceType": "codestra-observability-readonly-server-inventory",
        "collectedAt": utc_now(),
        "host": socket.gethostname(),
        "collectionPolicy": {
            "readOnlyCommandsOnly": True,
            "sudoUsed": False,
            "processEnvironmentRead": False,
            "containerEnvironmentRead": False,
            "logsRead": False,
            "configurationContentsRecorded": False,
            "secretValuesRecorded": False,
            "serviceStateChanged": False,
            "networkStateChanged": False,
            "firewallStateChanged": False,
        },
        "osRelease": read_os_release(),
        "probes": {probe.name: run_probe(probe) for probe in PROBES},
        "dns": {host: resolve_host(host) for host in CANONICAL_HOSTS},
        "privateServiceIdentities": dict(PRIVATE_SERVICE_IDENTITIES),
        "configurationHashes": {
            str(path): sha256_file(path) for path in args.hash_file
        },
    }

    encoded = (json.dumps(inventory, indent=2, sort_keys=True) + "\n").encode("utf-8")
    write_new_file(args.output, encoded)
    checksum = hashlib.sha256(encoded).hexdigest()
    print(f"INVENTORY_PATH={args.output.expanduser().resolve(strict=False)}")
    print(f"INVENTORY_SHA256=sha256:{checksum}")
    print("INVENTORY_MODE=READ_ONLY_NO_SUDO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
