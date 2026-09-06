# Observability and Dashboard Infrastructure Coordination

## Purpose

This infrastructure repository coordinates the shared topology, environment placement, networking, storage conventions, backup/restore/DR policy and combined deployment evidence for the Codestra observability stack.

It is **not** the principal configuration repository for observability components that now have dedicated GitHub repositories. Application-specific instrumentation stays in each principal application repository.

## Dedicated principal repositories

| Component | Principal repository | Owns |
|---|---|---|
| Grafana OSS | `appolon1908-hue/Codestra-Grafana-` | Grafana runtime/configuration, provisioning, dashboards, folders, data-source declarations, Grafana tests and release evidence |
| Prometheus | `appolon1908-hue/Codestra-Prometheus` | Prometheus runtime/configuration, scrape rules, recording/alert rules, retention policy, tests and release evidence |
| Alertmanager | `appolon1908-hue/Codestra-Alertmanager` | Alertmanager runtime/configuration, routes, inhibition, grouping and non-secret receiver policy |
| Loki | `appolon1908-hue/Codestra-Loki` | Loki runtime/configuration, ingestion/storage/retention/tenancy policy |
| OpenTelemetry | `appolon1908-hue/Codestra-Telemetry` | OpenTelemetry Collector pipelines and cross-service telemetry propagation conventions |
| Tempo | `appolon1908-hue/Codestra-Tempo` | Tempo runtime/configuration, trace ingestion/storage/retention/query policy |

If additional shared software such as Superset receives a dedicated repository later, authority automatically moves to that dedicated repository under the same rule.

## What Infustruction-repo owns

- development/test/staging/production topology diagrams;
- host/network placement and private/public ingress expectations;
- shared volume/storage placement conventions;
- resource budgets and capacity planning across the observability estate;
- backup/restore/DR coordination across components;
- cross-component dependency map;
- secret-injection conventions without secret values;
- combined deployment/release evidence template;
- environment naming and shared operational runbooks;
- integration expectations between component repositories.

## What Infustruction-repo must not own

Do not duplicate canonical `grafana.ini`, dashboard/provisioning source, `prometheus.yml`, alert rules, Alertmanager routes, Loki configuration, Tempo configuration or OpenTelemetry Collector pipeline configuration when those files belong to their dedicated repository.

Cross-stack deployment templates may reference immutable artifacts/config packages produced by the dedicated repos, but must not silently fork or override them.

## Environment model

Maintain separate configuration and data boundaries for:
- development
- test
- staging
- production

Production and staging should not share persistent telemetry stores when avoidable. Secrets and credentials must be injected externally and never committed.

## Network policy

- Grafana and future BI/admin interfaces should be behind authenticated ingress.
- Prometheus, Loki, Tempo, Alertmanager, exporters and OpenTelemetry Collector internal/admin endpoints should remain private unless an explicitly reviewed use case requires otherwise.
- Database exporters use least-privilege monitoring credentials only.
- No observability component receives unrestricted provider administration credentials.

## Data security

Do not collect or persist Authorization headers, access/refresh tokens, SMTP/SMPP/provider passwords, private keys, webhook signing secrets, raw payment information, or message bodies/recordings unless separately approved and access-controlled.

Standard correlation fields may include tenant-safe identifiers, correlation IDs, command/message IDs, service, environment and sanitized provider result codes.

## Availability and retention

Each dedicated component repo owns its component-specific retention/configuration source. Infrastructure coordination verifies the combined capacity, storage growth, backup/restore and host-placement implications before staging/production promotion.

## Dashboard separation

- Grafana: operational monitoring, incidents, infrastructure/service health. Principal source: `Codestra-Grafana-`.
- Superset if adopted: business and communications analytics from curated read models; dedicated repo should be created if it becomes a managed platform component.
- Purpose-built communications admin UI: controlled workflows and actions through Kong -> Middleware.

Grafana, Superset or any observability tool must never become an alternate write path to Postal, Jasmin, VICIdial/Asterisk, Odoo or provider databases.

## Cross-stack dependency model

```text
Applications / exporters
   +--> Codestra-Prometheus ------> Codestra-Alertmanager
   |            |
   |            +-----------------> Codestra-Grafana-
   |
   +--> Codestra-Telemetry -------> Codestra-Tempo ------> Codestra-Grafana-
                  |
                  +---------------> Codestra-Loki -------> Codestra-Grafana-
```

Exact paths may vary by telemetry type, but ownership does not.

## Deployment gates

Before production deployment:
1. every participating dedicated repo has an accepted exact SHA/version/digest;
2. component-specific CI and upgrade tests pass;
3. cross-component compatibility is proven in test/staging;
4. secrets remain externally injected;
5. authentication/private-network boundaries are proven;
6. retention/capacity is validated as a combined stack;
7. backup and restore are validated where state is material;
8. alert delivery and dashboard datasource connectivity are tested;
9. exact source/image/config identities are recorded;
10. rollback targets are known and rehearsed where required;
11. explicit production approval is obtained.

## Branch/upgrade policy

The architecture authority for required persistent branches and future upgrade branches is maintained in `communication-platform-/docs/OBSERVABILITY-BRANCH-AND-UPGRADE-POLICY.md`.

All six dedicated repos should maintain `main`, `development`, `test`, `staging`, and `production`, plus short-lived `feature/*`, `fix/*`, `docs/*`, `upgrade/*`, `security/*`, `hotfix/*`, and optional `release/*`/`rollback/*` branches.

## Source ownership

`Infustruction-repo` coordinates shared infrastructure only. Dedicated observability repositories own their runtime/configuration source. Metric names, traces and service-specific log policies are defined with each owning service repository and coordinated through `communication-platform-`.