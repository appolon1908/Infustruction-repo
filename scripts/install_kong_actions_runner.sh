#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

readonly REPOSITORY="appolon1908-hue/Kong"
readonly REPOSITORY_URL="https://github.com/${REPOSITORY}"
readonly RUNNER_VERSION="2.337.0"
readonly RUNNER_FILENAME="actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"
readonly RUNNER_URL="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${RUNNER_FILENAME}"
readonly RUNNER_SHA256="70920811a4f8ad4328818682bca5c6469c1c942fab52448868071d0063816613"
readonly CACHE_ROOT="/var/cache/codestra-actions-runner"
readonly CACHE_ARCHIVE="${CACHE_ROOT}/${RUNNER_FILENAME}"
readonly RUNNER_NAME="codestra-kong-staging-01"
readonly RUNNER_USER="codestra-kong-staging-runner"
readonly RUNNER_LABEL="kong-runtime"
readonly INSTALL_ROOT="/opt/codestra/actions-runner/kong-staging"

TOKEN_STDIN=false
REPLACE_STALE=false
PREFLIGHT_ONLY=false

fail() {
  printf 'KONG_ACTIONS_RUNNER_BOOTSTRAP=FAIL:%s\n' "$1" >&2
  exit 2
}

usage() {
  cat <<'EOF'
Usage:
  install_kong_actions_runner.sh \
    [--registration-token-stdin] \
    [--replace-stale-registration] \
    [--preflight-only]

This installer is staging-only. It creates no Docker authorization, changes no
Kong/Redis/Middleware/Caddy runtime object, and accepts the short-lived GitHub
runner registration token only from standard input.

--replace-stale-registration is valid only after the exact non-busy repository
runner record has been removed through the GitHub API by the controller.
EOF
}

while (($#)); do
  case "$1" in
    --registration-token-stdin) TOKEN_STDIN=true; shift ;;
    --replace-stale-registration) REPLACE_STALE=true; shift ;;
    --preflight-only) PREFLIGHT_ONLY=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) fail "unknown_argument:${1}" ;;
  esac
done

[[ "$(id -u)" -eq 0 ]] || fail root_required
[[ "$(uname -s)" == Linux ]] || fail unsupported_os
[[ "$(uname -m)" == x86_64 ]] || fail unsupported_architecture

for tool in /usr/bin/curl /usr/bin/docker /usr/bin/find /usr/bin/pgrep \
            /usr/bin/runuser /usr/bin/sha256sum /usr/bin/systemctl /usr/bin/tar; do
  [[ -x "$tool" && ! -L "$tool" ]] || fail "trusted_binary:${tool##*/}"
done

id "$RUNNER_USER" >/dev/null 2>&1 || fail "runner_identity_missing:${RUNNER_USER}"

# release.yml executes scripts/verify_runtime_integration.py directly as the
# runner identity, and that script talks to unix:///var/run/docker.sock.
# Therefore direct Docker readback and the locked service identity must already
# be explicitly provisioned. This installer deliberately creates neither one.
/usr/bin/runuser -u "$RUNNER_USER" -- /usr/bin/docker info >/dev/null 2>&1 \
  || fail "docker_authorization_missing:${RUNNER_USER}"

for container in \
  codestra-caddy-upstream-gateway \
  codestra-kong-kong-gateway-1 \
  codestra-middleware-integration-api-1 \
  codestra-redis-1; do
  /usr/bin/runuser -u "$RUNNER_USER" -- \
    /usr/bin/docker inspect "$container" >/dev/null 2>&1 \
    || fail "runtime_container_readback_missing:${container}"
done

if "$PREFLIGHT_ONLY"; then
  printf '%s\n' \
    'KONG_ACTIONS_RUNNER_PREFLIGHT=PASS' \
    "RUNNER_NAME=$RUNNER_NAME" \
    "RUNNER_LABEL=$RUNNER_LABEL" \
    'DOCKER_AUTHORIZATION=PREEXISTING:direct' \
    'RUNTIME_MUTATION=NONE'
  exit 0
fi

"$TOKEN_STDIN" || fail registration_token_stdin_required
IFS= read -r registration_token || fail registration_token_unreadable
[[ "$registration_token" =~ ^[A-Za-z0-9_.=-]{20,512}$ ]] \
  || fail registration_token_format

if [[ -e "$INSTALL_ROOT/.runner" || -e "$INSTALL_ROOT/.credentials" ]]; then
  "$REPLACE_STALE" || fail local_registration_exists
  if [[ -x "$INSTALL_ROOT/svc.sh" ]]; then
    "$INSTALL_ROOT/svc.sh" stop >/dev/null 2>&1 || true
    "$INSTALL_ROOT/svc.sh" uninstall >/dev/null 2>&1 || true
  fi
  pgrep -f -- "$INSTALL_ROOT/(Runner.Listener|run.sh)" >/dev/null 2>&1 \
    && fail runner_process_still_active
  rm -rf --one-file-system "$INSTALL_ROOT"
fi

install -d -m 0755 "$CACHE_ROOT"
if [[ ! -f "$CACHE_ARCHIVE" ]] || \
   ! printf '%s  %s\n' "$RUNNER_SHA256" "$CACHE_ARCHIVE" \
       | /usr/bin/sha256sum --check --status; then
  tmp_archive="$(mktemp "${CACHE_ROOT}/.${RUNNER_FILENAME}.XXXXXX")"
  trap 'rm -f -- "${tmp_archive:-}"' EXIT
  /usr/bin/curl \
    --proto '=https' \
    --tlsv1.2 \
    --fail \
    --show-error \
    --silent \
    --location \
    --output "$tmp_archive" \
    "$RUNNER_URL"
  printf '%s  %s\n' "$RUNNER_SHA256" "$tmp_archive" \
    | /usr/bin/sha256sum --check --status \
    || fail runner_archive_checksum
  install -o root -g root -m 0644 "$tmp_archive" "$CACHE_ARCHIVE"
  rm -f -- "$tmp_archive"
  trap - EXIT
fi

install -d -o "$RUNNER_USER" -g "$RUNNER_USER" -m 0750 "$INSTALL_ROOT"
/usr/bin/tar --extract --gzip --file "$CACHE_ARCHIVE" --directory "$INSTALL_ROOT" \
  --no-same-owner --no-same-permissions
chown -R "$RUNNER_USER:$RUNNER_USER" "$INSTALL_ROOT"
chmod 0750 "$INSTALL_ROOT"
find "$INSTALL_ROOT" -xdev -type d -exec chmod go-w {} +
find "$INSTALL_ROOT" -xdev -type f -exec chmod go-w {} +

/usr/bin/runuser -u "$RUNNER_USER" -- \
  "$INSTALL_ROOT/config.sh" \
    --unattended \
    --ephemeral \
    --disableupdate \
    --url "$REPOSITORY_URL" \
    --token "$registration_token" \
    --name "$RUNNER_NAME" \
    --labels "$RUNNER_LABEL" \
    --work "_work" >/dev/null
unset registration_token

"$INSTALL_ROOT/svc.sh" install "$RUNNER_USER" >/dev/null
"$INSTALL_ROOT/svc.sh" start >/dev/null

service_name="$(basename "$(find /etc/systemd/system -maxdepth 1 -type f \
  -name "actions.runner.appolon1908-hue-Kong.${RUNNER_NAME}.service" -print -quit)")"
[[ -n "$service_name" ]] || fail service_unit_missing
/usr/bin/systemctl is-active --quiet "$service_name" || fail service_not_active

printf '%s\n' \
  'KONG_ACTIONS_RUNNER_BOOTSTRAP=PASS' \
  "RUNNER_NAME=$RUNNER_NAME" \
  "RUNNER_LABEL=$RUNNER_LABEL" \
  "RUNNER_VERSION=$RUNNER_VERSION" \
  'RUNNER_EPHEMERAL=true' \
  'RUNNER_ONE_JOB=true' \
  'REGISTRATION_TOKEN_PERSISTED=false' \
  'RUNTIME_MUTATION=NONE'
