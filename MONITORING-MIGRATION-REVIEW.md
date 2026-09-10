# Monitoring migration and release review

The 36-operation implementation is committed in [Middleware PR 226](https://github.com/appolon1908-hue/Middleware-/pull/226), source `cedaa23b89f84f365ae6789413411c3f01516952`. Runtime deployment remains unverified and no production activation is authorized.

## Separate schema-authority review required

Middleware's `scripts/production_migration_authority.py` requires a separate protected review before advancing the approved migration head. The API PR adds the actual migration, but intentionally retains the existing approved release authority. Full repository CI therefore rejects the new head until that independent review is completed. Do not skip this validator or use an administrator bypass.

| Field | Current approved value | Proposed value for review |
| --- | --- | --- |
| artifactAuthority.requiredSchemaHead | 0057_platform_service_catalog | 0058_integrated_monitoring |
| artifactAuthority.requiredMigrationHistorySha256 | sha256:4a97d128e6dd23e5d03cda761dc3263c339e37a66ff789b4537a08b7747e3f7f | sha256:02c6394a883ac817afe00b40b8f0d72555645cfb4d31d8c6e6167716a953df0c |
| New migration file SHA-256 | Not present | sha256:7e9ecbe7563d8449f273ce5339f90b2939c5d8e045a0dede87836a19b6da6884 |

The authority file is `config/middleware-forward-release-authority.v1.json` in Middleware. Review the corresponding platform release tuple and its required runtime evidence together. Preserve historical signed evidence at its actual schema head; it must not be relabeled as a new signed release. Keep all deployment, production-traffic and external-effect authorization fields false. After the separate approval is merged, rebase the implementation and rerun the complete migration, container, contract and runtime-certification gates.

The migration creates `monitoring_resources`, `monitoring_operations` and `monitoring_events`, with tenant keys, replay uniqueness, revision ordering and scoped indexes. Runtime never auto-creates tables. The focused suite applies the actual migration and exercises durable observations, concurrent replay, scoped reads and all 36 routes. Empty downgrade/reupgrade is supported for the existing disposable CI rehearsal. Downgrade takes an exclusive lock and refuses to remove any nonempty monitoring evidence. Application rollback preserves these tables; retained data requires the reviewed export/restore process.

## Existing trust-workflow mismatch

The protected launcher also rejects `.github/workflows/production-orchestrator-contract.yml`: its SHA-256 is `5d5f118c8089a7298cc7439327689f862bf669bad46ec9160a0b5763fa11e869`, which is absent from the launcher's approved workflow hashes. These workflow bytes are unchanged from implementation base `b02f29f84e801fb38592be98624790892607964b`. This change does not edit the protected trust launcher or its approval list. A separate authorized trust-root review must reconcile that baseline mismatch.

## Release evidence still needed

Exact protected-branch source and immutable signed image; full required CI; approved schema/history tuple; separately applied forward migration; mounted tenant/service/backend identities; actual app instrumentation and collectors; private endpoint connectivity; synthetic metrics/logs/traces/alert evidence; backup restore and rollback evidence. The repository documents and passing API tests do not certify live connectivity for all apps.
