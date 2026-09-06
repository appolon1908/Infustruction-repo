#!/usr/bin/env python3
"""Fail-closed validation for Codestra observability staging preparation."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "release" / "observability-staging-preparation.v1.json"
RUNBOOK = ROOT / "docs" / "OBSERVABILITY-STAGING-PREPARATION.md"
EVIDENCE = ROOT / "docs" / "OBSERVABILITY-STAGING-EVIDENCE-CONTRACT.md"

SHA40 = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
EXPECTED_POLICY = ["development", "test", "staging", "production", "main"]
EXPECTED = [
    ("grafana", "appolon1908-hue/Codestra-Grafana-", "graf.codestra.media", None, "loopback_edge_only"),
    ("prometheus", "appolon1908-hue/Codestra-Prometheus", "prom.codestra.media", None, "internal_private"),
    ("alertmanager", "appolon1908-hue/Codestra-Alertmanager", "aler.codestra.media", None, "internal_private"),
    ("loki", "appolon1908-hue/Codestra-Loki", "loki.codestra.media", None, "internal_private"),
    ("tempo", "appolon1908-hue/Codestra-Tempo", "temp.codestra.media", None, "internal_private"),
    ("opentelemetry", "appolon1908-hue/Codestra-Telemetry", "otel.codestra.media", None, "internal_private"),
    ("superset", "appolon1908-hue/Superset", "supe.codestra.media", None, "loopback_edge_only"),
    ("node-exporter", "appolon1908-hue/Codestra-Node-Exporter", "node.codestra.media", None, "internal_private"),
    ("cadvisor", "appolon1908-hue/Codestra-cAdvisor", "cadv.codestra.media", None, "internal_private"),
    ("postgres-exporter", "appolon1908-hue/Codestra-Postgres-Exporter", None, "postgres-exporter:9187", "internal_private"),
    ("redis-exporter", "appolon1908-hue/Codestra-Redis-Exporter", "rdex.codestra.media", None, "internal_private"),
    ("blackbox-exporter", "appolon1908-hue/Codestra-Blackbox-Exporter", "blac.codestra.media", None, "internal_private"),
    ("alloy", "appolon1908-hue/Codestra-Alloy", "allo.codestra.media", None, "internal_private"),
    ("openbao", "appolon1908-hue/Codestra-OpenBao", "bao.codestra.media", None, "private_strong_auth"),
]
ARTIFACT_FIELDS = {
    "imageReference",
    "imageDigest",
    "sbomDigest",
    "provenanceDigest",
    "signatureDigest",
    "configurationChecksum",
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
LIVE_ACTION_FIELDS = SAFETY_FIELDS | {
    "deploymentAuthorized",
    "productionAuthorized",
    "liveApplyAllowed",
    "clientSecretGenerationAllowed",
    "userRoleAssignmentAllowed",
    "reloadAllowed",
    "certificateActivationAllowed",
    "applyAllowed",
    "nativePublicPortsAllowed",
    "initializeAllowed",
    "unsealAllowed",
    "policyApplyAllowed",
    "secretWriteAllowed",
}
NON_COMPUTED_GATES = {
    "telemetryCompatibilityGateAccepted",
    "immutableImagesResolved",
    "sbomsGenerated",
    "provenanceAttested",
    "signaturesVerified",
    "configurationChecksumsRecorded",
    "readOnlyServerInventoryCaptured",
    "backupEvidenceCaptured",
    "isolatedRestoreValidationPassed",
    "rollbackRehearsalPassed",
    "disposableIntegrationLabPassed",
    "keycloakPlanOnlyGenerated",
    "keycloakIndependentReviewRecorded",
    "caddyPlanRendered",
    "firewallPlanRendered",
    "openBaoInitializationApproved",
    "stagingChangeApprovalRecorded",
}


class ValidationError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise ValidationError(message)


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot parse {path.relative_to(ROOT)}: {exc}")
    if not isinstance(value, dict):
        fail(f"{path.relative_to(ROOT)} must contain an object")
    return value


def validate_components(manifest: dict[str, Any]) -> tuple[bool, bool, bool]:
    values = manifest.get("components")
    if not isinstance(values, list) or len(values) != len(EXPECTED):
        fail("exactly fourteen component records are required")

    expected_names = [item[0] for item in EXPECTED]
    if [item.get("component") for item in values] != expected_names:
        fail("component order must match the canonical fourteen-authority order")

    seen_repositories: set[str] = set()
    seen_hosts: set[str] = set()
    seen_private_identities: set[str] = set()
    all_test = True
    all_ci = True
    all_artifacts = True

    for value, expected in zip(values, EXPECTED, strict=True):
        component, repository, hostname, private_identity, exposure = expected
        for key, wanted in {
            "component": component,
            "repository": repository,
            "canonicalHostname": hostname,
            "nativeExposure": exposure,
        }.items():
            if value.get(key) != wanted:
                fail(f"{component}: {key} must be {wanted!r}")

        if repository in seen_repositories:
            fail(f"{component}: duplicate repository")
        seen_repositories.add(repository)
        if hostname is not None:
            if hostname in seen_hosts:
                fail(f"{component}: duplicate hostname")
            if not hostname.endswith(".codestra.media"):
                fail(f"{component}: canonical hostname is outside codestra.media")
            seen_hosts.add(hostname)
            if "privateServiceIdentity" in value:
                fail(f"{component}: unexpected private service identity")
        else:
            if value.get("privateServiceIdentity") != private_identity:
                fail(f"{component}: private service identity mismatch")
            if not isinstance(private_identity, str) or private_identity in seen_private_identities:
                fail(f"{component}: invalid or duplicate private service identity")
            seen_private_identities.add(private_identity)

        stage = value.get("sourceStage")
        source_ref = value.get("sourceRef")
        gate = value.get("sourceTrainGate")
        ci_green = value.get("exactHeadCiGreen")
        if stage not in {"test", "development", "feature-review"}:
            fail(f"{component}: unsupported sourceStage")
        if not isinstance(source_ref, str) or not source_ref:
            fail(f"{component}: sourceRef is required")
        if not SHA40.fullmatch(str(value.get("sourceSha", ""))):
            fail(f"{component}: sourceSha must be a full lowercase Git SHA")
        if not isinstance(ci_green, bool):
            fail(f"{component}: exactHeadCiGreen must be boolean")

        if stage == "test":
            if source_ref != "test" or gate != "pass" or ci_green is not True:
                fail(f"{component}: test-stage evidence must be exact, green, and passed")
        elif stage == "development":
            if source_ref != "development" or gate != "pending-test-promotion" or ci_green is not True:
                fail(f"{component}: development-stage evidence mismatch")
            all_test = False
        else:
            if source_ref in EXPECTED_POLICY or gate != "pending-exact-head-ci" or ci_green is not False:
                fail(f"{component}: feature-review evidence mismatch")
            all_test = False

        all_ci = all_ci and ci_green

        artifact = value.get("artifact")
        if not isinstance(artifact, dict) or set(artifact) != ARTIFACT_FIELDS | {"status"}:
            fail(f"{component}: artifact evidence object is incomplete")
        status = artifact.get("status")
        if status not in {"NOT_BUILT", "EVIDENCE_COMPLETE"}:
            fail(f"{component}: invalid artifact status")
        if status == "NOT_BUILT":
            if any(artifact.get(field) is not None for field in ARTIFACT_FIELDS):
                fail(f"{component}: artifact evidence may not be populated before a build")
            all_artifacts = False
        else:
            if not isinstance(artifact.get("imageReference"), str) or "@sha256:" not in artifact["imageReference"]:
                fail(f"{component}: immutable imageReference is required")
            if ":latest" in artifact["imageReference"]:
                fail(f"{component}: mutable latest image is forbidden")
            for field in ARTIFACT_FIELDS - {"imageReference"}:
                if not DIGEST.fullmatch(str(artifact.get(field, ""))):
                    fail(f"{component}: {field} must be a sha256 digest")

    return all_test, all_ci, all_artifacts


def validate_gates(manifest: dict[str, Any], all_test: bool, all_ci: bool) -> bool:
    gates = manifest.get("crossRepositoryGates")
    if not isinstance(gates, dict):
        fail("crossRepositoryGates must be an object")
    expected_keys = NON_COMPUTED_GATES | {
        "allFourteenAuthoritiesAtTest",
        "allExactHeadAndMergeResultCiGreen",
    }
    if set(gates) != expected_keys:
        fail("crossRepositoryGates field set mismatch")
    if gates["allFourteenAuthoritiesAtTest"] is not all_test:
        fail("allFourteenAuthoritiesAtTest does not match component evidence")
    if gates["allExactHeadAndMergeResultCiGreen"] is not all_ci:
        fail("allExactHeadAndMergeResultCiGreen does not match component evidence")
    for key in NON_COMPUTED_GATES:
        if not isinstance(gates[key], bool):
            fail(f"gate must be boolean: {key}")
    return all(gates.values())


def validate_freeze(manifest: dict[str, Any]) -> None:
    serialized = json.dumps(manifest, sort_keys=True)
    dash = chr(45) * 5
    for signature in (
        dash + "BEGIN " + "PRIVATE" + " KEY" + dash,
        dash + "BEGIN " + "OPENSSH" + " PRIVATE" + " KEY" + dash,
        "A" + "K" + "I" + "A",
    ):
        if signature in serialized:
            fail("secret-shaped material is forbidden")

    for key in ("deploymentAuthorized", "productionAuthorized"):
        if manifest.get(key) is not False:
            fail(f"{key} must remain false")

    plans = manifest.get("changePlans")
    if not isinstance(plans, dict) or set(plans) != {"keycloak", "caddy", "firewall", "openbao"}:
        fail("changePlans must define Keycloak, Caddy, firewall, and OpenBao")
    if plans["keycloak"].get("mode") != "plan-only":
        fail("Keycloak must remain plan-only")
    if plans["caddy"].get("mode") != "render-and-validate-only":
        fail("Caddy must remain render-and-validate-only")
    if plans["firewall"].get("mode") != "render-and-diff-only":
        fail("firewall must remain render-and-diff-only")
    if plans["openbao"].get("mode") != "configuration-review-only":
        fail("OpenBao must remain configuration-review-only")

    freeze = manifest.get("safetyFreeze")
    if not isinstance(freeze, dict) or not freeze:
        fail("safetyFreeze is required")
    if set(freeze) != SAFETY_FIELDS:
        missing = sorted(SAFETY_FIELDS - set(freeze))
        unexpected = sorted(set(freeze) - SAFETY_FIELDS)
        fail(f"safetyFreeze field mismatch; missing={missing}, unexpected={unexpected}")
    if any(value is not False for value in freeze.values()):
        fail("all safety-freeze actions must remain false")

    def walk(value: Any, path: tuple[str, ...] = ()) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                next_path = path + (key,)
                if key in LIVE_ACTION_FIELDS and nested is not False:
                    fail(f"live action enabled at {'.'.join(next_path)}")
                walk(nested, next_path)
        elif isinstance(value, list):
            for index, nested in enumerate(value):
                walk(nested, path + (str(index),))

    walk(manifest)


def validate_decision(manifest: dict[str, Any], ready: bool, all_artifacts: bool) -> None:
    decision = manifest.get("stagingDecision")
    if not isinstance(decision, dict):
        fail("stagingDecision must be an object")
    computed_go = ready and all_artifacts
    if decision.get("go") is not computed_go:
        fail("stagingDecision.go does not match computed readiness")
    expected_status = "GO_STAGING_CHANGE_APPROVED" if computed_go else "NO_GO_PREPARATION_INCOMPLETE"
    if decision.get("status") != expected_status:
        fail(f"stagingDecision.status must be {expected_status}")
    blockers = decision.get("blockers")
    if computed_go:
        if blockers != []:
            fail("approved staging decision may not retain blockers")
    elif not isinstance(blockers, list) or not blockers:
        fail("NO_GO staging decision requires explicit blockers")


def validate_docs() -> None:
    for path in (RUNBOOK, EVIDENCE):
        if not path.is_file() or path.is_symlink():
            fail(f"required documentation is missing: {path.relative_to(ROOT)}")
    runbook = RUNBOOK.read_text(encoding="utf-8")
    evidence = EVIDENCE.read_text(encoding="utf-8")
    for phrase in (
        "No deployment is authorized by this package.",
        "Keycloak remains plan-only.",
        "Caddy and firewall changes remain render-only.",
        "OpenBao initialization and unseal remain prohibited.",
        "development → test → staging → production → main",
    ):
        if phrase not in runbook:
            fail(f"staging runbook is missing: {phrase}")
    for phrase in (
        "immutable OCI digest",
        "SBOM digest",
        "provenance digest",
        "signature verification",
        "isolated restore validation",
        "rollback rehearsal",
        "unchanged-plan hash",
    ):
        if phrase not in evidence:
            fail(f"evidence contract is missing: {phrase}")


def main() -> int:
    for path in (MANIFEST, RUNBOOK, EVIDENCE):
        if not path.is_file() or path.is_symlink():
            fail(f"required regular file is missing: {path.relative_to(ROOT)}")
    manifest = load(MANIFEST)
    if manifest.get("schemaVersion") != "1.0":
        fail("schemaVersion must be 1.0")
    if manifest.get("releaseTrain") != "codestra-observability-security-v1":
        fail("releaseTrain mismatch")
    if manifest.get("milestone") != "STAGING_DEPLOYMENT_PREPARATION":
        fail("milestone mismatch")
    if manifest.get("state") != "PREPARATION_IN_PROGRESS_NO_DEPLOYMENT":
        fail("state must remain PREPARATION_IN_PROGRESS_NO_DEPLOYMENT")
    if manifest.get("targetEnvironment") != "staging":
        fail("targetEnvironment must be staging")
    if manifest.get("promotionPolicy") != EXPECTED_POLICY:
        fail("promotionPolicy mismatch")

    all_test, all_ci, all_artifacts = validate_components(manifest)
    all_gates = validate_gates(manifest, all_test, all_ci)
    validate_freeze(manifest)
    validate_decision(manifest, all_gates, all_artifacts)
    validate_docs()

    print("OBSERVABILITY_COMPONENT_COUNT=14")
    print("PUBLIC_DNS_HOST_COUNT=13")
    print("PRIVATE_SERVICE_IDENTITY_COUNT=1")
    print(f"ALL_AUTHORITIES_AT_TEST={'YES' if all_test else 'NO'}")
    print(f"ALL_EXACT_HEAD_CI_GREEN={'YES' if all_ci else 'NO'}")
    print(f"IMMUTABLE_ARTIFACT_EVIDENCE_COMPLETE={'YES' if all_artifacts else 'NO'}")
    print("STAGING_DECISION=NO_GO_PREPARATION_INCOMPLETE")
    print("DEPLOYMENT_AUTHORIZED=NO")
    print("PRODUCTION_AUTHORIZED=NO")
    print("OBSERVABILITY_STAGING_PREPARATION_VALIDATION=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as exc:
        print(f"OBSERVABILITY_STAGING_PREPARATION_ERROR={exc}", file=sys.stderr)
        raise SystemExit(1)
