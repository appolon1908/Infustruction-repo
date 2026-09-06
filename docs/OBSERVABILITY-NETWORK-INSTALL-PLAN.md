# Observability Network, Firewall, Install and Smoke-Test Plan

## Canonical DNS
All fourteen names resolve to `37.27.128.39`, TTL `600`: `graf`, `prom`, `aler`, `loki`, `temp`, `otel`, `supe`, `node`, `cadv`, `pgex`, `rdex`, `blac`, `allo`, `bao` under `codestra.media`.

## Exposure policy

### Browser-facing through Caddy only
- `graf.codestra.media`
- `supe.codestra.media`
- `bao.codestra.media` only with strong protection

### Private/allowlisted service endpoints
- `prom.codestra.media`
- `aler.codestra.media`
- `loki.codestra.media`
- `temp.codestra.media`
- `otel.codestra.media`
- `node.codestra.media`
- `cadv.codestra.media`
- `pgex.codestra.media`
- `rdex.codestra.media`
- `blac.codestra.media`
- `allo.codestra.media`

Public DNS is not permission to expose native service ports.

## Firewall policy
Default-deny inbound for native observability ports. Allow only explicit source networks/services required for scrape, ingestion, query, or administration. Prefer private/VLAN/container networks for east-west traffic. Public 443 terminates at Caddy for the three approved browser-facing hosts. Do not expose exporter ports, Prometheus, Alertmanager, Loki, Tempo, OTLP receivers, Alloy admin endpoints, or OpenBao backend/storage ports directly.

## Required network flows
- Prometheus -> Node Exporter, cAdvisor, PostgreSQL Exporter, Redis Exporter, Blackbox Exporter, and approved service metrics endpoints.
- Prometheus -> Alertmanager for alerts.
- Grafana -> Prometheus, Loki, Tempo and approved curated data sources.
- Apps/Alloy/OpenTelemetry -> Loki/Tempo/Prometheus-compatible ingestion according to approved design.
- Superset -> curated analytics/read databases using read-only/least-privilege credentials.
- Approved services -> OpenBao using least-privilege machine identities.

## Server install order
1. private networks/storage/volumes and service accounts
2. OpenBao only if required for secret injection; initialize/unseal using an approved secure ceremony and never commit bootstrap material
3. Node Exporter + cAdvisor + database/cache exporters
4. Prometheus
5. Alertmanager
6. Loki
7. Tempo
8. OpenTelemetry Collector
9. Grafana Alloy where needed
10. Grafana
11. Superset
12. Blackbox probes and final synthetic checks
13. Caddy routes for graf/supe/protected bao only

Pin image versions/digests. Secrets are injected externally. Do not use floating `latest` for production.

## Smoke tests
- DNS exact-name resolution -> `37.27.128.39`.
- Private native endpoints reachable only from approved sources and rejected from unapproved/public sources.
- Prometheus targets healthy; failed targets are explained, not hidden.
- Alertmanager accepts a controlled test alert and routes it to a test receiver without leaking secrets.
- Loki accepts/query retrieves a sanitized test log.
- Tempo accepts/query retrieves a synthetic trace.
- OTLP ingest works through the approved collector path.
- Node/cAdvisor/Postgres/Redis exporters expose expected non-sensitive metrics.
- Blackbox performs approved HTTPS/TLS probes.
- Grafana HTTPS/auth works and datasources are healthy.
- Superset HTTPS/auth works against curated read-only data.
- OpenBao HTTPS/auth works only when explicitly enabled; no root/recovery material is exposed.
- Caddy configuration validates before reload and rollback is prepared.

## Production gate
No server install is production-ready until exact repository SHA, image digest, configuration checksum, firewall evidence, TLS evidence, authentication evidence, smoke-test results, backup/restore requirements, and rollback instructions are recorded.
