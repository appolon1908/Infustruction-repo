# Codestra Marketing Platform — Stage 9 / Production Readiness Status

Date: 2026-08-30

## Decision

SOURCE_AND_SYNTHETIC_STAGE9_READINESS=ACHIEVED
PRODUCTION_RELEASE_READINESS=GREEN
PRODUCTION_WRITE_ACTIVATION=NOT_AUTHORIZED
LIVE_PRODUCTION_CUTOVER=NOT_EXECUTED

Production release readiness is GREEN for the reviewed source tracks and required repository certification gates. This is a release-readiness decision, not authorization to activate live advertising, customer delivery, social publishing, external AI execution, or production gateway/identity writes.

## Exact source tracks

| Repository | Branch | PR | Certification state |
|---|---|---:|---|
| Codestra-Marketing- | feat/marketing-core-foundation-20260830 | 2 | core CI + PostgreSQL certification green |
| Codestra-AI | feat/ai-gateway-foundation-20260830 | 2 | core CI + reversible PostgreSQL certification green |
| Codestra-Communication-CC | feat/communications-core-foundation-20260830 | 2 | core CI + PostgreSQL certification green |
| Codesrea-Social- | feat/social-control-plane-foundation-20260830 | 2 | core CI + reversible PostgreSQL certification green |
| Middleware- | feat/marketing-integration-foundation-20260830 | 60 | full CI + production-route contract + marketing durability certification green |
| Odoo | feat/marketing-crm-foundation-20260830 | 51 | exact head 27a1c66a3de5d19afb29d61db68eb461f5a6954b; Security gates + Odoo Addons CI including Odoo 19/PostgreSQL runtime certification green |
| SDK-repository | feat/marketing-sdk-foundation-20260830 | 42 | Stage 5 SDK + compatibility + workspace CI green |
| N8N | feat/marketing-workflows-foundation-20260830 | 21 | source validation + design-contract certification green; executable marketing workflows intentionally absent until bindings are verified |
| Kong | feat/marketing-edge-foundation-20260830 | 26 | exact clean head 7c4fddfae1e9722eceea7a1e2d0fb6fb26708e20; Stage 5 certification + complete source authority + canonical config + fail-closed security green; immutable manifests synchronized |
| Keycloak | feat/marketing-identity-foundation-20260830 | 40 | authoritative Keycloak GitOps validation green |
| social.codestra.co | feat/codestra-social-adapter-foundation-20260830 | 26 | read-only adapter certification green |
| Infustruction-repo | feat/marketing-stage3-execution-authority-20260830 | 11 | Stage 9 synthetic end-to-end certification green |

## Stage 9 synthetic flow proven

provider.test_lead
→ kong.authenticated_ingress
→ middleware.inbox.accepted
→ marketing.attribution.recorded
→ odoo.crm.lead_upserted
→ n8n.workflow.received
→ communication.dry_run_created
→ odoo.outcome.recorded
→ marketing.conversion_feedback_recorded

The synthetic evidence proves tenant/correlation continuity, unique idempotency identities, dry-run communications, and zero advertising-provider writes.

## Production safety baseline

LIVE_ADVERTISING_ENABLED=false
META_READ_SYNC_ENABLED=false
EXTERNAL_MODEL_CALLS_ENABLED=false
EXTERNAL_DELIVERY_ENABLED=false
SOCIAL_READ_SYNC_ENABLED=false
SOCIAL_PUBLISHING_ENABLED=false
KEYCLOAK_LIVE_APPLY=false
KONG_LIVE_APPLY=false

These switches remain mandatory for the current GREEN release-readiness state.

## Runtime cutover evidence still required before live activation

1. Apply/read back the reviewed Kong declarative fragment in staging only.
2. Execute Keycloak staging CHECK/APPLY/read-back with managed service-client credentials held outside Git.
3. Import the marketing workflow into the target n8n staging version only after endpoint and credential bindings are VERIFIED; keep it inactive for initial certification.
4. Bind a Meta test-account/read-only credential and prove pagination, checkpointing, reconciliation, and zero provider writes.
5. Prove social runtime staging read synchronization using the read-only adapter.
6. Run a traceable deployed staging flow through Kong → Middleware → Marketing → Odoo → n8n → Communication dry-run → conversion feedback.
7. Capture rollback and reconciliation evidence for each staged component.
8. Perform an explicit production go/no-go review before changing any live-write capability from false.

No item above is automatically authorized by `PRODUCTION_RELEASE_READINESS=GREEN`. Live production remains fail-closed until the runtime cutover evidence and explicit go/no-go approval exist.
