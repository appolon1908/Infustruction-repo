#!/bin/sh
set -eu

CANDIDATE_DIGEST='sha256:dd3039f69532ccd918cf2e44f58871199943fffa492423b3e6235517a8e8976e'
CANDIDATE_SOURCE='6d52b253fc208f46aa32b26565dcb2f2be30c409'
CONTRACT_DIGEST='856f55ce980fe661a6a326c1a70207496f0eb3fc4bc335141e874c075b5a7e93'
ROLLBACK_DIGEST='sha256:1c8f28d3627955c0d07f8a3f2e4187edb0770f3a9fc7cbc7dc9d819fcd255ffd'
ROLLBACK_COMPOSE='/home/codestra-admin/releases/middleware-69723c25a27e2a64cf55539c7d6df362a33579a4/websocket_gateway/compose.yaml'
SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
COMPOSE="$SCRIPT_DIR/compose.yaml"
PROJECT='codestra-websocket-gateway'
CONTAINER='codestra-websocket-gateway-gateway-1'
CUTOVER_STARTED=0

fail() { printf '%s\n' "ERROR: $*" >&2; exit 1; }
probe_json() {
  path=$1
  ip=$(docker inspect "$CONTAINER" --format '{{(index .NetworkSettings.Networks "codestra_backend").IPAddress}}')
  [ -n "$ip" ] || return 1
  curl -fsS --connect-timeout 2 --max-time 4 "http://$ip:8080$path"
}
rollback() {
  status=$?
  [ "$status" -eq 0 ] && return
  [ "$CUTOVER_STARTED" -eq 1 ] || return "$status"
  printf '%s\n' 'Candidate failed; restoring recorded legacy compose.' >&2
  docker compose -p "$PROJECT" -f "$ROLLBACK_COMPOSE" up -d --no-deps gateway || true
  actual=$(docker inspect "$CONTAINER" --format '{{.Image}}' 2>/dev/null || true)
  [ "$actual" = "$ROLLBACK_DIGEST" ] || printf '%s\n' "ROLLBACK VERIFICATION FAILED: $actual" >&2
  exit "$status"
}
trap rollback EXIT HUP INT TERM

[ "$(id -u)" -eq 0 ] || fail 'run as root so the service token can be read safely'
[ -r /etc/codestra/secrets/websocket-gateway/middleware_service_token ] || fail 'missing middleware_service_token secret'
[ -f "$ROLLBACK_COMPOSE" ] || fail 'recorded rollback compose is unavailable'
[ "$(docker inspect "$CONTAINER" --format '{{.Image}}')" = "$ROLLBACK_DIGEST" ] || fail 'live rollback digest drifted'

: "${MIDDLEWARE_URL:=http://middleware:8095}"
: "${ALLOWED_ORIGINS:=https://crm.codestra.agency,https://phone.codestra.agency,https://dialer.codestra.agency}"
MIDDLEWARE_SERVICE_TOKEN=$(sed -e 's/[[:space:]]*$//' /etc/codestra/secrets/websocket-gateway/middleware_service_token)
export MIDDLEWARE_URL MIDDLEWARE_SERVICE_TOKEN ALLOWED_ORIGINS
[ -n "$MIDDLEWARE_SERVICE_TOKEN" ] || fail 'middleware service token is empty'

docker pull "ghcr.io/appolon1908-hue/websocket-gateway@$CANDIDATE_DIGEST"
docker image inspect "ghcr.io/appolon1908-hue/websocket-gateway@$CANDIDATE_DIGEST" --format '{{join .RepoDigests "\n"}}' | grep -q "@$CANDIDATE_DIGEST$" || fail 'pulled candidate digest mismatch'
docker compose -p "$PROJECT" -f "$COMPOSE" config --quiet
CUTOVER_STARTED=1
docker compose -p "$PROJECT" -f "$COMPOSE" up -d --no-deps gateway

health=''
attempt=0
while [ "$attempt" -lt 12 ]; do
  health=$(probe_json '/healthz' 2>/dev/null) && break
  attempt=$((attempt + 1))
  sleep 5
done
[ -n "$health" ] || fail 'healthz did not become reachable in 60 seconds'
ready=$(probe_json '/readyz')
version=$(probe_json '/version')
printf '%s' "$health" | grep -q '"status":"ok"' || fail 'healthz mismatch'
printf '%s' "$ready" | grep -q '"status":"ready"' || fail 'readyz mismatch'
printf '%s' "$version" | grep -q "$CANDIDATE_SOURCE" || fail 'source SHA mismatch'
printf '%s' "$version" | grep -q "$CANDIDATE_DIGEST" || fail 'image digest mismatch'
printf '%s' "$version" | grep -q "$CONTRACT_DIGEST" || fail 'contract digest mismatch'

trap - EXIT HUP INT TERM
printf '%s\n' "PASS candidate=$CANDIDATE_DIGEST source=$CANDIDATE_SOURCE contract=$CONTRACT_DIGEST"
