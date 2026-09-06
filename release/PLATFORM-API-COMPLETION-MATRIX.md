# Codestra Platform API Completion Matrix

Generated: `2026-09-02T15:08:48Z`

## Authority

```text
CHANGE_ID=CHG-20260901-CODESTRA-PLATFORM-API-COMPLETION-01
MODE=REPOSITORY_FIRST_SOURCE_COMPLETION
PRODUCTION_AUTHORIZED=false
EXTERNAL_EFFECTS_ENABLED=false
PROMETHEUS_NEW_TARGETS=pending
BLACKBOX_TARGET=pending
```

## Confirmed audit conclusions

- Middleware already implements the lead and survey intake boundaries plus health, readiness, version, metrics, runtime safety, and part of Communications.
- The thirteen automation-v2 operations remain runtime gaps and have active conformance waivers.
- Six provider-control operations are defined by policy but require durable runtime implementation.
- A durable Alertmanager ingestion and incident lifecycle API is required.
- Marketing, AI, Communication, and Social have runnable foundations but incomplete route families and provider actions that currently terminate safely rather than execute.
- SDK readiness must validate real OpenAPI instead of source-string matches.

## Current operation status totals

| Status | Count |
|---|---:|
| `canonical_replacement_required` | 1 |
| `implemented` | 17 |
| `implemented_provider_execution_501` | 2 |
| `implemented_read_disabled` | 1 |
| `legacy_equivalent` | 2 |
| `legacy_equivalent_without_auth_idempotency` | 1 |
| `legacy_equivalent_without_tenant_auth` | 1 |
| `legacy_publish_501` | 1 |
| `missing` | 52 |
| `missing_in_service` | 5 |
| `open_pr_57` | 1 |
| `policy_defined_runtime_missing` | 6 |
| `required` | 25 |
| `runtime_missing` | 5 |
| `runtime_missing_waiver_active` | 13 |

## Repository ownership summary

| Repository | Operations | Primary remaining work |
|---|---:|---|
| `appolon1908-hue/Codesrea-Social-` | 26 | Canonical tenant-safe `/v1/social` APIs, approvals, scheduling, publication operations and runtime sync. |
| `appolon1908-hue/Codestra-AI` | 13 | Model/policy/usage APIs, request events/cancel and Middleware-backed provider operations. |
| `appolon1908-hue/Codestra-Communication-CC` | 22 | List/events/cancel, templates, consent, suppression, provider status and Middleware-backed delivery. |
| `appolon1908-hue/Codestra-Marketing-` | 33 | Campaign lifecycle, activation requests through Middleware, attribution, bounded analytics and OpenAPI. |
| `appolon1908-hue/Middleware-` | 37 | Automation-v2 runtime, provider-operation ledger, incident APIs, migrations, OpenAPI parity. |
| `appolon1908-hue/Odoo` | 2 | Private canonical CRM upsert/status boundary; no public CRM write route. |

## Existing PR authority to preserve

| Repository | PR | Disposition |
|---|---:|---|
| Middleware | #82 | Review provider-operation policy, then implement runtime on a separate current-base branch. |
| Keycloak | #60 | Review exact service identities and provider-worker scopes after Middleware policy stabilizes. |
| Kong | #43 | Review after accepted Middleware and Keycloak merge identities are known. |
| SDK | #54 | Merge branch reconciliation, then replace manifest string matching with OpenAPI validation. |
| N8N | #38 | Review exact automation-family client ownership. |
| N8N | #34 | Rebuild on current main; close the stale non-mergeable PR only after parity. |
| Odoo | #57 | Review the tenant-safe, replay-safe CRM lead upsert implementation. |

## Definition of source completion

```text
AUTOMATION_V2_RUNTIME_OPERATIONS=13/13
AUTOMATION_WAIVERS=0
PROVIDER_CONTROL_RUNTIME_OPERATIONS=6/6
ALERTMANAGER_INGESTION_API=PASS
INCIDENT_LIFECYCLE_API=PASS
OPENAPI_RUNTIME_PARITY=PASS
KEYCLOAK_SCOPE_PARITY=PASS
KONG_ROUTE_PARITY=PASS
SDK_GENERATION_PARITY=PASS
DIRECT_PROVIDER_BYPASS_PATHS=0
N8N_ACTIVE_WORKFLOWS=0
RUNTIME_DEPLOYED=false
PRODUCTION_CHANGED=false
EXTERNAL_EFFECTS_ENABLED=false
```

Source completion is not runtime certification. Staging integration, immutable artifact verification, migrations, rollback, observability evidence, and production activation remain separate gates.
