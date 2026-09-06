#!/usr/bin/env python3
"""Collect and reconcile a narrow, sanitized Stage 6 Hetzner inventory.

Only allowlisted HTTP GET requests are used. Resolution succeeds only when
live cloud metadata agrees exactly with the committed Stage 6 authority.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from stage6_inventory_common import (
    COLLECTIONS, DEFAULT_AUTHORITY, FIELDS, InventoryError, get_collection,
    load_authority,
)
from stage6_inventory_output import sanitized_inventory, write_new
from stage6_inventory_resolution import resolve_authority


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--authority", type=Path, default=DEFAULT_AUTHORITY)
    args = parser.parse_args()
    token = os.environ.get("HETZNER_CLOUD_TOKEN", "")
    if not token:
        raise SystemExit("INVENTORY_ERROR=missing_token")
    try:
        authority = load_authority(args.authority)
        raw = {name: get_collection(token, name) for name in COLLECTIONS}
        resolution = resolve_authority(raw, authority)
        inventory = sanitized_inventory(raw)
        args.output_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
        write_new(args.output_dir / "hetzner-inventory.sanitized.json", inventory)
        write_new(args.output_dir / "stage6-input-resolution.json", resolution)
    except InventoryError as exc:
        raise SystemExit(f"INVENTORY_ERROR={exc}") from exc
    print("HETZNER_INVENTORY=PASS")
    print("STAGE6_AUTHORITY_MATCH=PASS")
    print("UNRESOLVED_NON_SECRET_FIELDS=NONE")
    print("API_METHODS=GET_ONLY")
    print("CLOUD_MUTATION=NO")
    print("PRODUCTION_CHANGED=NO")


if __name__ == "__main__":
    main()
