#!/usr/bin/env bash
set -Eeuo pipefail

EXPECTED_IP="${OBSERVABILITY_EXPECTED_IP:-37.27.128.39}"
MODE="${OBSERVABILITY_SMOKE_MODE:-preflight}"
TIMEOUT_SECONDS="${OBSERVABILITY_SMOKE_TIMEOUT_SECONDS:-8}"
POSTGRES_EXPORTER_PRIVATE_IDENTITY="postgres-exporter:9187"

PUBLIC_HOSTS=(
  graf.codestra.media
  supe.codestra.media
  bao.codestra.media
)
PRIVATE_HOSTS=(
  prom.codestra.media
  aler.codestra.media
  loki.codestra.media
  temp.codestra.media
  otel.codestra.media
  node.codestra.media
  cadv.codestra.media
  rdex.codestra.media
  blac.codestra.media
  allo.codestra.media
)
NATIVE_PORTS=(3000 8088 8200 9090 9093 3100 3200 4317 4318 8888 8889 9100 8080 9187 9121 9115 12345)

fail() {
  printf 'OBSERVABILITY_SMOKE_ERROR=%s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "$1 is required"
}

for command_name in dig curl openssl timeout; do
  require_command "$command_name"
done

case "$MODE" in
  preflight | postdeploy | external-port-scan) ;;
  *) fail "OBSERVABILITY_SMOKE_MODE must be preflight, postdeploy, or external-port-scan" ;;
esac

check_dns() {
  local host="$1"
  local addresses
  addresses="$(dig +short A "$host" | sed '/^$/d' | sort -u)"
  [[ "$addresses" == "$EXPECTED_IP" ]] || fail "$host must resolve only to $EXPECTED_IP; got: ${addresses:-none}"
  printf 'DNS_OK=%s\n' "$host"
}

check_certificate() {
  local host="$1"
  local certificate
  certificate="$(
    timeout "$TIMEOUT_SECONDS" openssl s_client \
      -connect "${host}:443" \
      -servername "$host" \
      -verify_return_error \
      </dev/null 2>/dev/null \
      | openssl x509 -noout -subject -issuer -ext subjectAltName
  )" || fail "$host TLS handshake or certificate validation failed"
  grep -Fq "DNS:$host" <<<"$certificate" || fail "$host is not present in certificate SANs"
  printf 'TLS_OK=%s\n' "$host"
}

check_public_application() {
  local host="$1"
  local status
  status="$(curl --silent --show-error --output /dev/null \
    --connect-timeout "$TIMEOUT_SECONDS" \
    --max-time "$TIMEOUT_SECONDS" \
    --write-out '%{http_code}' \
    "https://${host}/")" || fail "$host HTTPS request failed"

  case "$host:$status" in
    graf.codestra.media:302 | graf.codestra.media:401 | graf.codestra.media:403) ;;
    supe.codestra.media:302 | supe.codestra.media:401 | supe.codestra.media:403) ;;
    bao.codestra.media:302 | bao.codestra.media:401 | bao.codestra.media:403) ;;
    *) fail "$host returned unexpected status $status" ;;
  esac
  [[ "$status" != "502" && "$status" != "503" ]] || fail "$host upstream is unavailable"
  printf 'HTTPS_OK=%s status=%s\n' "$host" "$status"
}

check_private_denial() {
  local host="$1"
  local status
  status="$(curl --silent --show-error --output /dev/null \
    --connect-timeout "$TIMEOUT_SECONDS" \
    --max-time "$TIMEOUT_SECONDS" \
    --write-out '%{http_code}' \
    "https://${host}/")" || fail "$host HTTPS request failed"
  [[ "$status" == "403" || "$status" == "404" ]] || fail "$host must return 403 or 404 publicly; got $status"
  printf 'PRIVATE_DENIAL_OK=%s\n' "$host"
}

check_native_port_closed() {
  local port="$1"
  if timeout 3 bash -c "</dev/tcp/${EXPECTED_IP}/${port}" >/dev/null 2>&1; then
    fail "native service port is publicly reachable: ${EXPECTED_IP}:${port}"
  fi
  printf 'PUBLIC_PORT_CLOSED=%s:%s\n' "$EXPECTED_IP" "$port"
}

for host in "${PUBLIC_HOSTS[@]}" "${PRIVATE_HOSTS[@]}"; do
  check_dns "$host"
done

printf 'POSTGRES_EXPORTER_PRIVATE_IDENTITY=%s\n' "$POSTGRES_EXPORTER_PRIVATE_IDENTITY"
printf 'POSTGRES_EXPORTER_PUBLIC_DNS=UNASSIGNED\n'

if [[ "$MODE" == "preflight" ]]; then
  printf 'OBSERVABILITY_PREFLIGHT_VALID=1\n'
  exit 0
fi

if [[ "$MODE" == "postdeploy" ]]; then
  for host in "${PUBLIC_HOSTS[@]}" "${PRIVATE_HOSTS[@]}"; do
    check_certificate "$host"
  done
  for host in "${PUBLIC_HOSTS[@]}"; do
    check_public_application "$host"
  done
  for host in "${PRIVATE_HOSTS[@]}"; do
    check_private_denial "$host"
  done
fi

# Run this mode from a genuinely external host, not from the observability server.
if [[ "$MODE" == "external-port-scan" ]]; then
  for port in "${NATIVE_PORTS[@]}"; do
    check_native_port_closed "$port"
  done
fi

printf 'OBSERVABILITY_SMOKE_VALID=1 mode=%s\n' "$MODE"
