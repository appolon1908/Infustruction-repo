# Codestra Stage 6-8 Staging, Observability, and Read-Only Canary Authority

Status: SOURCE PREPARATION ONLY. This document does not authorize live external writes.

## Objective

Move the Codestra marketing platform from source/release readiness to deployed staging certification, full observability coverage, and a production read-only canary while preserving fail-closed external-write controls.

## Stage 6 — Staging Runtime

Required services: Kong, Keycloak, Middleware, Codestra Marketing, Codestra AI, Codestra Communication, Codestra Social, social.codestra.co runtime, n8n, Odoo, PostgreSQL/Redis as required.

Required staging rules:
- Deploy immutable artifacts built from reviewed main commits only.
- Run database migrations as one-shot release actions, never from application replica startup.
- Apply Keycloak and Kong from repository-controlled plans/manifests.
- Keep n8n workflows inactive until endpoint/credential binding validation passes.
- Install and upgrade the Odoo marketing CRM addon in staging.
- Use test/read-only provider credentials only.
- No production advertising spend, customer messaging, social publishing, or external AI calls are authorized by this stage.

## Stage 6 End-to-End Certification

Canonical staging trace:

TEST LEAD -> Kong -> Middleware durable inbox -> Marketing attribution -> Odoo CRM -> n8n orchestration -> Communication DRY RUN -> Odoo outcome -> Marketing conversion feedback

Evidence required for a PASS:
- tenant_id continuity
- correlation_id continuity
- idempotency/replay protection
- durable inbox/outbox persistence
- retry and dead-letter behavior
- Odoo lead identity and attribution
- n8n Middleware-only effects
- Communication dry-run state
- zero provider writes
- complete trace/log evidence

## Stage 7 — Observability Hookup

Every service must emit or expose the following where applicable:
- Prometheus-compatible metrics
- OpenTelemetry traces
- structured logs suitable for Loki
- health/readiness endpoints
- correlation_id and tenant_id fields in operational telemetry without leaking secrets or prohibited PII

Collection and storage authority:
- Alloy: collection/routing
- Prometheus: metrics
- Loki: logs
- Tempo: distributed traces
- Grafana: operational dashboards
- Node Exporter: host metrics
- cAdvisor: container metrics
- Redis Exporter: Redis metrics
- Blackbox Exporter: external HTTP/TLS probes
- Superset: business analytics only; not operational alert authority
- OpenBao: secrets and runtime credential authority

Minimum dashboards:
1. Platform executive health
2. Kong edge/API
3. Keycloak identity
4. Middleware inbox/outbox/retry/dead-letter
5. Marketing acquisition and synchronization
6. Communication delivery/dry-run state
7. Social synchronization/publishing-disabled state
8. Odoo CRM integration
9. n8n workflow health
10. AI gateway usage/cost/error
11. PostgreSQL/Redis
12. Host/container capacity

Minimum alerts:
- service unavailable
- elevated HTTP 5xx
- latency SLO breach
- Middleware queue stalled
- dead-letter growth
- database unavailable
- Keycloak/Kong unavailable
- backup/restore validation failure
- provider reconciliation failure
- unexpected dangerous capability enabled

## Stage 8 — Production Read-Only Canary

Prerequisites:
- Stage 6 end-to-end staging PASS
- Stage 7 observability PASS
- rollback evidence PASS
- exact production artifacts and configuration identified by commit/image digest
- backups validated
- release/security approval recorded

Canary mode:
- deploy production artifacts with all dangerous capabilities OFF
- apply only approved identity/gateway configuration required for read-only health/auth checks
- verify runtime read-back against Git source
- verify TLS, authentication, authorization, service discovery, health, metrics, logs, traces, database connectivity, and rollback
- allow read-only/test probes and internal dry-run operations only

## Mandatory Kill Switch Baseline

LIVE_ADVERTISING_ENABLED=false
META_READ_SYNC_ENABLED=false unless explicitly enabled for approved read-only provider test/canary
EXTERNAL_MODEL_CALLS_ENABLED=false
EXTERNAL_DELIVERY_ENABLED=false
SOCIAL_READ_SYNC_ENABLED=false unless explicitly enabled for approved read-only provider test/canary
SOCIAL_PUBLISHING_ENABLED=false
PUBLISHING_KILL_SWITCH=true

## Production Activation Boundary

A successful Stage 8 read-only canary does not authorize write activation. Paid-media writes, external customer delivery, social publishing, and external AI provider calls are separate Stage 9 write-activation decisions with independent approval, limits, canaries, monitoring, and rollback.

## Exit State

The target state for this release authority is:
- STAGING_RUNTIME_READY=YES
- END_TO_END_STAGING_CERTIFIED=YES after deployed evidence exists
- OBSERVABILITY_HOOKUP_CERTIFIED=YES after telemetry/dashboards/alerts are verified
- PRODUCTION_READ_ONLY_CANARY_READY=YES after staging and observability evidence pass
- PRODUCTION_WRITE_ACTIVATION=NO
