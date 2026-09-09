# Repository Profile — `Infustruction-repo`

## Identity

- **Repository:** `appolon1908-hue/Infustruction-repo`
- **Category:** Platform infrastructure and GitOps
- **Visibility:** `public`
- **Default branch:** `main`
- **Authority:** Primary shared infrastructure, topology, environment, and infrastructure release-governance authority
- **Status:** Active infrastructure repository with observability topology, release-train, environment, network, backup, and DR work.

## Purpose

Defines shared deployment topology, environment models, networking, infrastructure-as-code, observability infrastructure, backup/recovery, release manifests, and infrastructure orchestration.

## Owns

- Shared infrastructure definitions and environment topology
- Network, storage, backup/restore/DR, capacity, security baseline, and infrastructure release governance
- Combined manifests that reference exact component SHAs and immutable image digests

## Does not own

- Application/runtime source already owned by principal component repositories
- Production secrets or secret-bearing evidence
- Automatic production activation caused by a source merge

## Key integrations

- Caddy, Kong, Keycloak, and Middleware
- Product/provider repositories and shared databases/queues where infrastructure-owned
- Grafana, Prometheus, Alertmanager, Loki, Tempo, Telemetry, Alloy, exporters, Superset, and OpenBao

## Current priorities

1. Promote the central repository registry and release-train authority
2. Keep component references exact, immutable, and source-traceable
3. Maintain the disposable integration laboratory and predeployment manifests
4. Require an explicitly approved, isolated staging scope before deployment; shared-host capacity does not waive isolation gates

## Governance and safety

- `main` is the accepted infrastructure source authority. `development` is the integration branch; scoped `feature/*`, `infra/*`, `docs/*`, `fix/*`, `security/*`, and `upgrade/*` branches use reviewed pull requests.
- Long-lived source branches are `main`, `development`, and `staging`; their reviewed pull requests govern source integration.
- Deployment environments follow `development -> test -> staging -> production`. Environment promotion is a separate approved operation; `test` and `production` are not additional long-lived branches defined by this profile.
- Use pull requests and exact-head/merge-result validation; merge never applies infrastructure.
- Never commit credentials, private keys, certificates, customer PII, database dumps, or secret-bearing evidence.
- Every deployment requires accepted component artifacts, inventory, backups, plan review, smoke tests, and rollback readiness.
- This document does not create infrastructure, change firewall/network rules, deploy services, initialize OpenBao, or activate production.

## Account-wide catalog

See `appolon1908-hue/documentaions/REPOSITORY_CATALOG.md`.
