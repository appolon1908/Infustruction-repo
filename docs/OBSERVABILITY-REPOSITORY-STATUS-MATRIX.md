# Codestra Observability/Security Repository Status Matrix

## Binding state

This document is the human-readable view of `config/observability/repository-registry.v1.json` and `config/observability/active-branch-lock.v1.json`.

```text
PROGRAM_STATE=BUILDING
REPOSITORY_FIRST=YES
DEPLOYMENT_ENABLED=NO
SERVER_INSTALL_ALLOWED=NO
FIREWALL_CHANGE_ALLOWED=NO
CADDY_LIVE_RELOAD_ALLOWED=NO
KEYCLOAK_LIVE_APPLY_ALLOWED=NO
OPENBAO_INITIALIZATION_ALLOWED=NO
```

Thirteen public DNS names may resolve to `37.27.128.39`, but DNS is not evidence of service installation, authentication, TLS activation, private-port closure, health or release approval. PostgreSQL Exporter has no public hostname; its principal repository assigns only the private service identity `postgres-exporter:9187`.

## Persistent branch audit

All 14 principal repositories contain:

```text
main
 development
 test
 staging
 production
```

The GitHub branch inventory reported every persistent branch as **unprotected**. This is an R0 governance gap, not a release success. The desired protection model is defined separately in `docs/BRANCH-PROTECTION-DESIRED-STATE.md`.

## Exact repository matrix

| # | Component | Endpoint authority | Canonical candidate | PR/stack | Current source state |
|---:|---|---|---|---|---|
| 1 | Grafana | `graf.codestra.media` | `integration/enterprise-observability-control-plane-20260829` @ `55a29aade410a6d2e6bb31384533ae6c3824121d` | PR #1 -> `development` | Source ready for review; no deployment |
| 2 | Prometheus | `prom.codestra.media` | `feature/observability/authoritative-prometheus-20260829` @ `5d8bf6905a8ad79f9234700bc2818e8155f08427` | PR #1 -> `development` | Source ready for review; targets remain gated |
| 3 | Alertmanager | `aler.codestra.media` | `integration/central-alert-routing-v1-20260829` @ `8b3aad22be080dd898d173e9a7901da488d1427d` | PR #1 | Source ready; live Middleware ingestion endpoint still evidence-gated |
| 4 | Loki | `loki.codestra.media` | `feature/codestra-corporate-suite-v1-20260829` @ `73706f3ece2061a94163a4bf4c90a6503af37e63` | PR #1 -> `development` | Source ready for review; no ingestion |
| 5 | Tempo | `temp.codestra.media` | `feature/codestra-corporate-suite-v1-20260829` @ `edf217b31b227c63a1def27ac4b03a67c3aff100` | PR #1 -> `development` | Test/staging single-binary candidate; production HA remains required |
| 6 | OpenTelemetry | `otel.codestra.media` | `feature/observability/collector-prometheus-authority-20260829` @ `9e44696978080368b9af3743db505fa4f59136a0` | PR #2 -> `development` | Source ready for review; no certificates/networks/backends activated |
| 7 | Superset | `supe.codestra.media` | `feature/codestra-corporate-suite-v1-20260829` @ `9ff12b1a321120218da2d8fa91b78e6b9bc43bdd` | PR #1 OIDC foundation -> PR #2 analytics | Ordered stack; read-model-only policy; no database connection |
| 8 | Node Exporter | `node.codestra.media` | `feature/codestra-corporate-suite-v1-20260829` @ `d444b4ec10291d9517c969f37cc63a3c69f062f4` | PR #1 runtime -> PR #2 corporate | Exact-head CI rerun after locked-source fixes |
| 9 | cAdvisor | `cadv.codestra.media` | `feature/codestra-corporate-suite-v1-20260829` @ `2fea43e3fb043056f426ba420f188cefe3832f62` | PR #1 runtime -> PR #2 corporate | Exact-current-head verification pending |
| 10 | PostgreSQL Exporter | `postgres-exporter:9187` private service identity; no public hostname | `feature/observability/postgres-exporter-20260829` @ `8919709a9e020acf250aafb4c691021a12a5331f` | PR #1 authority -> PR #2 runtime | Principal repository authority confirmed; port 9187 remains private and publicly forbidden |
| 11 | Redis Exporter | `rdex.codestra.media` | `feature/codestra-corporate-suite-v1-20260829` @ `96ef1dcad350cea074dfb4082315ddd6d62c6adf` | PR #1 runtime -> PR #2 corporate | Exact-head CI rerun after upstream-fixture scan correction |
| 12 | Blackbox Exporter | `blac.codestra.media` | `feature/codestra-corporate-suite-v1-20260829` @ `97a386f3124fad4560ccf6429b1a806736bcfabc` | PR #1 runtime -> PR #2 corporate | Exact-head CI green; no probes activated |
| 13 | Alloy | `allo.codestra.media` | `feature/codestra-corporate-suite-v1-20260829` @ `76b73fd244e819039ec5faee1281321d689f0250` | PR #1 | Source ready for review; no mounts, certificates or ingestion activated |
| 14 | OpenBao | `bao.codestra.media` | `feature/codestra-corporate-suite-v1-20260829` @ `ecfe6e6e094c1b9f3127e0ba35a4c4b8475cd693` | PR #1 OIDC foundation -> PR #2 feature model -> required storage/HA stage | Blocked on storage, seal, HA, custody, audit, backup/restore and DR |

## Cross-cutting authorities

| Authority | Active source | Required work | Live state |
|---|---|---|---|
| Keycloak | `feature/observability-managed-clients-v1` | Issue #30: three managed clients, five realm roles, plan/review/apply/export/rollback and secret-safe tests | No apply |
| Caddy | `feature/observability-edge-routing-v1`, PR #6 | Authenticated `graf`/`supe`, restricted `bao`, controlled denial for ten private DNS hosts; PostgreSQL Exporter remains private-only without a public host | No reload or certificates |
| Infrastructure | `feature/observability-private-network-v1`, PR #2 | Topology, firewall desired state, integration coordination and evidence | No firewall or install |
| Integration lab | `codex/observability-integration-foundation`, PR #4 | Disposable synthetic full-stack validation | No production dependencies |
| Communications dashboard | `communication-platform-:feat/dashboard-read-model-v1`, PR #3 | Unified operational/read-model contract | No business mutation |

## Duplicate-prevention rule

A branch named in `active-branch-lock.v1.json` is the only active implementation authority for its scope. An agent must not create a replacement branch because a planned name differs from the branch that already exists.

Permitted cases:

1. Continue the locked canonical branch.
2. Add a non-overlapping ordered stack stage explicitly listed in the lock.
3. Propose a lock-file change explaining why the active authority must change.

Prohibited cases:

- parallel branches implementing the same runtime;
- direct writes to persistent branches;
- force pushes over another agent's commits;
- rebasing away reviewed ancestry;
- merging a downstream stacked PR before its foundation;
- declaring a merge to be deployment approval.

## R0 exit gates

R0 is complete only when:

- the registry and branch lock validate in CI;
- all 14 persistent-branch sets remain present;
- branch-protection desired state is accepted;
- every overlapping branch has a continuation, stack or blocked decision;
- each candidate has a responsible PR or an explicit missing-stage entry;
- the combined release manifest remains fail-closed while any component is incomplete;
- no repository or workflow enables deployment.

## Release-train interpretation

`source_ready_for_review` means a repository has a meaningful candidate and is ready for source review. It does **not** mean CI is complete, the PR is accepted, the image is immutable, the component is release-frozen, or deployment is allowed.

Only the final release manifest may declare a 14-component freeze, and its validator refuses `frozen=true` or `releaseReady=true` while any component gate is incomplete.
