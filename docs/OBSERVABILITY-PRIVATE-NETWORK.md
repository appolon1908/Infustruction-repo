# Observability Private Network, Firewall, and Installation Runbook

## Current state

All 14 `codestra.media` DNS A records point to `37.27.128.39` with TTL 600. DNS completion does not expose or authenticate a service.

This branch defines desired state only. It does not apply firewall rules, start containers, issue certificates, or reload Caddy.

## Public edge

The observability change may add or manage only these Internet-facing ports:

```text
22/tcp   restricted administrative SSH
80/tcp   Caddy ACME and HTTPS redirect
443/tcp  Caddy HTTPS edge
```

This is not a complete host firewall inventory. The server is shared with the
approved mail service, so SMTP on TCP 25 remains outside this observability
policy and must be preserved. No observability change may flush or replace the
host firewall without a separately reviewed full-host inventory.

Browser-facing applications:

```text
graf.codestra.media  -> Caddy -> private Grafana listener
supe.codestra.media  -> Caddy -> private Superset listener
bao.codestra.media   -> Caddy source allowlist -> private OpenBao listener
```

The browser applications still enforce native Keycloak OIDC and their own authorization policies.

## Private-only services

```text
prom.codestra.media  Prometheus
aler.codestra.media  Alertmanager
loki.codestra.media  Loki
temp.codestra.media  Tempo
otel.codestra.media  OpenTelemetry Collector
node.codestra.media  Node Exporter
cadv.codestra.media  cAdvisor
pgex.codestra.media  PostgreSQL Exporter
rdex.codestra.media  Redis Exporter
blac.codestra.media  Blackbox Exporter
allo.codestra.media  Grafana Alloy
```

Their native ports must bind to loopback, the `10.40.0.0/24` private integration VLAN, or an environment-specific private Docker network. Public HTTPS requests to these DNS names are handled by Caddy with `403`; Caddy does not proxy the native services.

## Listener-authority blocker

The native listener values in this branch are reference values only. As of
2026-08-29, the dedicated service repositories do not contain accepted
deployment/listener definitions, so the actual ports and bind addresses are
not confirmed by accepted deployment source. The PostgreSQL Exporter repository
`appolon1908-hue/Codestra-Postgres-Exporter` was created on 2026-08-29 and its
runtime contract references internal port 9187 with no host publication, but
deployment and immutable-image activation remain disabled.

Every component therefore remains `pending-principal-repository-deployment-definition`,
including PostgreSQL Exporter. Server installation is prohibited until these
authority gaps are resolved and the topology contract is updated through review.

## Approved communication graph

```text
Caddy -> Grafana / Superset / OpenBao

Grafana -> Prometheus
Grafana -> Loki
Grafana -> Tempo

Prometheus -> Alertmanager
Prometheus -> Node Exporter
Prometheus -> cAdvisor
Prometheus -> PostgreSQL Exporter
Prometheus -> Redis Exporter
Prometheus -> Blackbox Exporter

Instrumented services -> OpenTelemetry Collector
OpenTelemetry Collector -> Tempo / Loki / Prometheus-compatible metrics
Alloy -> Loki / Tempo / OpenTelemetry Collector

Superset -> curated analytics read models only
Authorized applications -> OpenBao over private authenticated paths
```

No monitoring component becomes a cross-system write authority or an authoritative business database.

## Read-only preflight

Before installation, inventory the server without changing it:

```bash
ss -lntup
docker ps --format '{{.Names}} {{.Ports}}'
docker network ls
ufw status numbered || true
nft list ruleset || true
df -h
docker system df
```

Record:

- active listener/address/port ownership;
- existing container networks;
- conflicting ports;
- active Caddy source and checksum;
- firewall backend and current policy;
- available disk, memory, and CPU;
- backup/restore locations;
- exact repository SHAs and image digests.

The earlier server inventory reported severe filesystem pressure. Installation must stop if capacity is unsafe.

## Installation order

1. Prepare private Docker networks and externally injected secrets.
2. Install Node Exporter and cAdvisor with private listeners.
3. Install PostgreSQL, Redis, and Blackbox exporters with least-privilege credentials.
4. Install Prometheus and validate every scrape target.
5. Install Alertmanager and send a non-production test alert.
6. Install Loki and validate retention/storage.
7. Install Tempo and validate trace storage/query.
8. Install OpenTelemetry Collector and prove OTLP routing.
9. Install Alloy and prove log/metric/trace pipelines.
10. Install Grafana with provisioned private data sources and Keycloak OIDC.
11. Install Superset with curated read-only analytics sources and Keycloak OIDC.
12. Install OpenBao with its storage/seal design, Keycloak OIDC, policies, and Caddy source allowlist.
13. Validate Caddy configuration from the exact accepted Caddy SHA.
14. Apply firewall changes through a separately reviewed host-change plan.
15. Reload Caddy only after backup and validation.
16. Run external smoke and port-exposure tests.

Do not install all services in one unreviewed Compose change.

## Firewall application procedure

The JSON policy in `config/observability/firewall.v1.json` is authoritative intent, not an executable firewall script.

Before applying a host rule set:

1. export the current UFW/nftables rules;
2. preserve the current SSH session and establish a second recovery session;
3. confirm Caddy owns ports 80/443;
4. confirm native services bind privately before blocking ports;
5. generate a diff/plan;
6. independently review the plan;
7. apply one bounded change;
8. verify SSH, Caddy, private scrapes, and rollback access;
9. run an external port scan;
10. store before/after evidence and checksums.

A firewall command must never be generated from untrusted repository data and applied automatically.

## Caddy and TLS

Caddy source authority is `appolon1908-hue/Caddy`. The accepted edge branch must:

- proxy only `graf`, `supe`, and restricted `bao`;
- return controlled `403` for the eleven private hostnames;
- remove authorization/cookie values from access logs;
- validate successfully before reload;
- obtain certificates only through the reviewed edge configuration;
- leave native service ports private.

## Identity

Keycloak source authority is `appolon1908-hue/Keycloak`. The reviewed identity contract defines:

```text
grafana-observability
superset-analytics
openbao-secrets
```

The protected Keycloak plan/apply engine now covers these client definitions,
but live creation remains disabled. Realm-role provisioning, MFA enforcement,
application mappings, and all live secrets still require separate review and
runtime evidence.

## Validation commands

Repository validation:

```bash
python3 scripts/validate-observability-topology.py
bash -n scripts/smoke-observability-edge.sh
```

DNS preflight:

```bash
OBSERVABILITY_SMOKE_MODE=preflight \
  bash scripts/smoke-observability-edge.sh
```

Post-deployment test:

```bash
OBSERVABILITY_SMOKE_MODE=postdeploy \
  bash scripts/smoke-observability-edge.sh
```

The post-deployment mode validates TLS and authenticated/denied HTTPS behavior;
it does not claim that native ports were tested from outside the provider.

Run the external port test from a machine outside the server/private network:

```bash
OBSERVABILITY_SMOKE_MODE=external-port-scan \
  bash scripts/smoke-observability-edge.sh
```

## Exit criteria

The phase passes only when:

- exact repository SHAs are recorded;
- all desired-state validators pass;
- Grafana and Superset require valid OIDC access;
- OpenBao rejects unapproved source networks and enforces native policies;
- all eleven private hostnames return controlled public denial;
- native service ports are unreachable from the Internet;
- Grafana data sources work over private paths;
- Prometheus targets and Alertmanager are healthy;
- logs and traces reach Loki/Tempo through approved collectors;
- Superset uses curated read-only data;
- backups, rollback, retention, and capacity evidence are complete;
- no secret appears in Git or logs;
- explicit production approval is recorded.
