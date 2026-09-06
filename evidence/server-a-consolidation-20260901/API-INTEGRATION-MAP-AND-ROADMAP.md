# Codestra API, integration, and completion roadmap

Evidence date: 2026-09-01. Routes below are extracted from the canonical Middleware source tree (`/opt/codestra/middleware`) and the reviewed `Middleware-` contract tree. A route listed here is source evidence, not proof that it is currently exposed by Caddy/Kong or certified in production.

## Request path and ownership

`Browser/service -> Caddy -> Kong -> Keycloak -> Middleware -> durable inbox/outbox -> worker -> Odoo/n8n/approved adapter -> provider`. Middleware owns authorization, tenant context, idempotency, audit, retry/dead-letter, and provider policy. n8n is orchestration only. Provider writes remain disabled.

## Middleware endpoints

### Health and runtime

| Endpoint | Consumer | Purpose |
|---|---|---|
| `GET /health`, `/healthz` | Caddy/Kong/monitoring | Process liveness |
| `GET /readiness`, `/readyz` | deployment/monitoring | Dependency readiness |
| `GET /version` | release read-back | Safe release identity |
| `GET /dependencies` | operators/monitoring | Dependency status |

### Durable control and automation (`/api/v1`, `/api/v1/automation`)

| Endpoint family | Consumer | Purpose |
|---|---|---|
| `POST /api/v1/events/odoo`, `/events/vicidial` | Odoo/VICIdial adapters | Authenticated inbound events; enqueue durable processing |
| `GET /api/v1/events/{event_id}` | workers/operators | Event status/read-back |
| `POST /api/v1/callbacks`, `PATCH /api/v1/callbacks/{id}` | callback adapters | Persist callback work/state |
| `POST /api/v1/automation/idempotency/check` | services/n8n | Duplicate-command decision |
| `POST /api/v1/automation/events` | n8n/workers | Durable event intake |
| `POST /api/v1/automation/policy-check` | all effect paths | Policy/safety authorization |
| `POST /api/v1/automation/executions/{transition}` | n8n | Execution state transition |
| `POST /api/v1/automation/events/dead-letter` | workers | Dead-letter persistence |
| `GET /api/v1/automation/events/{event_id}` | operations | Event read-back |
| `GET /api/v1/automation/context/{resource}/{identifier}` | orchestration | Tenant/resource context |
| `GET /api/v1/automation/callbacks/{state}` | operations | Callback state query |
| `GET /api/v1/automation/queues/status` | monitoring | Queue depth/health |
| `POST /api/v1/automation/actions/{action}` | authorized services | Controlled asynchronous action; must return operation state |

### Odoo and n8n integration (`/api/v1/integrations`)

| Endpoint | Consumer | Purpose |
|---|---|---|
| `GET /api/v1/integrations/odoo/health`, `/odoo/readiness` | monitoring | Odoo adapter health |
| `POST /api/v1/integrations/odoo/commands` | Middleware worker | Canonical Odoo command submission |
| `GET /api/v1/integrations/odoo/commands/{command_id}` | Middleware/n8n | Odoo command status |
| `POST /api/v1/integrations/n8n/dispatch` | Middleware | Dispatch orchestration job |
| `POST /api/v1/integrations/n8n/results`, `/n8n/errors` | n8n | Result/error callback |
| `POST /api/v1/integrations/n8n/reconciliation` | operations | Reconcile execution state |

### Telephony, webphone, and reconciliation

| Endpoint family | Consumer | Purpose |
|---|---|---|
| `/v1/telephony/extensions/*` | provisioning/telephony | Audit, pools, availability, reserve |
| `/v1/telephony/provisioning*` | provisioning service | Create/status/activate/suspend/deprovision/rollback |
| `/v1/telephony/reconcile` | telephony worker | Reconcile external state |
| `/api/v2/telephony/canary` | controlled publisher | Synthetic canary only; no live dialing |
| `/webphone-api/v1/*` | browser/webphone | Session/provision/config/revoke; requires identity and tenant checks |
| `/api/v1/crm-vicidial/reconciliation/*` | CRM/VICIdial worker | Lead reconciliation and metrics |

### Operations, policy, reports, quarantine

| Endpoint family | Consumer | Purpose |
|---|---|---|
| `/api/v1/operations/reliability` | operators | Reliability summary |
| `/api/v1/operations/dead-letters` | operators | Inspect/replay failed durable work |
| `/api/v1/operations/maintenance/recover` | DBA/operator | Controlled maintenance recovery |
| `/api/v1/policy/decisions` | all effect paths | Central policy decision |
| `/api/v1/reports/{report_name}` | reporting | Read-only operational reports |
| `/api/v1/quarantine/*` | evidence/operator | Review/correct/reprocess invalid events |

### Social/Postiz adapter surface

`/integrations/postiz/health`, `/readiness`, `/results`, `/errors`, `/channels`, `/posts`, `/posts/{post_id}/cancel`, and `/analytics/platform` are adapter routes. Publishing must remain disabled and require Middleware policy, approval, idempotency, and audit.

## Reviewed connector integrations

| Integration | Direction | What it does | Authority |
|---|---|---|---|
| Odoo 19 CRM | Middleware ↔ Odoo | Lead/contact/activity command and status reconciliation | Middleware command + Odoo bridge |
| n8n | Middleware ↔ n8n | Orchestrates workflows and returns execution state | Middleware remains provider authority |
| VICIdial | VICIdial → Middleware | Authenticated call-result/callback ingestion and reconciliation | Private adapter; dialing disabled |
| Provisioning service | Middleware ↔ provisioning | Telephony/extension provisioning lifecycle | Middleware policy |
| Postiz/social | Middleware ↔ social adapter | Draft/channel/post/result/analytics lifecycle | Publishing disabled |
| SMS connector | Middleware ↔ approved SMS adapter | Command/status delivery path | No direct n8n/provider credentials |
| Email connector | Middleware ↔ approved email adapter | Preview/queue/delivery-event path | Delivery disabled |
| AI | Middleware ↔ approved AI adapter | Policy/budgeted job orchestration | External model calls disabled |
| Marketing | Middleware ↔ campaign service | Draft/approval/attribution | Advertising disabled |

## Common contract required for every mutating route

`Authorization`, `Idempotency-Key`, `X-Correlation-ID`, authenticated principal, tenant context, operation ID, policy decision, audit event, and durable inbox/outbox state. Asynchronous effects should return `202 Accepted` with `operation_id`, state, and a status URL. Errors must include safe `code`, `message`, `correlation_id`, `retryable`, and optional safe details. Webhooks require signature, timestamp, replay, tenant/provider binding, persistence, and dead-letter handling.

## Roadmap to production readiness

1. **Authority:** merge PR #55 evidence; map every running service to one GitHub repository, protected SHA, build recipe, digest, config checksum, SBOM, provenance, and rollback digest.
2. **Contracts:** generate OpenAPI from the actual Middleware entrypoint; compare Kong routes; remove or quarantine undocumented/duplicate route generations.
3. **Security:** provision separate Keycloak service identities and scopes; route all provider effects through Middleware; keep all effect switches disabled.
4. **Durability:** prove database roles/CONNECT isolation, one-shot migrations, inbox/outbox/idempotency, Redis recovery, and off-site encrypted restore.
5. **Application recovery:** run isolated Appolon, Beyvra, email-reseller, control-plane, Odoo-filestore, and n8n credential-aware restores with provider egress blocked.
6. **Staging:** deploy exact immutable digests to `2.29.17.172`; run auth, authorization, tenant-isolation, duplicate/replay, timeout, dead-letter, observability, failure-injection, load, soak, and rollback tests.
7. **Production canary:** deploy the identical digests to `65.109.65.169`; read back release/SHA/digest/schema/config and run read-only synthetic flows.
8. **Certification:** mark PASS only when every mandatory gate passes; keep external capabilities disabled until separate activation packets are approved.

## Current status

The route map is source-derived. Production exposure, Kong/Caddy mapping, endpoint readiness/version contracts, staging certification, backup/restore, and external-effect safety remain certification gates. Current overall decision remains **NO-GO / NOT PRODUCTION CERTIFIED**.
