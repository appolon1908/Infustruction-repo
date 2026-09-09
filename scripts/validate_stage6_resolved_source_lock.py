#!/usr/bin/env python3
"""Validate the resolved Stage 6 evidence copy and its fail-closed gates."""

import hashlib
import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "STAGE6-SOURCE-LOCK.yaml"
RESOLVED = ROOT / "STAGE6-SOURCE-LOCK.RESOLVED.yaml"
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
CLASSES = {
    "source_only",
    "custom_signed_image",
    "custom_attested_image",
    "official_upstream_image_plus_codestra_config",
    "frozen_observed_digest",
    "out_of_batch",
    "unresolved_blocking_artifact",
}


def main() -> None:
    source = yaml.safe_load(SOURCE.read_text())
    data = yaml.safe_load(RESOLVED.read_text())
    resolution = data["runtime_resolution"]
    expected_hash = "sha256:" + hashlib.sha256(SOURCE.read_bytes()).hexdigest()

    assert resolution["authoritative_lock_sha256"] == expected_hash
    assert data["repositories"] == source["repositories"]
    assert data["runtime_workloads"] == source["runtime_workloads"]
    assert data["status"] == "SOURCE_LOCK_FAIL_RUNTIME_UNVERIFIED"
    assert data["gates"]["source_lock"] == "FAIL"
    assert resolution["source_lock"] == "FAIL"
    assert resolution["runtime_mutation_performed"] is False

    components = resolution["components"]
    assert len(components) == len(source["repositories"]) == 23
    for name, row in components.items():
        locked = source["repositories"][name]
        repository = row["repository_integrity"]
        artifact = row["artifact_provenance"]
        assert row["classification"] == locked["artifact_class"]
        assert row["classification"] in CLASSES
        assert repository["locked_revision"] == locked["revision"]
        assert repository["checkout_head"] == locked["revision"]
        assert repository["authoritative_main_head"] == locked["revision"]
        assert repository["exact_head_match"] is True
        assert repository["authoritative_head_match"] is True
        assert repository["clean_worktree"] is True
        assert repository["status"] == "PASS"
        digest = artifact.get("resolved_digest")
        assert digest is None or DIGEST.fullmatch(digest), (name, digest)
        assert row["activation_eligible"] is False

    gates = resolution["gates"]
    assert gates["repository_integrity"] == {
        "status": "PASS",
        "passed": 23,
        "required": 23,
    }
    assert gates["artifact_provenance"]["status"] == "FAIL_PARTIAL"
    assert gates["runtime_readback"]["status"] == "FAIL_REQUIRED_COMPONENTS_ABSENT_OR_UNBOUND"
    assert gates["runtime_readback"]["fresh_verified_digest_matches"] >= 1
    assert gates["runtime_readback"]["nonzero_match_requirement"] == "PASS"
    assert gates["activation_eligibility"]["status"] == "FAIL"
    assert gates["activation_eligibility"]["blackbox_staging_target"] == "PENDING"
    assert gates["activation_eligibility"]["production"] == "DISABLED_NOT_AUTHORIZED"

    middleware = components["middleware"]["artifact_provenance"]
    assert middleware["status"] == "PASS"
    assert middleware["verified_source_revision"] == source["repositories"]["middleware"]["revision"]
    assert middleware["release_manifest_source_sha"] == middleware["verified_source_revision"]
    assert middleware["release_manifest_image_digest"] == middleware["locked_digest"]
    assert DIGEST.fullmatch(middleware["release_manifest_sha256"])
    crypto = middleware["cryptographic_verification"]
    assert crypto["status"] == "PASS"
    assert crypto["digest"] == middleware["locked_digest"]
    assert crypto["source_sha"] == middleware["verified_source_revision"]
    assert crypto["checks"]
    assert all(value is True for value in crypto["checks"].values())

    openbao = components["openbao"]
    assert openbao["artifact_provenance"]["status"] == "PASS_OFFICIAL_DIGEST_WITH_SEPARATE_CONFIG"
    assert openbao["artifact_provenance"]["image_not_built_from_codestra_config"] is True
    assert openbao["runtime_readback"]["digest_match"] is True
    assert openbao["runtime_readback"]["codestra_config_runtime_binding"] is False
    assert (
        openbao["runtime_readback"]["upstream_image_revision"]
        != openbao["runtime_readback"]["codestra_config_revision"]
    )

    private = resolution["private_middleware_staging"]
    assert private["status"] == "HELD"
    assert private["artifact_gate"] == "FAIL_STALE_DEPLOYMENT_LOCK"
    assert private["scoped_safety_gate"] == "FAIL_RUNTIME_READBACK_UNAVAILABLE"
    assert private["resume_authorized"] is False

    isolation = resolution["stage6_klyrow_postal_isolation"]
    assert isolation["status"] == "PASS_SOURCE_ISOLATION_RUNTIME_NOT_ACTIVATED"
    assert isolation["distinct_hosts"] is True
    assert isolation["stage6_private_network_internal"] is True
    assert isolation["stage6_middleware_host_ports"] == []
    assert isolation["stage6_no_host_ports"] is True
    assert isolation["stage6_external_effects_enabled"] is False
    assert isolation["stage6_production_authorized"] is False
    assert isolation["stage6_outbound_klyrow_postal_endpoint_declared"] is False
    assert isolation["klyrow_postal_classification"] == "out_of_batch"
    assert isolation["klyrow_postal_mutation_performed"] is False
    assert resolution["bounded_inventory"]["host_identity"]["address_present"] is True
    assert (
        resolution["bounded_inventory"]["host_identity"]["expected_address"]
        == resolution["bounded_inventory"]["host"]
        == "37.27.128.39"
    )
    assert (
        resolution["bounded_inventory"]["host_identity"]["docker_endpoint"]
        == "unix:///var/run/docker.sock"
    )

    extensions = resolution["component_catalog_extensions"]
    assert extensions["legacy_stage6_core_runtime"]["classification"] == "frozen_observed_digest"
    assert extensions["klyrow_postal"]["classification"] == "out_of_batch"
    assert extensions["infrastructure_evidence"]["classification"] == "source_only"

    print("RESOLVED_SOURCE_LOCK_VALIDATION=PASS")
    print("REPOSITORY_INTEGRITY=PASS")
    print("ARTIFACT_PROVENANCE=FAIL_PARTIAL")
    print("RUNTIME_READBACK=FAIL_REQUIRED_COMPONENTS_ABSENT_OR_UNBOUND")
    print("RUNTIME_DIGEST_MATCH=NONZERO")
    print("ACTIVATION_ELIGIBILITY=FAIL")
    print("SOURCE_LOCK=FAIL")


if __name__ == "__main__":
    main()
