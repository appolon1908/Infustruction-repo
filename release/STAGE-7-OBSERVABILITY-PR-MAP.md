# Stage 7 Observability Integration PR Map

These PRs prepare the Codestra marketing platform for staging observability. They are source-only and do not activate runtime monitoring by themselves.

| Authority | Repository | PR | Purpose |
|---|---|---:|---|
| Metrics | Codestra-Prometheus | #13 | platform metrics, safe dimensions, alerts |
| Dashboards | Codestra-Grafana- | #11 | operational dashboard catalog |
| Logs | Codestra-Loki | #12 | structured/redacted log contract |
| Traces | Codestra-Tempo | #12 | critical-path trace and sampling contract |
| Telemetry | Codestra-Telemetry | #14 | OTel resource identity, mTLS, redaction, durable queues |
| Collector | Codestra-Alloy | #12 | collection/routing to Prometheus/Loki/Tempo |
| Host metrics | Codestra-Node-Exporter | #16 | CPU/RAM/disk/network/load scope |
| Container metrics | Codestra-cAdvisor | #13 | container CPU/memory/network/fs/restarts scope |
| Redis metrics | Codestra-Redis-Exporter | #14 | Redis connection/memory/key/latency/replication scope |
| Synthetic probes | Codestra-Blackbox-Exporter | #13 | side-effect-free HTTPS/TLS/DNS/TCP probe catalog |
| Business analytics | Superset | #14 | read-only business KPI catalog |
| Secrets | Codestra-OpenBao | #14 | staging/read-only-canary secret classes and policy boundary |

## Runtime hookup order
1. OpenBao staging policy/secret injection.
2. Telemetry Collector mTLS and resource identity.
3. Alloy collection/routing.
4. Loki and Tempo backend connectivity.
5. Prometheus service/exporter scrapes and rules.
6. Node Exporter, cAdvisor, Redis Exporter target discovery.
7. Blackbox staging probes.
8. Grafana datasources and dashboards.
9. Superset curated read models/datasets.
10. Alert evaluation and incident routing validation.

## Exit evidence
- Every Stage 6 service is visible in metrics/logs/traces where applicable.
- Every staging host/container/cache dependency has infrastructure telemetry.
- Synthetic HTTP/TLS checks are side-effect-free and green.
- No secret appears in Git, labels, logs, traces, dashboards, or business BI.
- A dangerous-capability activation generates a critical alert.
- The full synthetic lead trace can be followed across Kong, Middleware, Marketing, Odoo, n8n, Communication dry-run, and conversion feedback.
