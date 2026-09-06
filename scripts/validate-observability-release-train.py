#!/usr/bin/env python3
"""Fail-closed validation for the 14-repository observability release train."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "observability" / "repository-registry.v1.json"
LOCK = ROOT / "config" / "observability" / "active-branch-lock.v1.json"
MANIFEST = ROOT / "release" / "observability-release-manifest.v1.json"
MATRIX = ROOT / "docs" / "OBSERVABILITY-REPOSITORY-STATUS-MATRIX.md"
PROTECTION = ROOT / "docs" / "BRANCH-PROTECTION-DESIRED-STATE.md"

SHA40 = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_COMPONENTS = [
    "grafana",
    "prometheus",
    "alertmanager",
    "loki",
    "tempo",
    "opentelemetry",
    "superset",
    "node-exporter",
    "cadvisor",
    "postgres-exporter",
    "redis-exporter",
    "blackbox-exporter",
    "alloy",
    "openbao",
]
EXPECTED_REPOSITORIES = {
    "grafana": "appolon1908-hue/Codestra-Grafana-",
    "prometheus": "appolon1908-hue/Codestra-Prometheus",
    "alertmanager": "appolon1908-hue/Codestra-Alertmanager",
    "loki": "appolon1908-hue/Codestra-Loki",
    "tempo": "appolon1908-hue/Codestra-Tempo",
    "opentelemetry": "appolon1908-hue/Codestra-Telemetry",
    "superset": "appolon1908-hue/Superset",
    "node-exporter": "appolon1908-hue/Codestra-Node-Exporter",
    "cadvisor": "appolon1908-hue/Codestra-cAdvisor",
    "postgres-exporter": "appolon1908-hue/Codestra-Postgres-Exporter",
    "redis-exporter": "appolon1908-hue/Codestra-Redis-Exporter",
    "blackbox-exporter": "appolon1908-hue/Codestra-Blackbox-Exporter",
    "alloy": "appolon1908-hue/Codestra-Alloy",
    "openbao": "appolon1908-hue/Codestra-OpenBao",
}
EXPECTED_HOSTS: dict[str, str | None] = {
    "grafana": "graf.codestra.media",
    "prometheus": "prom.codestra.media",
    "alertmanager": "aler.codestra.media",
    "loki": "loki.codestra.media",
    "tempo": "temp.codestra.media",
    "opentelemetry": "otel.codestra.media",
    "superset": "supe.codestra.media",
    "node-exporter": "node.codestra.media",
    "cadvisor": "cadv.codestra.media",
    "postgres-exporter": None,
    "redis-exporter": "rdex.codestra.media",
    "blackbox-exporter": "blac.codestra.media",
    "alloy": "allo.codestra.media",
    "openbao": "bao.codestra.media",
}
EXPECTED_PRIVATE_SERVICE_IDENTITIES = {
    "postgres-exporter": "postgres-exporter:9187",
}
EXPECTED_PERSISTENT_BRANCHES = ["main", "development", "test", "staging", "production"]
PUBLIC_BROWSER_COMPONENTS = {"grafana", "superset", "openbao"}


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
        fail(f"{path.relative_to(ROOT)} must contain a JSON object")
    return value


def require_regular(path: Path) -> None:
    if not path.is_file() or path.is_symlink():
        fail(f"required regular non-symlink file is missing: {path.relative_to(ROOT)}")


def validate_registry(registry: dict[str, Any]) -> None:
    if registry.get("schemaVersion") != 1:
        fail("registry schemaVersion must be 1")
    if registry.get("deploymentEnabled") is not False:
        fail("registry must keep deployment disabled")
    if registry.get("dnsTarget") != "37.27.128.39":
        fail("registry DNS target mismatch")
    if registry.get("persistentBranches") != EXPECTED_PERSISTENT_BRANCHES:
        fail("persistent branch list or order mismatch")

    repositories = registry.get("repositories")
    if not isinstance(repositories, list) or len(repositories) != 14:
        fail("registry must contain exactly 14 repositories")
    components = [item.get("component") for item in repositories]
    if components != EXPECTED_COMPONENTS:
        fail("registry component set or canonical order mismatch")
    if [item.get("order") for item in repositories] != list(range(1, 15)):
        fail("registry order values must be 1 through 14")

    seen_repositories: set[str] = set()
    seen_hosts: set[str] = set()
    seen_private_identities: set[str] = set()
    for item in repositories:
        component = item["component"]
        repository = item.get("repository")
        hostname = item.get("hostname")
        expected_hostname = EXPECTED_HOSTS[component]
        if repository != EXPECTED_REPOSITORIES[component]:
            fail(f"{component}: repository mismatch")
        if hostname != expected_hostname:
            fail(f"{component}: hostname mismatch")
        if repository in seen_repositories:
            fail(f"{component}: duplicate repository")
        seen_repositories.add(repository)

        expected_private_identity = EXPECTED_PRIVATE_SERVICE_IDENTITIES.get(component)
        if expected_private_identity is not None:
            if item.get("privateServiceIdentity") != expected_private_identity:
                fail(f"{component}: private service identity mismatch")
            if expected_private_identity in seen_private_identities:
                fail(f"{component}: duplicate private service identity")
            seen_private_identities.add(expected_private_identity)
            if hostname is not None:
                fail(f"{component}: public hostname must remain unassigned")
        else:
            if "privateServiceIdentity" in item:
                fail(f"{component}: unexpected private service identity")
            if not isinstance(hostname, str) or not hostname.endswith(".codestra.media"):
                fail(f"{component}: hostname is outside codestra.media")
            if hostname in seen_hosts:
                fail(f"{component}: duplicate hostname")
            seen_hosts.add(hostname)

        if item.get("nativePortPublic") is not False:
            fail(f"{component}: native port must not be public")
        if item.get("persistentBranchesPresent") is not True:
            fail(f"{component}: persistent branch inventory is incomplete")
        if item.get("persistentBranchesProtected") is not False:
            fail(f"{component}: source must not claim protection has been applied")

        exposure = item.get("exposure")
        if component in PUBLIC_BROWSER_COMPONENTS:
            if "caddy" not in str(exposure):
                fail(f"{component}: browser exposure must be through Caddy")
        elif "private" not in str(exposure):
            fail(f"{component}: non-browser service must remain private")

        candidate = item.get("candidate")
        if not isinstance(candidate, dict):
            fail(f"{component}: candidate object missing")
        if not isinstance(candidate.get("branch"), str) or not candidate["branch"]:
            fail(f"{component}: candidate branch missing")
        if not SHA40.fullmatch(str(candidate.get("headSha", ""))):
            fail(f"{component}: candidate SHA must be exact 40-character lowercase hex")
        if not isinstance(candidate.get("pullRequest"), int) or candidate["pullRequest"] <= 0:
            fail(f"{component}: candidate PR number missing")
        if candidate.get("stackRole") not in {
            "single_canonical_implementation",
            "foundation_then_corporate_extension",
            "hostname_governance_then_runtime",
        }:
            fail(f"{component}: invalid stack role")

    cross = registry.get("crossCuttingAuthorities")
    if not isinstance(cross, list) or len(cross) != 4:
        fail("exactly four cross-cutting authorities are required")
    serialized = json.dumps(cross, sort_keys=True)
    for prohibited in (
        "liveApplyAllowed\": true",
        "liveReloadAllowed\": true",
        "liveFirewallApplyAllowed\": true",
        "liveMutationAllowed\": true",
    ):
        if prohibited in serialized:
            fail(f"cross-cutting authority enabled a live action: {prohibited}")


def validate_lock(lock: dict[str, Any], registry: dict[str, Any]) -> None:
    if lock.get("schemaVersion") != 1:
        fail("branch lock schemaVersion must be 1")
    policy = lock.get("policy")
    required_true = {
        "oneActiveImplementationPerScope",
        "stackedBranchesRequireExplicitOrder",
        "newParallelBranchesBlockedWithoutRegistryChange",
    }
    required_false = {
        "forcePushAllowed",
        "directPersistentBranchCommitsAllowed",
        "mergeIsDeploymentAuthorization",
        "liveDeploymentAllowed",
    }
    if not isinstance(policy, dict):
        fail("branch lock policy missing")
    for key in required_true:
        if policy.get(key) is not True:
            fail(f"branch lock control disabled: {key}")
    for key in required_false:
        if policy.get(key) is not False:
            fail(f"unsafe branch policy enabled: {key}")

    locks = lock.get("locks")
    if not isinstance(locks, list) or len(locks) != 14:
        fail("branch lock must contain exactly 14 repository locks")
    registry_by_repo = {item["repository"]: item for item in registry["repositories"]}
    seen_scopes: set[tuple[str, str]] = set()
    for item in locks:
        repository = item.get("repository")
        scope = item.get("scope")
        if repository not in registry_by_repo:
            fail(f"branch lock references unknown repository: {repository}")
        key = (str(repository), str(scope))
        if key in seen_scopes:
            fail(f"duplicate active scope: {repository}:{scope}")
        seen_scopes.add(key)
        if item.get("canonicalBranch") != registry_by_repo[repository]["candidate"]["branch"]:
            fail(f"{repository}: branch lock and registry candidate differ")
        blocked = item.get("blockedParallelBranches")
        if not isinstance(blocked, list) or len(blocked) != len(set(blocked)):
            fail(f"{repository}: blocked parallel branch list is invalid")
        if item["canonicalBranch"] in blocked:
            fail(f"{repository}: canonical branch cannot be blocked")

        stack = item.get("stack")
        if stack is not None:
            if not isinstance(stack, list) or not stack:
                fail(f"{repository}: explicit stack must be non-empty")
            orders = [stage.get("order") for stage in stack]
            if orders != list(range(1, len(stack) + 1)):
                fail(f"{repository}: stack order must be contiguous")
            branches = [stage.get("branch") for stage in stack]
            if len(branches) != len(set(branches)):
                fail(f"{repository}: duplicate branch in stack")
            if item["canonicalBranch"] not in branches:
                fail(f"{repository}: canonical branch missing from its stack")

    cross = lock.get("crossCuttingLocks")
    if not isinstance(cross, list) or len(cross) != 3:
        fail("three cross-cutting branch locks are required")
    if not any(
        item.get("repository") == "appolon1908-hue/Keycloak" and item.get("issue") == 30
        for item in cross
    ):
        fail("Keycloak issue #30 lock is missing")


def validate_manifest(manifest: dict[str, Any], registry: dict[str, Any]) -> None:
    if manifest.get("schemaVersion") != 1:
        fail("manifest schemaVersion must be 1")
    if manifest.get("state") != "BUILDING":
        fail("manifest must remain BUILDING until the release freeze")
    for field in ("frozen", "releaseReady", "deploymentEnabled", "dnsIsDeploymentAuthorization"):
        if manifest.get(field) is not False:
            fail(f"manifest gate must remain false: {field}")
    if manifest.get("serverTargetRecordedForFuturePlanningOnly") != "37.27.128.39":
        fail("future server target evidence mismatch")

    components = manifest.get("components")
    if not isinstance(components, list) or len(components) != 14:
        fail("manifest must contain exactly 14 components")
    names = [item.get("component") for item in components]
    if names != EXPECTED_COMPONENTS:
        fail("manifest component set or order mismatch")
    registry_by_component = {item["component"]: item for item in registry["repositories"]}
    for item in components:
        component = item["component"]
        registry_item = registry_by_component[component]
        if item.get("repository") != registry_item["repository"]:
            fail(f"{component}: manifest repository mismatch")
        if item.get("candidateBranch") != registry_item["candidate"]["branch"]:
            fail(f"{component}: manifest candidate branch mismatch")
        if item.get("candidateSha") != registry_item["candidate"]["headSha"]:
            fail(f"{component}: manifest candidate SHA mismatch")
        if item.get("sourceCandidateRecorded") is not True:
            fail(f"{component}: source candidate must be recorded")
        if item.get("releaseReady") is not False:
            fail(f"{component}: releaseReady must remain false")
        for future_field in (
            "acceptedMainSha",
            "releaseTag",
            "imageDigest",
            "sbomDigest",
            "configurationChecksum",
        ):
            if item.get(future_field) is not None:
                fail(f"{component}: premature release evidence in {future_field}")

    gates = manifest.get("crossRepositoryGates")
    if not isinstance(gates, dict) or not gates:
        fail("cross-repository gates missing")
    if any(value is not False for value in gates.values()):
        fail("no cross-repository release gate may be true in BUILDING state")
    freeze = manifest.get("deploymentFreeze")
    if not isinstance(freeze, dict) or not freeze:
        fail("deployment freeze missing")
    if any(value is not False for value in freeze.values()):
        fail("all deployment actions must remain disabled")


def validate_docs() -> None:
    for path in (MATRIX, PROTECTION):
        require_regular(path)
        text = path.read_text(encoding="utf-8")
        if "DEPLOYMENT_ENABLED=NO" not in text:
            fail(f"{path.relative_to(ROOT)} does not state the deployment freeze")
    matrix = MATRIX.read_text(encoding="utf-8")
    for component in EXPECTED_COMPONENTS:
        repository = EXPECTED_REPOSITORIES[component]
        hostname = EXPECTED_HOSTS[component]
        private_identity = EXPECTED_PRIVATE_SERVICE_IDENTITIES.get(component)
        alternatives = [repository]
        if hostname is not None:
            alternatives.append(hostname)
        if private_identity is not None:
            alternatives.append(private_identity)
        if not any(value in matrix for value in alternatives):
            fail(f"status matrix omits {component}")
    protection = PROTECTION.read_text(encoding="utf-8")
    for branch in EXPECTED_PERSISTENT_BRANCHES:
        if f"`{branch}`" not in protection:
            fail(f"branch protection desired state omits {branch}")


def main() -> int:
    for path in (REGISTRY, LOCK, MANIFEST, MATRIX, PROTECTION):
        require_regular(path)
    registry = load(REGISTRY)
    lock = load(LOCK)
    manifest = load(MANIFEST)
    validate_registry(registry)
    validate_lock(lock, registry)
    validate_manifest(manifest, registry)
    validate_docs()
    print("OBSERVABILITY_REPOSITORY_COUNT=14")
    print("PUBLIC_DNS_HOST_COUNT=13")
    print("POSTGRES_EXPORTER_PRIVATE_IDENTITY=postgres-exporter:9187")
    print("PERSISTENT_BRANCH_SETS_RECORDED=14")
    print("ACTIVE_BRANCH_LOCK=PASS")
    print("RELEASE_MANIFEST_STATE=BUILDING")
    print("DEPLOYMENT_ENABLED=NO")
    print("OBSERVABILITY_RELEASE_TRAIN_VALIDATION=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as exc:
        print(f"OBSERVABILITY_RELEASE_TRAIN_ERROR={exc}", file=sys.stderr)
        raise SystemExit(1)
