# Codestra Marketing Stage 4 Authority

Stage 4 converts the Stage 3 service foundations into durable, contract-tested services without authorizing production provider writes.

## Required deliverables

- Marketing: PostgreSQL campaigns, approvals, audiences, creatives; Meta read-only synchronization adapter.
- AI: durable request/audit/usage records; provider routing abstraction; external execution disabled by default.
- Communication: durable messages, idempotency, consent and suppression; provider delivery disabled by default.
- Social: durable account/post/metric state; read/reconciliation adapter; publishing disabled by default.
- Middleware: versioned command/event envelopes, durable outbox/inbox, webhook verification and replay safety.
- Odoo: installable marketing CRM addon with attribution and conversion-feedback fields.
- SDK: typed marketing, AI, communication and social clients through Kong only.
- n8n: inactive version-controlled workflow JSON using service identities and idempotency.
- Kong: version-controlled route fragments; no promotion without auth, upstream health, contract and rollback validation.
- Keycloak: version-controlled client/scope declarations; automation may never receive approval, budget-raise or provider-write authority.
- Social runtime: read/reconciliation adapter first; publishing remains blocked.

## Mandatory default capabilities

LIVE_ADVERTISING_ENABLED=false
META_READ_SYNC_ENABLED=false
EXTERNAL_MODEL_CALLS_ENABLED=false
EXTERNAL_DELIVERY_ENABLED=false
SOCIAL_READ_SYNC_ENABLED=false
SOCIAL_PUBLISHING_ENABLED=false

## Promotion gates

1. Migrations apply and rollback in isolated test databases.
2. Unit and contract tests pass at exact PR head.
3. Tenant isolation tests pass.
4. Idempotency/replay tests pass.
5. Odoo addon installs/upgrades in test environment.
6. Kong and Keycloak plans validate without live apply.
7. Meta integration is read-only and uses least-privilege credentials.
8. All external write capability flags remain false.
9. No runtime/deployment workflow is dispatched from this stage.

Stage 4 completion authorizes staging integration testing only; it does not authorize live advertising, customer delivery, social publishing, or production AI-provider calls.
