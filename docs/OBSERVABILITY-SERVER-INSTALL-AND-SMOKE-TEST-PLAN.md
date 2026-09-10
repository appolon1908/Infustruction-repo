# Observability Server Install and Smoke-Test Plan

## Gate

Do not install or expose services on the server until repository authority, hostname ownership, branch structure, image/version pinning, network policy, secret handling and rollback plans are reviewed.

## Deployment order

### Phase A — foundational metrics
1. Node Exporter
2. cAdvisor
3. Redis Exporter
4. PostgreSQL Exporter only after its disabled runtime contract is promoted to an accepted immutable deployment
5. Blackbox Exporter
6. Prometheus
7. Alertmanager
8. Grafana

### Phase B — telemetry/logs/traces
9. OpenTelemetry Collector
10. Loki
11. Tempo
12. Grafana Alloy, with explicit ownership of collection paths to avoid duplicate ingestion

### Phase C — analytics and secrets
13. Superset
14. OpenBao — independently gated; do not treat it as an ordinary observability service

## Before each install

- use exact reviewed branch/SHA;
- pin image version/digest; never use `latest` for production;
- validate config from a clean checkout;
- secret scan repository/config artifacts;
- create dedicated service user/network/volume as appropriate;
- define persistent storage and backup need;
- define health/readiness endpoint;
- define resource limits;
- define private/public bind address;
- record rollback command and prior artifact identity.

## Smoke tests

### DNS/TLS
- derive the complete DNS inventory from every non-null `components[].hostname` in [the topology contract](../config/observability/topology.v1.json): currently 13 names, comprising three UI/management names and ten private-service denial names;
- verify all 13 names against the accepted `dnsTarget` (`37.27.128.39` in the current contract); missing, stale or unexpected DNS answers fail the rollout check;
- after the reviewed Caddy routes are enabled, validate certificate trust and hostname coverage for all 13 HTTPS names, including private-service denial routes;
- verify application access/authentication at `graf.codestra.media`, `supe.codestra.media`, and the restricted `bao.codestra.media`;
- for every name in [the firewall contract's `publicDnsButNoPublicProxy` list](../config/observability/firewall.v1.json), verify the deployed deny-only Caddy virtual host and its controlled public denial (`403` under the current network contract); a missing virtual host, TLS/connection failure, or response from a proxied native service is not successful denial evidence;
- exclude only PostgreSQL Exporter from public DNS/TLS and denial-host checks: its `hostname` is explicitly null and its private identity is `postgres-exporter:9187`; retain its private scrape and public native-port closure checks.

### Prometheus/exporters
- Prometheus config validation passes;
- every intended target is `UP` from the private monitoring path;
- unauthorized public access to Node/cAdvisor/DB exporters fails;
- recording and alert rule tests pass;
- storage/retention path is writable and capacity-reviewed.

### Alertmanager
- config validation passes;
- test alert flows from Prometheus to Alertmanager;
- grouping/inhibition/silence behavior matches policy;
- approved notification receiver receives a test alert without leaking secrets.

### Grafana
- protected HTTPS login works at `graf.codestra.media`;
- direct Grafana port is not internet-reachable;
- Prometheus/Loki/Tempo data sources connect with least privilege;
- dashboards load without broken data-source UIDs;
- authentication/logout/session behavior works;
- no default/admin bootstrap password remains.

### OpenTelemetry
- OTLP gRPC/HTTP works only from approved sources;
- processors/redaction rules work;
- bounded queue/retry behavior works;
- collector failure does not block application requests.

### Loki
- approved agents can push sanitized logs;
- Grafana can query them;
- prohibited secret-bearing fields are absent;
- retention/compaction works as designed;
- public ingestion/query is blocked.

### Tempo
- test trace reaches Tempo through the approved collector path;
- Grafana can query trace by ID;
- service/correlation relationships are visible;
- sensitive headers/bodies are not captured;
- public ingestion/query is blocked.

### Alloy
- only documented sources are collected;
- no duplicate metrics/logs/traces are produced against OTel collection;
- outbound destinations are restricted and healthy;
- admin/listener endpoints remain private.

### Superset
- protected HTTPS works at `supe.codestra.media`;
- direct service port is not public;
- only curated/read-only data sources are configured;
- RBAC prevents unauthorized datasets/dashboards;
- migrations/backup procedure is validated.

### Blackbox
- approved probes work;
- arbitrary caller-supplied target probing is impossible;
- Prometheus receives probe metrics;
- failures generate the intended test alert.

### OpenBao
OpenBao requires its own security acceptance before browser/API exposure:
- initialized/sealed/unsealed procedure documented and tested;
- root/bootstrap credentials handled offline/securely;
- policies/auth methods tested least privilege;
- audit device enabled as designed;
- backup/snapshot and restore tested;
- cluster/raft ports private;
- protected `bao.codestra.media` route tested only after these gates;
- secrets never appear in logs, metrics, traces or Git.

## Cross-stack smoke test

Generate a controlled synthetic application request with a correlation/trace ID. Verify:
1. application/host metrics appear in Prometheus;
2. sanitized logs appear in Loki;
3. trace appears in Tempo;
4. Grafana correlates/query access correctly;
5. a controlled failing probe/rule reaches Alertmanager;
6. Superset remains isolated to curated analytics data;
7. no private native service port is reachable externally.

## Evidence packet

For each deployed component record:
- repository;
- exact branch and SHA;
- image tag/digest;
- configuration checksum;
- hostname;
- bind/listen addresses;
- firewall evidence;
- health/smoke-test output;
- backup/restore evidence where stateful;
- rollback identity;
- approver and activation timestamp.

Server deployment is not considered complete until the combined evidence packet passes and no public/private exposure discrepancy remains.

## Latest runtime verification

See [the 10 September 2026 live verification](../reports/observability/20260910-runtime-verification.md).
Container liveness and Prometheus scrape success alone do not certify service
readiness, configured receiver credential mounts, webhook transport, log/trace
ingestion or authenticated dashboard access. The fourteen-component provider
release remains incomplete; this report records the separate core alert repair.
