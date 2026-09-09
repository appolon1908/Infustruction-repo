#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
readonly REPOSITORY="appolon1908-hue/Kong"
readonly INSTALLER="$ROOT/scripts/install_kong_actions_runner.sh"
readonly API_VERSION="2022-11-28"
readonly EXPECTED_WORKFLOW="Generate immutable Kong release evidence"
readonly EXPECTED_WORKFLOW_PATH=".github/workflows/release.yml"
readonly EXPECTED_JOB="runtime-topology"
readonly RUNNER_NAME="codestra-kong-staging-01"
readonly RUNNER_LABEL="kong-runtime"
readonly REMOTE_INSTALLER="/usr/local/sbin/install-codestra-kong-actions-runner"

HOST=""
SSH_USER=""
SSH_PORT="22"
SSH_KEY_FILE=""
KNOWN_HOSTS_FILE=""
ADMIN_TOKEN_FILE=""
RUNTIME_RUN_ID=""
EVIDENCE_FILE=""
REPLACE_STALE=false

fail() {
  printf 'KONG_RUNTIME_RUNNER_CONFIGURATION=FAIL:%s\n' "$1" >&2
  exit 2
}

usage() {
  cat <<'EOF'
Usage:
  configure_kong_runtime_runner.sh \
    --host HOST \
    --ssh-user USER \
    --ssh-port PORT \
    --ssh-key-file FILE \
    --known-hosts-file FILE \
    --admin-token-file FILE \
    --runtime-run-id RUN_ID \
    --evidence-file ABSOLUTE_PATH \
    [--replace-stale-registration]

The controller verifies that the supplied run is the exact protected `staging`
release run and that its `runtime-topology` job is queued with labels
[self-hosted, linux, kong-runtime] and no runner assigned before it touches the
host. It does not set release evidence variables, mutate Kong/Admin/runtime
objects, grant Docker access, or authorize production traffic/external effects.
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
    --host) HOST="${2:?}"; shift 2 ;;
    --ssh-user) SSH_USER="${2:?}"; shift 2 ;;
    --ssh-port) SSH_PORT="${2:?}"; shift 2 ;;
    --ssh-key-file) SSH_KEY_FILE="${2:?}"; shift 2 ;;
    --known-hosts-file) KNOWN_HOSTS_FILE="${2:?}"; shift 2 ;;
    --admin-token-file) ADMIN_TOKEN_FILE="${2:?}"; shift 2 ;;
    --runtime-run-id) RUNTIME_RUN_ID="${2:?}"; shift 2 ;;
    --evidence-file) EVIDENCE_FILE="${2:?}"; shift 2 ;;
    --replace-stale-registration) REPLACE_STALE=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) fail "unknown_argument:${1}" ;;
  esac
done

[[ "$HOST" =~ ^[A-Za-z0-9_.-]+$ ]] || fail invalid_host
[[ "$SSH_USER" =~ ^[A-Za-z_][A-Za-z0-9_-]{0,31}$ ]] || fail invalid_ssh_user
[[ "$SSH_PORT" =~ ^[0-9]{1,5}$ ]] && ((SSH_PORT >= 1 && SSH_PORT <= 65535)) \
  || fail invalid_ssh_port
[[ "$RUNTIME_RUN_ID" =~ ^[1-9][0-9]*$ ]] || fail invalid_runtime_run_id
[[ "$EVIDENCE_FILE" = /* && "$EVIDENCE_FILE" != *..* && "$EVIDENCE_FILE" != *//* ]] \
  || fail invalid_evidence_path
secure_file "$SSH_KEY_FILE" ssh_key
secure_file "$KNOWN_HOSTS_FILE" known_hosts
secure_file "$ADMIN_TOKEN_FILE" admin_token
ssh-keygen -y -f "$SSH_KEY_FILE" >/dev/null 2>&1 || fail ssh_private_key_unusable
known_host_lookup="$HOST"
[[ "$SSH_PORT" == 22 ]] || known_host_lookup="[$HOST]:$SSH_PORT"
ssh-keygen -F "$known_host_lookup" -f "$KNOWN_HOSTS_FILE" >/dev/null 2>&1 \
  || fail known_hosts_target_missing
[[ -x "$INSTALLER" && ! -L "$INSTALLER" ]] || fail installer_unavailable

for tool in awk base64 cat gh jq mkdir python3 sha256sum ssh ssh-keygen stat; do
  command -v "$tool" >/dev/null || fail "missing_tool:${tool}"
done

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

export GH_TOKEN
GH_TOKEN="$(<"$ADMIN_TOKEN_FILE")"
[[ -n "$GH_TOKEN" ]] || fail empty_admin_token

gh api -H "X-GitHub-Api-Version: $API_VERSION" "repos/$REPOSITORY" \
  --jq 'select(.permissions.admin == true) | .full_name' | grep -Fxq "$REPOSITORY" \
  || fail repository_administration_required

staging_json="$(gh api -H "X-GitHub-Api-Version: $API_VERSION" \
  "repos/$REPOSITORY/branches/staging")"
staging_sha="$(jq -er '.commit.sha' <<<"$staging_json")"
[[ "$staging_sha" =~ ^[0-9a-f]{40}$ ]] || fail staging_sha_readback
jq -e '.protected == true' <<<"$staging_json" >/dev/null || fail staging_not_protected

run_json="$(gh api -H "X-GitHub-Api-Version: $API_VERSION" \
  "repos/$REPOSITORY/actions/runs/$RUNTIME_RUN_ID")"
jq -e \
  --arg name "$EXPECTED_WORKFLOW" \
  --arg path "$EXPECTED_WORKFLOW_PATH" \
  --arg sha "$staging_sha" '
    .name == $name and
    .path == $path and
    .head_branch == "staging" and
    .head_sha == $sha and
    .event == "push" and
    .status == "queued" and
    .conclusion == null
  ' <<<"$run_json" >/dev/null || fail runtime_run_identity

jobs_json="$(gh api -H "X-GitHub-Api-Version: $API_VERSION" \
  "repos/$REPOSITORY/actions/runs/$RUNTIME_RUN_ID/jobs?filter=latest&per_page=100")"
matching_job="$(jq -c --arg name "$EXPECTED_JOB" '.jobs[] | select(.name == $name)' <<<"$jobs_json")"
[[ -n "$matching_job" ]] || fail runtime_job_missing
[[ "$(wc -l <<<"$matching_job")" -eq 1 ]] || fail duplicate_runtime_jobs
job_id="$(jq -er '.id' <<<"$matching_job")"
jq -e --arg label "$RUNNER_LABEL" '
  .status == "queued" and
  .conclusion == null and
  ((.runner_id == null) or (.runner_id == 0)) and
  ([.labels[]] | index("self-hosted") != null and index("linux") != null and index($label) != null)
' <<<"$matching_job" >/dev/null || fail runtime_job_not_waiting_for_exact_runner

# Inspect repository runner registration before requesting a new token.
runner_matches="$(gh api --paginate -H "X-GitHub-Api-Version: $API_VERSION" \
  "repos/$REPOSITORY/actions/runners?per_page=100" \
  --jq ".runners[] | select(.name == \"$RUNNER_NAME\") | @base64")"
replace_arg=()
if [[ -n "$runner_matches" ]]; then
  [[ "$(wc -l <<<"$runner_matches")" -eq 1 ]] || fail duplicate_exact_runner_names
  decoded="$(base64 --decode <<<"$runner_matches")"
  runner_id="$(jq -er '.id' <<<"$decoded")"
  runner_busy="$(jq -er '.busy' <<<"$decoded")"
  runner_status="$(jq -er '.status' <<<"$decoded")"
  "$REPLACE_STALE" || fail exact_runner_already_registered
  [[ "$runner_busy" == false && "$runner_status" == offline ]] || fail stale_runner_not_safe_to_replace
  gh api --method DELETE -H "X-GitHub-Api-Version: $API_VERSION" \
    "repos/$REPOSITORY/actions/runners/$runner_id" >/dev/null
  replace_arg=(--replace-stale-registration)
fi

installer_sha256="$(sha256sum "$INSTALLER" | awk '{print $1}')"
ssh "${ssh_options[@]}" "$remote" \
  "sudo -n install -d -m 0755 /usr/local/sbin && sudo -n tee '$REMOTE_INSTALLER' >/dev/null && sudo -n chmod 0755 '$REMOTE_INSTALLER'" \
  <"$INSTALLER"
remote_installer_sha256="$(ssh "${ssh_options[@]}" "$remote" \
  "sudo -n sha256sum '$REMOTE_INSTALLER' | awk '{print \$1}'")"
[[ "$remote_installer_sha256" == "$installer_sha256" ]] || fail remote_installer_checksum

# Host preflight is deliberately before registration-token creation. It may
# create the dedicated locked service identity, but it performs no runtime or
# network mutation and refuses to grant Docker authorization.
ssh "${ssh_options[@]}" "$remote" "sudo -n '$REMOTE_INSTALLER' --preflight-only"

registration_token="$(gh api --method POST -H "X-GitHub-Api-Version: $API_VERSION" \
  "repos/$REPOSITORY/actions/runners/registration-token" --jq .token)"
[[ "$registration_token" =~ ^[A-Za-z0-9_.=-]{20,512}$ ]] || fail registration_token_format
printf '%s\n' "$registration_token" | ssh "${ssh_options[@]}" "$remote" \
  "sudo -n '$REMOTE_INSTALLER' --registration-token-stdin ${replace_arg[*]}"
unset registration_token

# Bound the assignment check: the exact queued job must either be assigned to
# this exact runner or complete on it. Never register another runner to chase it.
assigned=false
assigned_runner_id=""
for _ in $(seq 1 20); do
  current_job="$(gh api -H "X-GitHub-Api-Version: $API_VERSION" \
    "repos/$REPOSITORY/actions/jobs/$job_id")"
  current_name="$(jq -r '.runner_name // ""' <<<"$current_job")"
  current_id="$(jq -r '.runner_id // 0' <<<"$current_job")"
  current_status="$(jq -r '.status' <<<"$current_job")"
  if [[ "$current_name" == "$RUNNER_NAME" && "$current_id" =~ ^[1-9][0-9]*$ ]]; then
    assigned=true
    assigned_runner_id="$current_id"
    break
  fi
  [[ "$current_status" == queued ]] || fail runtime_job_moved_without_exact_runner
  sleep 2
done
"$assigned" || fail exact_runner_assignment_timeout

mkdir -p "$(dirname "$EVIDENCE_FILE")"
python3 - "$EVIDENCE_FILE" "$RUNTIME_RUN_ID" "$job_id" "$staging_sha" \
  "$RUNNER_NAME" "$assigned_runner_id" "$installer_sha256" <<'PY'
import json
import sys
from pathlib import Path

out, run_id, job_id, sha, runner_name, runner_id, installer_sha = sys.argv[1:]
payload = {
    "schema": "codestra.kong-runtime-runner-bootstrap-evidence.v1",
    "repository": "appolon1908-hue/Kong",
    "branch": "staging",
    "protected_source_sha": sha,
    "runtime_run_id": int(run_id),
    "runtime_job_id": int(job_id),
    "runner_name": runner_name,
    "runner_id": int(runner_id),
    "required_labels": ["self-hosted", "linux", "kong-runtime"],
    "installer_sha256": installer_sha,
    "registration_token_persisted": False,
    "docker_authorization_created": False,
    "runtime_changed_by_bootstrap": False,
    "certification_claimed": False,
}
Path(out).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
chmod 0600 "$EVIDENCE_FILE"

printf '%s\n' \
  'KONG_RUNTIME_RUNNER_CONFIGURATION=PASS' \
  "STAGING_SHA=$staging_sha" \
  "RUNTIME_RUN_ID=$RUNTIME_RUN_ID" \
  "RUNTIME_JOB_ID=$job_id" \
  "RUNNER_NAME=$RUNNER_NAME" \
  "RUNNER_ID=$assigned_runner_id" \
  "EVIDENCE_FILE=$EVIDENCE_FILE" \
  'CERTIFICATION_CLAIMED=false' \
  'RUNTIME_MUTATION=NONE'
