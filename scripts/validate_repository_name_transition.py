#!/usr/bin/env python3
"""Validate per-record repository identity and one-repository rename transitions."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = "config/repository-name-aliases.v1.json"
MANIFEST = ROOT / MANIFEST_PATH
AUTHORITY_PATH = ROOT / "scripts" / "validate_repository_name_aliases.py"
ACTIVE_REPOSITORY_FIELDS = (
    "repo",
    "repository",
    "repository_full_name",
    "principal_repository",
)
ALLOWED_STATUS_TRANSITIONS = {
    ("PREPARED_NOT_RENAMED", "RENAMED_VERIFIED"),
    ("RENAMED_VERIFIED", "ROLLED_BACK_VERIFIED"),
    ("ROLLED_BACK_VERIFIED", "RENAMED_VERIFIED"),
}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_authority() -> Any:
    spec = importlib.util.spec_from_file_location(
        "repository_name_alias_authority",
        AUTHORITY_PATH,
    )
    if spec is None or spec.loader is None:
        fail("repository-name authority module cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_json_text(text: str, source: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {source}: {exc}")
    if not isinstance(value, dict):
        fail(f"JSON root must be an object: {source}")
    return value


def iter_dicts(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_dicts(child)


def repository_id(record: dict[str, Any]) -> int | None:
    value = record.get("github_repository_id", record.get("repository_id"))
    return value if isinstance(value, int) else None


def validate_record_repository_fields(
    document: Any,
    operational_by_id: dict[int, str],
    source: str,
) -> None:
    """Reject any recognized repository field that conflicts with its stable ID."""

    for record in iter_dicts(document):
        stable_id = repository_id(record)
        if stable_id not in operational_by_id:
            continue
        expected = operational_by_id[stable_id]

        values = {
            field: value
            for field, value in record.items()
            if (
                field == "current_repository" or field in ACTIVE_REPOSITORY_FIELDS
            )
            and isinstance(value, str)
        }
        if not values:
            fail(
                f"{source} binds repository ID {stable_id} without a recognized "
                "repository field"
            )

        conflicts = {
            field: value for field, value in values.items() if value != expected
        }
        if conflicts:
            rendered = ", ".join(
                f"{field}={value}" for field, value in sorted(conflicts.items())
            )
            fail(
                f"{source} binds repository ID {stable_id} to conflicting "
                f"repository fields ({rendered}); expected {expected}"
            )


def mapping_statuses(document: dict[str, Any]) -> dict[int, str]:
    mappings = document.get("mappings")
    if not isinstance(mappings, list):
        fail("repository alias mappings must be a list")
    result: dict[int, str] = {}
    for item in mappings:
        if not isinstance(item, dict):
            fail("repository alias mapping must be an object")
        stable_id = item.get("repository_id")
        status = item.get("status")
        if not isinstance(stable_id, int) or not isinstance(status, str):
            fail("repository alias mapping ID/status is invalid")
        if stable_id in result:
            fail(f"duplicate repository alias ID: {stable_id}")
        result[stable_id] = status
    return result


def changed_status_ids(
    base: dict[str, Any],
    current: dict[str, Any],
) -> set[int]:
    before = mapping_statuses(base)
    after = mapping_statuses(current)
    if set(before) != set(after):
        fail("cutover PR may not add or remove governed repository IDs")
    return {
        stable_id
        for stable_id in before
        if before[stable_id] != after[stable_id]
    }


def validate_one_repository_transition(
    base: dict[str, Any],
    current: dict[str, Any],
) -> None:
    before = mapping_statuses(base)
    after = mapping_statuses(current)
    changed = changed_status_ids(base, current)
    if len(changed) > 1:
        fail(
            "one_repository_per_cutover violation: status changed for repository "
            f"IDs {sorted(changed)}"
        )

    for stable_id in changed:
        edge = (before[stable_id], after[stable_id])
        if edge not in ALLOWED_STATUS_TRANSITIONS:
            fail(
                "unsupported repository status transition for repository "
                f"ID {stable_id}: {edge[0]} -> {edge[1]}"
            )


def base_manifest(base_ref: str) -> dict[str, Any] | None:
    result = subprocess.run(
        ["git", "show", f"{base_ref}:{MANIFEST_PATH}"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return load_json_text(result.stdout, f"{base_ref}:{MANIFEST_PATH}")


def validate() -> None:
    authority = load_authority()
    current = load_json_text(MANIFEST.read_text(encoding="utf-8"), MANIFEST_PATH)
    operational_by_id = authority.operational_repository_map(current)

    sources = authority.operational_sources()
    # Re-run the authority module's record-scoped checks for both JSON and
    # YAML/TOML/HCL so conflicting fields cannot hide behind one valid value.
    authority.validate_repository_id_current_name_pairing(
        sources,
        operational_by_id,
    )

    for path in sources:
        if path.suffix.lower() != ".json":
            continue
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            fail(f"invalid operational JSON in {path.relative_to(ROOT)}: {exc}")
        validate_record_repository_fields(
            document,
            operational_by_id,
            str(path.relative_to(ROOT)),
        )

    base_ref = os.environ.get("REPOSITORY_NAME_BASE_SHA", "").strip()
    if not base_ref:
        return
    base = base_manifest(base_ref)
    if base is None:
        # Bootstrap PR: the base does not yet contain the authority manifest.
        if set(mapping_statuses(current).values()) != {"PREPARED_NOT_RENAMED"}:
            fail("bootstrap authority must introduce only prepared mappings")
        return
    validate_one_repository_transition(base, current)


def main() -> None:
    validate()
    print("Repository record and one-cutover transition authority: PASS")


if __name__ == "__main__":
    main()
