#!/usr/bin/env python3
"""Build the sanitized Stage 6 reconciliation matrix from inventory and lock."""

import csv
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "reports/runtime-reconciliation/STAGE6-RUNTIME-INVENTORY.csv"
LOCK = ROOT / "STAGE6-SOURCE-LOCK.yaml"
OUTPUT = ROOT / "reports/runtime-reconciliation/STAGE6-RECONCILIATION-MATRIX.csv"


def main() -> None:
    inventory = {
        row["container"]: row
        for row in csv.DictReader(INVENTORY.open())
        if row["classification"] == "Codestra release workload"
    }
    lock = yaml.safe_load(LOCK.read_text())
    workloads = lock["runtime_workloads"]
    if set(inventory) != set(workloads):
        raise SystemExit("inventory/lock workload mismatch")

    fields = [
        "SERVICE", "CURRENT_IMAGE", "CURRENT_DIGEST", "CURRENT_GIT_SHA",
        "EXPECTED_REPOSITORY", "EXPECTED_SHA", "EXPECTED_DIGEST",
        "SAFETY_STATE", "MIGRATION_MODEL", "ROLLBACK_DIGEST", "ACTION", "RISK",
    ]
    rows = []
    for name in sorted(workloads):
        current = inventory[name]
        target = workloads[name]
        command = current["startup_command"]
        if "alembic upgrade" in command:
            migration = "FAIL:migration-in-normal-startup"
        elif "--init=" in command or "--update=" in command:
            migration = "FAIL:module-operation-in-normal-startup"
        elif "postgres" in name or "redis" in name:
            migration = "NOT_APPLICABLE_INFRASTRUCTURE"
        else:
            migration = "application-only-or-no-schema-operation-observed"
        action = target["disposition"]
        rows.append({
            "SERVICE": name,
            "CURRENT_IMAGE": current["image"],
            "CURRENT_DIGEST": target["image_digest"],
            "CURRENT_GIT_SHA": target.get("git_sha", "UNVERIFIED"),
            "EXPECTED_REPOSITORY": target.get("expected_repository") or target.get("workflow_repository") or target.get("addons_repository") or target["repository"],
            "EXPECTED_SHA": target.get("expected_sha") or target.get("workflow_sha") or target.get("addons_sha") or target.get("git_sha", "UNVERIFIED"),
            "EXPECTED_DIGEST": target.get("expected_digest") or target["image_digest"],
            "SAFETY_STATE": current["safety_state"] if current["safety_applicable"] == "true" else "NOT_APPLICABLE_INFRASTRUCTURE",
            "MIGRATION_MODEL": migration,
            "ROLLBACK_DIGEST": target["rollback_digest"],
            "ACTION": action,
            "RISK": "HIGH:freeze-no-automatic-replacement" if "UNVERIFIED" in action else "MEDIUM:backup-and-readback-required",
        })
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
