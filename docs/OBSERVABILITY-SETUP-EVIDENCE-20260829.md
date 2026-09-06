# Codestra Observability/Security Setup Evidence — 2026-08-29

## Decision

Repository setup for the secure `codestra.media` observability/security edge is **source-ready for review**. Live server installation and production activation remain blocked.

## DNS evidence supplied by the operator

All 14 A records resolve to `37.27.128.39` with TTL 600:

```text
graf  prom  aler  loki  temp  otel  supe
node  cadv  pgex  rdex  blac  allo  bao
```

The operator reported 56/56 checks passing across both GoDaddy authoritative nameservers, Cloudflare, and Google.
The repository preflight was repeated on 2026-08-29 and all 14 A answers again
included `37.27.128.39`; that preflight does not validate TLS or application
exposure.

Recorded DNS backups:

```text
klyrow-backups/godaddy-codestra-media-observability-20260829T180439Z
klyrow-backups/godaddy-codestra-media-observability-postchange-20260829T180556Z
```

DNS evidence does not prove service exposure, authentication, TLS, private binding, or runtime health.

## Candidate repository evidence

| Responsibility | Repository / branch | Exact head | CI evidence | Result |
|---|---|---|---|---|
| Caddy edge | `appolon1908-hue/Caddy:feature/observability-edge-routing-v1` | candidate `5ee8755ddc900239d891358a0221295e0fe4a915` | repository validator and Caddy 2.10.2 validation pass locally; candidate CI pending | REVIEW REQUIRED |
| Keycloak OIDC contract | `appolon1908-hue/Keycloak:feature/observability-oidc-clients-v1` | candidate `76464c4cce21fff2788cac58966888c51f548634` | full policy, protected plan/rollback, convergence, and unit tests pass locally; candidate CI pending | REVIEW REQUIRED |
| Private network/firewall | `appolon1908-hue/Infustruction-repo:feature/observability-private-network-v1` | use exact PR head after this reconciliation is pushed | topology/firewall/communication validation and DNS preflight pass locally; candidate CI pending | REVIEW REQUIRED |
| Grafana app contract | `appolon1908-hue/Codestra-Grafana-:feature/private-bind-keycloak-oidc-v1` | `f83e8235d01ec9c5d8a89f064170872923a5f8f6` | `Validate Codestra Grafana integration` run `33269022076` | PASS |
| Superset app contract | `appolon1908-hue/Superset:feature/private-bind-keycloak-oidc-v1` | `7ddf9932caaf50fff406220739eb08844990c489` | `Validate Codestra Superset integration` run `33269031021` | PASS |
| OpenBao app contract | `appolon1908-hue/Codestra-OpenBao:feature/private-bind-keycloak-oidc-v1` | `a3f6c4469cdf7acee032b024fcc3c707b7e71645` | `Validate Codestra OpenBao integration` run `33269083948` | PASS |

## Source-ready behavior

The reviewed source now defines:

- Caddy TLS sites for all 14 hostnames;
- private upstream proxies only for Grafana, Superset, and source-restricted OpenBao;
- controlled public `403` responses for the eleven native monitoring/telemetry hostnames;
- exact Keycloak OIDC client IDs, callbacks, PKCE, role separation, and external secret ownership;
- Grafana loopback binding, Keycloak OIDC, strict role mapping, anonymous access denial, and private datasources;
- Superset loopback binding, Keycloak OIDC, approved-role extraction, secure proxy/cookie settings, and curated-read-model-only policy;
- OpenBao loopback listeners, Caddy source restrictions, plan-only OIDC roles, exact callbacks/audience, and native-policy requirements;
- a machine-readable private service graph and default-deny firewall intent;
- DNS/TLS/HTTP/private-denial/external-port smoke-test tooling.

## Live activation blockers

The following remain mandatory before a production change:

1. Review and merge the managed Keycloak client candidate; separately implement/review realm-role provisioning, administrative MFA enforcement, user/group assignment, and application-side role mappings.
2. Generate/retrieve client secrets through the approved protected process and inject them into service secret files/environment; never commit them.
3. Add accepted immutable deployment/listener definitions to every principal service repository. PostgreSQL Exporter now has a repository and a disabled runtime contract, but still needs an accepted immutable deployment and private-listener evidence; all familiar ports remain unconfirmed deployment references until then.
4. Select and certify OpenBao storage, HA, seal, initialization custody, audit, backup/restore, DR, and narrow policy design.
5. Reconcile the target server's current Nginx ownership of 80/443 with the reviewed Caddy migration; Caddy is not currently installed or active there.
6. Apply a separately reviewed additive firewall plan preserving restricted SSH, separately approved SMTP on TCP 25, and all unrelated approved services while denying native observability ports publicly.
7. Validate Caddy against the exact accepted source, back up the live config, rehearse rollback, and only then reload.
8. Prove TLS certificate issuance and hostname SANs for all 14 names.
9. Prove Grafana/Superset OIDC login and role denial; prove OpenBao network, OIDC, and policy isolation.
10. Run post-deploy and genuinely external port smoke tests.
11. Record post-change exact SHAs, image digests, configuration checksums, smoke evidence, and explicit approval.

## Current activation state

```text
DNS_CONFIGURED=YES
REPOSITORY_SOURCE_READY_FOR_REVIEW=YES
CADDY_RELOADED=NO
TLS_CERTIFICATES_PROVEN=NO
KEYCLOAK_CLIENTS_APPLIED=NO
SERVICE_SECRETS_INSTALLED=NO
SERVICES_INSTALLED_OR_CHANGED_BY_THIS_WORK=NO
FIREWALL_APPLIED=NO
OPENBAO_INITIALIZED=NO
EXTERNAL_PORT_SCAN_PASSED=NO
PRODUCTION_ACTIVATED=NO
```
