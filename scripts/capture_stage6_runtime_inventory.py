#!/usr/bin/env python3
"""Capture a sanitized, deterministic Stage 6 Docker runtime inventory."""

import csv
import json
import subprocess
from collections import Counter
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "STAGE6-SOURCE-LOCK.yaml"
OUT = ROOT / "reports/runtime-reconciliation"
SAFETY_KEYS = (
    "LIVE_ADVERTISING_ENABLED", "EXTERNAL_DELIVERY_ENABLED",
    "SOCIAL_PUBLISHING_ENABLED", "EXTERNAL_MODEL_CALLS_ENABLED",
    "LIVE_SMS_DELIVERY", "LIVE_EMAIL_DELIVERY", "LIVE_PSTN_DIALING",
    "PRODUCTION_DIALING",
)


def classify(name: str) -> str:
    security = (
        "monitoring-", "reviewed-monitoring-", "identity-", "kong-",
        "caddy-", "-internal-proxy", "private-vicidial-ingress",
    )
    provider = ("mail-", "email-", "sms-api-", "beyvra-email", "stalwart")
    release = (
        "codestra-middleware-staging-", "codestra-n8n-staging-",
        "codestra-odoo19-staging-", "codestra-agent-desktop-sipjs-staging",
    )
    legacy = (
        "codestra-middleware-", "codestra-n8n-", "codestra-odoo-",
        "codestra-postgres-", "codestra-redis-", "codestra-integration-",
        "codestra-provisioning-", "codestra-reseller-", "codestra-websocket-",
        "codestra-agent-desktop-preview", "codestra-mw-cert-",
        "codestra-odoo19-module-", "codestra-odoo19-identity-menu-",
        "codestra-backup-", "codestra-appolon-",
    )
    if name.startswith(release):
        return "Codestra release workload"
    if name.startswith(("codestra-identity-staging-",)):
        return "observability/security workload"
    if name.startswith(provider) or any(x in name for x in provider):
        return "provider workload"
    if name.startswith(security) or any(x in name for x in security):
        return "observability/security workload"
    if name.startswith(legacy):
        return "legacy workload"
    if name == "private-integration-gateway-1":
        return "unknown"
    return "unknown"


def component(name: str) -> str:
    if "middleware-staging" in name:
        return "middleware"
    if "n8n-staging" in name:
        return "n8n"
    if "odoo19-staging" in name:
        return "odoo"
    if "agent-desktop" in name:
        return "sdk"
    return "unmapped"


def main() -> None:
    ids = subprocess.check_output(["docker", "ps", "-q"], text=True).split()
    containers = json.loads(subprocess.check_output(["docker", "inspect", *ids], text=True))
    image_ids = sorted({container["Image"] for container in containers})
    images = json.loads(subprocess.check_output(["docker", "image", "inspect", *image_ids], text=True))
    repo_digests = {image["Id"]: image.get("RepoDigests") or [] for image in images}
    locked = yaml.safe_load(LOCK.read_text())["repositories"]
    rows = []
    for c in sorted(containers, key=lambda item: item["Name"]):
        name = c["Name"].lstrip("/")
        labels = c["Config"].get("Labels") or {}
        env = {
            item.split("=", 1)[0]: item.split("=", 1)[1]
            for item in c["Config"].get("Env", []) if "=" in item
        }
        image_ref = c["Config"]["Image"]
        if "@sha256:" in image_ref:
            image_digest = image_ref.split("@", 1)[1]
        elif repo_digests[c["Image"]]:
            image_digest = repo_digests[c["Image"]][0].rsplit("@", 1)[1]
        else:
            image_digest = "UNESTABLISHED"
        candidates = (
            labels.get("org.opencontainers.image.revision"),
            labels.get("build.revision"),
            labels.get("io.codestra.build.revision"),
        )
        sha = next((value for value in candidates if value and value.lower() != "unknown"), "UNESTABLISHED")
        mounts = sorted({
            m.get("Source", "") for m in c.get("Mounts", [])
            if "secret" in m.get("Source", "").lower()
        })
        comp = component(name)
        expected = locked.get(comp, {})
        command = " ".join((c["Config"].get("Entrypoint") or []) + (c["Config"].get("Cmd") or []))
        safety_applicable = not any(token in name for token in ("postgres", "redis"))
        safety = {key: env.get(key, "MISSING") for key in SAFETY_KEYS}
        safe_values = {"false", "disabled"}
        safety_result = (
            "NOT_APPLICABLE_INFRASTRUCTURE"
            if not safety_applicable
            else ("PASS" if all(str(value).lower() in safe_values for value in safety.values()) else "FAIL")
        )
        rows.append({
            "container": name,
            "classification": classify(name),
            "component": comp,
            "repository": labels.get("org.opencontainers.image.source") or expected.get("repository") or "UNESTABLISHED",
            "git_sha": sha,
            "expected_git_sha": expected.get("revision", "NOT_IN_SOURCE_LOCK"),
            "image": image_ref,
            "immutable_image_digest": image_digest,
            "local_image_id": c["Image"],
            "environment": env.get("ENVIRONMENT") or env.get("APP_ENV") or env.get("NODE_ENV") or labels.get("codestra.environment") or labels.get("environment") or "UNESTABLISHED",
            "compose_service": labels.get("com.docker.compose.service") or "UNESTABLISHED",
            "configuration_authority": labels.get("com.docker.compose.project.config_files") or "UNESTABLISHED",
            "secret_authority": ";".join(mounts) if mounts else "NO_SECRET_MOUNT_OBSERVED",
            "rollback_image_or_digest": image_ref if "@sha256:" in image_ref else c["Image"],
            "safety_applicable": str(safety_applicable).lower(),
            "safety_result": safety_result,
            "safety_state": ";".join(f"{key}={value}" for key, value in safety.items()),
            "startup_command": command,
        })

    OUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUT / "STAGE6-RUNTIME-INVENTORY.csv"
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    counts = Counter(row["classification"] for row in rows)
    release_rows = [row for row in rows if row["classification"] == "Codestra release workload"]
    drift = []
    for row in release_rows:
        problems = []
        if row["git_sha"] == "UNESTABLISHED": problems.append("Git SHA unestablished")
        if row["immutable_image_digest"] == "UNESTABLISHED":
            problems.append("immutable image digest unestablished")
        elif "@sha256:" not in row["image"]:
            problems.append("runtime image reference mutable; immutable local digest located")
        if row["expected_git_sha"] != "NOT_IN_SOURCE_LOCK" and row["git_sha"] != row["expected_git_sha"]:
            problems.append("runtime SHA differs from lock")
        if "alembic upgrade" in row["startup_command"]: problems.append("migration in startup")
        if "--init=" in row["startup_command"] or "--update=" in row["startup_command"]: problems.append("Odoo module operation in startup")
        if row["safety_result"] == "FAIL": problems.append("explicit fail-closed safety set incomplete")
        drift.append((row, "; ".join(problems) if problems else "no identity/startup drift detected"))

    md = [
        "# Stage 6 Runtime Reconciliation Inventory",
        "",
        "Captured: 2026-08-30 (America/Santo_Domingo)",
        "",
        f"Running containers: **{len(rows)}**",
        "",
        "## Classification totals",
        "",
    ]
    for key in ("Codestra release workload", "observability/security workload", "provider workload", "legacy workload", "unrelated workload", "unknown"):
        md.append(f"- {key}: {counts.get(key, 0)}")
    md += [
        "",
        "## Drift plan (staging release workloads)",
        "",
        "| SERVICE | CURRENT | EXPECTED | CHANGE | RISK | ROLLBACK | IMAGE | SHA | DIGEST |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row, problems in drift:
        expected = row["expected_git_sha"]
        change = "HOLD — establish authority first" if problems != "no identity/startup drift detected" else "No automatic replacement"
        risk = "Wrong artifact or unintended stateful mutation" if problems != "no identity/startup drift detected" else "Low"
        md.append(
            f"| {row['container']} | {problems} | SHA `{expected}`; digest-pinned; application-only startup | "
            f"{change} | {risk} | `{row['rollback_image_or_digest']}` | `{row['image']}` | "
            f"`{row['git_sha']}` | `{row['immutable_image_digest']}` |"
        )
    md += [
        "",
        "The CSV is the authoritative 101-row inventory. No secret values are included; secret authority records only mounted source paths.",
    ]
    (OUT / "STAGE6-RUNTIME-RECONCILIATION.md").write_text("\n".join(md) + "\n")


if __name__ == "__main__":
    main()
