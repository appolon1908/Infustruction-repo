# CODESTRA Core Production Consolidation — Readiness Report

Date: 2026-09-01 UTC  
Host: `65.109.65.169` / `10.40.0.1`

## Decision

**NO-GO — NOT PRODUCTION READY.**

The read-only authoritative inventory is complete for the current runtime snapshot. No live delivery, dialing, publishing, advertising, model call, financial, callback, or uncontrolled n8n action was executed. SSH was not changed. No database, volume, image, release, worktree, or production data was deleted.

## Inventory result

- 102 running containers captured.
- 32 containers expose a 40-character OCI revision label and source URL together; 55 expose a source URL; several production-facing images remain tag-only or have no repository/revision label. This is not sufficient for a complete source lock.
- Actual image IDs, Compose labels, source paths, health, restart policies, networks, published ports, volumes, and redacted environment keys captured in `PRODUCTION-RUNTIME-INVENTORY.json` and `PRODUCTION-CONTAINER-INVENTORY.csv`.
- 102 running containers does not itself establish that all are production; environment ownership remains a required source-authority mapping.

## Mandatory gates

| Gate | Result | Evidence/remaining issue |
|---|---|---|
| SOURCE_LOCK | FAIL | Canonical repo/SHA not proven for every workload |
| IMMUTABLE_IMAGES | FAIL | Digest pinning/provenance not proven for every production workload |
| OPENBAO | UNKNOWN | Deployment and recovery authority not established |
| DATABASE_BACKUPS | FAIL | Complete current/off-host coverage not proven |
| RESTORE_TEST | FAIL | Required exact production recovery set not proven |
| ONE_SHOT_MIGRATIONS | UNKNOWN | Source-controlled migration authority not established |
| MIDDLEWARE/ODOO/N8N/OBSERVABILITY | UNKNOWN | Full exact-head gates not executed |
| POSTGRES_PRIVATE/REDIS_PRIVATE | FAIL | Perimeter and environment isolation not re-certified |
| DOCKER_SOCKET_PROTECTED | UNKNOWN | Complete workload review pending |
| METRICS/LOGS/TRACES/ALERTS | UNKNOWN | End-to-end delivery not re-certified |
| IDEMPOTENCY/OUTBOX/INBOX | UNKNOWN | Application-level tests not executed |
| ROLLBACK | PARTIAL | False-standby containment rollback exists; complete release rollback not proven |
| STAGING_CERTIFICATION | FAIL | Exact production candidate not certified on target staging host |

## Remediation already performed

The false realtime standby remains stopped with automatic restart disabled; its volume is preserved. The valid realtime primary and streaming replica remain aligned. This is operational containment, not complete source-controlled consolidation.

## Blocking conditions

1. Canonical source/repository/SHA and exact immutable artifact mapping are incomplete.
2. The staging target `2.29.17.172` has not been certified with the exact production candidate.
3. Central encrypted off-host backup and exact restore coverage are not proven.
4. Required application health/readiness/version/capability contracts are not proven for every production service.
5. PostgreSQL role/CONNECT/TLS, Redis recovery, Odoo-copy governance, n8n credential recovery, and selective application recoveries remain open.
6. Firewall, Docker-published-port policy, and full production/staging isolation remain unverified.

## Safety status

`LIVE_SMS_DELIVERY=false`, `LIVE_EMAIL_DELIVERY=false`, `LIVE_PSTN_DIALING=false`, `PRODUCTION_DIALING=DISABLED`, `ODOO_WRITE=false`, `CALLBACK_DISPATCH=false`, `ENABLE_EXTERNAL_DELIVERY=false`, `SEND_EVENTS=false`, and `N8N_DELIVERY_ENABLED=false` were preserved where observed. Values were not changed.

## GO/NO-GO

**NO-GO.** Do not relocate staging, deploy a consolidated production manifest, enable providers, or perform cleanup until source authority, exact artifacts, backup/restore, staging certification, rollback, and mandatory gates are independently passing.
