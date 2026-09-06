# Stage 6 Source-lock and Runtime-provenance Remediation Evidence

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

## Outcome

The Git source authority was remediated without mutating runtime. The new
`STAGE6-SOURCE-LOCK.yaml` is the sole current lock; the older JSON lock is
explicitly marked `SUPERSEDED_DO_NOT_DEPLOY`.

The lock contains current protected-main SHAs for all release, observability,
security, and analytics repositories. Kong protected main
`3594fe25b8fe36633c1de95a8e485c72f32a60f8` was verified one commit ahead of,
and descended from, required merge
`186630b40c19d72aa9bdf9ef1f64e8a17bd0e33e`. Social Runtime is locked exactly
to required merged SHA `4f7817f6c6d1bb38fa7d85bb1656eb41865283d5`.

## Immutable artifact findings

- All 22 running release workloads now have an observed immutable digest and a
  rollback digest recorded in the lock and matrix.
- Thirteen runtime image references were already digest-pinned.
- The other nine use mutable references, but their exact local repository
  digests were located. They remain runtime drift and were not replaced.
- Middleware protected main SHA
  `c720e529ea89f1f0d5d035d4ac12a1d5aa30ab62` has a successful signed release
  with digest
  `sha256:92954f809e811487f8ac15bde3ba636f3bdb1c37547838e9579bb1fd9567f8da`.
- That new Middleware image is not command-compatible with every legacy worker.
  Those workers are frozen rather than automatically mapped to an incompatible
  artifact.
- Social Runtime has no reviewed published immutable image for its locked SHA;
  its component artifact remains unresolved.

## Source configuration remediation

- Middleware application startup is application-only in the candidate source.
- Middleware migration is a profile-gated, `restart: "no"` one-shot service.
- Long-running Odoo candidate services contain no `--init` or `--update`.
- Odoo module changes are profile-gated, `restart: "no"`, `--stop-after-init`
  one-shot services.
- The 17 safety-applicable release services are covered by explicit source
  definitions with advertising, external delivery, social publishing, external
  models, SMS, email, PSTN, and production dialing disabled.
- PostgreSQL and Redis are excluded from irrelevant business-write controls.

## Unknown gateway

`private-integration-gateway-1` was inspected read-only. It is a root-owned,
non-Git provider integration bridge on private host binding `10.40.0.1:8095`,
connected to `codestra_edge`, with Kyqra/Telnexa upstreams and the Codestra
integration control plane downstream. Ownership and source provenance remain
unverified. It was not restarted, replaced, or reclassified as release scope.

## Phase 0 re-run

- Running containers: 101
- Release workloads: 22
- Release workloads with an observed immutable digest: 22
- Runtime references directly pinned by digest: 13
- Applicable runtime services with the complete explicit safety set: 0/17
- Current Middleware migration-on-startup violations: 1
- Current Odoo module-operation-on-startup violations: 2
- Unverified/frozen workload dispositions: 9
- Unknown workloads: 1
- Runtime containers changed by this mission: 0

Phase 0 source/preflight certification passes because every runtime workload has
a resolved disposition, every planned replacement is digest-pinned, unverified
workloads are frozen from automatic replacement, source migration and safety
models are explicit, and every rollback digest exists. Runtime drift remains
expected and is the subject of the subsequent backup-gated staging
reconciliation. The unresolved Social Runtime artifact is not a running member
of the 22-workload set and is not authorized for deployment.

```text
SOURCE_LOCK=PASS
STAGE6_PREFLIGHT=PASS
PRODUCTION_BUSINESS_WRITES=DISABLED
NEXT_ACTION=BACKUP_PREPARATION_ONLY
```
