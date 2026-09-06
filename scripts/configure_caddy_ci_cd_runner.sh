#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
readonly REPOSITORY="appolon1908-hue/Caddy"
readonly INSTALLER="$ROOT/scripts/install_caddy_actions_runner.sh"
readonly API_VERSION="2022-11-28"
readonly CANONICAL_RULESET="Protect Caddy promotion branches"

TARGET=""
HOST=""
SSH_USER=""
SSH_PORT="22"
SSH_KEY_FILE=""
KNOWN_HOSTS_FILE=""
ADMIN_TOKEN_FILE=""
REPLACE_STALE=false
EVIDENCE_FILE=""
BOUNDED_RUNTIME_RUN_ID=""

declare -A ENVIRONMENT_VARIABLES=()

fail() {
  printf 'CADDY_CI_CD_RUNNER_CONFIGURATION=FAIL:%s\n' "$1" >&2
  exit 2
}

usage() {
  cat <<'EOF'
Usage:
  configure_caddy_ci_cd_runner.sh \
    --target staging|production-readonly-canary \
    --host HOST \
    --ssh-user USER \
    --ssh-port PORT \
    --ssh-key-file FILE \
    --known-hosts-file FILE \
    --admin-token-file FILE \
    --bounded-runtime-run-id RUN_ID \
    --evidence-file FILE \
    [--replace-stale-registration] \
    --environment-variable NAME=ABSOLUTE_PATH [...]

Required staging variables:
  CADDY_STAGING_ENV_FILE
  CADDY_STAGING_DATA_SOURCE
  CADDY_STAGING_MTLS_CLIENT_CERT
  CADDY_STAGING_MTLS_CLIENT_KEY
  CADDY_STAGING_MTLS_CA_CERT

Required production variables:
  CADDY_PRODUCTION_MTLS_CLIENT_CERT
  CADDY_PRODUCTION_MTLS_CLIENT_KEY
  CADDY_PRODUCTION_MTLS_CA_CERT

The canonical Caddy ruleset must already be active and match the exact
protected production source. This bootstrap verifies it and never creates,
updates, retires, or deletes a repository ruleset.
EOF
}

secure_file() {
  local path="$1" label="$2" mode
  [[ -f "$path" && ! -L "$path" && -s "$path" ]] || fail "invalid_${label}_file"
  mode="$(stat -c '%a' -- "$path")"
  (( (8#$mode & 0077) == 0 )) || fail "${label}_file_permissions"
}

while (($#)); do
  case "$1" in
    --target) TARGET="${2:?}"; shift 2 ;;
    --host) HOST="${2:?}"; shift 2 ;;
    --ssh-user) SSH_USER="${2:?}"; shift 2 ;;
    --ssh-port) SSH_PORT="${2:?}"; shift 2 ;;
    --ssh-key-file) SSH_KEY_FILE="${2:?}"; shift 2 ;;
    --known-hosts-file) KNOWN_HOSTS_FILE="${2:?}"; shift 2 ;;
    --admin-token-file) ADMIN_TOKEN_FILE="${2:?}"; shift 2 ;;
    --bounded-runtime-run-id) BOUNDED_RUNTIME_RUN_ID="${2:?}"; shift 2 ;;
    --evidence-file) EVIDENCE_FILE="${2:?}"; shift 2 ;;
    --replace-stale-registration) REPLACE_STALE=true; shift ;;
    --environment-variable)
      pair="${2:?}"
      name="${pair%%=*}"
      value="${pair#*=}"
      [[ "$pair" == *=* && "$name" =~ ^[A-Z][A-Z0-9_]*$ ]] || fail invalid_environment_variable
      [[ "$value" = /* && "$value" != *..* && "$value" != *//* ]] || fail "invalid_environment_path:${name}"
      [[ "$value" != *$'\n'* && "$value" != *$'\r'* ]] || fail "invalid_environment_control_character:${name}"
      ENVIRONMENT_VARIABLES["$name"]="$value"
      shift 2
      ;;
    -h|--help) usage; exit 0 ;;
    *) fail "unknown_argument:${1}" ;;
  esac
done

[[ "$TARGET" == staging || "$TARGET" == production-readonly-canary ]] || fail invalid_target
[[ "$HOST" =~ ^[A-Za-z0-9_.-]+$ ]] || fail invalid_host
[[ "$SSH_USER" =~ ^[A-Za-z_][A-Za-z0-9_-]{0,31}$ ]] || fail invalid_ssh_user
[[ "$SSH_PORT" =~ ^[0-9]{1,5}$ ]] && ((SSH_PORT >= 1 && SSH_PORT <= 65535)) || fail invalid_ssh_port
[[ "$BOUNDED_RUNTIME_RUN_ID" =~ ^[0-9]+$ ]] || fail invalid_bounded_runtime_run_id
[[ "$EVIDENCE_FILE" = /* && "$EVIDENCE_FILE" != *..* && "$EVIDENCE_FILE" != *//* ]] || fail invalid_evidence_path
secure_file "$SSH_KEY_FILE" ssh_key
secure_file "$KNOWN_HOSTS_FILE" known_hosts
secure_file "$ADMIN_TOKEN_FILE" admin_token
ssh-keygen -y -f "$SSH_KEY_FILE" >/dev/null 2>&1 || fail ssh_private_key_unusable
known_host_lookup="$HOST"
[[ "$SSH_PORT" == 22 ]] || known_host_lookup="[$HOST]:$SSH_PORT"
ssh-keygen -F "$known_host_lookup" -f "$KNOWN_HOSTS_FILE" >/dev/null 2>&1 || fail known_hosts_target_missing
[[ -x "$INSTALLER" && ! -L "$INSTALLER" ]] || fail installer_unavailable

for tool in awk base64 cat gh grep head jq mktemp rm sha256sum ssh ssh-keygen stat tr wc python3; do
  command -v "$tool" >/dev/null || fail "missing_tool:${tool}"
done

case "$TARGET" in
  staging)
    readonly ENVIRONMENT="staging-readonly"
    readonly RUNNER_NAME="codestra-caddy-staging-01"
    readonly RUNNER_LABEL="codestra-staging"
    readonly EXPECTED_JOB_NAME="bounded-staging-runtime"
    required_variables=(
      CADDY_STAGING_ENV_FILE
      CADDY_STAGING_DATA_SOURCE
      CADDY_STAGING_MTLS_CLIENT_CERT
      CADDY_STAGING_MTLS_CLIENT_KEY
      CADDY_STAGING_MTLS_CA_CERT
    )
    ;;
  production-readonly-canary)
    readonly ENVIRONMENT="production-readonly-canary"
    readonly RUNNER_NAME="codestra-caddy-production-canary-01"
    readonly RUNNER_LABEL="codestra-production-canary"
    readonly EXPECTED_JOB_NAME="production-readonly-canary"
    required_variables=(
      CADDY_PRODUCTION_MTLS_CLIENT_CERT
      CADDY_PRODUCTION_MTLS_CLIENT_KEY
      CADDY_PRODUCTION_MTLS_CA_CERT
    )
    ;;
esac

for name in "${required_variables[@]}"; do
  [[ -n "${ENVIRONMENT_VARIABLES[$name]:-}" ]] || fail "missing_environment_variable:${name}"
done
[[ "${#ENVIRONMENT_VARIABLES[@]}" -eq "${#required_variables[@]}" ]] || fail unexpected_environment_variable

ssh_options=(
  -o BatchMode=yes
  -o IdentitiesOnly=yes
  -o StrictHostKeyChecking=yes
  -o "UserKnownHostsFile=$KNOWN_HOSTS_FILE"
  -o ConnectTimeout=15
  -o ServerAliveInterval=15
  -o ServerAliveCountMax=2
  -i "$SSH_KEY_FILE"
  -p "$SSH_PORT"
)
remote="${SSH_USER}@${HOST}"
installer_sha256="$(sha256sum "$INSTALLER" | awk '{print $1}')"

remote_preflight='set -Eeuo pipefail;'
for name in "${required_variables[@]}"; do
  path="${ENVIRONMENT_VARIABLES[$name]}"
  if [[ "$name" == *DATA_SOURCE ]]; then
    remote_preflight+=" sudo -n test -d $(printf '%q' "$path");"
  else
    remote_preflight+=" sudo -n test -f $(printf '%q' "$path");"
  fi
done
remote_preflight+=" sudo -n /usr/bin/docker info >/dev/null;"
if [[ "$TARGET" == production-readonly-canary ]]; then
  remote_preflight+=" sudo -n /usr/bin/docker inspect codestra-caddy >/dev/null;"
fi
ssh "${ssh_options[@]}" "$remote" "$remote_preflight"

export GH_TOKEN
GH_TOKEN="$(<"$ADMIN_TOKEN_FILE")"
[[ -n "$GH_TOKEN" ]] || fail empty_admin_token
gh api -H "X-GitHub-Api-Version: $API_VERSION" "repos/$REPOSITORY" \
  --jq 'select(.permissions.admin == true) | .full_name' | grep -Fxq "$REPOSITORY" \
  || fail repository_administration_required

production_sha="$(gh api -H "X-GitHub-Api-Version: $API_VERSION" \
  "repos/$REPOSITORY/git/ref/heads/production" --jq .object.sha)"
[[ "$production_sha" =~ ^[0-9a-f]{40}$ ]] || fail production_sha_readback

bounded_run="$(gh api -H "X-GitHub-Api-Version: $API_VERSION" \
  "repos/$REPOSITORY/actions/runs/$BOUNDED_RUNTIME_RUN_ID")"
jq -e --arg sha "$production_sha" '
  .name == "Caddy bounded runtime certification" and
  .path == ".github/workflows/bounded-runtime-certification.yml" and
  .head_branch == "production" and
  .head_sha == $sha and
  .event == "push" and
  (.status == "queued" or .status == "in_progress") and
  .conclusion == null
' <<<"$bounded_run" >/dev/null || fail bounded_runtime_run_identity

matching_jobs="$(gh api -H "X-GitHub-Api-Version: $API_VERSION" \
  "repos/$REPOSITORY/actions/runs/$BOUNDED_RUNTIME_RUN_ID/jobs?filter=latest&per_page=100" \
  --jq ".jobs[] | select(.name == \"$EXPECTED_JOB_NAME\")")"
[[ -n "$matching_jobs" ]] || fail expected_bounded_job_missing
[[ "$(jq -s length <<<"$matching_jobs")" -eq 1 ]] || fail duplicate_expected_bounded_jobs
bounded_job_id="$(jq -er '.id' <<<"$matching_jobs")"
jq -e --arg label "$RUNNER_LABEL" '
  .status == "queued" and
  .conclusion == null and
  ((.runner_id == null) or (.runner_id == 0)) and
  ([.labels[]] | index("self-hosted") != null and index($label) != null)
' <<<"$matching_jobs" >/dev/null || fail bounded_job_not_waiting_for_exact_runner

ruleset_file="$(mktemp)"
trap 'rm -f -- "${ruleset_file:-}"' EXIT
gh api -H "X-GitHub-Api-Version: $API_VERSION" \
  "repos/$REPOSITORY/contents/config/github/protected-branches-ruleset.json?ref=$production_sha" \
  --jq .content | tr -d '\n' | base64 --decode >"$ruleset_file"

expected_refs='refs/heads/development,refs/heads/main,refs/heads/production,refs/heads/staging,refs/heads/test'
expected_checks='immutable-release-gate,promotion-guard,validate-merge-result,validate-source'
validate_ruleset() {
  local input="$1"
  jq -e --arg refs "$expected_refs" --arg checks "$expected_checks" '
    .name == "Protect Caddy promotion branches" and
    .target == "branch" and
    .enforcement == "active" and
    (.bypass_actors | length) == 0 and
    ([.conditions.ref_name.include[]] | sort | join(",")) == $refs and
    ([.rules[] | select(.type == "pull_request") | .parameters.required_approving_review_count][0]) == 1 and
    ([.rules[] | select(.type == "pull_request") | .parameters.dismiss_stale_reviews_on_push][0]) == true and
    ([.rules[] | select(.type == "pull_request") | .parameters.require_last_push_approval][0]) == true and
    ([.rules[] | select(.type == "pull_request") | .parameters.required_review_thread_resolution][0]) == true and
    ([.rules[] | select(.type == "pull_request") | .parameters.allowed_merge_methods[]] | join(",")) == "squash" and
    ([.rules[] | select(.type == "required_linear_history")] | length) == 1 and
    ([.rules[] | select(.type == "non_fast_forward")] | length) == 1 and
    ([.rules[] | select(.type == "deletion")] | length) == 1 and
    ([.rules[] | select(.type == "required_status_checks") | .parameters.required_status_checks[].context] | sort | join(",")) == $checks
  ' "$input" >/dev/null
}
validate_ruleset "$ruleset_file" || fail ruleset_source_contract

mapfile -t canonical_ids < <(gh api -H "X-GitHub-Api-Version: $API_VERSION" \
  "repos/$REPOSITORY/rulesets" \
  --jq ".[] | select(.name == \"$CANONICAL_RULESET\") | .id")
[[ "${#canonical_ids[@]}" -eq 1 ]] || fail canonical_ruleset_count
canonical_id="${canonical_ids[0]}"
[[ "$canonical_id" =~ ^[0-9]+$ ]] || fail canonical_ruleset_id
ruleset_readback_file="$(mktemp)"
gh api -H "X-GitHub-Api-Version: $API_VERSION" \
  "repos/$REPOSITORY/rulesets/$canonical_id" >"$ruleset_readback_file"
validate_ruleset "$ruleset_readback_file" || fail canonical_ruleset_readback
rm -f -- "$ruleset_file" "$ruleset_readback_file"
trap - EXIT

echo CADDY_CANONICAL_RULESET_READBACK=PASS
echo CADDY_CANONICAL_RULESET_MUTATION_FORBIDDEN=PASS

# Environment binding is a separate, explicit bootstrap mutation. It never
# changes repository rulesets, source, Caddy runtime, traffic, or credentials.
gh api --method PUT -H "X-GitHub-Api-Version: $API_VERSION" \
  "repos/$REPOSITORY/environments/$ENVIRONMENT" --input - >/dev/null <<'JSON'
{
  "wait_timer": 0,
  "prevent_self_review": false,
  "deployment_branch_policy": {
    "protected_branches": true,
    "custom_branch_policies": false
  }
}
JSON
for name in "${required_variables[@]}"; do
  gh variable set "$name" --env "$ENVIRONMENT" --repo "$REPOSITORY" \
    --body "${ENVIRONMENT_VARIABLES[$name]}" >/dev/null
done
environment_readback="$(gh api -H "X-GitHub-Api-Version: $API_VERSION" \
  "repos/$REPOSITORY/environments/$ENVIRONMENT")"
jq -e '
  .deployment_branch_policy.protected_branches == true and
  .deployment_branch_policy.custom_branch_policies == false
' <<<"$environment_readback" >/dev/null || fail environment_branch_policy_readback
for name in "${required_variables[@]}"; do
  actual_value="$(gh api -H "X-GitHub-Api-Version: $API_VERSION" \
    "repos/$REPOSITORY/environments/$ENVIRONMENT/variables/$name" --jq .value)"
  [[ "$actual_value" == "${ENVIRONMENT_VARIABLES[$name]}" ]] || fail "environment_variable_readback:${name}"
done

ssh "${ssh_options[@]}" "$remote" \
  "sudo -n install -d -m 0755 /usr/local/sbin && sudo -n tee /usr/local/sbin/install-codestra-caddy-actions-runner >/dev/null && sudo -n chmod 0755 /usr/local/sbin/install-codestra-caddy-actions-runner" \
  <"$INSTALLER"
remote_installer_sha256="$(ssh "${ssh_options[@]}" "$remote" \
  "sudo -n sha256sum /usr/local/sbin/install-codestra-caddy-actions-runner | awk '{print \$1}'")"
[[ "$remote_installer_sha256" == "$installer_sha256" ]] || fail remote_installer_checksum

runner_json="$(gh api --paginate -H "X-GitHub-Api-Version: $API_VERSION" \
  "repos/$REPOSITORY/actions/runners?per_page=100" \
  --jq ".runners[] | select(.name == \"$RUNNER_NAME\") | @base64")"
if [[ -n "$runner_json" ]]; then
  "$REPLACE_STALE" || fail exact_runner_already_registered
  [[ "$(wc -l <<<"$runner_json")" -eq 1 ]] || fail duplicate_exact_runner_names
  decoded="$(base64 --decode <<<"$runner_json")"
  runner_id="$(jq -er '.id' <<<"$decoded")"
  runner_busy="$(jq -er '.busy' <<<"$decoded")"
  [[ "$runner_busy" == false ]] || fail exact_runner_busy
  gh api --method DELETE -H "X-GitHub-Api-Version: $API_VERSION" \
    "repos/$REPOSITORY/actions/runners/$runner_id" >/dev/null
fi

registration_token="$(gh api --method POST -H "X-GitHub-Api-Version: $API_VERSION" \
  "repos/$REPOSITORY/actions/runners/registration-token" --jq .token)"
[[ "$registration_token" =~ ^[A-Za-z0-9_.=-]{20,512}$ ]] || fail registration_token_response
printf '::add-mask::%s\n' "$registration_token" 2>/dev/null || true
remote_arguments=(--target "$TARGET" --registration-token-stdin)
"$REPLACE_STALE" && remote_arguments+=(--replace-stale-registration)
printf '%s\n' "$registration_token" | ssh "${ssh_options[@]}" "$remote" \
  "sudo -n /usr/local/sbin/install-codestra-caddy-actions-runner $(printf '%q ' "${remote_arguments[@]}")"
unset registration_token GH_TOKEN

export GH_TOKEN
GH_TOKEN="$(<"$ADMIN_TOKEN_FILE")"
deadline=$((SECONDS + 120))
verified_runner=""
while ((SECONDS < deadline)); do
  verified_runner="$(gh api --paginate -H "X-GitHub-Api-Version: $API_VERSION" \
    "repos/$REPOSITORY/actions/runners?per_page=100" \
    --jq ".runners[] | select(.name == \"$RUNNER_NAME\" and .status == \"online\")")"
  if [[ -n "$verified_runner" ]] && jq -e --arg label "$RUNNER_LABEL" \
    '[.labels[].name] | index("self-hosted") != null and index($label) != null' \
    <<<"$verified_runner" >/dev/null; then
    break
  fi
  verified_runner=""
  sleep 3
done
[[ -n "$verified_runner" ]] || fail runner_not_online
verified_runner_id="$(jq -er '.id' <<<"$verified_runner")"

assignment_deadline=$((SECONDS + 120))
assigned_job=""
while ((SECONDS < assignment_deadline)); do
  assigned_job="$(gh api -H "X-GitHub-Api-Version: $API_VERSION" \
    "repos/$REPOSITORY/actions/jobs/$bounded_job_id")"
  assigned_runner_id="$(jq -r '.runner_id // 0' <<<"$assigned_job")"
  assigned_status="$(jq -r '.status' <<<"$assigned_job")"
  if [[ "$assigned_runner_id" == "$verified_runner_id" ]] && \
     [[ "$assigned_status" == queued || "$assigned_status" == in_progress ]]; then
    break
  fi
  if [[ "$assigned_runner_id" != 0 && "$assigned_runner_id" != "$verified_runner_id" ]]; then
    fail bounded_job_assigned_to_different_runner
  fi
  [[ "$assigned_status" != completed ]] || fail bounded_job_completed_without_exact_runner
  assigned_job=""
  sleep 3
done
unset GH_TOKEN
[[ -n "$assigned_job" ]] || fail bounded_job_not_assigned_to_exact_runner

mkdir -p -- "$(dirname -- "$EVIDENCE_FILE")"
python3 - "$EVIDENCE_FILE" "$TARGET" "$ENVIRONMENT" "$RUNNER_NAME" "$RUNNER_LABEL" \
  "$installer_sha256" "$verified_runner_id" "$production_sha" "$canonical_id" \
  "$BOUNDED_RUNTIME_RUN_ID" "$bounded_job_id" "$EXPECTED_JOB_NAME" <<'PY'
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

(
    path, target, environment, name, label, installer_sha256, runner_id,
    production_sha, ruleset_id, bounded_runtime_run_id, bounded_job_id,
    bounded_job_name,
) = sys.argv[1:]
evidence = {
    "schema": "codestra.caddy-ci-cd-runner-bootstrap-evidence.v2",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "repository": "appolon1908-hue/Caddy",
    "target": target,
    "environment": environment,
    "runner_name": name,
    "runner_id": int(runner_id),
    "required_labels": ["self-hosted", label],
    "runner_status": "online",
    "runner_ephemeral": True,
    "runner_one_job": True,
    "installer_sha256": installer_sha256,
    "strict_host_key_checking": True,
    "registration_token_persisted": False,
    "registration_token_logged": False,
    "docker_authorization_created": False,
    "production_source_sha": production_sha,
    "canonical_ruleset": "Protect Caddy promotion branches",
    "canonical_ruleset_id": int(ruleset_id),
    "canonical_ruleset_verified": True,
    "canonical_ruleset_mutated": False,
    "unrelated_rulesets_changed": False,
    "bounded_runtime_run_id": int(bounded_runtime_run_id),
    "bounded_job_id": int(bounded_job_id),
    "bounded_job_name": bounded_job_name,
    "bounded_job_was_queued_for_exact_labels": True,
    "bounded_job_assigned_to_runner": True,
    "runtime_changed_by_bootstrap": False,
    "result": "PASS",
}
Path(path).write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

printf '%s\n' \
  'CADDY_CI_CD_RUNNER_CONFIGURATION=PASS' \
  "TARGET=$TARGET" \
  "ENVIRONMENT=$ENVIRONMENT" \
  "RUNNER_NAME=$RUNNER_NAME" \
  "RUNNER_LABEL=$RUNNER_LABEL" \
  'RUNNER_STATUS=online' \
  'RUNNER_EPHEMERAL=true' \
  'CANONICAL_RULESET_VERIFIED=true' \
  'CANONICAL_RULESET_MUTATED=false' \
  'RUNTIME_CHANGED_BY_BOOTSTRAP=false'
