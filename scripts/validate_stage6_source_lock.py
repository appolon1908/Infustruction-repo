#!/usr/bin/env python3
"""Fail-closed validation for the four independent Stage 6 evidence gates."""

import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "STAGE6-SOURCE-LOCK.yaml"
COMPOSE_DIR = ROOT / "deploy/staging/runtime-reconciliation"
SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
ARTIFACT_CLASSES = {
    "source_only",
    "custom_signed_image",
    "custom_attested_image",
    "official_upstream_image_plus_codestra_config",
    "frozen_observed_digest",
    "out_of_batch",
    "unresolved_blocking_artifact",
}
EFFECT_CONTROLS = {
    "LIVE_ADVERTISING_ENABLED",
    "SOCIAL_PUBLISHING_ENABLED",
    "EXTERNAL_MODEL_CALLS_ENABLED",
    "LIVE_SMS_DELIVERY",
    "LIVE_EMAIL_DELIVERY",
    "LIVE_PSTN_DIALING",
    "PRODUCTION_DIALING",
}


def main() -> None:
    lock = yaml.safe_load(LOCK.read_text())
    assert lock["production_write_activation"] is False
    assert lock["runtime_mutation_authorized"] is False
    assert lock["status"] == "SOURCE_LOCK_FAIL_RUNTIME_UNVERIFIED"
    assert len(lock["repositories"]) == 23
    assert len(lock["runtime_workloads"]) == 22

    classes = {}
    for name, repo in lock["repositories"].items():
        assert SHA.fullmatch(repo["revision"]), (name, "revision")
        assert SHA.fullmatch(repo["rollback_git_sha"]), (name, "rollback_git_sha")
        assert repo["rollback_git_sha"] != repo["revision"], (name, "rollback_equals_revision")
        assert repo["artifact_class"] in ARTIFACT_CLASSES, (name, "artifact_class")
        classes[name] = repo["artifact_class"]
        for field in ("image_digest", "rollback_digest"):
            value = repo[field]
            assert DIGEST.fullmatch(value) or value.startswith("UNRESOLVED_"), (name, field, value)
        if repo["artifact_class"] == "source_only":
            assert repo["image_digest"] == "UNRESOLVED_NO_RUNTIME_IMAGE_REQUIRED", name

    assert classes["middleware"] == "custom_signed_image"
    assert classes["openbao"] == "official_upstream_image_plus_codestra_config"
    assert classes["social_runtime"] == "custom_attested_image"
    assert classes["keycloak"] == "official_upstream_image_plus_codestra_config"
    assert lock["repositories"]["middleware"]["revision"] == "9152a04ed8df52269b30d7a9c6b18ef00a0caf75"
    assert lock["repositories"]["middleware"]["image_digest"] == "sha256:91b91b6ba1c828919c86102806eb2cfe6da1295cd7b4fe34df3121dd0bbff1b2"
    assert lock["repositories"]["n8n"]["revision"] == "b620860c04bf0fe6998c5fc25857262aa5c89d74"
    assert lock["repositories"]["kong"]["revision"] == "961edbf56e29ce78f305273c3efeec386a2bba62"
    assert lock["repositories"]["keycloak"]["revision"] == "7aef62a020c87ffcbf0fbb2f8c4890a8e9d13098"
    assert lock["repositories"]["social_runtime"]["image_digest"] == "sha256:8576f49ae136c87efbd87827958a6b3b70e4fc597a3eedbacdaddbd7d3474e87"
    assert lock["repositories"]["openbao"]["image_digest"] == "sha256:5b2486ab0fb90bbc788cc345b0a08616dfb375873ee8be5df3a2fd4d378a67e0"
    assert lock["repositories"]["openbao"]["rollback_target"] == "ABSENT_RUNTIME_WITH_NGINX_BACKUP"

    for name, workload in lock["runtime_workloads"].items():
        assert DIGEST.fullmatch(workload["image_digest"]), (name, "image_digest")
        assert DIGEST.fullmatch(workload["rollback_digest"]), (name, "rollback_digest")
        value = workload.get("git_sha")
        assert value in {"UNVERIFIED", "NOT_APPLICABLE_VENDOR_IMAGE"} or SHA.fullmatch(value), (name, value)

    middleware = lock["runtime_workloads"]["codestra-middleware-staging-middleware-staging-1"]
    assert middleware["expected_sha"] == lock["repositories"]["middleware"]["revision"]
    assert middleware["expected_digest"] == lock["repositories"]["middleware"]["image_digest"]
    n8n = lock["runtime_workloads"]["codestra-n8n-staging-n8n-1"]
    assert n8n["expected_workflow_sha"] == lock["repositories"]["n8n"]["revision"]
    odoo = lock["runtime_workloads"]["codestra-odoo19-staging-odoo19-staging-1"]
    assert odoo["image_digest"] == lock["repositories"]["odoo"]["image_digest"]

    enforcement = lock["safety_enforcement"]
    assert enforcement["gate_model"] == "EFFECTIVE_DENIAL_NETWORK_GATEWAY_AND_NEGATIVE_READBACK"
    assert enforcement["status"] == "DESIGN_PASS_APPLICATION_NOT_AUTHORIZED"
    assert set(enforcement["controls"]) == EFFECT_CONTROLS
    for control, mechanisms in enforcement["controls"].items():
        assert "internal_only_network" in mechanisms, control
        assert "negative_probe" in mechanisms, control

    source_services = set()
    for filename in (
        "compose.middleware-source-remediation.yaml",
        "compose.odoo-source-remediation.yaml",
        "compose.n8n-safety-remediation.yaml",
        "compose.legacy-application-safety-hold.yaml",
    ):
        compose = yaml.safe_load((COMPOSE_DIR / filename).read_text())
        source_services.update(name for name in compose["services"] if "migration" not in name)
    assert len(source_services) == 17, source_services

    middleware_compose = yaml.safe_load(
        (COMPOSE_DIR / "compose.middleware-source-remediation.yaml").read_text()
    )
    app_command = " ".join(
        middleware_compose["services"]["middleware-staging"]["command"]
    )
    assert "migrat" not in app_command.lower()
    assert "alembic" not in app_command.lower()
    assert middleware_compose["services"]["middleware-migration"]["restart"] == "no"

    odoo_compose = yaml.safe_load(
        (COMPOSE_DIR / "compose.odoo-source-remediation.yaml").read_text()
    )
    for service in ("odoo19-staging", "odoo19-master-staging"):
        command = " ".join(odoo_compose["services"][service]["command"])
        assert "--init" not in command
        assert "--update" not in command
    for service in ("odoo19-module-migration", "odoo19-master-module-migration"):
        assert odoo_compose["services"][service]["restart"] == "no"
        assert "--stop-after-init" in odoo_compose["services"][service]["command"]

    gates = lock["gates"]
    assert set(("repository_integrity", "artifact_provenance", "runtime_readback", "activation_eligibility")) <= set(gates)
    assert gates["repository_integrity"]["status"] == "PASS"
    assert gates["repository_integrity"]["repositories_expected"] == 23
    assert gates["repository_integrity"]["infrastructure_evidence_base_sha"] == "244a743a771d1f93c1445392bb45f8325908ca72"
    assert gates["artifact_provenance"]["status"] == "FAIL_PARTIAL"
    assert gates["runtime_readback"]["status"] == "FAIL_REQUIRED_COMPONENTS_ABSENT_OR_UNBOUND"
    assert gates["runtime_readback"]["minimum_verified_digest_matches"] > 0
    assert gates["activation_eligibility"] == {
        "status": "FAIL",
        "stage6_private_middleware_staging": False,
        "stage7_prometheus_target_activation": False,
        "production": False,
    }
    assert gates["source_lock"] == "FAIL"
    assert gates["runtime_reconciliation_allowed"] is False
    assert gates["stage6_path_business_writes"] == "NOT_PROVEN_DISABLED"
    assert gates["out_of_scope_production_writes"] == "ACTIVE_DO_NOT_TOUCH"

    scope = lock["safety_scope"]
    assert scope["in_scope_host"] == "65.109.65.169"
    assert scope["out_of_scope_active_production"]["product"] == "Klyrow/Postal"
    assert scope["out_of_scope_active_production"]["host"] == "37.27.128.39"
    assert scope["out_of_scope_active_production"]["disposition"] == "OUT_OF_SCOPE_ACTIVE_PRODUCTION_DO_NOT_TOUCH"
    assert any("no Stage 6 route" in item for item in scope["invariants"])

    print("REPOSITORY_INTEGRITY=PASS")
    print("ARTIFACT_PROVENANCE=FAIL_PARTIAL")
    print("RUNTIME_READBACK=FAIL_REQUIRED_COMPONENTS_ABSENT_OR_UNBOUND")
    print("ACTIVATION_ELIGIBILITY=FAIL")
    print("SOURCE_LOCK=FAIL")
    print("PRODUCTION_AUTHORIZED=NO")


if __name__ == "__main__":
    main()
