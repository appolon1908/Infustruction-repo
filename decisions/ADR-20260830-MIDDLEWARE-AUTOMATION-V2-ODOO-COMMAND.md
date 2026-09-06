# ADR — Middleware automation v2 and canonical Odoo CRM command

- **Date:** 2026-08-30
- **Status:** Accepted for source integration; runtime activation remains blocked
- **Decision owner:** Codestra platform owner
- **Repositories:** `N8N`, `Middleware-`, `Odoo`, `Kong`, `Keycloak`

## Context

Codestra Middleware already contains a substantial durable integration core:
command persistence, idempotency, inbox/outbox primitives, dead letters, replay,
leases and reconciliation. n8n separately defined a stronger automation-v2
control plane with job leasing, exact client-family scopes, approvals,
capability reads and protected replay.

The conflict was not whether either design was coherent. The problem was that
Middleware implemented one contract while its n8n and Odoo consumers expected
another.

The same conflict existed at the Odoo boundary:

- Odoo's reviewed bridge declared `crm.lead.upsert` and command-status read-back;
- the Middleware adapter used separate create/update command types and direct
  CRM CRUD paths;
- the two sides signed different HMAC byte strings;
- n8n templates used a numeric command version and older route names.

## Decision

### 1. Middleware adopts automation v2

The canonical n8n control plane is:

```text
POST /v2/automation/jobs/claim
GET  /v2/automation/jobs/{job_id}
POST /v2/automation/jobs/{job_id}/heartbeat
POST /v2/automation/jobs/{job_id}/steps
POST /v2/automation/jobs/{job_id}/complete
POST /v2/automation/jobs/{job_id}/fail
POST /v2/automation/commands
GET  /v2/automation/commands/{command_id}
POST /v2/automation/approvals
GET  /v2/automation/approvals/{approval_id}
POST /v2/automation/dead-letters/{dead_letter_id}/replay
POST /v2/automation/jobs/reconcile
GET  /v2/automation/capabilities/{capability}
```

The existing `/v1/integrations/n8n/*` endpoints are deprecated compatibility
aliases. They are not canonical for new workflows and must not appear in new
n8n templates.

### 2. Odoo keeps one canonical CRM mutation

The canonical business command is:

```text
command_type    = crm.lead.upsert
command_version = "1.0"
target          = odoo-19
capability      = ODOO_WRITE
```

Middleware calls the reviewed Odoo module `codestra_middleware_bridge` through:

```text
POST /codestra/middleware/v1/commands/crm.lead.upsert
GET  /codestra/middleware/v1/commands/{command_id}/status
```

The direct Odoo CRM CRUD routes remain deprecated compatibility surfaces.

### 3. Middleware remains the only cross-system writer

n8n, product applications, websites, crawlers, provider systems and reporting
tools do not write directly to Odoo or its PostgreSQL database. n8n requests a
governed command; Middleware persists, authorizes, executes and reconciles it.

### 4. Tenant and actor assertions never grant authority

The verified Keycloak token and durable automation job are authoritative. The
request headers and body contain assertions that must agree with those
authorities:

- `X-Tenant-ID` / `tenant_id`;
- token subject / `requested_by`;
- `X-Correlation-ID` / `correlation_id`;
- `Idempotency-Key` / `idempotency_key`.

A Kong routing or header mistake cannot grant a tenant, actor, workflow family,
command prefix or capability.

### 5. Odoo HMAC is byte-exact

Middleware and Odoo join the following byte sequences with one newline in this
exact order and compute HMAC-SHA256:

```text
X-Codestra-Timestamp
X-Codestra-Event-ID
HTTP method in uppercase
request path
X-Tenant-ID
X-Correlation-ID
Idempotency-Key
raw request body
```

A synthetic cross-repository golden vector must remain identical in the Odoo
and Middleware repositories. Runtime secrets never enter Git.

### 6. Unknown outcomes require reconciliation

A timeout after a write is an unknown outcome, not a failure. Therefore:

```text
blind resubmission after unknown outcome = prohibited
Odoo command-status reconciliation       = required
n8n automatic retry on timeout            = prohibited
Temporal adapter write attempts           = one
```

If Odoo recorded the command, Middleware returns the recorded result. If not,
the command remains unresolved until policy permits a retry with the same
semantic identity.

## Exact client and scope for CRM automation

```text
client_id     = n8n-crm-automation
audience      = middleware-api
submit_scope  = automation.command.crm
read_scope    = automation.command.read
command_prefixes = crm. and support.
```

Generic `automation.execute` and `automation.command` scopes remain prohibited.
Client scopes are exact, with no implicit union.

## Source implementation order

1. Review and merge the Odoo canonical integration contract.
2. Review and merge the Middleware canonical Odoo adapter and validation.
3. Review and merge the n8n automation-v2 contract, schema, surface and disabled templates.
4. Review and merge this decision and the architecture/index documentation.
5. Implement the thirteen Middleware runtime routes in separately reviewable PRs, removing each conformance waiver only when the route and invariant tests land.
6. Complete write-disabled isolated-staging certification.
7. Enable any live capability only as a separate approved production change.

The code PRs may be reviewed in parallel, but the final merged source must be
contract-identical before staging begins.

## Superseded assumptions

This ADR supersedes documents or PR descriptions that treat any of the
following as canonical:

- `/v1/integrations/n8n/commands` for new n8n workflows;
- `crm.lead.create.v1` and `crm.lead.update.v1` as separate Odoo authorities;
- numeric `command_version = 1` for the Odoo command;
- HMAC over timestamp, event, method, path and body only;
- direct Marketing, n8n or product writes to Odoo;
- retrying an Odoo write merely because the caller timed out.

Historical evidence is not rewritten. It must be read as evidence for the exact
commit and contract version it reviewed.

## Safety and non-actions

This ADR does not:

- activate an n8n workflow;
- mount missing Middleware automation-v2 routes;
- provision or rotate Keycloak credentials;
- enable `ODOO_WRITE`;
- enable email, SMS, social, crawler, telephony or PSTN effects;
- install or upgrade an Odoo module;
- migrate a live database;
- deploy staging or production;
- authorize a merge bypass.

All capability and kill-switch values remain false until their own exact-artifact
review, staging canary, reconciliation, backup, restore and rollback gates pass.
