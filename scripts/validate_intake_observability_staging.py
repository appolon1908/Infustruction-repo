#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy/staging/intake-observability"
EXPECTED_SOURCE = "9a96ff1651a324b98f3a7efd60b7a342983ded4e"
EXPECTED_DIGEST = "sha256:01a61e6c9761968bce04db855df565e9104338c2ba2056da570cacb9fd21f0f4"
EXPECTED_SCHEMA = "0008_durable_communications"
EXPECTED_RELEASE_ID = "9a96ff1651a3-01a61e6c9761"
EXPECTED_RELEASE_ARTIFACT_DIGEST = (
    "sha256:56fc7bd5cca57df0bfd04e27eb3e294bd160a8071e4e8ae1974addb6d040f46e"
)
EXPECTED_RELEASE_MANIFEST_SHA256 = (
    "sha256:55f809c9f6436fd886c7a8a19a2b557da22696e190ebf806df16f3e401b7f9a6"
)
EXPECTED_SBOM_SHA256 = (
    "sha256:2aef347da05c39956671e9f431b36dd5b8a2a0ec76a72ded155b062db321c3ea"
)
EXPECTED_VULNERABILITY_REPORT_SHA256 = (
    "sha256:4652fc5b7de5be1e0f7e2c977a3970a09d47df71a4ddff5bc3866b32f01a6e49"
)
EXPECTED_RELEASE_IDENTITY = (
    "https://github.com/appolon1908-hue/Middleware-/.github/workflows/"
    "release.yml@refs/heads/main"
)
EXPECTED_RELEASE_ISSUER = "https://token.actions.githubusercontent.com"
EXPECTED_UMBRELLA_CONTROLS = {
    "LIVE_ADVERTISING_ENABLED": False,
    "EXTERNAL_DELIVERY_ENABLED": False,
    "SOCIAL_PUBLISHING_ENABLED": False,
    "EXTERNAL_MODEL_CALLS_ENABLED": False,
    "N8N_EXTERNAL_PROVIDER_WRITES": False,
}
EXPECTED_PROFILE = "codestra-middleware-staging-v1"
EXPECTED_KEYCLOAK_PUBLIC_URL = "https://auth-staging.codestra.co"
EXPECTED_KEYCLOAK_ISSUER = EXPECTED_KEYCLOAK_PUBLIC_URL + "/realms/codestra"
EXPECTED_KEYCLOAK_JWKS_URI = EXPECTED_KEYCLOAK_ISSUER + "/protocol/openid-connect/certs"
POSTGRES_HOST = "postgresql.middleware-staging.svc.cluster.local"
REDIS_HOST = "redis.middleware-staging.svc.cluster.local"
EXPECTED_OBSERVABILITY_NETWORK = {
    "name": "codestra-observability",
    "contract": "codestra-observability-staging-v1",
    "driver": "bridge",
    "scope": "local",
    "internal": False,
    "attachable": False,
    "ingress": False,
    "subnet": "192.168.16.0/24",
    "gateway": "192.168.16.1",
    "inter_container_communication": True,
    "ip_masquerade": True,
    "host_ports_published": False,
    "allowed_container_names": [
        "codestra-prometheus-staging",
        "codestra-grafana-staging",
    ],
}


def main() -> None:
    lock = json.loads((DEPLOY / "runtime-lock.v1.json").read_text())
    assert lock["schema_version"] == "1.4" and lock["environment"] == "staging"
    assert lock["middleware"]["source_sha"] == EXPECTED_SOURCE
    assert lock["middleware"]["image_digest"] == EXPECTED_DIGEST
    assert lock["middleware"]["image_reference"].endswith("@" + EXPECTED_DIGEST)
    assert lock["middleware"]["schema_head"] == EXPECTED_SCHEMA
    assert lock["middleware"]["runtime_profile_id"] == EXPECTED_PROFILE
    assert lock["middleware"]["release_id"] == EXPECTED_RELEASE_ID
    assert lock["middleware"]["release_artifact_id"] == 9859370333
    assert (
        lock["middleware"]["release_artifact_digest"]
        == EXPECTED_RELEASE_ARTIFACT_DIGEST
    )
    assert (
        lock["middleware"]["release_manifest_sha256"]
        == EXPECTED_RELEASE_MANIFEST_SHA256
    )
    assert lock["middleware"]["sbom_sha256"] == EXPECTED_SBOM_SHA256
    assert (
        lock["middleware"]["vulnerability_report_sha256"]
        == EXPECTED_VULNERABILITY_REPORT_SHA256
    )
    assert lock["middleware"]["release_evidence_root"] == (
        "/var/lib/codestra/releases/middleware/9a96ff1651a3-01a61e6c9761"
    )
    assert (
        lock["middleware"]["release_workflow_identity"]
        == EXPECTED_RELEASE_IDENTITY
    )
    assert lock["middleware"]["release_oidc_issuer"] == EXPECTED_RELEASE_ISSUER
    assert lock["embedded_profile_identities"] == {
        "postgres_host": POSTGRES_HOST,
        "postgres_port": 5432,
        "postgres_database": "codestra_staging",
        "postgres_username": "middleware_staging",
        "postgres_sslmode": "verify-full",
        "redis_host": REDIS_HOST,
        "redis_port": 6379,
        "redis_database": 14,
        "redis_username": "middleware-staging",
        "redis_scheme": "rediss",
    }
    assert lock["transport"] == {
        "private_ca_generated_outside_git": True,
        "postgres_tls": True,
        "redis_tls": True,
        "hostname_verification": True,
        "middleware_trust_bundle_mounted_read_only": True,
    }
    assert lock["network"]["middleware_host_ports"] == []
    assert lock["network"]["private_network_internal"] is True
    assert lock["network"]["shared_observability"] == EXPECTED_OBSERVABILITY_NETWORK
    assert lock["persistence"] == {
        "named_volumes": ["postgres_data", "redis_data"],
        "preserve_on_redeploy": True,
        "preserve_on_failure_rollback": True,
        "destructive_reset_requires_explicit_confirmation": True,
    }
    assert lock["identity"] == {
        "public_url": EXPECTED_KEYCLOAK_PUBLIC_URL,
        "admin_api_base_url": EXPECTED_KEYCLOAK_PUBLIC_URL,
        "issuer": EXPECTED_KEYCLOAK_ISSUER,
        "jwks_uri": EXPECTED_KEYCLOAK_JWKS_URI,
        "realm": "codestra",
        "admin_authentication_realm": "master",
        "client_id": "monitoring-readonly",
        "audience": "middleware-api",
        "metrics_scope": "metrics.read",
        "health_scope": "health.read",
        "maximum_token_ttl_seconds": 300,
        "token_values_committed": False,
        "production_identity_endpoint_allowed": False,
    }
    assert lock["activation"] == {
        "prometheus_target": "pending",
        "blackbox_target": "pending",
        "production_authorized": False,
    }
    assert lock["umbrella_controls"] == EXPECTED_UMBRELLA_CONTROLS
    assert lock["external_effects_enabled"] is False
    for value in lock["support_images"].values():
        assert re.fullmatch(r"[^\s]+@sha256:[0-9a-f]{64}", value)

    compose = yaml.safe_load((DEPLOY / "compose.yaml").read_text())
    services = compose["services"]
    assert set(services) == {"postgres", "redis", "middleware-migrate", "middleware"}
    assert services["middleware"]["image"] == lock["middleware"]["image_reference"]
    assert services["middleware-migrate"]["image"] == lock["middleware"]["image_reference"]
    assert "ports" not in services["middleware"]
    assert services["middleware"]["expose"] == ["8080"]
    assert compose["networks"]["private"]["internal"] is True
    assert services["postgres"]["image"] == lock["support_images"]["postgres"]
    assert services["redis"]["image"] == lock["support_images"]["redis"]
    assert set(compose["volumes"]) == {"postgres_data", "postgres_tls", "redis_data"}

    for name in ("postgres", "redis"):
        service = services[name]
        assert service["cap_drop"] == ["ALL"]
        assert set(service["cap_add"]) == {"CHOWN", "DAC_OVERRIDE", "FOWNER", "SETGID", "SETUID"}
        assert service["read_only"] is True
        assert "no-new-privileges:true" in service["security_opt"]
    assert POSTGRES_HOST in services["postgres"]["networks"]["private"]["aliases"]
    assert REDIS_HOST in services["redis"]["networks"]["private"]["aliases"]
    postgres_command = services["postgres"]["command"][0]
    redis_command = services["redis"]["command"][0]
    for required in ("ssl=on", "ssl_cert_file", "ssl_key_file", "hba_file", "docker-entrypoint.sh"):
        assert required in postgres_command
    for required in ("--tls-port 6379", "--port 0", "--aclfile /data/users.acl", "gosu redis"):
        assert required in redis_command
    middleware_mounts = services["middleware"]["volumes"]
    assert any("ca-certificates.crt:ro" in value for value in middleware_mounts)

    script = (ROOT / "scripts/deploy_intake_observability_staging.sh").read_text()
    for required in (
        "docker pull \"$image\"",
        "\"$COSIGN\" verify \\",
        "\"$COSIGN\" verify-attestation \\",
        "host ports are prohibited",
        "STAGING_DEPLOYMENT=PASS",
        "RUNTIME_PROFILE_ID=$EXPECTED_PROFILE",
        "sslmode=verify-full",
        "rediss://middleware-staging:",
        "openssl x509 -in \"$cert\" -noout -checkhost",
        "OUTBOX_DISPATCH_ENABLED=false",
        "EXTERNAL_EFFECTS_ENABLED=false",
        "LIVE_ADVERTISING_ENABLED=false",
        "EXTERNAL_DELIVERY_ENABLED=false",
        "SOCIAL_PUBLISHING_ENABLED=false",
        "EXTERNAL_MODEL_CALLS_ENABLED=false",
        "N8N_EXTERNAL_PROVIDER_WRITES=false",
        "LIVE_PSTN_DIALING=false",
        "DATA_VOLUMES=PRESERVED",
        "DELETE_CODESTRA_STAGE6_STAGING_DATA",
        "EXPECTED_KEYCLOAK_PUBLIC_URL='https://auth-staging.codestra.co'",
        "EXPECTED_KEYCLOAK_ISSUER=\"${EXPECTED_KEYCLOAK_PUBLIC_URL}/realms/codestra\"",
        "EXPECTED_KEYCLOAK_JWKS_URI=\"${EXPECTED_KEYCLOAK_ISSUER}/protocol/openid-connect/certs\"",
        "KEYCLOAK_ISSUER=$EXPECTED_KEYCLOAK_ISSUER",
        "KEYCLOAK_JWKS_URI=$EXPECTED_KEYCLOAK_JWKS_URI",
        "keycloak_public_url",
        "keycloak_issuer",
        "validate_protected_checkout",
        "validate_exact_merged_source",
        "INFRASTRUCTURE_SOURCE_SHA",
        "CANONICAL_REPOSITORY='https://github.com/appolon1908-hue/Infustruction-repo.git'",
        "CANONICAL_MAIN_REF='refs/remotes/codestra-canonical/main'",
        "OBSERVABILITY_NETWORK='codestra-observability'",
        "OBSERVABILITY_NETWORK_CONTRACT='codestra-observability-staging-v1'",
        "OBSERVABILITY_NETWORK_SUBNET='192.168.16.0/24'",
        "validate_observability_network",
        "ensure_observability_network",
        "com.docker.network.bridge.enable_ip_masquerade=true",
        '.[0].Containers | to_entries | all(',
        '.value.Name == "codestra-prometheus-staging"',
        '.value.Name == "codestra-grafana-staging"',
        ".HostConfig.PortBindings",
        ".HostConfig.PublishAllPorts == false",
        ".NetworkSettings.Ports",
        "to_entries | all(.value == null)",
        ".NetworkSettings.Networks[$network] != null",
        "shared observability member publishes a host port",
        "PATH='/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'",
        "unset BASH_ENV ENV CDPATH",
        "DOCKER_CONFIG='/nonexistent'",
        "GIT_CONFIG_NOSYSTEM=1",
        "GIT_CONFIG_GLOBAL=/dev/null",
        "COMPOSE_BIN='/usr/libexec/docker/cli-plugins/docker-compose'",
        'docker() { /usr/bin/docker "$@"; }',
        '/usr/bin/git "$@"',
        'STATE_ROOT="${CODESTRA_STAGING_ROOT:-/root/.local/share/codestra/staging/intake-observability}"',
        '.schema_version == "1.4"',
        "validate_release_evidence",
        "EXPECTED_RELEASE_ARTIFACT_NAME=",
        "EXPECTED_RELEASE_ARTIFACT_ID='9859370333'",
        "EXPECTED_RELEASE_EVIDENCE_ROOT=",
        "EXPECTED_SBOM_SHA256=",
        "EXPECTED_VULNERABILITY_REPORT_SHA256=",
        '"codestra.source_sha"',
        "verify-blob",
        "middleware-spdx-attestation.json",
    ):
        assert required in script, required
    assert "https://auth.codestra.co" not in script
    assert script.count("compose down --volumes --remove-orphans") == 1
    assert script.count("compose down --remove-orphans") >= 3
    assert "compose down --volumes --remove-orphans >/dev/null 2>&1 || true" not in script
    assert "production-activation" not in script
    assert script.count("WEBHOOK_SECRET_") >= 7
    assert "REDIS_ACL_FILE" not in script
    deployment_readme = (DEPLOY / "README.md").read_text()
    assert "root-owned protected checkout" in deployment_readme
    assert "INFRASTRUCTURE_SOURCE_SHA" in deployment_readme
    assert "/var/lib/codestra/staging/intake-observability" in deployment_readme
    assert "/usr/bin/env -i" in deployment_readme
    assert "codestra-observability" in deployment_readme
    assert "actions/artifacts/9859370333/zip" in deployment_readme
    assert "signed manifest" in deployment_readme
    print("INFRASTRUCTURE_STAGING_INTAKE_OBSERVABILITY=PASS")


if __name__ == "__main__":
    main()
