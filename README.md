# Codestra Infrastructure Authority

This repository is the principal source for shared Codestra infrastructure-as-code, deployment topology, environment definitions, observability infrastructure, backup/recovery infrastructure, and infrastructure release governance.

## Scope

This repository owns infrastructure definitions and deployment orchestration that are shared across components. It does **not** become a second source for application/runtime code that already has its own principal repository.

### Principal component repositories

- `appolon1908-hue/Caddy` — edge TLS and reverse-proxy source
- `appolon1908-hue/Kong` — API gateway routes, plugins, policies and Kong operations
- `appolon1908-hue/Keycloak` — identity realms, clients, scopes and identity deployment source
- `appolon1908-hue/Middleware-` — cross-system control plane and durable write boundary
- `appolon1908-hue/SDK-repository` — distributable contracts, SDKs and connector tooling
- `appolon1908-hue/klyrow.com` — email runtime around Postal/Mautic
- `appolon1908-hue/telnexa` — SMS/Jasmin runtime
- `appolon1908-hue/Vicidialer-Codestra` — voice/VICIdial/Asterisk connector runtime
- `appolon1908-hue/Odoo` — CRM/business application authority
- `appolon1908-hue/N8N` — workflow/orchestration authority
- `appolon1908-hue/kyqra-crawler` — crawler runtime
- `appolon1908-hue/codestra-provisioning-service` — provisioning runtime

## Permanent authority rule

If a component has its own principal repository, infrastructure code in this repository may deploy or reference that component but must not duplicate its application/runtime source.

## Target platform path

```text
Internet
  -> Caddy
  -> Kong
  -> Keycloak identity validation
  -> Middleware
  -> product/provider adapters
     -> Odoo
     -> Klyrow/Postal/Mautic
     -> Telnexa/Jasmin
     -> VICIdial/Asterisk
     -> Kyqra crawler

SDK-repository supplies versioned clients/contracts.
n8n orchestrates through Middleware only.
```

Middleware remains the only privileged cross-system write boundary.

## Infrastructure responsibilities

This repository should contain:

- environment topology: development, test, staging, production;
- Docker/Compose or Kubernetes deployment definitions that orchestrate accepted component artifacts;
- Terraform/OpenTofu/Ansible infrastructure definitions where adopted;
- Hetzner networking, private network/vSwitch/VLAN declarations without secret values;
- shared PostgreSQL/Redis/NATS infrastructure topology where infrastructure-owned;
- observability deployment: Prometheus, Alertmanager, Grafana, Loki and exporters;
- backup, restore, disaster-recovery and retention definitions;
- immutable image and release manifest references;
- environment promotion policy;
- infrastructure security baselines;
- capacity, storage and host lifecycle documentation;
- combined deployment manifests that pin exact component SHAs/image digests.

This repository must not contain production passwords, API tokens, private keys, certificates, customer PII, database dumps or secret-bearing evidence.

## Environment model

```text
development -> test -> staging -> production
```

Production promotion requires exact artifact identities and evidence from every affected principal repository. Production and staging should be physically separated when capacity permits; logical Docker-network separation on one host is not equivalent to host isolation.

## Current infrastructure remediation priorities

The current server inventory identified several infrastructure risks that this repository must help eliminate:

1. source/runtime configuration is spread across multiple filesystem locations;
2. live containers do not always map cleanly to immutable Git/release identities;
3. production and staging share physical host resources;
4. old worktrees, Docker volumes, images and evidence consume significant disk;
5. some runtime Compose files still originate from development or release worktrees;
6. observability components documented architecturally are not all proven active;
7. source-to-runtime reconciliation needs one authoritative deployment manifest.

## Required documentation set

- `docs/ARCHITECTURE.md`
- `docs/REPOSITORY-AUTHORITY.md`
- `docs/ENVIRONMENTS.md`
- `docs/NETWORKING.md`
- `docs/SECURITY-BASELINE.md`
- `docs/OBSERVABILITY.md`
- `docs/BACKUP-RESTORE-DR.md`
- `docs/RELEASE-AND-PROMOTION.md`
- `docs/RUNTIME-SOURCE-TRACEABILITY.md`
- `docs/CAPACITY-AND-STORAGE.md`
- `docs/RUNBOOKS.md`

## Server 37 production evidence

`SERVER-37-PRODUCTION-API-MATRIX.yaml` classifies the completed runtime inventory and the bounded custom API contract without counting product-native APIs as custom implementation work. `SERVER-37-PRODUCTION-ROLLBACK.yaml` records before/candidate identities and remains fail-closed until reviewed promotion and isolated rollback rehearsal are complete.

## Branch policy

After repository bootstrap, use:

- `main` — accepted infrastructure authority
- `development` — integration development
- `staging` — staging promotion
- `feature/*` or `infra/*` — scoped changes
- `fix/*` — corrective changes

Never perform production activation merely by merging documentation or infrastructure source. Deployment is a separate, explicitly approved action.

## Observability private-network candidate

The canonical topology, east-west communication map, and additive default-deny
firewall intent are under `config/observability/`. Validate them with
`python3 scripts/validate-observability-topology.py`. These files are
source-only and explicitly keep live installation disabled until principal
service repositories confirm their deployment listeners and the Caddy and
Keycloak changes pass review.
