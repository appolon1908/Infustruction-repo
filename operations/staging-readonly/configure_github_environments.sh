#!/usr/bin/env bash
set -Eeuo pipefail

# Configure the two protected GitHub release environments without accepting
# credential values on the command line. Every sensitive input must be a
# pre-existing regular file with owner-only permissions.

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
REPOSITORY="appolon1908-hue/Infustruction-repo"
CANDIDATE=""
STAGING_ENDPOINTS=""
PRODUCTION_ENDPOINTS=""
STAGING_BEARER_FILE=""
STAGING_METRICS_FILE=""
STAGING_GHCR_FILE=""
STAGING_RESTIC_REPOSITORY_FILE=""
STAGING_RESTIC_PASSWORD_PATH_FILE=""
PRODUCTION_BEARER_FILE=""
PRODUCTION_METRICS_FILE=""
PRODUCTION_GHCR_FILE=""

usage() {
  cat <<'EOF'
Usage:
  configure_github_environments.sh \
    --candidate FILE \
    --staging-endpoints FILE \
    --production-endpoints FILE \
    --staging-bearer-file FILE \
    --staging-metrics-file FILE \
    --staging-ghcr-file FILE \
    --staging-restic-repository-file FILE \
    --staging-restic-password-path-file FILE \
    --production-bearer-file FILE \
    --production-metrics-file FILE \
    --production-ghcr-file FILE \
    [--repository OWNER/REPO]

Credential values are never accepted inline. Each FILE must be a regular,
non-symlink, owner-readable file that is not group/world accessible.
EOF
}

while (($#)); do
  case "$1" in
    --repository) REPOSITORY="${2:?}"; shift 2 ;;
    --candidate) CANDIDATE="${2:?}"; shift 2 ;;
    --staging-endpoints) STAGING_ENDPOINTS="${2:?}"; shift 2 ;;
    --production-endpoints) PRODUCTION_ENDPOINTS="${2:?}"; shift 2 ;;
    --staging-bearer-file) STAGING_BEARER_FILE="${2:?}"; shift 2 ;;
    --staging-metrics-file) STAGING_METRICS_FILE="${2:?}"; shift 2 ;;
    --staging-ghcr-file) STAGING_GHCR_FILE="${2:?}"; shift 2 ;;
    --staging-restic-repository-file) STAGING_RESTIC_REPOSITORY_FILE="${2:?}"; shift 2 ;;
    --staging-restic-password-path-file) STAGING_RESTIC_PASSWORD_PATH_FILE="${2:?}"; shift 2 ;;
    --production-bearer-file) PRODUCTION_BEARER_FILE="${2:?}"; shift 2 ;;
    --production-metrics-file) PRODUCTION_METRICS_FILE="${2:?}"; shift 2 ;;
    --production-ghcr-file) PRODUCTION_GHCR_FILE="${2:?}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'ERROR=unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

for value in \
  "$CANDIDATE" \
  "$STAGING_ENDPOINTS" \
  "$PRODUCTION_ENDPOINTS" \
  "$STAGING_BEARER_FILE" \
  "$STAGING_METRICS_FILE" \
  "$STAGING_GHCR_FILE" \
  "$STAGING_RESTIC_REPOSITORY_FILE" \
  "$STAGING_RESTIC_PASSWORD_PATH_FILE" \
  "$PRODUCTION_BEARER_FILE" \
  "$PRODUCTION_METRICS_FILE" \
  "$PRODUCTION_GHCR_FILE"; do
  [[ -n "$value" ]] || { usage >&2; exit 2; }
done

[[ "$REPOSITORY" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || {
  echo "ERROR=invalid repository name" >&2
  exit 2
}

for tool in gh jq python3 base64 sha256sum stat; do
  command -v "$tool" >/dev/null || {
    echo "ERROR=missing required tool: $tool" >&2
    exit 1
  }
done

gh auth status --hostname github.com >/dev/null
[[ "$(gh api "repos/$REPOSITORY" --jq '.permissions.admin // false')" == "true" ]] || {
  echo "ERROR=current GitHub identity lacks repository administration permission" >&2
  exit 1
}

umask 077
WORK="$(mktemp -d)"
trap 'rm -rf -- "$WORK"' EXIT

secure_file() {
  local path="$1"
  local label="$2"
  [[ -f "$path" && ! -L "$path" ]] || {
    echo "ERROR=$label must be a regular non-symlink file" >&2
    exit 1
  }
  local mode
  mode="$(stat -c '%a' -- "$path")"
  local mode_value=$((8#$mode))
  if ((mode_value & 0077)); then
    echo "ERROR=$label must not be group/world accessible (mode $mode)" >&2
    exit 1
  fi
  [[ -s "$path" ]] || {
    echo "ERROR=$label is empty" >&2
    exit 1
  }
}

for item in \
  "$CANDIDATE:candidate" \
  "$STAGING_ENDPOINTS:staging-endpoints" \
  "$PRODUCTION_ENDPOINTS:production-endpoints" \
  "$STAGING_BEARER_FILE:staging-bearer" \
  "$STAGING_METRICS_FILE:staging-metrics" \
  "$STAGING_GHCR_FILE:staging-ghcr" \
  "$STAGING_RESTIC_REPOSITORY_FILE:staging-restic-repository" \
  "$STAGING_RESTIC_PASSWORD_PATH_FILE:staging-restic-password-path" \
  "$PRODUCTION_BEARER_FILE:production-bearer" \
  "$PRODUCTION_METRICS_FILE:production-metrics" \
  "$PRODUCTION_GHCR_FILE:production-ghcr"; do
  secure_file "${item%%:*}" "${item#*:}"
done

[[ "$(wc -c <"$CANDIDATE")" -le 1048576 ]] || {
  echo "ERROR=candidate exceeds 1 MiB" >&2
  exit 1
}
[[ "$(wc -c <"$STAGING_ENDPOINTS")" -le 1048576 ]] || {
  echo "ERROR=staging endpoint manifest exceeds 1 MiB" >&2
  exit 1
}
[[ "$(wc -c <"$PRODUCTION_ENDPOINTS")" -le 1048576 ]] || {
  echo "ERROR=production endpoint manifest exceeds 1 MiB" >&2
  exit 1
}

python3 - "$ROOT" "$CANDIDATE" "$STAGING_ENDPOINTS" "$PRODUCTION_ENDPOINTS" <<'PY'
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / "operations" / "staging-readonly"))
import release_control_v2 as release  # noqa: E402

candidate = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
staging = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
production = json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))
release.validate_candidate(candidate)

synthetic = {
    "STAGING_READONLY_BEARER_TOKEN": "structural-validation-only",
    "STAGING_METRICS_BEARER_TOKEN": "structural-validation-only",
    "PRODUCTION_READONLY_BEARER_TOKEN": "structural-validation-only",
    "PRODUCTION_METRICS_BEARER_TOKEN": "structural-validation-only",
}
previous = {name: os.environ.get(name) for name in synthetic}
try:
    os.environ.update(synthetic)
    release.validate_endpoint_manifest(
        staging,
        candidate,
        release.STAGING_ENVIRONMENT,
    )
    release.validate_endpoint_manifest(
        production,
        candidate,
        release.CANARY_ENVIRONMENT,
    )
finally:
    for name, value in previous.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
PY

candidate_id="$(jq -er '.candidate_id' "$CANDIDATE")"
source_lock_sha="$(jq -er '.candidate_source_lock_sha' "$CANDIDATE")"
[[ "$candidate_id" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$ ]]
[[ "$source_lock_sha" =~ ^[0-9a-f]{40}$ ]]
candidate_sha256="$(sha256sum "$CANDIDATE" | cut -d' ' -f1)"

base64 -w0 -- "$CANDIDATE" >"$WORK/candidate.b64"
base64 -w0 -- "$STAGING_ENDPOINTS" >"$WORK/staging-endpoints.b64"
base64 -w0 -- "$PRODUCTION_ENDPOINTS" >"$WORK/production-endpoints.b64"

create_environment() {
  local environment="$1"
  gh api \
    --method PUT \
    -H 'Accept: application/vnd.github+json' \
    -H 'X-GitHub-Api-Version: 2022-11-28' \
    "repos/$REPOSITORY/environments/$environment" \
    --input - >/dev/null <<'JSON'
{
  "wait_timer": 0,
  "prevent_self_review": false,
  "deployment_branch_policy": {
    "protected_branches": true,
    "custom_branch_policies": false
  }
}
JSON
}

set_environment_secret() {
  local environment="$1"
  local name="$2"
  local path="$3"
  gh secret set "$name" --env "$environment" --repo "$REPOSITORY" <"$path" >/dev/null
}

create_environment staging-readonly
create_environment production-readonly-canary

set_environment_secret staging-readonly STAGING_CANONICAL_CANDIDATE_B64 "$WORK/candidate.b64"
set_environment_secret staging-readonly STAGING_ENDPOINT_MANIFEST_B64 "$WORK/staging-endpoints.b64"
set_environment_secret staging-readonly STAGING_READONLY_BEARER_TOKEN "$STAGING_BEARER_FILE"
set_environment_secret staging-readonly STAGING_METRICS_BEARER_TOKEN "$STAGING_METRICS_FILE"
set_environment_secret staging-readonly STAGING_GHCR_READ_TOKEN "$STAGING_GHCR_FILE"
set_environment_secret staging-readonly STAGING_RESTIC_REPOSITORY "$STAGING_RESTIC_REPOSITORY_FILE"
set_environment_secret staging-readonly STAGING_RESTIC_PASSWORD_FILE "$STAGING_RESTIC_PASSWORD_PATH_FILE"

set_environment_secret production-readonly-canary PRODUCTION_CANONICAL_CANDIDATE_B64 "$WORK/candidate.b64"
set_environment_secret production-readonly-canary PRODUCTION_ENDPOINT_MANIFEST_B64 "$WORK/production-endpoints.b64"
set_environment_secret production-readonly-canary PRODUCTION_READONLY_BEARER_TOKEN "$PRODUCTION_BEARER_FILE"
set_environment_secret production-readonly-canary PRODUCTION_METRICS_BEARER_TOKEN "$PRODUCTION_METRICS_FILE"
set_environment_secret production-readonly-canary PRODUCTION_GHCR_READ_TOKEN "$PRODUCTION_GHCR_FILE"

verify_secret_names() {
  local environment="$1"
  shift
  local expected actual
  expected="$(printf '%s\n' "$@" | sort)"
  actual="$(gh secret list --env "$environment" --repo "$REPOSITORY" --json name --jq '.[].name' | sort)"
  while IFS= read -r required; do
    grep -Fxq -- "$required" <<<"$actual" || {
      echo "ERROR=$environment is missing secret name $required" >&2
      exit 1
    }
  done <<<"$expected"
}

verify_secret_names staging-readonly \
  STAGING_CANONICAL_CANDIDATE_B64 \
  STAGING_ENDPOINT_MANIFEST_B64 \
  STAGING_READONLY_BEARER_TOKEN \
  STAGING_METRICS_BEARER_TOKEN \
  STAGING_GHCR_READ_TOKEN \
  STAGING_RESTIC_REPOSITORY \
  STAGING_RESTIC_PASSWORD_FILE

verify_secret_names production-readonly-canary \
  PRODUCTION_CANONICAL_CANDIDATE_B64 \
  PRODUCTION_ENDPOINT_MANIFEST_B64 \
  PRODUCTION_READONLY_BEARER_TOKEN \
  PRODUCTION_METRICS_BEARER_TOKEN \
  PRODUCTION_GHCR_READ_TOKEN

for environment in staging-readonly production-readonly-canary; do
  protected="$(gh api "repos/$REPOSITORY/environments/$environment" --jq '.deployment_branch_policy.protected_branches')"
  custom="$(gh api "repos/$REPOSITORY/environments/$environment" --jq '.deployment_branch_policy.custom_branch_policies')"
  [[ "$protected" == "true" && "$custom" == "false" ]] || {
    echo "ERROR=$environment branch policy is not protected-branches-only" >&2
    exit 1
  }
done

printf 'GITHUB_RELEASE_ENVIRONMENTS=PASS\n'
printf 'REPOSITORY=%s\n' "$REPOSITORY"
printf 'CANDIDATE_ID=%s\n' "$candidate_id"
printf 'CANDIDATE_SOURCE_LOCK_SHA=%s\n' "$source_lock_sha"
printf 'CANDIDATE_SHA256=%s\n' "$candidate_sha256"
printf 'STAGING_ENVIRONMENT=staging-readonly\n'
printf 'PRODUCTION_ENVIRONMENT=production-readonly-canary\n'
printf 'SECRET_VALUES_PRINTED=NO\n'
