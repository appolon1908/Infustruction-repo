#!/usr/bin/env python3
"""Write deterministic SHA-256 checksums for the Stage 6 evidence package."""

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports/runtime-reconciliation/STAGE6-EVIDENCE-SHA256SUMS"
FILES = (
    ".github/workflows/validate-stage6-source-lock.yml",
    ".github/workflows/stage6-source-regressions.yml",
    "STAGE6-SOURCE-LOCK.yaml",
    "STAGE6-SOURCE-LOCK.RESOLVED.yaml",
    "STAGE6-RUNTIME-PROVENANCE.md",
    "STAGE6-SAFETY-CAPABILITY-MATRIX.yaml",
    "deploy/staging/intake-observability/compose.yaml",
    "deploy/staging/intake-observability/runtime-lock.v1.json",
    "deploy/staging/runtime-reconciliation/compose.legacy-application-safety-hold.yaml",
    "deploy/staging/runtime-reconciliation/compose.middleware-source-remediation.yaml",
    "deploy/staging/runtime-reconciliation/compose.n8n-safety-remediation.yaml",
    "deploy/staging/runtime-reconciliation/compose.odoo-source-remediation.yaml",
    "releases/STAGE6-STAGING-DEPLOYMENT-PLAN-2026-08-30.yaml",
    "reports/runtime-reconciliation/middleware-release-9152a0/release-manifest.v1.json",
    "reports/runtime-reconciliation/middleware-release-9152a0/release-manifest.v1.sigstore.json",
    "reports/runtime-reconciliation/STAGE6-RECONCILIATION-MATRIX.csv",
    "reports/runtime-reconciliation/STAGE6-SOURCE-LOCK-GATE-EVIDENCE-20260831.md",
    "scripts/build_stage6_reconciliation_matrix.py",
    "scripts/generate_stage6_evidence_checksums.py",
    "scripts/prepare_stage6_locked_checkouts.py",
    "scripts/resolve_stage6_source_lock.py",
    "scripts/validate_stage6_authority_heads.py",
    "scripts/validate_stage6_remediation.py",
    "scripts/validate_stage6_resolved_source_lock.py",
    "scripts/validate_stage6_source_lock.py",
    "scripts/validate_stage6_staging_plan.py",
    "scripts/verify_stage6_middleware_artifact.py",
    "tests/test_stage6_source_regressions.py",
)


def main() -> None:
    rows = []
    for relative in FILES:
        path = ROOT / relative
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append(f"{digest}  {relative}")
    OUTPUT.write_text("\n".join(rows) + "\n")
    package_digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    print(f"EVIDENCE_CHECKSUM_FILE={OUTPUT}")
    print(f"EVIDENCE_CHECKSUM_SHA256={package_digest}")


if __name__ == "__main__":
    main()
