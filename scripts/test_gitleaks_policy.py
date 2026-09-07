#!/usr/bin/env python3
"""Test narrow exceptions using generated, non-secret negative controls only."""
from __future__ import annotations

import hashlib
import json
import re
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


def scan(binary: str, content: str, path: str, configured: bool = True) -> tuple[list[dict], list[str]]:
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
             "--log-level", "trace", "--config", str(config), "--report-format", "json", "--report-path", str(report), "."],
            cwd=source, capture_output=True, text=True, timeout=30,
        )
        if completed.returncode not in (0, 1) or not report.is_file():
            raise RuntimeError("Gitleaks did not produce a valid scan report")
        findings = json.loads(report.read_text(encoding="utf-8"))
        if not isinstance(findings, list):
            raise RuntimeError("Gitleaks report must be a list")
        if completed.returncode != (1 if findings else 0):
            raise RuntimeError("Gitleaks exit status contradicts its findings")
        # Emit decision metadata only, never finding values or unredacted logs.
        reasons = []
        for raw in completed.stderr.splitlines():
            line = re.sub(r"\x1b\[[0-9;]*m", "", raw)
            if "skipping" in line:
                reasons.append("skipping" + line.split("skipping", 1)[1].split("finding=", 1)[0])
        return findings, reasons


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: test_gitleaks_policy.py /path/to/gitleaks")
    binary = str(Path(sys.argv[1]).resolve(strict=True))
    fake = hashlib.sha256(b"non-secret local regression fixture").hexdigest()
    auth_command = "cu" + "rl --" + "user "
    numeric = auth_command + ":".join([str(65532)] * 2) + " https://example.invalid\n"
    synthetic = auth_command + "qa:" + fake + " https://example.invalid\n"
    token_field = "api_key: " + "gh" + "p_" + fake[:36] + "\n"
    # Keep digits while replacing hexadecimal letters, so the generic-key
    # control is neither a hexadecimal checksum nor an alphabetic word.
    generic_field = 'api_key: "' + fake.translate(str.maketrans("abcdef", "GHJKLM")) + '"\n'
    lock_path = "STAGE6-SOURCE-LOCK.yaml"
    resolved_path = "STAGE6-SOURCE-LOCK.RESOLVED.yaml"
    reviewed_revision = "7aef62a020c87ffcbf0fb" + "b2f8c4890a8e9d13098"
    refreshed = "    keycloak: " + reviewed_revision + "\n"
    cases = [
        ("reproduce original false positive", ARCHIVED, EVIDENCE, False, True),
        ("allow only archived Podman context", ARCHIVED, EVIDENCE, True, False),
        ("keep same numeric credentials detectable", numeric, EVIDENCE, True, True),
        ("keep other credentials detectable", synthetic, EVIDENCE, True, True),
        ("do not allow another evidence path", ARCHIVED, "other-evidence.md", True, True),
        ("allow typed Git SHA field", "keycloak_locked_sha: " + fake[:40] + "\n", lock_path, True, False),
        ("prove default token detection", token_field, lock_path, False, True),
        ("do not allow unrelated token family", token_field, lock_path, True, True),
        ("prove default generic-key detection", generic_field, lock_path, False, True),
        ("do not allow unrelated generic key", generic_field, lock_path, True, True),
        ("reproduce source-refresh SHA false positive", refreshed, lock_path, False, True),
        ("allow exact reviewed source-refresh SHA", refreshed, lock_path, True, False),
        ("allow exact reviewed resolved-refresh SHA", refreshed, resolved_path, True, False),
        ("allow exact reviewed resolved conflict SHA", "  keycloak_locked_sha: " + reviewed_revision + "\n", resolved_path, True, False),
        ("do not allow refreshed SHA in other files", refreshed, "other-lock.yaml", True, True),
        ("keep tokens detectable in resolved lock", token_field, resolved_path, True, True),
        ("keep generic keys detectable in resolved lock", generic_field, resolved_path, True, True),
    ]
    for name, content, path, configured, expected in cases:
        findings, reasons = scan(binary, content, path, configured)
        if bool(findings) != expected:
            for reason in reasons:
                print(reason)
            raise RuntimeError(f"secret-scan regression failed: {name}")
        print(f"PASS: {name}")
    print(f"GITLEAKS_POLICY_REGRESSIONS=PASS ({len(cases)} cases)")


if __name__ == "__main__":
    main()
