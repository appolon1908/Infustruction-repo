# Codestra Observability and Security Stack — Repository-First Build Program

## Decision

All observability, analytics, telemetry, exporter, identity, edge, and secrets work must be completed and validated in GitHub before any server deployment begins.

The existing DNS records may remain active, but DNS is not deployment authorization. Until the repository exit gate in this document passes, the following actions are prohibited:

- no SSH-driven installation on `37.27.128.39`;
- no container or systemd service start;
- no Caddy validation against the live filesystem, reload, or route cutover;
- no TLS certificate issuance as part of a service activation;
- no firewall or security-group mutation;
- no Keycloak client, role, mapper, or secret apply;
- no OpenBao initialization, unseal, policy apply, or secret write;
- no public exposure of native service ports;
- no production smoke traffic that depends on a newly deployed service.

## Canonical repository set

| Order | Capability | Principal repository | Canonical host | Exposure after deployment |
|---:|---|---|---|---|
| 1 | Grafana | `appolon1908-hue/Codestra-Grafana-` | `graf.codestra.media` | authenticated browser route through Caddy |
| 2 | Prometheus | `appolon1908-hue/Codestra-Prometheus` | `prom.codestra.media` | private; public host returns controlled denial |
| 3 | Alertmanager | `appolon1908-hue/Codestra-Alertmanager` | `aler.codestra.media` | private; public host returns controlled denial |
| 4 | Loki | `appolon1908-hue/Codestra-Loki` | `loki.codestra.media` | private; public host returns controlled denial |
| 5 | Tempo | `appolon1908-hue/Codestra-Tempo` | `temp.codestra.media` | private; public host returns controlled denial |
| 6 | OpenTelemetry Collector | `appolon1908-hue/Codestra-Telemetry` | `otel.codestra.media` | private; public host returns controlled denial |
| 7 | Superset | `appolon1908-hue/Superset` | `supe.codestra.media` | authenticated browser route through Caddy |
| 8 | Node Exporter | `appolon1908-hue/Codestra-Node-Exporter` | `node.codestra.media` | private; public host returns controlled denial |
| 9 | cAdvisor | `appolon1908-hue/Codestra-cAdvisor` | `cadv.codestra.media` | private; public host returns controlled denial |
| 10 | PostgreSQL Exporter | `appolon1908-hue/Codestra-Postgres-Exporter` | `pgex.codestra.media` | private; public host returns controlled denial |
| 11 | Redis Exporter | `appolon1908-hue/Codestra-Redis-Exporter` | `rdex.codestra.media` | private; public host returns controlled denial |
| 12 | Blackbox Exporter | `appolon1908-hue/Codestra-Blackbox-Exporter` | `blac.codestra.media` | private; public host returns controlled denial |
| 13 | Grafana Alloy | `appolon1908-hue/Codestra-Alloy` | `allo.codestra.media` | private; public host returns controlled denial |
| 14 | OpenBao | `appolon1908-hue/Codestra-OpenBao` | `bao.codestra.media` | source-restricted and authenticated browser route through Caddy |

Cross-cutting source authorities:

- `appolon1908-hue/Keycloak` — identity clients, roles, mappers, plan/apply/rollback and identity evidence;
- `appolon1908-hue/Caddy` — TLS edge, public host policy, controlled denial and private upstream handoff;
- `appolon1908-hue/Infustruction-repo` — topology, release dependency graph, firewall desired state, integration harness, deployment manifest, rollback and DR coordination;
- `appolon1908-hue/communication-platform-` — communications dashboard information model and approved business/operational read-model definitions.

## Permanent branch model

Every component repository must retain these persistent branches:

```text
main
  accepted release authority; immutable release tags originate here

development
  integration target for normal feature, fix, upgrade, security, and documentation work

test
  automated integration and destructive-test candidate

staging
  staging release-candidate source

production
  production release-candidate source; deployment still requires explicit approval
```

Temporary branch prefixes:

```text
feature/*
fix/*
upgrade/*
security/*
docs/*
test/*
release/*
hotfix/*
rollback/*
```

Canonical promotion path:

```text
feature|fix|upgrade|security|docs branch
  -> development
  -> test
  -> staging
  -> production
  -> main
  -> signed/annotated release tag and immutable release manifest
```

A merge does not deploy anything. Promotion changes source authority only.

## Global definition of repository-complete

A component repository is `REPOSITORY_COMPLETE` only when all applicable requirements below pass on an exact source SHA.

### Source and release identity

- upstream software version is explicitly selected and pinned;
- container images use an immutable version or digest, never `latest`;
- build inputs and generated configuration are reproducible from a clean checkout;
- repository identifies its canonical hostname and native listener;
- deployment remains disabled until the final release train is approved;
- release manifest records source SHA, upstream version, image digest, configuration checksum, and SBOM/provenance locations.

### Security

- no secret, token, password, private key, client secret, database URI with credentials, or unseal material is committed;
- secret scan passes;
- dependency/container/configuration security checks pass;
- native service listener is loopback or approved private-network only;
- anonymous or default administrative access is disabled where applicable;
- authentication and authorization fail closed;
- logs redact credentials, cookies, bearer tokens, and sensitive query values;
- least-privilege service identity and network dependencies are documented.

### Operability

- configuration validation runs in CI;
- health/readiness behavior is defined and tested;
- metrics/logging/tracing behavior is defined without collecting prohibited message bodies, credentials, payment data, or recordings;
- resource requests/limits or capacity assumptions are documented;
- retention, storage, backup, restore, and disaster-recovery requirements are implemented or explicitly marked not applicable;
- upgrade and downgrade paths are documented;
- rollback is executable from retained immutable artifacts;
- runbook covers startup, verification, failure diagnosis, and safe shutdown.

### Integration

- exact upstream and downstream relationships are machine-readable;
- ports and protocols are explicit;
- TLS/mTLS/OIDC/JWT or internal trust boundaries are explicit;
- provider/client compatibility tests exist where applicable;
- cross-repository contract tests can run without sending live email, SMS, calls, or production mutations;
- private-service public denial expectations are tested;
- all dashboards, rules, alerts, probes, pipelines, and datasource definitions are version-controlled.

### Governance

- required persistent branches exist;
- protected-branch desired state is documented and, where supported, managed through reviewed source;
- pull requests require exact-head CI and resolved review threads;
- CODEOWNERS or equivalent ownership is present;
- `SECURITY.md`, contribution guidance, and release evidence templates exist;
- no feature branch may directly activate production.

## Repository build sequence

The sequence below is a source dependency order. Multiple independent repositories may be developed in parallel, but a downstream repository cannot be declared complete before its upstream contracts are stable.

## Phase R0 — Governance and shared contracts

Principal branch in `Infustruction-repo`:

```text
feature/observability-repository-release-train-v1
```

Required outputs:

- canonical 14-repository registry;
- branch and protection matrix;
- canonical host/port/exposure registry;
- machine-readable dependency graph;
- standard release evidence schema;
- standard rollback evidence schema;
- standard immutable-image policy;
- prohibited-secret and prohibited-PII logging policy;
- cross-repository version matrix;
- deployment-disabled assertion for every repo;
- local/sandbox integration harness design.

Exit gate: every repository has an assigned build branch and an accountable source authority.

## Phase R1 — Exporter foundation

### Node Exporter

Repository: `Codestra-Node-Exporter`

Build branch:

```text
feature/node-exporter-runtime-v1
```

Required source:

- pinned Node Exporter version/image digest;
- private listener and approved collectors;
- filesystem/process exclusions;
- no public native port;
- health/scrape tests;
- systemd and/or container deployment template without activation;
- upgrade and rollback runbook;
- CI validation and secret scan.

### cAdvisor

Repository: `Codestra-cAdvisor`

Build branch:

```text
feature/cadvisor-runtime-v1
```

Required source:

- pinned cAdvisor version/image digest;
- minimal read-only host/container mounts;
- disabled privileged capabilities unless technically unavoidable and documented;
- private listener;
- scrape and container-metric tests;
- cardinality and retention guidance;
- upgrade and rollback runbook;
- CI validation and secret scan.

### PostgreSQL Exporter

Repository: `Codestra-Postgres-Exporter`

Build branch:

```text
feature/postgres-exporter-runtime-v1
```

Required source:

- repository accessibility/name confirmed;
- pinned exporter version/image digest;
- least-privilege monitoring role SQL;
- external secret reference for DSN;
- query allowlist/custom-query policy;
- private listener;
- no business row contents in metrics;
- connection, permission-denial, and scrape tests;
- upgrade and rollback runbook;
- CI validation and secret scan.

### Redis Exporter

Repository: `Codestra-Redis-Exporter`

Build branch:

```text
feature/redis-exporter-runtime-v1
```

Required source:

- pinned exporter version/image digest;
- external credential reference;
- private listener;
- approved Redis targets and TLS policy;
- no key/value contents in metrics;
- connection, auth-denial, and scrape tests;
- upgrade and rollback runbook;
- CI validation and secret scan.

### Blackbox Exporter

Repository: `Codestra-Blackbox-Exporter`

Build branch:

```text
feature/blackbox-probes-v1
```

Required source:

- pinned exporter version/image digest;
- HTTP/HTTPS/TCP/DNS probe modules;
- certificate-expiry, redirect, hostname, and status-code assertions;
- private listener;
- target allowlist and SSRF protections;
- no unrestricted user-supplied probe targets;
- probe unit tests and CI validation;
- upgrade and rollback runbook.

Phase R1 exit gate: all exporters build and validate without a server, expose no public native listener in their desired state, and publish a stable scrape contract for Prometheus.

## Phase R2 — Metrics and alert control plane

### Prometheus

Repository: `Codestra-Prometheus`

Build branch:

```text
feature/metrics-control-plane-v1
```

Required source:

- pinned Prometheus version/image digest;
- canonical scrape jobs for every approved service/exporter;
- TLS/auth credentials referenced externally;
- service discovery strategy;
- recording rules and SLO metric conventions;
- rule unit tests;
- `promtool` validation;
- private listener;
- storage retention, capacity, backup/restore and WAL recovery policy;
- remote-write policy, disabled unless explicitly approved;
- Alertmanager target contract;
- upgrade/downgrade and rollback runbook.

### Alertmanager

Repository: `Codestra-Alertmanager`

Build branch:

```text
feature/central-alert-routing-v1
```

Required source:

- pinned Alertmanager version/image digest;
- route tree by environment, severity, service, tenant-safe context, and ownership;
- grouping, inhibition, repeat intervals, silence policy and maintenance handling;
- receiver credentials referenced externally;
- notification templates with secret/PII redaction;
- private listener;
- routing and inhibition tests;
- HA/cluster decision;
- backup/restore for silences where required;
- upgrade/downgrade and rollback runbook.

Phase R2 exit gate: Prometheus and Alertmanager configurations validate together in the repository integration harness, including positive alerts, inhibited alerts, receiver failure, and retry behavior.

## Phase R3 — Logs, traces, and telemetry pipelines

### Loki

Repository: `Codestra-Loki`

Build branch:

```text
feature/log-control-plane-v1
```

Required source:

- pinned Loki version/image digest;
- storage/schema/index design;
- retention and deletion policy;
- private listener and tenant/auth boundary;
- ingestion limits and cardinality controls;
- explicit prohibited log fields;
- backup/restore and corruption recovery where stateful;
- query/readiness tests;
- upgrade migration and rollback plan.

### Tempo

Repository: `Codestra-Tempo`

Build branch:

```text
feature/trace-control-plane-v1
```

Required source:

- pinned Tempo version/image digest;
- OTLP receiver contract through approved private paths;
- storage, retention, compaction and capacity design;
- private listener;
- trace-to-log and trace-to-metric correlation contracts;
- secret-bearing attribute redaction policy;
- ingestion/query/readiness tests;
- upgrade migration and rollback plan.

### OpenTelemetry Collector

Repository: `Codestra-Telemetry`

Build branch:

```text
feature/telemetry-pipelines-v1
```

Required source:

- pinned Collector distribution/version/image digest;
- explicit receivers, processors, exporters and connectors;
- memory limiter, batching, retries, queueing, backpressure and health extensions;
- attribute allowlist/redaction processors;
- separate development/test/staging/production configurations;
- private OTLP gRPC/HTTP listeners;
- failover and exporter-outage tests;
- configuration linting and synthetic telemetry tests;
- upgrade and rollback runbook.

### Grafana Alloy

Repository: `Codestra-Alloy`

Build branch:

```text
feature/alloy-collection-pipelines-v1
```

Required source:

- pinned Alloy version/image digest;
- file/container/system log discovery;
- metrics and trace collection where justified;
- positions/state persistence design;
- private diagnostics listener;
- labels/cardinality/redaction rules;
- no duplicate collection with the Collector unless ownership is explicit;
- output outage/backpressure/restart tests;
- upgrade and rollback runbook.

Phase R3 exit gate: a synthetic trace, log record, and metric can traverse the repository-only integration harness with correlation IDs and without prohibited secrets or PII.

## Phase R4 — Visualization and analytics

### Grafana

Repository: `Codestra-Grafana-`

Existing foundation branch:

```text
feature/private-bind-keycloak-oidc-v1
```

Next build branch after foundation acceptance:

```text
feature/provisioned-dashboards-alert-views-v1
```

Required source:

- pinned Grafana version/image digest;
- loopback/private listener;
- Keycloak OIDC and exact role mapping;
- anonymous and local password login disabled or break-glass only under a documented procedure;
- provisioned Prometheus, Loki and Tempo datasources using external credentials;
- version-controlled folders, dashboards, contact-point views and correlations;
- dashboards for infrastructure, API edge, identity, middleware, email, SMS, voice, databases, queues, webhooks and reconciliation;
- datasource and dashboard tests;
- plugin allowlist and pinned plugin versions;
- backup/restore of material Grafana state;
- upgrade and rollback runbook.

### Superset

Repository: `Superset`

Existing foundation branch:

```text
feature/private-bind-keycloak-oidc-v1
```

Next build branch after foundation acceptance:

```text
feature/communications-analytics-models-v1
```

Required source:

- pinned Superset version/image digest;
- loopback/private listener;
- Keycloak OIDC, role mapping, secure cookies, CSRF and proxy awareness;
- metadata database migrations and backup/restore;
- curated read-model-only database contracts;
- row-level security and tenant-safe datasets;
- version-controlled dataset/chart/dashboard exports;
- no provider administration database or write credentials;
- query timeout/resource controls;
- analytics validation fixtures;
- upgrade and rollback runbook.

Phase R4 exit gate: Grafana and Superset can be built and tested entirely against synthetic/local data and the approved Keycloak contract without any public route or live client apply.

## Phase R5 — Secrets authority

### OpenBao

Repository: `Codestra-OpenBao`

Existing foundation branch:

```text
feature/private-bind-keycloak-oidc-v1
```

Required next branch:

```text
feature/storage-seal-ha-dr-v1
```

Required source before OpenBao may be called repository-complete:

- pinned OpenBao version/image digest;
- explicit storage backend and HA design;
- seal/unseal or auto-unseal architecture;
- initialization ceremony and custody model;
- recovery key and break-glass procedure;
- audit device configuration and audit-log protection;
- Keycloak OIDC roles and narrow policies;
- machine auth methods and per-application namespaces/paths;
- rotation/revocation workflows;
- backup/restore and full disaster-recovery rehearsal procedure;
- snapshot integrity validation;
- policy unit tests and deny tests;
- no root/default broad policy for normal users;
- upgrade migration, downgrade limitations and rollback plan;
- explicit `deployment_enabled=false` until a separate production authorization.

Phase R5 exit gate: storage, seal, policy, audit, backup/restore and recovery are all source-defined and validated with an ephemeral, disposable test cluster. No real secrets or production initialization are used.

## Phase R6 — Identity and edge completion

### Keycloak

Repository: `Keycloak`

Required implementation branch:

```text
feature/observability-managed-clients-v1
```

This branch implements issue #30 and must include:

- managed desired-state client overlays for Grafana, Superset and OpenBao;
- client export allowlists;
- managed and creatable policy updates;
- realm-role desired state for observability and secrets roles;
- client/role plan, independent review, apply and rollback support;
- deterministic before/desired hashes;
- absence and optimistic-concurrency checks;
- secret-safe create/update behavior;
- exact callback, origin, audience, grant and PKCE validation;
- role-isolation and MFA policy tests;
- staging login/denial evidence procedure;
- no live apply from the feature branch.

### Caddy

Repository: `Caddy`

Existing source branch:

```text
feature/observability-edge-routing-v1
```

Required completion work:

- renderable Caddy sites for the three approved browser-facing services;
- controlled denial for the eleven private hostnames;
- private upstream health behavior;
- exact security headers and log redaction;
- OpenBao source-network restrictions;
- configuration formatting and validation tests;
- certificate and upstream failure test cases in a disposable harness;
- rollback rendering and checksum evidence;
- no live reload.

Phase R6 exit gate: identity and edge source validate against Grafana, Superset and OpenBao configuration in the repository integration harness. No live clients, certificates or routes are activated.

## Phase R7 — Cross-repository integration laboratory

Principal repository:

```text
appolon1908-hue/Infustruction-repo
```

Branch:

```text
feature/observability-integration-lab-v1
```

Required outputs:

- version-pinned disposable Compose or equivalent test topology;
- synthetic secrets only;
- isolated bridge networks matching the approved dependency graph;
- no host publication for private native ports;
- test-only TLS/identity strategy;
- configuration validation for all 14 repositories;
- exporter-to-Prometheus tests;
- Prometheus-to-Alertmanager tests;
- Alloy/Collector-to-Loki/Tempo/Prometheus tests;
- Grafana datasource and dashboard provisioning tests;
- Superset metadata migration and curated dataset tests;
- Keycloak client/role plan tests without live production apply;
- Caddy public-route and private-denial tests;
- OpenBao ephemeral storage/policy/OIDC deny tests;
- restart, dependency outage, retry, backpressure and recovery tests;
- no live email, SMS, voice, provider, CRM, payment or production database effects.

Phase R7 exit gate: one command or workflow produces an exact-SHA integration report covering all participating repositories.

## Phase R8 — Upgrade, rollback, and disaster-recovery certification

Each repository receives an `upgrade/<component>-<target-version>` rehearsal branch or equivalent fixture proving:

- current version to target version compatibility;
- configuration migration;
- data migration where stateful;
- dashboard/rule/schema/plugin compatibility;
- downgrade limitations;
- rollback to retained immutable artifact;
- backup restoration;
- documented recovery time and recovery point assumptions;
- exact test evidence.

OpenBao, Prometheus, Loki, Tempo, Grafana metadata, Superset metadata, and any stateful Alertmanager design require explicit restore evidence.

## Phase R9 — Repository release freeze

For every principal repository:

1. all component PRs are accepted through the persistent branch promotion path;
2. exact-head and merge-result CI pass;
3. release candidate is tagged from accepted `main`;
4. immutable image is built and scanned without deployment;
5. image digest, SBOM and provenance are recorded;
6. configuration checksum is recorded;
7. integration-lab report references the exact release SHA/digest;
8. deployment remains disabled.

The infrastructure authority then creates one cross-repository release manifest containing all 14 source SHAs, release tags, image digests, configuration checksums, dependencies, upgrade order and rollback order.

## Repository exit gate before deployment planning

Deployment planning may begin only when all statements below are true:

```text
ALL_14_REPOSITORIES_RESOLVED=YES
ALL_PERSISTENT_BRANCHES_PRESENT=YES
ALL_COMPONENT_SOURCE_COMPLETE=YES
ALL_IMAGES_VERSION_PINNED=YES
ALL_COMPONENT_CI_GREEN_ON_EXACT_HEADS=YES
ALL_SECURITY_SCANS_PASS=YES
ALL_INTEGRATION_CONTRACTS_PASS=YES
ALL_PRIVATE_BIND_POLICIES_PASS=YES
ALL_OIDC_AND_ROLE_CONTRACTS_PASS=YES
OPENBAO_SOURCE_DESIGN_CERTIFIED=YES
BACKUP_RESTORE_AND_ROLLBACK_EVIDENCE_COMPLETE=YES
CROSS_REPOSITORY_INTEGRATION_LAB_PASS=YES
RELEASE_MANIFEST_COMPLETE=YES
DEPLOYMENT_ENABLED=NO
```

Only after this exit gate passes should a separate deployment program begin with read-only server inventory, capacity validation, backup capture, installation, protected identity apply, firewall changes, Caddy reload, TLS verification, external smoke tests, and production approval.

## Immediate work queue

1. Complete Keycloak issue #30 on `feature/observability-managed-clients-v1`.
2. Confirm the exact PostgreSQL Exporter repository identity and access.
3. Create or validate the R0 governance/release-train branch and registry.
4. Complete exporter repositories R1.
5. Complete Prometheus and Alertmanager R2.
6. Complete Loki, Tempo, Collector and Alloy R3.
7. Complete Grafana and Superset product source R4.
8. Complete OpenBao storage/seal/HA/DR/policy source R5.
9. Finalize Keycloak and Caddy R6.
10. Build and pass the disposable integration laboratory R7.
11. Certify upgrades/rollback/restore R8.
12. Freeze exact releases and the cross-repository manifest R9.
13. Keep all server deployment actions blocked until a new explicit deployment authorization.