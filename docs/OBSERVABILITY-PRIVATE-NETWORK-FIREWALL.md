# Observability Private-Network and Firewall Plan

## Principle

DNS records for internal observability hosts may resolve publicly to `37.27.128.39`, but DNS resolution must not make the underlying service ports public. Public exposure is controlled separately at Caddy/firewall/network layers.

## Browser-facing HTTPS only

The only standard browser-facing hosts are:
- `graf.codestra.media`
- `supe.codestra.media`
- `bao.codestra.media` only after additional access hardening

These use Caddy on 443. Their upstream service ports remain loopback/private.

## Private-only services

The following hosts/services must remain reachable only from approved local/private networks or specific monitoring peers:
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

## Network rules by relationship

### Prometheus
Allow outbound/scrape access from Prometheus to approved metrics targets only. Allow Prometheus UI/API only from loopback/private operator networks or an explicitly protected internal route. Deny public access to the native Prometheus port.

### Alertmanager
Allow Prometheus -> Alertmanager. Allow Alertmanager outbound only to approved receivers. Deny public native-port access.

### Loki
Allow ingestion only from approved Alloy/OpenTelemetry/private agents. Allow query access from Grafana and approved operators. Deny public API access.

### Tempo
Allow trace ingestion only from approved OpenTelemetry/Alloy sources. Allow query access from Grafana. Deny public API access.

### OpenTelemetry Collector
Allow OTLP/listener traffic only from approved applications, agents and private subnets. Restrict admin/health/pprof/zPages endpoints to loopback/private networks. Deny public OTLP unless a separately approved mTLS edge is designed.

### Exporters
Node Exporter, cAdvisor, PostgreSQL Exporter and Redis Exporter must accept scrapes only from the Prometheus host/private monitoring subnet. They must not listen on unrestricted public interfaces unless host firewall rules strictly restrict access.

### Blackbox Exporter
Allow requests from Prometheus only. Probe targets/modules must be allowlisted. Never expose Blackbox as a public arbitrary URL-fetch endpoint.

### Alloy
Restrict administrative/listener interfaces to private networks. Permit outbound connections only to approved telemetry backends. Where Alloy receives telemetry, restrict sources to approved networks/workloads.

### OpenBao
Native listener is private. If `bao.codestra.media` is enabled, only Caddy reaches the upstream listener. Restrict OpenBao cluster/raft ports to cluster peers/private network. Root/bootstrap/seal operations require operator-controlled paths and must not be generally internet-accessible.

## Host firewall model

Default posture for the observability host:
1. deny inbound by default;
2. allow established/related traffic;
3. allow SSH only from approved administration sources;
4. allow 80/443 to Caddy as required for public browser routes/TLS;
5. allow native observability ports only from loopback, Docker/private bridge, Hetzner private network, or explicit monitoring source IPs;
6. never open exporter/Prometheus/Loki/Tempo/OTel/Alloy ports to `0.0.0.0/0` at the firewall;
7. document every exception with source, destination, port, purpose and owner.

## Docker/container policy

Prefer binding private services to `127.0.0.1` or a private Docker/network interface rather than publishing native ports on the public interface. A container port published by Docker must still be covered by host firewall/network policy and verified externally.

## Verification gates

Before production:
- external scan confirms only approved public ports/hosts are reachable;
- private monitoring sources can reach required native ports;
- unauthorized public probes fail closed;
- Grafana/Superset/OpenBao upstream ports are unreachable directly from the internet;
- Prometheus can scrape all approved targets;
- Loki/Tempo/OTel reject unauthorized ingress;
- Blackbox cannot probe arbitrary caller-supplied destinations;
- no secrets appear in network diagnostics/logging evidence.
