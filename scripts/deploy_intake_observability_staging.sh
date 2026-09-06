#!/bin/bash
set -Eeuo pipefail
umask 077
PATH='/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
HOME='/nonexistent'
DOCKER_CONFIG='/nonexistent'
XDG_CONFIG_HOME='/nonexistent'
export PATH HOME DOCKER_CONFIG XDG_CONFIG_HOME
unset BASH_ENV ENV CDPATH GIT_CONFIG_GLOBAL GIT_CONFIG_SYSTEM GIT_CONFIG_COUNT

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/deploy/staging/intake-observability/compose.yaml"
LOCK_FILE="$ROOT_DIR/deploy/staging/intake-observability/runtime-lock.v1.json"
ACTION="${1:-deploy}"
STATE_ROOT="${CODESTRA_STAGING_ROOT:-/root/.local/share/codestra/staging/intake-observability}"
EXPECTED_IMAGE='ghcr.io/appolon1908-hue/codestra-middleware@sha256:01a61e6c9761968bce04db855df565e9104338c2ba2056da570cacb9fd21f0f4'
EXPECTED_DIGEST='sha256:01a61e6c9761968bce04db855df565e9104338c2ba2056da570cacb9fd21f0f4'
EXPECTED_SOURCE='9a96ff1651a324b98f3a7efd60b7a342983ded4e'
EXPECTED_PROFILE='codestra-middleware-staging-v1'
EXPECTED_RELEASE_ID='9a96ff1651a3-01a61e6c9761'
EXPECTED_RELEASE_ARTIFACT_DIGEST='sha256:56fc7bd5cca57df0bfd04e27eb3e294bd160a8071e4e8ae1974addb6d040f46e'
EXPECTED_RELEASE_ARTIFACT_NAME='signed-middleware-release-9a96ff1651a324b98f3a7efd60b7a342983ded4e-33662230894-2'
EXPECTED_RELEASE_MANIFEST_SHA256='sha256:55f809c9f6436fd886c7a8a19a2b557da22696e190ebf806df16f3e401b7f9a6'
EXPECTED_SBOM_SHA256='sha256:2aef347da05c39956671e9f431b36dd5b8a2a0ec76a72ded155b062db321c3ea'
EXPECTED_VULNERABILITY_REPORT_SHA256='sha256:4652fc5b7de5be1e0f7e2c977a3970a09d47df71a4ddff5bc3866b32f01a6e49'
EXPECTED_RELEASE_RUN_ID='33662230894'
EXPECTED_RELEASE_RUN_ATTEMPT='2'
EXPECTED_RELEASE_ARTIFACT_ID='9859370333'
EXPECTED_RELEASE_IDENTITY='https://github.com/appolon1908-hue/Middleware-/.github/workflows/release.yml@refs/heads/main'
EXPECTED_RELEASE_ISSUER='https://token.actions.githubusercontent.com'
EXPECTED_RELEASE_EVIDENCE_ROOT='/var/lib/codestra/releases/middleware/9a96ff1651a3-01a61e6c9761'
COSIGN='/usr/local/bin/cosign'
COMPOSE_BIN='/usr/libexec/docker/cli-plugins/docker-compose'
EXPECTED_KEYCLOAK_PUBLIC_URL='https://auth-staging.codestra.co'
EXPECTED_KEYCLOAK_ISSUER="${EXPECTED_KEYCLOAK_PUBLIC_URL}/realms/codestra"
EXPECTED_KEYCLOAK_JWKS_URI="${EXPECTED_KEYCLOAK_ISSUER}/protocol/openid-connect/certs"
EXPECTED_KEYCLOAK_REALM='codestra'
CANONICAL_REPOSITORY='https://github.com/appolon1908-hue/Infustruction-repo.git'
CANONICAL_MAIN_REF='refs/remotes/codestra-canonical/main'
POSTGRES_IMAGE='postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73'
REDIS_IMAGE='redis:7.4-alpine@sha256:e7723ff73d963f5cc6d9c4643ea3d989527a402a319239054e9472a7fb9219a2'
PROJECT='codestra-intake-observability-staging'
OBSERVABILITY_NETWORK='codestra-observability'
OBSERVABILITY_NETWORK_CONTRACT='codestra-observability-staging-v1'
OBSERVABILITY_NETWORK_SUBNET='192.168.16.0/24'
OBSERVABILITY_NETWORK_GATEWAY='192.168.16.1'
POSTGRES_HOST='postgresql.middleware-staging.svc.cluster.local'
REDIS_HOST='redis.middleware-staging.svc.cluster.local'
WEBHOOK_PRODUCERS=(
  ODOO_INTEGRATION
  N8N_AUTOMATION
  VICIDIAL_ADAPTER
  TELNEXA_GATEWAY
  KLYROW_GATEWAY
  KYQRA_GATEWAY
  POSTLY_ADAPTER
)

fail() { printf 'STAGING_DEPLOYMENT=FAIL %s\n' "$*" >&2; exit 1; }
require() { command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"; }
docker() { /usr/bin/docker "$@"; }
git() {
  /usr/bin/env -i \
    PATH=/usr/bin:/bin \
    HOME=/nonexistent \
    XDG_CONFIG_HOME=/nonexistent \
    GIT_CONFIG_NOSYSTEM=1 \
    GIT_CONFIG_GLOBAL=/dev/null \
    GIT_TERMINAL_PROMPT=0 \
    LC_ALL=C \
    /usr/bin/git "$@"
}
compose() { "$COMPOSE_BIN" --project-name "$PROJECT" --env-file "$STATE_ROOT/deployment.env" -f "$COMPOSE_FILE" "$@"; }
new_secret() { python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
}
ensure_secret() {
  local path="$1"
  if [[ ! -s "$path" ]]; then
    new_secret >"$path"
  fi
  [[ ! -L "$path" ]] || fail "secret path is a symlink: $path"
  chmod 600 "$path"
}

assert_protected_path() {
  local path="$1" mode
  [[ ! -L "$path" ]] || fail "protected source path is a symlink: $path"
  [[ "$(stat -c '%u' -- "$path")" == 0 ]] || fail "protected source path is not root-owned: $path"
  mode="$(stat -c '%a' -- "$path")"
  (( (8#$mode & 8#022) == 0 )) || fail "protected source path is group- or other-writable: $path"
}

validate_protected_checkout() {
  [[ $EUID -eq 0 ]] || fail 'runtime actions must execute as root from protected source'
  [[ "$ROOT_DIR" == /* && ! -L "$ROOT_DIR" ]] || fail 'deployment checkout must be an absolute non-symlink path'
  local current="$ROOT_DIR" path
  while :; do
    assert_protected_path "$current"
    [[ "$current" == / ]] && break
    current="$(dirname -- "$current")"
  done
  [[ -d "$ROOT_DIR/.git" && ! -L "$ROOT_DIR/.git" ]] || fail 'deployment checkout must be a standalone protected Git checkout'
  while IFS= read -r -d '' path; do
    assert_protected_path "$path"
  done < <(
    find \
      "$ROOT_DIR/.git" \
      "$ROOT_DIR/deploy/staging/intake-observability" \
      "$ROOT_DIR/scripts" \
      "$ROOT_DIR/scripts/deploy_intake_observability_staging.sh" \
      "$ROOT_DIR/scripts/validate_intake_observability_staging.py" \
      -xdev -print0
  )
}

validate_observability_network() {
  local network_json container_id container_json
  network_json="$(docker network inspect "$OBSERVABILITY_NETWORK")" ||
    fail 'shared observability network is absent'
  jq -e \
      --arg name "$OBSERVABILITY_NETWORK" \
      --arg contract "$OBSERVABILITY_NETWORK_CONTRACT" \
      --arg subnet "$OBSERVABILITY_NETWORK_SUBNET" \
      --arg gateway "$OBSERVABILITY_NETWORK_GATEWAY" '
        length == 1
        and .[0].Name == $name
        and .[0].Driver == "bridge"
        and .[0].Scope == "local"
        and .[0].Internal == false
        and .[0].Attachable == false
        and .[0].Ingress == false
        and .[0].IPAM.Driver == "default"
        and .[0].IPAM.Config == [{"Subnet": $subnet, "Gateway": $gateway}]
        and .[0].Options["com.docker.network.bridge.enable_icc"] == "true"
        and .[0].Options["com.docker.network.bridge.enable_ip_masquerade"] == "true"
        and .[0].Labels["com.codestra.authority.repository"] == "appolon1908-hue/Infustruction-repo"
        and .[0].Labels["com.codestra.environment"] == "staging"
        and .[0].Labels["com.codestra.network.contract"] == $contract
        and (.[0].Containers | to_entries | all(
          .value.Name == "codestra-prometheus-staging"
          or .value.Name == "codestra-grafana-staging"
        ))
      ' <<<"$network_json" >/dev/null ||
    fail 'shared observability network does not match its reviewed contract'
  while IFS= read -r container_id; do
    [[ "$container_id" =~ ^[0-9a-f]{64}$ ]] ||
      fail 'shared observability network returned a malformed container ID'
    container_json="$(docker container inspect "$container_id")" ||
      fail 'shared observability member could not be inspected'
    jq -e \
      --arg id "$container_id" \
      --arg network "$OBSERVABILITY_NETWORK" '
        length == 1
        and .[0].Id == $id
        and .[0].HostConfig.PublishAllPorts == false
        and (.[0].HostConfig.PortBindings // {}) == {}
        and ((.[0].NetworkSettings.Ports // {}) | to_entries | all(.value == null))
        and .[0].NetworkSettings.Networks[$network] != null
      ' <<<"$container_json" >/dev/null ||
      fail 'shared observability member publishes a host port'
  done < <(jq -r '.[0].Containers | keys[]' <<<"$network_json")
}

ensure_observability_network() {
  if ! docker network inspect "$OBSERVABILITY_NETWORK" >/dev/null 2>&1; then
    docker network create \
      --driver bridge \
      --subnet "$OBSERVABILITY_NETWORK_SUBNET" \
      --gateway "$OBSERVABILITY_NETWORK_GATEWAY" \
      --opt com.docker.network.bridge.enable_icc=true \
      --opt com.docker.network.bridge.enable_ip_masquerade=true \
      --label com.codestra.authority.repository=appolon1908-hue/Infustruction-repo \
      --label com.codestra.environment=staging \
      --label "com.codestra.network.contract=$OBSERVABILITY_NETWORK_CONTRACT" \
      "$OBSERVABILITY_NETWORK" >/dev/null ||
      fail 'shared observability network could not be created'
  fi
  validate_observability_network
}

validate_release_evidence() {
  local evidence_root archive manifest bundle sbom vulnerability_report
  local archive_hash manifest_hash sbom_hash vulnerability_hash current
  evidence_root="${MIDDLEWARE_RELEASE_EVIDENCE_ROOT:-$EXPECTED_RELEASE_EVIDENCE_ROOT}"
  [[ "$evidence_root" == "$EXPECTED_RELEASE_EVIDENCE_ROOT" ]] ||
    fail 'Middleware release evidence root does not match the reviewed path'
  [[ -d "$evidence_root" && ! -L "$evidence_root" ]] ||
    fail 'Middleware release evidence directory is absent or symbolic'
  current="$evidence_root"
  while :; do
    assert_protected_path "$current"
    [[ "$current" == / ]] && break
    current="$(dirname -- "$current")"
  done
  while IFS= read -r -d '' current; do
    assert_protected_path "$current"
  done < <(find "$evidence_root" -xdev -print0)

  archive="$evidence_root/$EXPECTED_RELEASE_ARTIFACT_NAME.zip"
  manifest="$evidence_root/release-manifest.v1.json"
  bundle="$evidence_root/release-manifest.v1.sigstore.json"
  sbom="$evidence_root/middleware.spdx.json"
  vulnerability_report="$evidence_root/middleware.grype.json"
  for current in "$archive" "$manifest" "$bundle" "$sbom" "$vulnerability_report"; do
    [[ -f "$current" && ! -L "$current" ]] ||
      fail 'required Middleware release evidence file is absent or symbolic'
  done

  read -r archive_hash _ < <(sha256sum -- "$archive")
  read -r manifest_hash _ < <(sha256sum -- "$manifest")
  read -r sbom_hash _ < <(sha256sum -- "$sbom")
  read -r vulnerability_hash _ < <(sha256sum -- "$vulnerability_report")
  [[ "sha256:$archive_hash" == "$EXPECTED_RELEASE_ARTIFACT_DIGEST" ]] ||
    fail 'Middleware release artifact digest does not match the lock'
  [[ "sha256:$manifest_hash" == "$EXPECTED_RELEASE_MANIFEST_SHA256" ]] ||
    fail 'Middleware release manifest digest does not match the lock'
  [[ "sha256:$sbom_hash" == "$EXPECTED_SBOM_SHA256" ]] ||
    fail 'Middleware SBOM digest does not match the signed manifest'
  [[ "sha256:$vulnerability_hash" == "$EXPECTED_VULNERABILITY_REPORT_SHA256" ]] ||
    fail 'Middleware vulnerability report digest does not match the signed manifest'

  "$COSIGN" verify-blob \
    --bundle "$bundle" \
    --certificate-identity "$EXPECTED_RELEASE_IDENTITY" \
    --certificate-oidc-issuer "$EXPECTED_RELEASE_ISSUER" \
    "$manifest" >/dev/null
  jq -e \
    --arg source "$EXPECTED_SOURCE" \
    --arg image "$EXPECTED_IMAGE" \
    --arg digest "$EXPECTED_DIGEST" \
    --arg schema '0008_durable_communications' \
    --arg releaseId "$EXPECTED_RELEASE_ID" \
    --arg workflow "$EXPECTED_RELEASE_IDENTITY" \
    --arg sbom "$EXPECTED_SBOM_SHA256" \
    --arg vulnerability "$EXPECTED_VULNERABILITY_REPORT_SHA256" \
    --argjson runId "$EXPECTED_RELEASE_RUN_ID" \
    --argjson runAttempt "$EXPECTED_RELEASE_RUN_ATTEMPT" '
      .schema_version == "1.0"
      and .repository == "appolon1908-hue/Middleware-"
      and .service == "middleware-api"
      and .source.git_sha == $source
      and .source.ref == "refs/heads/main"
      and .image.reference == $image
      and .image.digest == $digest
      and .image.platforms == ["linux/amd64"]
      and .runtime.schema_or_migration_head == $schema
      and .runtime.external_effects_default == "disabled"
      and .release_id == $releaseId
      and .build.run_id == $runId
      and .build.run_attempt == $runAttempt
      and .build.workflow_identity == $workflow
      and .artifacts.sbom.sha256 == $sbom
      and .artifacts.vulnerability_report.sha256 == $vulnerability
      and .promotion.mutable_tags_authoritative == false
      and .verification.transparency_log_required == true
    ' "$manifest" >/dev/null ||
    fail 'signed Middleware release manifest does not match the runtime lock'

  "$COSIGN" verify \
    --certificate-identity "$EXPECTED_RELEASE_IDENTITY" \
    --certificate-oidc-issuer "$EXPECTED_RELEASE_ISSUER" \
    "$EXPECTED_IMAGE" --output json >"$STATE_ROOT/state/middleware-image-signature.json"
  jq -e \
    --arg source "$EXPECTED_SOURCE" \
    --arg digest "$EXPECTED_DIGEST" '
      length == 1
      and .[0].critical.image["docker-manifest-digest"] == $digest
      and .[0].optional["codestra.source_sha"] == $source
      and .[0].optional["codestra.schema_head"] == "0008_durable_communications"
    ' "$STATE_ROOT/state/middleware-image-signature.json" >/dev/null ||
    fail 'Middleware image signature annotations do not match the lock'

  "$COSIGN" verify-attestation \
    --type spdxjson \
    --certificate-identity "$EXPECTED_RELEASE_IDENTITY" \
    --certificate-oidc-issuer "$EXPECTED_RELEASE_ISSUER" \
    "$EXPECTED_IMAGE" --output json >"$STATE_ROOT/state/middleware-spdx-attestation.json"
  jq -e --arg digest "${EXPECTED_DIGEST#sha256:}" '
      (.payload | @base64d | fromjson) as $statement
      | $statement._type == "https://in-toto.io/Statement/v0.1"
      and $statement.predicateType == "https://spdx.dev/Document"
      and $statement.subject == [{
        "name": "ghcr.io/appolon1908-hue/codestra-middleware",
        "digest": {"sha256": $digest}
      }]
    ' "$STATE_ROOT/state/middleware-spdx-attestation.json" >/dev/null ||
    fail 'Middleware SPDX attestation subject does not match the locked image'
  /usr/bin/cmp --silent \
    <(jq -S . "$sbom") \
    <(jq -S -r '.payload | @base64d | fromjson | .predicate' "$STATE_ROOT/state/middleware-spdx-attestation.json") ||
    fail 'signed SPDX attestation does not match the locked release SBOM'
  chmod 600 \
    "$STATE_ROOT/state/middleware-image-signature.json" \
    "$STATE_ROOT/state/middleware-spdx-attestation.json"
}

validate_exact_merged_source() {
  : "${INFRASTRUCTURE_SOURCE_SHA:?INFRASTRUCTURE_SOURCE_SHA is required for deployment}"
  [[ "$INFRASTRUCTURE_SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]] || fail 'infrastructure source SHA is malformed'
  [[ "$(git -C "$ROOT_DIR" rev-parse HEAD)" == "$INFRASTRUCTURE_SOURCE_SHA" ]] || fail 'infrastructure source SHA does not match checkout'
  [[ -z "$(git -C "$ROOT_DIR" status --porcelain)" ]] || fail 'infrastructure deployment checkout is not clean'
  git -C "$ROOT_DIR" fetch --quiet --no-tags "$CANONICAL_REPOSITORY" \
    "+refs/heads/main:$CANONICAL_MAIN_REF" ||
    fail 'canonical infrastructure main could not be refreshed'
  git -C "$ROOT_DIR" merge-base --is-ancestor \
    "$INFRASTRUCTURE_SOURCE_SHA" "$CANONICAL_MAIN_REF" ||
    fail 'infrastructure source SHA is not merged into canonical main'
}

for command in docker python3 jq sha256sum openssl git stat find; do require "$command"; done
[[ -x /usr/bin/docker && -x /usr/bin/git && -x "$COMPOSE_BIN" ]] ||
  fail 'trusted Docker, Compose, or Git executable is absent'
if [[ "$ACTION" != render ]]; then
  validate_protected_checkout
fi
if [[ "$ACTION" == deploy ]]; then
  validate_exact_merged_source
fi
"$COMPOSE_BIN" version >/dev/null
[[ "$STATE_ROOT" == /* ]] || fail 'CODESTRA_STAGING_ROOT must be an absolute path'
[[ "$STATE_ROOT" != / && "$STATE_ROOT" != /etc && "$STATE_ROOT" != /opt && "$STATE_ROOT" != /srv ]] || fail 'unsafe staging root'

mkdir -p "$STATE_ROOT" "$STATE_ROOT/secrets" "$STATE_ROOT/evidence" "$STATE_ROOT/state" "$STATE_ROOT/tls/postgres" "$STATE_ROOT/tls/redis"
chmod 700 "$STATE_ROOT" "$STATE_ROOT/secrets" "$STATE_ROOT/evidence" "$STATE_ROOT/state" "$STATE_ROOT/tls" "$STATE_ROOT/tls/postgres" "$STATE_ROOT/tls/redis"

case "$ACTION" in
  render)
    jq -e \
      --arg image "$EXPECTED_IMAGE" \
      --arg digest "$EXPECTED_DIGEST" \
      --arg source "$EXPECTED_SOURCE" \
      --arg profile "$EXPECTED_PROFILE" \
      --arg releaseId "$EXPECTED_RELEASE_ID" \
      --argjson releaseArtifactId "$EXPECTED_RELEASE_ARTIFACT_ID" \
      --arg releaseArtifactName "$EXPECTED_RELEASE_ARTIFACT_NAME" \
      --arg releaseArtifactDigest "$EXPECTED_RELEASE_ARTIFACT_DIGEST" \
      --arg releaseManifestSha "$EXPECTED_RELEASE_MANIFEST_SHA256" \
      --arg sbomSha "$EXPECTED_SBOM_SHA256" \
      --arg vulnerabilitySha "$EXPECTED_VULNERABILITY_REPORT_SHA256" \
      --arg evidenceRoot "$EXPECTED_RELEASE_EVIDENCE_ROOT" \
      --arg releaseIdentity "$EXPECTED_RELEASE_IDENTITY" \
      --arg releaseIssuer "$EXPECTED_RELEASE_ISSUER" \
      --arg publicUrl "$EXPECTED_KEYCLOAK_PUBLIC_URL" \
      --arg issuer "$EXPECTED_KEYCLOAK_ISSUER" \
      --arg jwksUri "$EXPECTED_KEYCLOAK_JWKS_URI" '
        .schema_version == "1.4"
        and .environment == "staging"
        and .middleware.image_reference == $image
        and .middleware.image_digest == $digest
        and .middleware.source_sha == $source
        and .middleware.runtime_profile_id == $profile
        and .middleware.release_id == $releaseId
        and .middleware.release_artifact_id == $releaseArtifactId
        and .middleware.release_artifact_name == $releaseArtifactName
        and .middleware.release_artifact_digest == $releaseArtifactDigest
        and .middleware.release_manifest_sha256 == $releaseManifestSha
        and .middleware.sbom_sha256 == $sbomSha
        and .middleware.vulnerability_report_sha256 == $vulnerabilitySha
        and .middleware.release_evidence_root == $evidenceRoot
        and .middleware.release_workflow_identity == $releaseIdentity
        and .middleware.release_oidc_issuer == $releaseIssuer
        and .identity.public_url == $publicUrl
        and .identity.admin_api_base_url == $publicUrl
        and .identity.issuer == $issuer
        and .identity.jwks_uri == $jwksUri
        and .identity.realm == "codestra"
        and .identity.admin_authentication_realm == "master"
        and .identity.production_identity_endpoint_allowed == false
        and .transport.postgres_tls == true
        and .transport.redis_tls == true
        and .network.shared_observability == {
          "name": "codestra-observability",
          "contract": "codestra-observability-staging-v1",
          "driver": "bridge",
          "scope": "local",
          "internal": false,
          "attachable": false,
          "ingress": false,
          "subnet": "192.168.16.0/24",
          "gateway": "192.168.16.1",
          "inter_container_communication": true,
          "ip_masquerade": true,
          "host_ports_published": false,
          "allowed_container_names": [
            "codestra-prometheus-staging",
            "codestra-grafana-staging"
          ]
        }
        and .persistence.preserve_on_redeploy == true
        and .persistence.preserve_on_failure_rollback == true
        and .activation.prometheus_target == "pending"
        and .activation.blackbox_target == "pending"
        and .umbrella_controls == {
          "LIVE_ADVERTISING_ENABLED": false,
          "EXTERNAL_DELIVERY_ENABLED": false,
          "SOCIAL_PUBLISHING_ENABLED": false,
          "EXTERNAL_MODEL_CALLS_ENABLED": false,
          "N8N_EXTERNAL_PROVIDER_WRITES": false
        }
        and .external_effects_enabled == false
      ' "$LOCK_FILE" >/dev/null
    printf 'STAGING_RUNTIME_LOCK=PASS\n'
    exit 0
    ;;
  status)
    [[ -f "$STATE_ROOT/deployment.env" ]] || fail 'deployment state is absent'
    validate_observability_network
    compose ps
    exit 0
    ;;
  rollback)
    [[ -f "$STATE_ROOT/deployment.env" ]] || fail 'deployment state is absent'
    compose down --remove-orphans
    rm -f "$STATE_ROOT/runtime-context.json"
    printf 'STAGING_ROLLBACK=PASS DATA_VOLUMES=PRESERVED\n'
    exit 0
    ;;
  reset)
    [[ "${CONFIRM_DESTRUCTIVE_RESET:-}" == 'DELETE_CODESTRA_STAGE6_STAGING_DATA' ]] || fail 'destructive reset confirmation is missing'
    [[ -f "$STATE_ROOT/deployment.env" ]] || fail 'deployment state is absent'
    compose down --volumes --remove-orphans
    rm -f "$STATE_ROOT/runtime-context.json"
    printf 'STAGING_RESET=PASS DATA_VOLUMES=DELETED\n'
    exit 0
    ;;
  deploy) ;;
  *) fail "unsupported action: $ACTION" ;;
esac

: "${KEYCLOAK_PUBLIC_URL:?KEYCLOAK_PUBLIC_URL is required}"
: "${KEYCLOAK_REALM:?KEYCLOAK_REALM is required}"
[[ "${KEYCLOAK_PUBLIC_URL%/}" == "$EXPECTED_KEYCLOAK_PUBLIC_URL" ]] || fail "staging runtime requires canonical Keycloak URL $EXPECTED_KEYCLOAK_PUBLIC_URL"
[[ "$KEYCLOAK_REALM" == "$EXPECTED_KEYCLOAK_REALM" ]] || fail 'staging runtime requires Keycloak realm codestra'

[[ -x "$COSIGN" ]] || fail "missing trusted cosign executable: $COSIGN"
validate_release_evidence

ensure_secret "$STATE_ROOT/secrets/postgres_password"
ensure_secret "$STATE_ROOT/secrets/redis_password"
for producer in "${WEBHOOK_PRODUCERS[@]}"; do
  ensure_secret "$STATE_ROOT/secrets/webhook_${producer,,}"
done

for image in "$EXPECTED_IMAGE" "$POSTGRES_IMAGE" "$REDIS_IMAGE"; do
  docker pull "$image" >/dev/null
done
resolved="$(docker image inspect "$EXPECTED_IMAGE" --format '{{json .RepoDigests}}')"
printf '%s' "$resolved" | grep -Fq "$EXPECTED_IMAGE" || fail 'local Middleware image does not match locked digest'

ensure_observability_network

CA_KEY="$STATE_ROOT/tls/ca.key"
CA_CERT="$STATE_ROOT/tls/ca.crt"
if [[ ! -s "$CA_KEY" || ! -s "$CA_CERT" ]]; then
  openssl req -x509 -newkey rsa:4096 -sha256 -nodes -days 30 \
    -subj '/CN=Codestra Stage 6 Private Staging CA' \
    -keyout "$CA_KEY" -out "$CA_CERT" >/dev/null 2>&1
fi
chmod 600 "$CA_KEY"
chmod 644 "$CA_CERT"

issue_server_certificate() {
  local name="$1" hostname="$2" directory="$STATE_ROOT/tls/$1"
  local key="$directory/server.key" csr="$directory/server.csr" cert="$directory/server.crt" ext="$directory/server.ext"
  if [[ ! -s "$key" || ! -s "$cert" ]]; then
    cat >"$ext" <<EXT
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:$hostname
EXT
    openssl req -new -newkey rsa:3072 -sha256 -nodes -subj "/CN=$hostname" -keyout "$key" -out "$csr" >/dev/null 2>&1
    openssl x509 -req -sha256 -days 30 -in "$csr" -CA "$CA_CERT" -CAkey "$CA_KEY" -CAcreateserial -extfile "$ext" -out "$cert" >/dev/null 2>&1
    rm -f "$csr" "$ext"
  fi
  chmod 600 "$key"
  chmod 644 "$cert"
  openssl verify -CAfile "$CA_CERT" "$cert" >/dev/null
  openssl x509 -in "$cert" -noout -checkhost "$hostname" >/dev/null
}
issue_server_certificate postgres "$POSTGRES_HOST"
issue_server_certificate redis "$REDIS_HOST"

cat >"$STATE_ROOT/tls/pg_hba.conf" <<'HBA'
local all all trust
hostssl all all 0.0.0.0/0 scram-sha-256
hostssl all all ::/0 scram-sha-256
hostnossl all all 0.0.0.0/0 reject
hostnossl all all ::/0 reject
HBA
chmod 644 "$STATE_ROOT/tls/pg_hba.conf"

SYSTEM_CA="$STATE_ROOT/tls/system-ca-certificates.crt"
COMBINED_CA="$STATE_ROOT/tls/combined-ca-certificates.crt"
temporary_container="$(docker create "$EXPECTED_IMAGE")"
if ! docker cp "$temporary_container:/etc/ssl/certs/ca-certificates.crt" "$SYSTEM_CA"; then
  docker rm -f "$temporary_container" >/dev/null 2>&1 || true
  fail 'unable to extract immutable image CA bundle'
fi
docker rm "$temporary_container" >/dev/null
cat "$SYSTEM_CA" "$CA_CERT" >"$COMBINED_CA"
chmod 644 "$SYSTEM_CA" "$COMBINED_CA"

postgres_password="$(cat "$STATE_ROOT/secrets/postgres_password")"
redis_password="$(cat "$STATE_ROOT/secrets/redis_password")"
cat >"$STATE_ROOT/middleware.env" <<ENV
APP_ENV=staging
RUNTIME_PROFILE_ID=$EXPECTED_PROFILE
APP_VERSION=0.1.0
APP_SOURCE_SHA=$EXPECTED_SOURCE
IMAGE_DIGEST=$EXPECTED_DIGEST
SCHEMA_HEAD=0008_durable_communications
BUILD_TIME=2026-09-02T17:41:48Z
EXTERNAL_EFFECTS_ENABLED=false
LIVE_ADVERTISING_ENABLED=false
EXTERNAL_DELIVERY_ENABLED=false
SOCIAL_PUBLISHING_ENABLED=false
EXTERNAL_MODEL_CALLS_ENABLED=false
N8N_EXTERNAL_PROVIDER_WRITES=false
KEYCLOAK_ISSUER=$EXPECTED_KEYCLOAK_ISSUER
KEYCLOAK_JWKS_URI=$EXPECTED_KEYCLOAK_JWKS_URI
MIDDLEWARE_AUDIENCE=middleware-api
JWKS_TIMEOUT_SECONDS=3
READINESS_TIMEOUT_SECONDS=3
DATABASE_URL=postgresql://middleware_staging:${postgres_password}@${POSTGRES_HOST}:5432/codestra_staging?sslmode=verify-full
REDIS_URL=rediss://middleware-staging:${redis_password}@${REDIS_HOST}:6379/14
ALLOW_IN_MEMORY_STORAGE=false
NATS_URL=
NATS_STREAM=CODESTRA_STAGING_EVENTS
NATS_SUBJECT_PREFIX=codestra.staging.events
NATS_CREDS_FILE=
NATS_DISPATCH_MODE=disabled
NATS_ALLOW_INSECURE_TEST_CONNECTION=false
TEMPORAL_ADDRESS=
TEMPORAL_NAMESPACE=codestra-staging
TEMPORAL_TASK_QUEUE=codestra-staging-critical
TEMPORAL_WORKER_MODE=disabled
TEMPORAL_SERVER_ROOT_CA_FILE=
TEMPORAL_CLIENT_CERT_FILE=
TEMPORAL_CLIENT_KEY_FILE=
TEMPORAL_TLS_SERVER_NAME=
TEMPORAL_ALLOW_INSECURE_TEST_CONNECTION=false
PRODUCTION_ACTIVATION_ID=
PRODUCTION_DIALING=DISABLED
WEBHOOK_SECRET_ODOO_INTEGRATION=$(cat "$STATE_ROOT/secrets/webhook_odoo_integration")
WEBHOOK_SECRET_N8N_AUTOMATION=$(cat "$STATE_ROOT/secrets/webhook_n8n_automation")
WEBHOOK_SECRET_VICIDIAL_ADAPTER=$(cat "$STATE_ROOT/secrets/webhook_vicidial_adapter")
WEBHOOK_SECRET_TELNEXA_GATEWAY=$(cat "$STATE_ROOT/secrets/webhook_telnexa_gateway")
WEBHOOK_SECRET_KLYROW_GATEWAY=$(cat "$STATE_ROOT/secrets/webhook_klyrow_gateway")
WEBHOOK_SECRET_KYQRA_GATEWAY=$(cat "$STATE_ROOT/secrets/webhook_kyqra_gateway")
WEBHOOK_SECRET_POSTLY_ADAPTER=$(cat "$STATE_ROOT/secrets/webhook_postly_adapter")
OUTBOX_DISPATCH_ENABLED=false
SEND_EVENTS=false
ENABLE_EXTERNAL_DELIVERY=false
LIVE_WRITE=false
LIVE_WRITES=false
ODOO_WRITE=false
CALLBACK_DISPATCH=false
N8N_DELIVERY_ENABLED=false
VICIDIAL_WRITES_ENABLED=false
ENABLE_VICIDIAL_WRITES=false
EXTERNAL_DIAL_ENABLED=false
PRODUCTION_CALLBACKS_ENABLED=false
N8N_PRODUCTION_WORKFLOWS_ENABLED=false
FORM_ODOO_DELIVERY_ENABLED=false
CRAWLER_ODOO_DELIVERY_ENABLED=false
SCRAPPER_ODOO_DELIVERY_ENABLED=false
CRAWLER_EXTERNAL_CONTACT_ENABLED=false
SCRAPPER_EXTERNAL_CONTACT_ENABLED=false
SMS_DELIVERY_ENABLED=false
EMAIL_DELIVERY_ENABLED=false
LIVE_SMS_DELIVERY=false
LIVE_EMAIL_DELIVERY=false
LIVE_PSTN_DIALING=false
SOCIAL_DELIVERY_ENABLED=false
CRAWLER_EXECUTION_ENABLED=false
SCRAPPER_EXECUTION_ENABLED=false
UNRESTRICTED_CRAWLING=false
LIVE_CALL_CONTROL=false
GENERAL_AI_DIALING=false
ENV
chmod 600 "$STATE_ROOT/middleware.env"

cat >"$STATE_ROOT/deployment.env" <<ENV
MIDDLEWARE_ENV_FILE=$STATE_ROOT/middleware.env
POSTGRES_PASSWORD_FILE=$STATE_ROOT/secrets/postgres_password
REDIS_PASSWORD_FILE=$STATE_ROOT/secrets/redis_password
STAGING_CA_CERT_FILE=$CA_CERT
POSTGRES_TLS_CERT_FILE=$STATE_ROOT/tls/postgres/server.crt
POSTGRES_TLS_KEY_FILE=$STATE_ROOT/tls/postgres/server.key
POSTGRES_HBA_FILE=$STATE_ROOT/tls/pg_hba.conf
REDIS_TLS_CERT_FILE=$STATE_ROOT/tls/redis/server.crt
REDIS_TLS_KEY_FILE=$STATE_ROOT/tls/redis/server.key
MIDDLEWARE_CA_BUNDLE_FILE=$COMBINED_CA
ENV
chmod 600 "$STATE_ROOT/deployment.env"
unset postgres_password redis_password

"$0" render

docker run --rm --env-file "$STATE_ROOT/middleware.env" \
  -v "$COMBINED_CA:/etc/ssl/certs/ca-certificates.crt:ro" \
  "$EXPECTED_IMAGE" -c 'from app.config import Settings, UMBRELLA_CONTROL_NAMES; s=Settings.from_env(); assert s.app_env == "staging"; assert s.runtime_profile_id == "codestra-middleware-staging-v1"; assert not s.allow_in_memory_storage; assert not s.outbox_dispatch_enabled; assert set(s.umbrella_controls) == set(UMBRELLA_CONTROL_NAMES); assert not any(s.umbrella_controls.values()); assert not any(s.external_effects.values())' >/dev/null

rendered="$STATE_ROOT/state/compose.rendered.yaml"
compose config >"$rendered"
chmod 600 "$rendered"
if grep -Eq '^[[:space:]]+ports:' "$rendered"; then
  fail 'host ports are prohibited'
fi

rollback_on_error() {
  status=$?
  if [[ $status -ne 0 ]]; then
    compose logs --no-color --tail=200 >"$STATE_ROOT/state/failed-deployment.log" 2>&1 || true
    chmod 600 "$STATE_ROOT/state/failed-deployment.log" || true
    compose down --remove-orphans >/dev/null 2>&1 || true
  fi
  exit "$status"
}
trap rollback_on_error EXIT

compose down --remove-orphans >/dev/null 2>&1 || true
compose up -d postgres redis
compose run --rm middleware-migrate
compose up -d middleware

health=''
for _ in $(seq 1 60); do
  health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "${PROJECT}-middleware-1" 2>/dev/null || true)"
  [[ "$health" == healthy ]] && break
  sleep 2
done
[[ "$health" == healthy ]] || fail 'Middleware did not become healthy'

network_internal="$(docker network inspect codestra-intake-observability-staging_private --format '{{.Internal}}')"
[[ "$network_internal" == true ]] || fail 'private network is not internal'
published="$(docker inspect --format '{{json .NetworkSettings.Ports}}' "${PROJECT}-middleware-1")"
[[ "$published" == '{"8080/tcp":null}' || "$published" == '{}' ]] || fail 'Middleware has a published port'
container_image="$(docker inspect --format '{{.Config.Image}}' "${PROJECT}-middleware-1")"
[[ "$container_image" == "$EXPECTED_IMAGE" ]] || fail 'running container does not use the locked image reference'

python3 - <<PY >"$STATE_ROOT/runtime-context.json"
import json
print(json.dumps({
  "schema_version": "1.4",
  "environment": "staging",
  "project": "$PROJECT",
  "middleware_source_sha": "$EXPECTED_SOURCE",
  "middleware_image_digest": "$EXPECTED_DIGEST",
  "middleware_runtime_profile": "$EXPECTED_PROFILE",
  "middleware_release_id": "$EXPECTED_RELEASE_ID",
  "middleware_release_artifact_digest": "$EXPECTED_RELEASE_ARTIFACT_DIGEST",
  "middleware_release_manifest_sha256": "$EXPECTED_RELEASE_MANIFEST_SHA256",
  "middleware_container": "${PROJECT}-middleware-1",
  "private_network": "codestra-intake-observability-staging_private",
  "private_network_internal": True,
  "shared_observability_network": "$OBSERVABILITY_NETWORK",
  "shared_observability_network_contract": "$OBSERVABILITY_NETWORK_CONTRACT",
  "shared_observability_network_internal": False,
  "shared_observability_network_subnet": "$OBSERVABILITY_NETWORK_SUBNET",
  "host_ports_published": False,
  "postgres_tls": True,
  "redis_tls": True,
  "keycloak_public_url": "$EXPECTED_KEYCLOAK_PUBLIC_URL",
  "keycloak_issuer": "$EXPECTED_KEYCLOAK_ISSUER",
  "umbrella_controls": {
    "LIVE_ADVERTISING_ENABLED": False,
    "EXTERNAL_DELIVERY_ENABLED": False,
    "SOCIAL_PUBLISHING_ENABLED": False,
    "EXTERNAL_MODEL_CALLS_ENABLED": False,
    "N8N_EXTERNAL_PROVIDER_WRITES": False
  },
  "named_volumes_preserved_on_redeploy": True,
  "deployment_result": "PASS",
  "external_effects_enabled": False
}, sort_keys=True, separators=(",", ":")))
PY
chmod 600 "$STATE_ROOT/runtime-context.json"
trap - EXIT
printf 'STAGING_DEPLOYMENT=PASS\n'
printf 'STAGING_PROJECT=%s\n' "$PROJECT"
printf 'STAGING_PRIVATE_NETWORK=codestra-intake-observability-staging_private\n'
printf 'STAGING_OBSERVABILITY_NETWORK=%s\n' "$OBSERVABILITY_NETWORK"
