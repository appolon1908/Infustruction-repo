# Stage 6-8 Evidence Checklist

## Stage 6 — Staging Runtime
- [ ] All service images/manifests identify exact reviewed main commits and immutable image digests.
- [ ] Staging PostgreSQL/Redis dependencies are provisioned and reachable only through approved network paths.
- [ ] One-shot database migrations pass for Marketing, AI, Communication, Social, Middleware, social runtime, and Odoo addon install/upgrade.
- [ ] Keycloak staging CHECK/APPLY/read-back passes.
- [ ] Kong staging validation/APPLY/read-back passes.
- [ ] n8n workflow designs import with verified endpoint and credential bindings and remain inactive until dry-run approval.
- [ ] Odoo marketing CRM addon installs/upgrades and campaign/tenant isolation tests pass.
- [ ] Meta/social provider connections are test/read-only only.

## End-to-End Staging
- [ ] Synthetic test lead enters through Kong.
- [ ] Middleware inbox persists and deduplicates it.
- [ ] Marketing attribution is created with the correct tenant/campaign identity.
- [ ] Odoo lead is created/upserted once with attribution intact.
- [ ] n8n receives only the canonical Middleware command/event path.
- [ ] Communication records a DRY RUN with no provider delivery.
- [ ] Odoo outcome is recorded.
- [ ] Conversion feedback reaches Marketing through Middleware.
- [ ] correlation_id is continuous across the trace.
- [ ] tenant_id is continuous across the trace.
- [ ] replaying the same event does not duplicate business effects.
- [ ] retry/dead-letter paths are exercised.
- [ ] zero external writes are proven.

## Stage 7 — Observability
- [ ] Prometheus scrapes every required service/exporter.
- [ ] Loki receives structured service logs.
- [ ] Tempo receives distributed traces.
- [ ] Alloy collection/routing is healthy.
- [ ] Grafana dashboards exist for platform, edge, identity, Middleware, Marketing, Communication, Social, Odoo, n8n, AI, databases, hosts, and containers.
- [ ] Node Exporter host metrics are present.
- [ ] cAdvisor container metrics are present.
- [ ] Redis Exporter metrics are present.
- [ ] Blackbox probes cover public/staging HTTPS and TLS endpoints.
- [ ] Superset business dashboards read curated business data without becoming an operational control plane.
- [ ] OpenBao supplies runtime secrets without Git-stored secrets.
- [ ] Alerts exist for availability, 5xx, latency, queue stall, dead-letter growth, database failure, identity/gateway failure, backup failure, reconciliation failure, and dangerous capability activation.

## Stage 8 — Production Read-Only Canary
- [ ] Exact production artifacts/digests are recorded.
- [ ] Production backup/restore readiness passes.
- [ ] Production deployment uses the fail-closed kill-switch baseline, including META_READ_SYNC_ENABLED=false and SOCIAL_READ_SYNC_ENABLED=false unless separately approved for a bounded read-only test.
- [ ] Keycloak and Kong runtime state read back to the expected Git configuration.
- [ ] TLS/auth/authz/health/service-discovery checks pass.
- [ ] Metrics/logs/traces appear for the canary.
- [ ] Read-only/internal dry-run tests pass.
- [ ] Rollback is demonstrated.
- [ ] Release approval is recorded.
- [ ] Security approval is recorded.
- [ ] No advertising spend occurs.
- [ ] No external customer messages are delivered.
- [ ] No social publishing occurs.
- [ ] No external AI provider call occurs unless separately authorized for a read-only/non-effect test.

## Final State
- [ ] STAGING_RUNTIME_READY=YES
- [ ] END_TO_END_STAGING_CERTIFIED=YES
- [ ] OBSERVABILITY_HOOKUP_CERTIFIED=YES
- [ ] PRODUCTION_READ_ONLY_CANARY_READY=YES
- [ ] PRODUCTION_WRITE_ACTIVATION=NO
