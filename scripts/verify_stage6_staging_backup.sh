#!/usr/bin/env bash
set -Eeuo pipefail

backup="${1:-}"
restore_container="${PG_RESTORE_CONTAINER:-codestra-middleware-staging-postgres-1}"
approved_postgres_digest='sha256:ef257d85f76e48da1c64832459b59fcaba1a4dac97bf5d7450c77753542eee94'
[[ "$backup" == /opt/codestra/backups/stage6-staging/* ]] || {
  printf 'STAGE6_BACKUP_VERIFY_ERROR=invalid backup path\n' >&2
  exit 1
}
[[ -d "$backup" && ! -L "$backup" ]] || exit 1
[[ "$(stat -c '%a' "$backup")" == 700 ]] || exit 1
(
  cd "$backup"
  sha256sum -c SHA256SUMS >/dev/null
)

command -v docker >/dev/null
[[ "$(docker inspect --format '{{.State.Running}}' "$restore_container")" == true ]]
[[ "$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' "$restore_container")" == healthy ]]
[[ "$(docker inspect --format '{{.Image}}' "$restore_container")" == "$approved_postgres_digest" ]]

shopt -s nullglob
database_archives=("$backup"/databases/*.dump)
volume_archives=("$backup"/volumes/*.tar)
config_archives=("$backup"/config/*.tar)
(( ${#database_archives[@]} > 0 ))
(( ${#volume_archives[@]} > 0 ))
(( ${#config_archives[@]} > 0 ))

for dump in "${database_archives[@]}"; do
  docker exec -i "$restore_container" pg_restore --list <"$dump" >/dev/null
done
for archive in "${volume_archives[@]}" "${config_archives[@]}"; do
  tar -tf "$archive" >/dev/null
done
grep -qx 'SECRET_VALUES_COPIED=NO' "$backup/MANIFEST"
grep -qx 'RUNTIME_RESTARTED=NO' "$backup/MANIFEST"
grep -qx 'PRODUCTION_TOUCHED=NO' "$backup/MANIFEST"
printf 'BACKUP_CHECKSUMS=PASS\n'
printf 'DATABASE_ARCHIVES_PG17_READABLE=%d\n' "${#database_archives[@]}"
printf 'VOLUME_ARCHIVES=READABLE\n'
printf 'STAGE6_BACKUP_VERIFY=PASS\n'
