#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_ROOT=/opt/codestra/backups/stage6-staging
EXPECTED_SOURCE_SHA=""
EXECUTE=false

fail() {
  printf 'STAGE6_BACKUP_ERROR=%s\n' "$*" >&2
  exit 1
}

while (($#)); do
  case "$1" in
    --expected-source-sha) EXPECTED_SOURCE_SHA="${2:-}"; shift 2 ;;
    --execute) EXECUTE=true; shift ;;
    *) fail "unsupported argument: $1" ;;
  esac
done

[[ "$EXPECTED_SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]] || fail "exact source SHA is required"
[[ "$EXPECTED_SOURCE_SHA" == '65018df89571042c1e7550adf3180d47bb495187' ]] ||
  fail "source SHA is not the reviewed Stage 6 lock merge"
$EXECUTE || fail "--execute is required"
git -C "$ROOT_DIR" merge-base --is-ancestor "$EXPECTED_SOURCE_SHA" HEAD ||
  fail "reviewed source lock is not an ancestor of the backup operation"
grep -qx '  source_lock: PASS' "$ROOT_DIR/STAGE6-SOURCE-LOCK.yaml" || fail "source lock is not PASS"
grep -qx '  stage6_preflight: PASS' "$ROOT_DIR/STAGE6-SOURCE-LOCK.yaml" || fail "preflight is not PASS"
grep -qx '  backup_preparation_allowed: true' "$ROOT_DIR/STAGE6-SOURCE-LOCK.yaml" || fail "backup preparation is not authorized"
grep -qx '  runtime_reconciliation_allowed: false' "$ROOT_DIR/STAGE6-SOURCE-LOCK.yaml" || fail "runtime hold is missing"

declare -a database_containers=(
  codestra-middleware-staging-postgres-1
  codestra-n8n-staging-postgres-1
  codestra-odoo19-staging-postgres-1
)
declare -a release_containers=(
  codestra-agent-desktop-sipjs-staging
  codestra-middleware-staging-callback-staging-1
  codestra-middleware-staging-middleware-staging-1
  codestra-middleware-staging-notification-worker-staging-1
  codestra-middleware-staging-odoo-result-worker-staging-1
  codestra-middleware-staging-postgres-1
  codestra-middleware-staging-redis-1
  codestra-middleware-staging-scheduler-staging-1
  codestra-middleware-staging-scraper-odoo-delivery-worker-1
  codestra-middleware-staging-social-dead-letter-worker-staging-1
  codestra-middleware-staging-social-delivery-worker-staging-1
  codestra-middleware-staging-social-reconciliation-worker-staging-1
  codestra-n8n-staging-n8n-1
  codestra-n8n-staging-postgres-1
  codestra-n8n-staging-redis-1
  codestra-n8n-staging-webhook-1
  codestra-n8n-staging-worker-1
  codestra-n8n-staging-worker-2-1
  codestra-odoo19-staging-odoo19-master-staging-1
  codestra-odoo19-staging-odoo19-scraper-canary-1
  codestra-odoo19-staging-odoo19-staging-1
  codestra-odoo19-staging-postgres-1
)

for container in "${release_containers[@]}"; do
  [[ "$(docker inspect -f '{{.State.Running}}' "$container")" == true ]] ||
    fail "required staging container is not running: $container"
done
for container in "${database_containers[@]}"; do
  [[ "$(docker inspect -f '{{.State.Health.Status}}' "$container")" == healthy ]] ||
    fail "staging database is not healthy: $container"
done

install -d -m 0700 "$BACKUP_ROOT"
target="$(mktemp -d "$BACKUP_ROOT/.partial.XXXXXXXX")"
trap 'printf "BACKUP_STATUS=FAILED\n" >"$target/FAILED"' ERR
install -d -m 0700 "$target/databases" "$target/volumes" "$target/config" "$target/evidence"

for container in "${database_containers[@]}"; do
  cluster="${container%-postgres-1}"
  docker exec "$container" sh -c \
    'exec pg_dumpall --globals-only --no-role-passwords -U "$POSTGRES_USER"' \
    >"$target/databases/${cluster}.globals.sql"
  mapfile -t databases < <(
    docker exec "$container" sh -c \
      'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc "select datname from pg_database where datallowconn and not datistemplate order by datname"'
  )
  ((${#databases[@]} > 0)) || fail "no databases discovered in $container"
  for database in "${databases[@]}"; do
    [[ "$database" =~ ^[A-Za-z0-9_]+$ ]] || fail "unsafe database name from $container"
    docker exec "$container" sh -c \
      'exec pg_dump -Fc --no-owner --no-acl -U "$POSTGRES_USER" -d "$1"' sh "$database" \
      >"$target/databases/${cluster}.${database}.dump"
  done
done

declare -A volumes=(
  [n8n-data]=/var/lib/docker/volumes/codestra-n8n-staging_n8n_data/_data
  [odoo-data]=/var/lib/docker/volumes/codestra-odoo19-staging_odoo_data/_data
  [odoo-master-data]=/var/lib/docker/volumes/codestra-odoo19-staging_master_odoo_data/_data
)
for label in "${!volumes[@]}"; do
  source_path="${volumes[$label]}"
  [[ -d "$source_path" && ! -L "$source_path" ]] || fail "invalid staging volume path: $source_path"
  tar --one-file-system --numeric-owner -C "$source_path" -cpf "$target/volumes/${label}.tar" .
done

declare -a config_paths=(
  opt/codestra/middleware-staging/compose.yaml
  opt/codestra/middleware-staging/compose.scraper-canary.yaml
  opt/codestra/n8n-staging/compose.yaml
  opt/codestra/n8n-staging/compose.queue.override.yaml
  opt/codestra/n8n-staging/scripts
  opt/codestra/n8n-staging/workflows
  opt/codestra/odoo19-staging/compose.yaml
  opt/codestra/odoo19-staging/compose.master.override.yaml
  opt/codestra/odoo19-staging/compose.scraper-canary.yaml
)
declare -a existing_config_paths=()
for path in "${config_paths[@]}"; do
  [[ -e "/$path" && ! -L "/$path" ]] && existing_config_paths+=("$path")
done
((${#existing_config_paths[@]} > 0)) || fail "no staging configuration paths found"
tar --one-file-system --numeric-owner -C / -cpf "$target/config/staging-config.tar" "${existing_config_paths[@]}"

for container in "${release_containers[@]}"; do
  docker inspect "$container" --format '{{json .}}' |
    jq '{name:.Name[1:], imageReference:.Config.Image, imageId:.Image, command:{entrypoint:.Config.Entrypoint,cmd:.Config.Cmd}, compose:{project:.Config.Labels["com.docker.compose.project"],service:.Config.Labels["com.docker.compose.service"],files:.Config.Labels["com.docker.compose.project.config_files"]}, networks:(.NetworkSettings.Networks|keys), mounts:[.Mounts[]|{type:.Type,source:.Source,destination:.Destination,readWrite:.RW}]}' \
    >"$target/evidence/${container}.json"
done

{
  printf 'SCHEMA=codestra.stage6.staging-backup.v1\n'
  printf 'SOURCE_LOCK_SHA=%s\n' "$EXPECTED_SOURCE_SHA"
  printf 'CREATED_AT=%s\n' "$(date -u +%FT%TZ)"
  printf 'DATABASE_CLUSTERS=%s\n' "${#database_containers[@]}"
  printf 'RELEASE_CONTAINERS=%s\n' "${#release_containers[@]}"
  printf 'SECRET_VALUES_COPIED=NO\n'
  printf 'RUNTIME_RESTARTED=NO\n'
  printf 'PRODUCTION_TOUCHED=NO\n'
} >"$target/MANIFEST"

checksum_tmp="$(mktemp)"
(
  cd "$target"
  find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >"$checksum_tmp"
  mv "$checksum_tmp" SHA256SUMS
  sha256sum -c SHA256SUMS >/dev/null
)
chmod -R go-rwx "$target"
final="$BACKUP_ROOT/$(date -u +%Y%m%dT%H%M%SZ)-65018df"
[[ ! -e "$final" ]] || fail "final backup path already exists"
mv "$target" "$final"
trap - ERR
printf 'STAGE6_BACKUP=%s\n' "$final"
printf 'BACKUP_CHECKSUMS=PASS\n'
printf 'RUNTIME_RESTARTED=NO\n'
printf 'PRODUCTION_TOUCHED=NO\n'
