# Observability Integration Wiring

## Canonical data flow

```text
Hosts / Containers / Applications
  |       |          |
  |       |          +--> OpenTelemetry SDKs / OTLP
  |       +-------------> cAdvisor
  +---------------------> Node Exporter

Redis ------------------> Redis Exporter
PostgreSQL -------------> PostgreSQL Exporter (deployment approval pending)
Approved endpoints ------> Blackbox Exporter

Alloy / OpenTelemetry Collector
  |            |             |
  |            |             +--> Tempo (traces)
  |            +----------------> Loki (logs)
  +-----------------------------> Prometheus-compatible metrics path

Node/cAdvisor/DB/Blackbox exporters ---> Prometheus
Prometheus alerts --------------------> Alertmanager

Prometheus ----+
Loki ----------+----> Grafana
Tempo ---------+

Curated analytics/read models --------> Superset

OpenBao ---> approved applications/operators for secrets/PKI/dynamic credentials
OpenBao ---> observability stack only for non-secret health/metrics
```

## Exact relationships

### Grafana (`graf.codestra.media`)
Reads from Prometheus, Loki and Tempo. May read approved health/analytics sources using least-privilege credentials. It does not write to provider/application systems and must not store unrestricted infrastructure credentials.

### Prometheus (`prom.codestra.media`)
Scrapes Node Exporter, cAdvisor, Redis Exporter, PostgreSQL Exporter, Blackbox Exporter, and approved application `/metrics` endpoints. Sends firing/resolved alerts to Alertmanager.

### Alertmanager (`aler.codestra.media`)
Receives alerts from Prometheus. Routes/group/inhibits to approved notification receivers. It is not a metrics store and does not own Prometheus rules.

### Loki (`loki.codestra.media`)
Receives sanitized logs from Alloy and/or OpenTelemetry Collector. Grafana is the primary query UI. High-cardinality and secret-bearing fields are prohibited.

### Tempo (`temp.codestra.media`)
Receives traces from OpenTelemetry Collector and/or approved Alloy trace pipelines. Grafana is the primary trace query UI. Authorization headers, tokens, message bodies, credentials and other sensitive raw payloads must be redacted before export.

### OpenTelemetry Collector (`otel.codestra.media`)
Receives OTLP/approved telemetry from applications and infrastructure. Applies batching, sampling, redaction and routing. Exports traces to Tempo, logs to Loki-approved paths, and metrics to the approved Prometheus-compatible destination.

### Alloy (`allo.codestra.media`)
Agent/collector for hosts and services where appropriate. Discovers and collects logs/metrics/traces, applies relabeling/redaction, then forwards to approved Loki, Tempo, and OpenTelemetry Collector destinations. Avoid duplicate collection with OpenTelemetry Collector; every signal/source must have one documented primary collection path.

### Superset (`supe.codestra.media`)
Reads curated analytics/read models only. It must not directly query operational provider administration databases when a curated read model is available. Credentials are read-only and least privilege.

### Node Exporter (`node.codestra.media`)
Exports host metrics to Prometheus only.

### cAdvisor (`cadv.codestra.media`)
Exports container/runtime metrics to Prometheus only.

### PostgreSQL Exporter (`pgex.codestra.media`)
Exports PostgreSQL metrics to Prometheus using monitoring-only credentials. Its repository exists and declares no host-published native port, but deployment remains blocked until an immutable image, credentials, private networks, and scrape evidence pass review.

### Redis Exporter (`rdex.codestra.media`)
Exports Redis metrics to Prometheus using monitoring-only credentials.

### Blackbox Exporter (`blac.codestra.media`)
Runs approved synthetic probes. Prometheus scrapes probe results. Targets and probe modules must be allowlisted and must not create an SSRF-style arbitrary probe service.

### OpenBao (`bao.codestra.media`)
Provides secrets/PKI/dynamic credentials to approved workloads and operators. Observability integrations may read only non-secret health/metrics. Grafana, Prometheus, Alloy, Loki, Tempo and Superset must never receive secret values through labels/logs/traces.

## Correlation standard

Where supported, propagate `trace_id`, `span_id`, `correlation_id`, `service`, and `environment`. Tenant identifiers may be used only where policy permits and cardinality is controlled. Never use credentials, access tokens, email/message bodies, phone numbers, payment data, or secret values as metric labels.

## Failure isolation

Loss of Grafana/Superset must not stop application runtime. Loss of Loki/Tempo must not stop business requests. Telemetry exporters must use bounded queues/timeouts and fail without blocking critical paths. Prometheus/Alertmanager failures must not trigger automated application mutation unless separately governed.
