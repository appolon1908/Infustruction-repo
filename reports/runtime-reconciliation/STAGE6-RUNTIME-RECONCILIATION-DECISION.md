# Stage 6 Runtime Reconciliation Decision

Status: **SUPERSEDED_DO_NOT_EXECUTE**

## Supersession notice — 2026-09-06

This report's PASS/preflight conclusions, disabled-write assertion, and
backup-preparation authorization are superseded. They must not be used to
start backups, reconciliation, deployment, or any runtime mutation. The
original report below is retained verbatim as historical evidence, not a
fresh runtime read-back or current operational instruction.

Use the [canonical source lock](../../STAGE6-SOURCE-LOCK.yaml) and
[current staging certification](../../STAGE6-STAGING-CERTIFICATION.md),
including their scope, runtime-safety failures, and explicit authorization
gates. A scoped source-lock PASS does not establish a complete application
artifact lock or prove runtime writes disabled. No backup or runtime action
is authorized by this report or by merging PR #30.

See the [retry prerequisites](pr-30-runtime-certification-20260831/README.md#retry-prerequisites-not-execution-authorization)
for immutable artifact resolution, scoped safety proof, and approved access.
Klyrow/Postal remains `OUT_OF_SCOPE_ACTIVE_PRODUCTION_DO_NOT_TOUCH`.
Separate verified backup evidence is not replaced or invalidated here.

## Historical report (superseded; retained verbatim)

Timestamp: 2026-08-30 (America/Santo_Domingo)

## Decision

`SOURCE_LOCK=PASS`

`STAGE6_PREFLIGHT=PASS`

The source/preflight reconciliation passed and stopped before backup or runtime
mutation. This pass authorizes backup preparation only. No container was
replaced or restarted, no database was changed, and no production deployment or
external-write activation occurred.

## Established inventory

The companion CSV records all 101 containers observed on the host, including
classification, image reference and local image ID, discovered Git revision,
environment, Compose service and file paths, configuration authority, mounted
secret-source paths, current rollback image, startup command, and explicit
safety-state read-back.

Classification totals:

- Codestra release workload: 22
- observability/security workload: 24
- provider workload: 7
- legacy workload: 47
- unrelated workload: 0
- unknown: 1

The unknown workload is `private-integration-gateway-1`. It was not modified.
Production and legacy workloads were inventory-only and were not modified.

## Resolved source authority and held runtime drift

1. `STAGE6-SOURCE-LOCK.yaml` is the sole current authority. The old JSON is
   explicitly historical and non-authoritative.
2. The Kong conflict is resolved by recording required merged release
   `186630b40c19d72aa9bdf9ef1f64e8a17bd0e33e` and its reviewed protected-main
   descendant `3594fe25b8fe36633c1de95a8e485c72f32a60f8`.
3. Of 22 classified staging release containers, only 13 have digest-pinned image
   references. Immutable local repository digests were located for the other
   nine, but those running references remain mutable. Runtime labels expose exact
   full revisions for four containers; tag-to-Git evidence resolves three social
   workers to one additional commit. The remaining workloads use vendor images,
   mounted-source models, or images with unverified provenance.
4. All 17 safety-applicable staging release containers fail the complete explicit
   safety-set read-back. The five remaining release containers are PostgreSQL or
   Redis and were correctly treated as infrastructure to which business-write
   switches do not apply.
5. `codestra-middleware-staging-middleware-staging-1` runs
   `alembic upgrade head` in normal application startup.
6. `codestra-odoo19-staging-odoo19-master-staging-1` and
   `codestra-odoo19-staging-odoo19-staging-1` run module `--init` operations in
   normal application startup.
7. The source lock includes Marketing, AI, Communication, Social Control and
   Social Runtime, but no corresponding unambiguous Stage 6 staging release
   workloads were identifiable among the 101 running containers.
8. Every planned replacement and rollback identity is digest-pinned. Workloads
   without proven compatible replacement provenance are explicitly frozen and
   excluded from automatic replacement.

## Backup-gated staging reconciliation sequence

1. Review and merge the authoritative source lock and exact reconciliation
   matrix.
2. Preserve each unverified workload as a freeze/hold; do not infer provenance.
3. Add capability-scoped fail-closed variables to application/workflow/provider
   workloads; do not add them to PostgreSQL, Redis, or observability exporters.
4. Add a dedicated Middleware one-shot Alembic service and change the API command
   to application-only startup.
5. Add dedicated Odoo one-shot module install/upgrade services and remove
   `--init`/`--update` from long-running Odoo services.
6. Verify rollback images and commands, then back up each affected staging
   database and configuration and verify checksums/restorability.
7. Reconcile only staging, one dependency tier at a time, with health/read-back
   and rollback readiness after each service.
8. Re-capture this inventory and require zero unresolved provenance, digest,
   startup-migration, and applicable safety drift before OpenBao work resumes.

## Safety outcome

Observed switches that were present were false/disabled, but missing switches
remain ambiguous and therefore do not certify the runtime. This run made no
production business write and did not enable any external write capability.

```text
SOURCE_LOCK=PASS
STAGE6_PREFLIGHT=PASS
PRODUCTION_BUSINESS_WRITES=DISABLED
NEXT_ACTION=BACKUP_PREPARATION_ONLY
```
