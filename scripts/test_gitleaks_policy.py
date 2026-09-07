#!/usr/bin/env python3
"""Exercise narrow false-positive exceptions against the pinned Gitleaks binary.

All credential-shaped negative controls are generated locally, never real secrets.
No service, provider, Docker daemon or deployment is contacted by these tests.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = "evidence/server-a-consolidation-20260901/PRODUCTION-SAFETY-SWITCH-INVENTORY.md"
PODMAN = (
    "/opt/codestra/backups/middleware-control-plane-20260815T073500Z/compose/"
    "telephony-gateway-schema-aware-ack-release-20260728/deployment-dropin-before.conf:7:"
    "ExecStart=/usr/bin/podman run --rm --name codestra-telephony-event-gateway-rc4 "
    "--pull=never --network=host --user=65532:65532"
)
ARCHIVED = (
    "/opt/codestra/backups/agent-desktop-baseline-mismatch/20260725T233810Z/verify_safe_state.sh:11:"
    "if grep -R -n -i -E --exclude='verify_safe_state.sh' "
    "'external_dial|SEND_EVENTS|activate.*workflow|requests\\.|httpx\\.|urllib\\.|curl .*vicidial|65\\.21\\.67\\.207' "
    '"$ROOT/scripts" "$ROOT/src"; then\n' + PODMAN + " --read-only --cap-drop=all\n"
)


def scan(binary: str, content: str, path: str, configured: bool = True) -> list[dict]:
    with tempfile.TemporaryDirectory(prefix="stage6-gitleaks-regression-") as directory:
        base = Path(directory)
        source = base / "source"
        target = source / path
        target.parent.mkdir(parents=True)
        target.write_text(content, encoding="utf-8")
        config = base / "policy.toml"
        if configured:
            shutil.copyfile(ROOT / ".gitleaks.toml", config)
        else:
            config.write_text("[extend]\nuseDefault = true\n", encoding="utf-8")
        report = base / "report.json"
        completed = subprocess.run(
            [binary, "dir", "--no-banner", "--redact", "--exit-code", "1",
             "--config", str(config), "--report-format", "json", "--report-path", str(report), "."],
            cwd=source, capture_output=True, text=True, timeout=30,
        )
        if completed.returncode not in (0, 1) or not report.is_file():
            raise RuntimeError("Gitleaks did not produce a valid scan report")
        findings = json.loads(report.read_text(encoding="utf-8"))
        if not isinstance(findings, list):
            raise RuntimeError("Gitleaks report must be a list")
        if completed.returncode != (1 if findings else 0):
            raise RuntimeError("Gitleaks exit status contradicts its findings")
        return findings


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: test_gitleaks_policy.py /path/to/gitleaks")
    binary = str(Path(sys.argv[1]).resolve(strict=True))
    fake = hashlib.sha256(b"non-secret local regression fixture").hexdigest()
    cases = [
        ("reproduce original false positive", ARCHIVED, EVIDENCE, False, True),
        ("allow only archived Podman context", ARCHIVED, EVIDENCE, True, False),
        ("keep same numeric curl credentials detectable", "curl --user " + "65532:65532 https://example.invalid\n", EVIDENCE, True, True),
        ("keep other curl credentials detectable", "curl --user qa:" + fake + " https://example.invalid\n", EVIDENCE, True, True),
        ("do not allow another evidence path", ARCHIVED, "other-evidence.md", True, True),
        ("allow typed Git SHA field", "keycloak_locked_sha: " + fake[:40] + "\n", "STAGE6-SOURCE-LOCK.yaml", True, False),
        ("do not allow unrelated key field", "api_key: " + fake + "\n", "STAGE6-SOURCE-LOCK.yaml", True, True),
    ]
    for name, content, path, configured, expected in cases:
        findings = scan(binary, content, path, configured)
        if bool(findings) != expected:
            raise RuntimeError(f"secret-scan regression failed: {name}")
        print(f"PASS: {name}")
    print(f"GITLEAKS_POLICY_REGRESSIONS=PASS ({len(cases)} cases)")


if __name__ == "__main__":
    main()
