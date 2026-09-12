# ADR — Middleware is the sole agent-provisioning saga authority

- **Date:** 2026-09-11
- **Status:** Accepted for source integration; runtime activation remains blocked
- **Decision owner:** Codestra platform owner
- **Mission:** `CHG-20260911-CODESTRA-PLATFORM-API-COMPLETION-02`
- **Repositories:** `Middleware-`, `codestra-provisioning-service`, `Odoo`, `Vicidialer-Codestra`, `Keycloak`

## Context

Three independent surfaces currently exist for what is conceptually one
capability — provisioning a human's platform identity, campaign membership,
and channel access (phone/WebRTC/email/SMS):

1. **`Middleware-` PR #238** — `POST /platform/v1/agent-provisioning/requests`
   (+ `/reconcile`, `/suspend`, `/reactivate`, `/revoke`). A durable saga with
   state machine `REQUESTED → VALIDATING → IDENTITY → ENTITLEMENTS →
   CHANNEL_PROVISIONING → READBACK → {EFFECTIVE, PARTIAL, FAILED,
   RECONCILING, SUSPENDED, REVOKED}`, gated by `live_identity_provisioning_enabled`
   (default `false`). Built this mission cycle; not yet merged.

2. **`codestra-provisioning-service`** — a private, staging-only FastAPI
   service (`app/engine.py`, `app/adapters.py`, `app/keycloak.py`,
   `app/sip_browser.py`, `app/mailbox.py`) exposing its own fully independent
   public route surface:

   ```text
   POST /v1/provisioning/requests/{request_id}/execute
   POST /v1/provisioning/requests/{request_id}/retry
   POST /v1/provisioning/requests/{request_id}/verify
   POST /v1/provisioning/requests/{request_id}/cancel
   GET  /v1/provisioning/requests/{request_id}
   POST /v1/identities/{employee_id}/{suspend|reactivate|terminate|rotate}
   GET  /v1/identities/{employee_id}/reconciliation
   POST /session   (SIP browser session issuance)
   POST /renew
   GET  /config
   POST /revoke
   ```

   with its own scope-based authorizer (`provisioning:execute`,
   `provisioning:read`, `identity:rotate`), its own step engine, dead-letter
   table, and compensation logic. It is network-isolated (TLS on a
   Docker-internal `private` network only, no published host port) and
   requires a Keycloak service JWT scoped to
   `codestra-provisioning-service-staging` — but nothing at the application
   layer restricts *who* on that private network may call it. It is a real,
   independent execution authority today, not merely an internal library.

3. **`Odoo`'s own `/v1/contact-center/` API** — a third, fully specified
   surface (`api/openapi/contact-center-v1.yaml`,
   `api/contracts/vicidial-route-map.json`,
   `docs/authority/ODOO_19_CONTACT_CENTER_AUTHORITY.md`) that includes:

   ```text
   POST /v1/contact-center/provisioning/agents   — "Start idempotent agent provisioning"
   ```

   Searched for an implementing controller across the org: **none found.**
   This route is specified (OpenAPI + route map + a corporate call-center
   mission doc) but never implemented. It is a paper duplicate, not a live
   competing system. `codestra-production-platform`'s own baseline audit
   already notes this OpenAPI surface and its authorization-negative tests
   are incomplete.

   Note: `/v1/contact-center/` also covers calls, interactions, dispositions,
   callbacks, and transfers — a broader call-center domain than agent
   provisioning alone, and it independently overlaps with the Calls/Activity
   read APIs added to `Middleware-` in PR #245 this same mission cycle. That
   overlap is **out of scope for this ADR** (which is scoped to
   agent-provisioning authority only) and is flagged as a follow-up
   investigation, not resolved here.

`Vicidialer-Codestra` is the actual telephony runtime authority underneath
all three, most recently extended this mission cycle (PR #52) with
`/v1/agents/sync`, `/v1/agents/disable`, `/v1/agents/provision-disabled`,
`/v1/extensions/{reserve,adopt}`, and `/v1/webrtc/{provision,rotate,revoke}`.

`codestra-provisioning-service` PR #28 ("Use canonical VICIdial provisioning
contract") independently discovered and fixed a real bug: its VICIdial
adapter was calling a nonexistent legacy route
(`create_user_disabled`/`update_user`/etc.) instead of the real
`/v1/agents/provision-disabled` contract. The fix narrows VICIdial support to
exactly `CREATE_DISABLED` via the real route, with a dedicated
`telephony:agent-provision` scope and a v2 HMAC signature
(method/path/identity/scope/timestamp/nonce/idempotency/body-bound), and
makes every other lifecycle operation fail closed rather than call an
unimplemented route. Full suite 92 passed; 12 adapter tests including exact
v2 signature and empty-HMAC rejection.

## Decision

### 1. Middleware is the sole active provisioning saga authority

```text
POST /platform/v1/agent-provisioning/requests
POST /platform/v1/agent-provisioning/requests/{request_id}/reconcile
POST /platform/v1/agent-provisioning/requests/{request_id}/suspend
POST /platform/v1/agent-provisioning/requests/{request_id}/reactivate
POST /platform/v1/agent-provisioning/requests/{request_id}/revoke
```

is canonical. It owns authorization, tenant validation, idempotency, saga
state, audit, retries, reconciliation, compensation, and final effective
status for agent identity, campaign membership, and channel provisioning.

This path is deliberately distinct from the pre-existing, unrelated
`/platform/v1/provisioning/requests` (infrastructure/service-catalog
provisioning) already live in `Middleware-`. The two are not the same
capability and neither is renamed by this ADR.

### 2. `codestra-provisioning-service` becomes a private downstream execution
   layer, not a peer saga

**Current state** (as found, not yet changed): a fully independent public
route surface with its own engine, scopes, and state — reachable by anything
holding a valid service-scoped Keycloak token on the private network, not
only by Middleware.

**Target state**: its step engine and adapters (Keycloak lifecycle calls, SIP
browser session issuance, mailbox provisioning) are reconciled into a
Middleware-controlled worker contract. Its `/v1/provisioning/requests/*` and
`/v1/identities/*` routes stop being independently callable saga entry
points; Middleware's saga becomes the only caller. Its SIP browser session
routes (`/session`, `/renew`, `/config`, `/revoke`) require the same review —
whether they should be invoked directly by a WebPhone client or brokered
through Middleware's WebRTC session issuance (`app/api/v1/webphone.py`) is an
open question for the reconciliation workstream, not decided here.

This reconciliation is **future work**, tracked separately. This ADR records
the target state and the ownership boundary; it does not implement the
worker-contract migration.

### 3. Odoo is desired-state authority; its `/v1/contact-center/provisioning/agents`
   route is deprecated before implementation

Since no controller ever implemented this route, deprecation here means:
remove it from `api/openapi/contact-center-v1.yaml` and
`api/contracts/vicidial-route-map.json`, and update
`docs/authority/ODOO_19_CONTACT_CENTER_AUTHORITY.md` /
`docs/missions/CODESTRA-CORPORATE-CALL-CENTER.md` to point agent-provisioning
initiation at Middleware's canonical route instead. Odoo's actual desired-state
models (`codestra.platform.user`, `codestra.tenant.membership`,
`codestra.agent.channel`, `codestra.provisioning.request`/`.step`/`.audit`,
the M2 provisioning wizard — all confirmed already built in `Odoo` main this
mission cycle) remain the correct origin of a provisioning request; they
should call Middleware's canonical route, not the unimplemented
`/v1/contact-center/` path.

### 4. Ownership of credentials, audit, retries, and reconciliation

```text
Identity authority              Keycloak
Desired state authority         Odoo (codestra_identity_provisioning models)
Public saga / effective state   Middleware- (agent-provisioning saga)
Private execution adapters      codestra-provisioning-service (target state)
Telephony runtime authority     Vicidialer-Codestra / Asterisk
Credential custody              OpenBao (secret references only; no plaintext
                                 credential in Odoo, Middleware DB, n8n, or Git)
Audit of record                 Middleware's agent_provisioning_audit table
                                 for saga-level decisions; provisioning-service
                                 keeps its own step-level execution audit as a
                                 subordinate record, not a competing one
Retry/compensation              Middleware's saga owns retry policy and
                                 compensation triggers; provisioning-service's
                                 own retry/dead-letter machinery becomes an
                                 execution-layer detail invoked by Middleware,
                                 not an independently-triggered retry path
```

### 5. `codestra-provisioning-service` PR #28 evaluation

**Recommendation: safe to merge on its own technical merits, independent of
the broader reconciliation.**

Reasoning: it does not add new public surface or expand the duplication this
ADR addresses — it only corrects the VICIdial adapter to call the real,
existing `Vicidialer-Codestra` route instead of nonexistent legacy ones, and
fails closed for unsupported operations instead of silently attempting a
dead endpoint. That is a strict risk reduction. It does not touch
`app/main.py`'s top-level route registration, so it neither resolves nor
worsens the "should this remain a fully independent public saga" question
addressed above. 92/92 suite passed; the dedicated v2 signature and
empty-HMAC-rejection tests give confidence in the specific change.

**Open item for the reconciliation workstream, not a blocker for #28**:
confirm whether `Vicidialer-Codestra` has real routes backing the other
VICIdial lifecycle operations this PR now fails closed on
(`UPDATE`/`VERIFY`/`ACTIVATE`/`SUSPEND`/`REACTIVATE`/`TERMINATE`/`RECONCILE`),
or whether those remain permanently out of scope for the VICIdial adapter.

This ADR does not merge PR #28. The merge decision remains with the
repository's own review process.

## Canonical vs. duplicate route table

| Route | Repository | Status | Disposition |
|---|---|---|---|
| `POST /platform/v1/agent-provisioning/requests` (+ lifecycle) | `Middleware-` | **Canonical** | Keep |
| `POST /v1/provisioning/requests/{id}/execute` (+ retry/verify/cancel) | `codestra-provisioning-service` | Live, private-network, independently callable | Reconcile into Middleware-invoked worker contract (future work) |
| `POST /v1/identities/{employee_id}/{suspend,reactivate,terminate,rotate}` | `codestra-provisioning-service` | Live, private-network, independently callable | Same — becomes Middleware-invoked, not independently callable |
| `POST /v1/contact-center/provisioning/agents` | `Odoo` (spec only) | Specified, **never implemented** | Deprecate in OpenAPI/route-map/docs; point at Middleware's canonical route |
| `/session`, `/renew`, `/config`, `/revoke` (SIP browser) | `codestra-provisioning-service` | Live, private-network | Open question: broker through Middleware's WebRTC session issuer, or keep as a direct Middleware-authorized execution detail — decide during reconciliation |
| `/v1/agents/sync`, `/v1/agents/disable`, `/v1/agents/provision-disabled`, `/v1/extensions/{reserve,adopt}`, `/v1/webrtc/{provision,rotate,revoke}` | `Vicidialer-Codestra` | **Canonical runtime adapter surface** | Keep; both Middleware and (post-reconciliation) provisioning-service call this, no competing implementation |
| `/platform/v1/provisioning/requests` (infrastructure/service-catalog) | `Middleware-` | **Canonical, unrelated capability** | Keep, unchanged — not the same domain as agent provisioning, not renamed |

## Source implementation order (future work, not this ADR)

1. Merge this ADR.
2. Review and merge `Middleware-` PR #238 (saga) and the channel-adapter PRs
   stacked on it (#240/#241/#243/#244/#245).
3. Review `codestra-provisioning-service` PR #28 on its own technical merits
   (recommended: merge).
4. Design the Middleware-controlled worker contract for
   `codestra-provisioning-service` (separate ADR or design doc when that
   workstream starts).
5. Migrate `codestra-provisioning-service`'s routes from independently
   callable to Middleware-invoked-only; add network/authorization
   enforcement so only Middleware's saga can reach it.
6. Remove `/v1/contact-center/provisioning/agents` from Odoo's OpenAPI
   contract and route map; update the corporate call-center mission docs.
7. Investigate the `/v1/contact-center/` vs. `Middleware-` PR #245
   Calls/Activity overlap as its own follow-up (out of scope here).
8. Enable any live capability only as a separate approved production change.

## Superseded assumptions

This ADR supersedes any document or PR description that treats any of the
following as a canonical, independently-callable agent-provisioning entry
point:

- `codestra-provisioning-service`'s `/v1/provisioning/requests/{id}/execute`
  and `/v1/identities/{employee_id}/*` as callable by anything other than
  Middleware's saga;
- `/v1/contact-center/provisioning/agents` as a real, implemented route (it
  is not implemented anywhere in the org as of this ADR);
- any assumption that `codestra-provisioning-service`'s own retry/dead-letter
  engine is an independent retry authority rather than a subordinate
  execution detail.

Historical evidence is not rewritten. It must be read as evidence for the
exact commit and contract version it reviewed.

## Safety and non-actions

This ADR does not:

- merge `codestra-provisioning-service` PR #28 (recommendation only);
- modify Middleware's agent-provisioning saga logic;
- modify `codestra-provisioning-service`'s engine, adapters, or routes;
- modify Odoo's OpenAPI contract or route map (the deprecation in Decision §3
  is a recommendation for a future PR, not executed here);
- change any Keycloak client, scope, or credential;
- enable `live_identity_provisioning_enabled`, `klyrow_write_enabled`,
  `telnexa_write_enabled`, or any `codestra-provisioning-service` gate
  (`PROVISIONING_SERVICE_GATE`, `SERVICE_AUTHENTICATION_GATE`, etc.);
- enable PSTN, live SMS, or live email delivery;
- authorize a merge bypass or claim staging/production certification.

All capability and kill-switch values remain false until their own
exact-artifact review, staging canary, reconciliation, backup, restore, and
rollback gates pass.

## Addendum (2026-09-11): Odoo `/v1/contact-center/` surface vs. Middleware PR #245

A separate finding, outside this ADR's original mandate, was raised: does
Odoo's `api/openapi/contact-center-v1.yaml` (interactions, dispositions,
callbacks, transfers) duplicate the Calls/Activity endpoints shipped in
`Middleware-` PR #245 (`GET /platform/v1/calls`, `/calls/{id}`, `/activity`,
`/activity/{id}`)?

**Verdict: false alarm, not a duplication requiring reconciliation.**

Evidence:

- The literal `/v1/contact-center/*` paths (including `/interactions/{id}`,
  `/disposition`, `/callback`, `/transfer`) have zero controller
  implementation anywhere in `appolon1908-hue/Odoo`. The only place these
  paths appear in code is `scripts/validate_call_center_workstreams.py`, a
  contract-registry validator for a planned, ordered workstream rollout
  (`workstreams` list, `order` 0 through 10) — not live routes.
- That same registry already declares
  `canonical_contracts.cross_system_writer = "codestra-middleware"` and
  requires `odoo_core_modification_allowed`, `vicidial_database_writes_allowed`,
  and `n8n_system_of_record_allowed` all be `false`. In other words, this
  spec already designates Middleware as the intended writer/implementer for
  this domain, once built — consistent with, not conflicting with, PR #245.
- Odoo does have real, live call-handling code today, but at a different
  path and for a different concern:
  `codestra_vicidial_crm/controllers/call_control.py` exposes
  `/codestra/call-control/v1/calls/<id>/disposition` and `/callbacks` —
  agent-facing actions an agent submits through the Odoo UI, backed by
  `codestra.vicidial.disposition`/`codestra.callback` models fed directly by
  VICIdial events. This is a write path for agent actions, not a read
  surface for call-lifecycle/activity querying.
- Odoo's only Middleware-facing client, `codestra.telephony.middleware.client`
  (`custom-addons/codestra_vicidial_crm/models/middleware_client.py`), is
  one-way: `originate_call`/`originate_test_syn`/`originate_command` push
  outbound-call requests to Middleware. It does not read back
  `telephony_call_lifecycle` or activity/audit data — there is currently no
  wired connection between Odoo and PR #245's read endpoints, in either
  direction.

**Note on provenance**: the interaction-event consumer commits referenced
when this addendum was requested (`dffcd7b`, `250a3be`, "consume interaction
events into real CRM writes") were verified this session to live in
`Codestra-SRL/codestra-odoo-addons` — a separate, reference-only fork, not
`appolon1908-hue/Odoo`. They could not be located in the canonical repo and
are not part of this addendum's evidence base.

**Recommendation**: no reconciliation action needed now. If/when the
`contact-center-v1.yaml` workstreams are actually implemented, they should
be built as Middleware routes per the registry's own
`cross_system_writer: codestra-middleware` contract — extending PR #245's
Calls/Activity work rather than adding a second implementation in Odoo.
