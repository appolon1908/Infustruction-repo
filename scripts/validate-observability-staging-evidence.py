#!/usr/bin/env python3
"""Validate a Codestra observability staging evidence record."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVIDENCE = ROOT / "release" / "templates" / "observability-staging-evidence.v1.json"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
EXPECTED = [
    ("grafana", "appolon1908-hue/Codestra-Grafana-"),
    ("prometheus", "appolon1908-hue/Codestra-Prometheus"),
    ("alertmanager", "appolon1908-hue/Codestra-Alertmanager"),
    ("loki", "appolon1908-hue/Codestra-Loki"),
    ("tempo", "appolon1908-hue/Codestra-Tempo"),
    ("opentelemetry", "appolon1908-hue/Codestra-Telemetry"),
    ("superset", "appolon1908-hue/Superset"),
    ("node-exporter", "appolon1908-hue/Codestra-Node-Exporter"),
    ("cadvisor", "appolon1908-hue/Codestra-cAdvisor"),
    ("postgres-exporter", "appolon1908-hue/Codestra-Postgres-Exporter"),
    ("redis-exporter", "appolon1908-hue/Codestra-Redis-Exporter"),
    ("blackbox-exporter", "appolon1908-hue/Codestra-Blackbox-Exporter"),
    ("alloy", "appolon1908-hue/Codestra-Alloy"),
    ("openbao", "appolon1908-hue/Codestra-OpenBao"),
]
COMPONENT_EVIDENCE_FIELDS = {
    "sourceSha",
    "imageReference",
    "imageDigest",
    "sbomDigest",
    "provenanceDigest",
    "signatureEvidenceDigest",
    "configurationChecksum",
    "vulnerabilityEvidenceDigest",
    "sourceCiEvidenceDigest",
}
SAFETY_FIELDS = {
    "serverInstallationAllowed",
    "containerOrSystemdStartAllowed",
    "firewallMutationAllowed",
    "caddyReloadAllowed",
    "tlsServiceActivationAllowed",
    "keycloakLiveApplyAllowed",
    "clientSecretInstallationAllowed",
    "openBaoInitializationAllowed",
    "openBaoUnsealAllowed",
    "publicNativePortsAllowed",
    "productionTrafficAllowed",
}


class ValidationError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise ValidationError(message)


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot parse evidence: {exc}")
    if not isinstance(value, dict):
        fail("evidence must contain a JSON object")
    return value


def require_digest(value: Any, field: str) -> None:
    if not DIGEST.fullmatch(str(value or "")):
        fail(f"{field} must be a sha256 digest")


def validate_components(evidence: dict[str, Any], template: bool) -> bool:
    components = evidence.get("components")
    if not isinstance(components, list) or len(components) != len(EXPECTED):
        fail("exactly fourteen component evidence records are required")
    if [item.get("component") for item in components] != [item[0] for item in EXPECTED]:
        fail("component order or set mismatch")

    complete = True
    for item, (component, repository) in zip(components, EXPECTED, strict=True):
        if item.get("repository") != repository:
            fail(f"{component}: repository mismatch")
        expected_fields = {"component", "repository"} | COMPONENT_EVIDENCE_FIELDS
        if set(item) != expected_fields:
            fail(f"{component}: evidence field set mismatch")

        values = [item.get(field) for field in COMPONENT_EVIDENCE_FIELDS]
        if template:
            if any(value is not None for value in values):
                fail(f"{component}: template evidence fields must remain null")
            complete = False
            continue

        if not SHA40.fullmatch(str(item.get("sourceSha", ""))):
            fail(f"{component}: sourceSha must be a full lowercase Git SHA")
        image_reference = item.get("imageReference")
        if not isinstance(image_reference, str) or "@sha256:" not in image_reference:
            fail(f"{component}: immutable imageReference is required")
        if ":latest" in image_reference:
            fail(f"{component}: latest is forbidden")
        require_digest(item.get("imageDigest"), f"{component}.imageDigest")
        if not image_reference.endswith(item["imageDigest"]):
            fail(f"{component}: imageReference and imageDigest differ")
        for field in COMPONENT_EVIDENCE_FIELDS - {"sourceSha", "imageReference", "imageDigest"}:
            require_digest(item.get(field), f"{component}.{field}")
    return complete


def validate_server_inventory(evidence: dict[str, Any], template: bool) -> bool:
    value = evidence.get("serverInventory")
    expected = {"status", "evidenceDigest", "collectorSourceSha", "secretValuesRecorded", "sudoUsed"}
    if not isinstance(value, dict) or set(value) != expected:
        fail("serverInventory field set mismatch")
    if value.get("secretValuesRecorded") is not False or value.get("sudoUsed") is not False:
        fail("server inventory may not record secrets or use sudo")
    if template:
        if value.get("status") != "NOT_COLLECTED" or value.get("evidenceDigest") is not None or value.get("collectorSourceSha") is not None:
            fail("server inventory template mismatch")
        return False
    if value.get("status") != "COLLECTED_READ_ONLY":
        fail("server inventory must be COLLECTED_READ_ONLY")
    require_digest(value.get("evidenceDigest"), "serverInventory.evidenceDigest")
    if not SHA40.fullmatch(str(value.get("collectorSourceSha", ""))):
        fail("serverInventory.collectorSourceSha must be a full Git SHA")
    return True


def validate_backup(evidence: dict[str, Any], template: bool) -> bool:
    value = evidence.get("backupRecovery")
    expected = {
        "backupStatus", "backupEvidenceDigest", "isolatedRestoreStatus",
        "isolatedRestoreEvidenceDigest", "rollbackRehearsalStatus", "rollbackEvidenceDigest",
    }
    if not isinstance(value, dict) or set(value) != expected:
        fail("backupRecovery field set mismatch")
    if template:
        if value != {
            "backupStatus": "NOT_COLLECTED",
            "backupEvidenceDigest": None,
            "isolatedRestoreStatus": "NOT_RUN",
            "isolatedRestoreEvidenceDigest": None,
            "rollbackRehearsalStatus": "NOT_RUN",
            "rollbackEvidenceDigest": None,
        }:
            fail("backupRecovery template mismatch")
        return False
    if value.get("backupStatus") != "COLLECTED_AND_CHECKSUMMED":
        fail("backup evidence is incomplete")
    if value.get("isolatedRestoreStatus") != "PASS":
        fail("isolated restore evidence is incomplete")
    if value.get("rollbackRehearsalStatus") != "PASS":
        fail("rollback rehearsal evidence is incomplete")
    for field in ("backupEvidenceDigest", "isolatedRestoreEvidenceDigest", "rollbackEvidenceDigest"):
        require_digest(value.get(field), f"backupRecovery.{field}")
    return True


def validate_change_plans(evidence: dict[str, Any], template: bool) -> bool:
    plans = evidence.get("changePlans")
    if not isinstance(plans, dict) or set(plans) != {"keycloak", "caddy", "firewall", "openbao"}:
        fail("changePlans field set mismatch")

    keycloak = plans["keycloak"]
    caddy = plans["caddy"]
    firewall = plans["firewall"]
    openbao = plans["openbao"]
    if keycloak.get("applied") is not False or caddy.get("reloaded") is not False or firewall.get("applied") is not False:
        fail("plan evidence may not claim live application")
    if openbao.get("initialized") is not False or openbao.get("unsealed") is not False:
        fail("OpenBao must remain uninitialized and sealed")

    if template:
        if keycloak != {
            "status": "NOT_GENERATED", "planDigest": None, "sourceSha": None,
            "independentReviewStatus": "NOT_REVIEWED", "independentReviewDigest": None,
            "applied": False,
        }:
            fail("Keycloak plan template mismatch")
        if caddy != {"status": "NOT_RENDERED", "planDigest": None, "validationDigest": None, "reloaded": False}:
            fail("Caddy plan template mismatch")
        if firewall != {"status": "NOT_RENDERED", "planDigest": None, "lockoutAnalysisDigest": None, "applied": False}:
            fail("firewall plan template mismatch")
        if openbao != {"status": "NOT_REVIEWED", "configurationEvidenceDigest": None, "initialized": False, "unsealed": False}:
            fail("OpenBao plan template mismatch")
        return False

    if keycloak.get("status") != "GENERATED_UNCHANGED_PLAN" or keycloak.get("independentReviewStatus") != "APPROVED_UNCHANGED_PLAN":
        fail("Keycloak plan and independent review are incomplete")
    if not SHA40.fullmatch(str(keycloak.get("sourceSha", ""))):
        fail("Keycloak sourceSha must be a full Git SHA")
    for field in ("planDigest", "independentReviewDigest"):
        require_digest(keycloak.get(field), f"changePlans.keycloak.{field}")
    if caddy.get("status") != "RENDERED_AND_VALIDATED":
        fail("Caddy plan is incomplete")
    for field in ("planDigest", "validationDigest"):
        require_digest(caddy.get(field), f"changePlans.caddy.{field}")
    if firewall.get("status") != "RENDERED_AND_REVIEWED":
        fail("firewall plan is incomplete")
    for field in ("planDigest", "lockoutAnalysisDigest"):
        require_digest(firewall.get(field), f"changePlans.firewall.{field}")
    if openbao.get("status") != "CONFIGURATION_REVIEW_PASS":
        fail("OpenBao configuration review is incomplete")
    require_digest(openbao.get("configurationEvidenceDigest"), "changePlans.openbao.configurationEvidenceDigest")
    return True


def validate_lab(evidence: dict[str, Any], template: bool) -> bool:
    value = evidence.get("integrationLab")
    expected = {
        "status", "evidenceDigest", "exactArtifactsUsed", "backupRestorePassed",
        "rollbackPassed", "externalSideEffectsObserved",
    }
    if not isinstance(value, dict) or set(value) != expected:
        fail("integrationLab field set mismatch")
    if value.get("externalSideEffectsObserved") is not False:
        fail("integration lab may not observe external side effects")
    if template:
        if value != {
            "status": "NOT_RUN", "evidenceDigest": None, "exactArtifactsUsed": False,
            "backupRestorePassed": False, "rollbackPassed": False,
            "externalSideEffectsObserved": False,
        }:
            fail("integration lab template mismatch")
        return False
    if value.get("status") != "PASS" or value.get("exactArtifactsUsed") is not True:
        fail("integration lab did not use and pass exact artifacts")
    if value.get("backupRestorePassed") is not True or value.get("rollbackPassed") is not True:
        fail("integration lab backup/restore/rollback evidence is incomplete")
    require_digest(value.get("evidenceDigest"), "integrationLab.evidenceDigest")
    return True


def validate_approval(evidence: dict[str, Any], template: bool) -> bool:
    value = evidence.get("approval")
    expected = {"status", "manifestDigest", "approver", "approvedAt", "evidenceDigest"}
    if not isinstance(value, dict) or set(value) != expected:
        fail("approval field set mismatch")
    if template:
        if value != {
            "status": "NOT_APPROVED", "manifestDigest": None, "approver": None,
            "approvedAt": None, "evidenceDigest": None,
        }:
            fail("approval template mismatch")
        return False
    if value.get("status") != "APPROVED_UNCHANGED_EVIDENCE":
        fail("independent staging approval is missing")
    require_digest(value.get("manifestDigest"), "approval.manifestDigest")
    require_digest(value.get("evidenceDigest"), "approval.evidenceDigest")
    if not isinstance(value.get("approver"), str) or not value["approver"].strip():
        fail("approval.approver is required")
    if not isinstance(value.get("approvedAt"), str) or not value["approvedAt"].endswith("Z"):
        fail("approval.approvedAt must be a UTC timestamp")
    return True


def validate_freeze(evidence: dict[str, Any]) -> None:
    if evidence.get("deploymentAuthorized") is not False or evidence.get("productionAuthorized") is not False:
        fail("evidence records may not authorize staging or production deployment")
    freeze = evidence.get("safetyFreeze")
    if not isinstance(freeze, dict) or set(freeze) != SAFETY_FIELDS:
        fail("safetyFreeze field set mismatch")
    if any(value is not False for value in freeze.values()):
        fail("all safetyFreeze values must remain false")

    serialized = json.dumps(evidence, sort_keys=True)
    dash = chr(45) * 5
    for signature in (
        dash + "BEGIN " + "OPENSSH" + " PRIVATE" + " KEY" + dash,
        "A" + "K" + "I" + "A",
    ):
        if signature in serialized:
            fail("secret-shaped material is forbidden")


def validate_decision(evidence: dict[str, Any], ready: bool) -> None:
    value = evidence.get("decision")
    if not isinstance(value, dict) or set(value) != {"goForStagingChangeReview", "status", "blockers"}:
        fail("decision field set mismatch")
    if value.get("goForStagingChangeReview") is not ready:
        fail("decision does not match computed evidence readiness")
    expected = "GO_FOR_STAGING_CHANGE_REVIEW" if ready else "NO_GO_EVIDENCE_INCOMPLETE"
    if value.get("status") != expected:
        fail(f"decision.status must be {expected}")
    blockers = value.get("blockers")
    if ready and blockers != []:
        fail("ready evidence may not retain blockers")
    if not ready and (not isinstance(blockers, list) or not blockers):
        fail("incomplete evidence requires blockers")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    args = parser.parse_args()
    evidence = load(args.evidence)

    if evidence.get("schemaVersion") != "1.0":
        fail("schemaVersion must be 1.0")
    if evidence.get("releaseTrain") != "codestra-observability-security-v1":
        fail("releaseTrain mismatch")
    if evidence.get("environment") != "staging":
        fail("environment must be staging")
    state = evidence.get("state")
    if state not in {"EVIDENCE_TEMPLATE_NOT_COLLECTED", "EVIDENCE_COMPLETE_FOR_STAGING_REVIEW"}:
        fail("invalid evidence state")
    template = state == "EVIDENCE_TEMPLATE_NOT_COLLECTED"
    if template and evidence.get("generatedAt") is not None:
        fail("template generatedAt must be null")
    if not template and (not isinstance(evidence.get("generatedAt"), str) or not evidence["generatedAt"].endswith("Z")):
        fail("completed evidence requires a UTC generatedAt timestamp")

    source = evidence.get("sourceManifest")
    if not isinstance(source, dict) or set(source) != {"repository", "ref", "sha", "sha256"}:
        fail("sourceManifest field set mismatch")
    if source.get("repository") != "appolon1908-hue/Infustruction-repo":
        fail("sourceManifest repository mismatch")
    if template:
        if any(source.get(key) is not None for key in ("ref", "sha", "sha256")):
            fail("sourceManifest template fields must be null")
    else:
        if not isinstance(source.get("ref"), str) or not source["ref"]:
            fail("sourceManifest.ref is required")
        if not SHA40.fullmatch(str(source.get("sha", ""))):
            fail("sourceManifest.sha must be a full Git SHA")
        require_digest(source.get("sha256"), "sourceManifest.sha256")

    readiness = [
        validate_components(evidence, template),
        validate_server_inventory(evidence, template),
        validate_backup(evidence, template),
        validate_change_plans(evidence, template),
        validate_lab(evidence, template),
        validate_approval(evidence, template),
    ]
    ready = all(readiness) and not template
    validate_freeze(evidence)
    validate_decision(evidence, ready)

    print(f"EVIDENCE_STATE={state}")
    print(f"EVIDENCE_READY_FOR_STAGING_CHANGE_REVIEW={'YES' if ready else 'NO'}")
    print("DEPLOYMENT_AUTHORIZED=NO")
    print("PRODUCTION_AUTHORIZED=NO")
    print("OBSERVABILITY_STAGING_EVIDENCE_VALIDATION=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as exc:
        print(f"OBSERVABILITY_STAGING_EVIDENCE_ERROR={exc}", file=sys.stderr)
        raise SystemExit(1)
