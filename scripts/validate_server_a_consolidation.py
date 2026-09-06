#!/usr/bin/env python3
"""Validate the September 1 inventory without making a new runtime claim."""
from __future__ import annotations

import csv
import hashlib
import ipaddress
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence/server-a-consolidation-20260901"
HEADER = ["name", "service", "project", "image", "image_id", "health",
          "restart_policy", "networks", "published_ports", "volumes", "revision"]
PORT = re.compile(r"(?P<first>[0-9]+)(?:-(?P<last>[0-9]+))?/(?P<protocol>tcp|udp|sctp)")
MEMBERS = {
    "MANIFEST.txt", "PRODUCTION-CONTAINER-INVENTORY.csv",
    "PRODUCTION-PORT-EXPOSURE.md", "PRODUCTION-READINESS-REPORT.md",
    "PRODUCTION-RUNTIME-INVENTORY.json", "PRODUCTION-SAFETY-SWITCH-INVENTORY.md",
    "API-INTEGRATION-MAP-AND-ROADMAP.md", "README.md",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def port_range(value: str) -> tuple[int, int, str]:
    match = PORT.fullmatch(value)
    require(match is not None, f"invalid port: {value!r}")
    first = int(match['first'])
    last = int(match['last'] or first)
    require(1 <= first <= last <= 65535, f"invalid port range: {value!r}")
    return first, last, match['protocol']


def parse_ports(value: str) -> tuple[list[str], list[str]]:
    """Retain Docker's complete host bindings; exposed-only entries stay separate."""
    published, exposed = [], []
    for item in filter(None, (part.strip() for part in value.split(','))):
        if '->' not in item:
            port_range(item)
            exposed.append(item)
            continue
        host, container = item.split('->')
        address, host_ports = host.rsplit(':', 1)
        ipaddress.ip_address(address.removeprefix('[').removesuffix(']'))
        first, last, protocol = port_range(container)
        host_first, host_last, _ = port_range(f'{host_ports}/{protocol}')
        require(last - first == host_last - host_first, 'unequal published port ranges')
        published.append(item)
    require(len(published) == len(set(published)), 'duplicate published binding')
    require(len(exposed) == len(set(exposed)), 'duplicate exposed port')
    return published, exposed


def read_port_snapshot(text: str) -> dict[str, tuple[list[str], list[str]]]:
    result = {}
    for line in text.splitlines():
        if line.startswith('Netid '):
            break  # The remaining historical ss output is a different table.
        if not line.strip() or line.startswith('#'):
            continue
        require('\t' in line, 'missing container/port delimiter')
        name, value = line.split('\t', 1)
        require(bool(name) and name not in result, f'duplicate or empty container: {name}')
        result[name] = parse_ports(value)
    require(bool(result), 'empty port snapshot')
    return result


def validate(directory: Path = EVIDENCE) -> None:
    ports = read_port_snapshot((directory / 'PRODUCTION-PORT-EXPOSURE.md').read_text())
    data = json.loads((directory / 'PRODUCTION-RUNTIME-INVENTORY.json').read_text())
    require(isinstance(data, list) and bool(data), 'empty or malformed JSON inventory')
    names = [row['name'] for row in data]
    require(len(set(names)) == len(names), 'duplicate JSON container')
    require(set(names) == set(ports), 'JSON/port snapshot container set mismatch')
    for row in data:
        published, exposed = ports[row['name']]
        require(row['published_ports'] == published, f"host bindings lost: {row['name']}")
        require(row['exposed_ports'] == exposed, f"exposed ports mismatch: {row['name']}")
    with (directory / 'PRODUCTION-CONTAINER-INVENTORY.csv').open(newline='') as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames == HEADER, 'missing or invalid CSV header')
        rows = list(reader)
    require(all(None not in row and all(v is not None for v in row.values()) for row in rows),
            'invalid CSV column count')
    csv_names = [row['name'] for row in rows]
    require(len(csv_names) == len(set(csv_names)), 'duplicate CSV container')
    require(csv_names == names, 'CSV records dropped, added or reordered')
    for row, original in zip(rows, data):
        require(row['published_ports'] == ';'.join(original['published_ports']),
                f"CSV host binding mismatch: {row['name']}")
        for key in ('service', 'project', 'image', 'image_id', 'health', 'restart_policy', 'revision'):
            require(row[key] == original[key], f'CSV/JSON field mismatch: {key}')
    seen = set()
    for line in (directory / 'SHA256SUMS').read_text().splitlines():
        digest, filename = line.split('  ', 1)
        require(filename in MEMBERS and filename not in seen, 'invalid/self/duplicate checksum member')
        require(re.fullmatch('[0-9a-f]{64}', digest) is not None, 'invalid checksum')
        require(hashlib.sha256((directory / filename).read_bytes()).hexdigest() == digest,
                f'checksum mismatch: {filename}')
        seen.add(filename)
    require(seen == MEMBERS, 'incomplete checksum manifest')
    print(f'SERVER_A_SNAPSHOT_SCHEMA=PASS containers={len(names)} runtime_revalidated=false')


if __name__ == '__main__':
    validate()
