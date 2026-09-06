# Mission: Codestra Platform API Completion

Change ID: `CHG-20260901-CODESTRA-PLATFORM-API-COMPLETION-01`

This branch establishes the Infrastructure-owned API authority used to complete the existing Codestra repositories without creating one repository per capability.

## Required implementation order

1. Merge or refresh Middleware PR #82.
2. Merge or refresh Keycloak PR #60.
3. Merge or refresh Kong PR #43.
4. Implement Middleware automation-v2, provider operations, and Alertmanager incident APIs.
5. Review Odoo PR #57.
6. Complete Marketing, AI, Communication, and Social route families.
7. Replace SDK path-string readiness with real OpenAPI validation.
8. Rebuild stale N8N PR #34 on current main; preserve PR #38 family-client authority.
9. Complete OpenBao policy and Prometheus observability bindings.
10. Promote through development, test, staging, production, and main without treating source merge as deployment permission.

## Non-negotiable state

```text
LIVE_ADVERTISING_ENABLED=false
META_READ_SYNC_ENABLED=false
EXTERNAL_MODEL_CALLS_ENABLED=false
EXTERNAL_DELIVERY_ENABLED=false
SOCIAL_READ_SYNC_ENABLED=false
SOCIAL_PUBLISHING_ENABLED=false
LIVE_EMAIL_DELIVERY=false
LIVE_SMS_DELIVERY=false
LIVE_PSTN_DIALING=false
ODOO_WRITE=false
N8N_DELIVERY_ENABLED=false
PRODUCTION_AUTHORIZED=false
PROMETHEUS_NEW_TARGETS=pending
BLACKBOX_TARGET=pending
```

## Binding artifacts

- `contracts/platform-api/authority.json`
- `contracts/platform-api/operations-*.json`
- `release/PLATFORM-API-COMPLETION-MATRIX.md`
- `scripts/validate_platform_api_authority.py`
- `.github/workflows/validate-platform-api-authority.yml`

## Completion rule

An operation may move from `missing` or `runtime_missing_*` only in the same reviewed change that adds the runtime route, committed OpenAPI, authorization, tenant handling, idempotency behavior where applicable, persistence/migration behavior, observability, and tests.

No operation in this mission authorizes an external provider effect.
