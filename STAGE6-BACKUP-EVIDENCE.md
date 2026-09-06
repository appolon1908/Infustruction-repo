# Stage 6 Staging Backup Evidence

Captured: 2026-08-30T23:39:31Z (America/Santo_Domingo)

## Authority

- Source-lock merge: `65018df89571042c1e7550adf3180d47bb495187`
- Backup-operation merge: `6ab3b3641d45343b11ab3cae48881d2aa56a823e`
- PostgreSQL 17 verifier merge: `b71f922a8d878a47c5a41f6b1cf9e8b47f9fba68`
- Backup identifier: `20260830T233931Z-65018df`
- Storage authority: `/opt/codestra/backups/stage6-staging/`

The absolute backup directory is root-only mode `0700`. No credential, token,
role password, cookie secret, or secret payload is included in this report or
the repository.

## Verified contents

The merged verifier checked the manifest checksum set, inspected every custom
PostgreSQL archive with the healthy digest-locked PostgreSQL 17 staging tool,
and listed every volume and configuration tar archive.

```text
BACKUP_CHECKSUMS=PASS
DATABASE_ARCHIVES_PG17_READABLE=24
VOLUME_ARCHIVES=READABLE
STAGE6_BACKUP_VERIFY=PASS
SECRET_VALUES_COPIED=NO
RUNTIME_RESTARTED=NO
PRODUCTION_TOUCHED=NO
```

The backup contains 24 database archives, three data-volume archives, the
staging configuration archive, a checksum manifest, and sanitized runtime
evidence for the 22 release workloads.

## Scope and limits

Archive readability and checksums are proven. A destructive restore was not
performed against any existing database. Restore drills must use an isolated,
empty staging-only target and require their own reviewed operation.

This evidence does not authorize production, external writes, migrations,
container replacement, service restart, secret rotation, or changes to any
legacy or unverified workload.

The exact merged source lock currently reports `STAGE6_PREFLIGHT=FAIL` and
`PRODUCTION_BUSINESS_WRITES=NOT_PROVEN_DISABLED`. The valid backup does not
override that runtime safety gate; staging reconciliation remains prohibited
until a fresh reviewed read-back closes it.

`BACKUPS=PASS`

`BACKUP_RESTORE_VERIFICATION=ARCHIVE_READABILITY_PASS`
