# Codestra Media Observability Host and Repository Map

## DNS authority

All 14 DNS records resolve to `37.27.128.39` with TTL `600` and were externally verified after the 2026-08-29 GoDaddy change.

| Host | Component | Principal repository | Exposure |
|---|---|---|---|
| `graf.codestra.media` | Grafana OSS | `appolon1908-hue/Codestra-Grafana-` | authenticated browser HTTPS only |
| `prom.codestra.media` | Prometheus | `appolon1908-hue/Codestra-Prometheus` | private/internal |
| `aler.codestra.media` | Alertmanager | `appolon1908-hue/Codestra-Alertmanager` | private/internal |
| `loki.codestra.media` | Loki | `appolon1908-hue/Codestra-Loki` | private/internal |
| `temp.codestra.media` | Tempo | `appolon1908-hue/Codestra-Tempo` | private/internal |
| `otel.codestra.media` | OpenTelemetry Collector | `appolon1908-hue/Codestra-Telemetry` | private/internal |
| `supe.codestra.media` | Apache Superset | `appolon1908-hue/Superset` | authenticated browser HTTPS only |
| `node.codestra.media` | Node Exporter | `appolon1908-hue/Codestra-Node-Exporter` | private/internal |
| `cadv.codestra.media` | cAdvisor | `appolon1908-hue/Codestra-cAdvisor` | private/internal |
| `pgex.codestra.media` | PostgreSQL Exporter | `appolon1908-hue/Codestra-Postgres-Exporter` | private/internal; deployment remains disabled pending review |
| `rdex.codestra.media` | Redis Exporter | `appolon1908-hue/Codestra-Redis-Exporter` | private/internal |
| `blac.codestra.media` | Blackbox Exporter | `appolon1908-hue/Codestra-Blackbox-Exporter` | private/internal |
| `allo.codestra.media` | Grafana Alloy | `appolon1908-hue/Codestra-Alloy` | private/internal |
| `bao.codestra.media` | OpenBao | `appolon1908-hue/Codestra-OpenBao` | protected browser/API HTTPS; direct port private |

## Naming rule

The four-character labels above are the only canonical `codestra.media` service hostnames for this stack. Do not introduce alternate public names in configuration, Caddy, dashboards, OAuth callbacks, service discovery, runbooks, or smoke tests without an explicit architecture change.

## Repository authority rule

Each principal repository owns component-specific source/configuration and its upgrade lifecycle. `Infustruction-repo` owns cross-stack topology, network/storage/backup/DR patterns, combined rollout evidence, and this ownership map. It must not become a duplicate source for component configs.

## Branch model

Every component repo must retain persistent branches:

- `main`
- `development`
- `test`
- `staging`
- `production`

Allowed temporary work branches include `feature/*`, `fix/*`, `upgrade/*`, `security/*`, `docs/*`, `hotfix/*`, optional `release/*`, and `rollback/*`.

Normal promotion is `work -> development -> test -> staging -> production -> main` with CI/evidence at every promotion.
