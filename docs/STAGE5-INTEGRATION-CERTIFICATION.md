# Stage 5 Integration Certification Authority

Stage 5 certifies repository-managed integrations before any deployment or production activation.

## Required gates

1. Database migrations are reversible and tenant-scoped.
2. Core service exact-head CI runs pytest and safety assertions.
3. Middleware event envelopes validate against a versioned schema.
4. Odoo marketing addon installs/upgrades without direct provider access.
5. Kong route configuration validates without production apply.
6. Keycloak service clients/scopes validate without realm apply.
7. n8n workflow JSON imports in inactive state and contains no live-write authority.
8. SDK clients preserve auth, correlation, and idempotency metadata.
9. Meta and social runtime synchronization are read-only.
10. All production capability switches remain false.

## Mandatory disabled state

- LIVE_ADVERTISING_ENABLED=false
- META_READ_SYNC_ENABLED=false until a dedicated sandbox credential set is supplied
- EXTERNAL_MODEL_CALLS_ENABLED=false
- EXTERNAL_DELIVERY_ENABLED=false
- SOCIAL_READ_SYNC_ENABLED=false until a dedicated staging runtime is supplied
- SOCIAL_PUBLISHING_ENABLED=false

Passing Stage 5 authorizes staging integration testing only. It does not authorize deployment, provider writes, advertising spend, message delivery, AI provider calls, or social publishing.
