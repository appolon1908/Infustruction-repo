# Codestra Stage 6-8 Runtime Preflight Inventory

Captured: `2026-08-31T01:38:54+02:00` (`2026-08-30T23:38:54Z`)

Scope: read-only discovery. No container, service, database, secret, identity,
gateway, workflow, firewall, or production runtime was changed.

## Gate result

`RUNTIME_PREFLIGHT=FAIL`

`PRODUCTION_BUSINESS_WRITES=NOT_PROVEN_DISABLED`

The mission stopped before runtime mutation because three running Klyrow
production-email containers expose `LIVE_EMAIL_DELIVERY=true`:

| Container | Image | Effective safety value |
|---|---|---|
| `klyrow-gateway-1` | `codestra/klyrow-gateway:webmail-20260828` | `LIVE_EMAIL_DELIVERY=true` |
| `klyrow-smtp-relay-1` | `codestra/klyrow-gateway:smtp-hotfix-20260826.9` | `LIVE_EMAIL_DELIVERY=true` |
| `klyrow-worker-1` | `codestra/klyrow-gateway:webmail-20260828` | `LIVE_EMAIL_DELIVERY=true` |

The host also exposes `37.27.128.39:25` through Docker to
`klyrow-postal-smtp-1`. This is a live external-delivery path, not a certified
dry-run-only configuration. Missing advertising, social, external-model, n8n
provider-write, dialing-state, and call-count controls remain ambiguous.

## Host authority and drift

| Documented role | Observed role | Result |
|---|---|---|
| `65.109.65.169` core/staging | General-purpose SSH denied; only a bounded provider-credential forced command is available | `BLOCKED` |
| `37.27.128.39` observability/security | Current local host, `10.40.0.4`; runs production Klyrow email, Telnexa SMS/billing, Kyqra crawler, and a private integration gateway | `DRIFT` |

Observed local host:

- Hostname: `Ubuntu-jammy-latest-amd64-base.zst`
- Kernel: Linux `5.15.0-187-generic`, x86_64
- Public address: `37.27.128.39/32`
- Private VLAN address: `10.40.0.4/24`
- Running containers: 41; total containers: 46
- Docker networks: 17; Docker volumes: 76
- Public listeners: SSH 22, HTTP 80, HTTPS 443, SMTP 25
- Private listeners include 587, 3100, 8443, and 18000

The expected observability/security topology is not present. Observed counts
are OpenBao 0, Prometheus 2, Grafana 1, Loki 0, Tempo 0, Alloy 0, Node Exporter
2, cAdvisor 0, Redis Exporter 0, Blackbox Exporter 0, and Superset 0. The
Prometheus/Grafana/Node Exporter instances belong to Klyrow or Telnexa stacks,
not a complete shared Codestra observability plane.

## Runtime stack summary

| Service/stack | Host | Containers | Runtime identity | Deployment authority | Data/cache | Exposure | Rollback/provenance |
|---|---|---:|---|---|---|---|---|
| Klyrow email/marketing | `37.27.128.39` | 21 | Mixed local tags and vendor tags; gateway image ID `sha256:7cb3769eceb3339dbbd4392580fceaa4ff285dbec3721fbb4dd2763a00e27d7f` | `/opt/klyrow/*.yaml`, `/root/klyrow.com/docker-compose.yml` | PostgreSQL, MariaDB, RabbitMQ | Public SMTP 25; private SMTP 587; local web ports | Dirty deployment checkout; several mutable/local tags; exact rollback not uniformly proven |
| Telnexa SMS/billing | `37.27.128.39` | 11 | Jasmin/RabbitMQ SHA tags; billing image ID `sha256:e92ec02857ac67c15030b26ca464ac07966b8bd0162c9dbd424844e42683012c` | `/opt/telnexa/compose.yml`, `/root/telnexa-main/docker-compose.yml` | PostgreSQL, Redis, RabbitMQ | Private/local endpoints | `/opt/telnexa` dirty and has no configured remote; `/root/telnexa-main` dirty/diverged |
| Kyqra crawler | `37.27.128.39` | 6 | Locally built mutable names | `/opt/kyqra-crawler/docker-compose.yml` | PostgreSQL, Redis | `10.40.0.4:3100` and localhost 3100 | Deployment checkout dirty; runtime Git SHA not labeled |
| Private integration gateway | `37.27.128.39` | 1 | local image ID `sha256:457971045f964ea80dadcfcd75069adf4d092cf6f075b2410055163b8fbc4981` | `/opt/private-integration/compose.yaml` | Telnexa backend dependency | localhost 18443; nginx private mTLS edge | Non-Git source authority; provenance unresolved |
| Scrapper validation leftovers | `37.27.128.39` | 2 | vendor PostgreSQL/Redis images | no Compose labels | PostgreSQL, Redis | private Docker network only | Ownership and cleanup disposition unresolved |

All listed running containers were inspected without reading or recording secret
values. Image IDs, Compose labels, networks, health, restart counts, and only the
named non-secret safety variables were read back.

## Core-server access evidence

General SSH attempts to `root@65.109.65.169` fail with public-key/password
authentication denied. The approved bounded key reaches `codestra-admin` at
`10.40.0.1`, but only the forced provider-credential interface is authorized.
Its non-secret status read-back was:

```text
telnexa: phase=active, pending=absent, current=present, previous=present
klyrow:  phase=active, pending=present, current=present, previous=present
kyqra:   phase=uninitialized, current=absent
```

That interface cannot supply the mandatory host, container, Compose, repository,
database, secret-source, port, health, and rollback inventory. Existing
`reports/runtime-reconciliation/` evidence on protected `main` remains useful
historical evidence, but it does not replace a fresh read-back for this run.

## Existing Git authority

Protected `main` at `c451ff0` is the evidence base. A fresh GitHub read-back
matched every locked component `main` except Keycloak. Keycloak had advanced by
reviewed merge 48 from `ef1212d53ec8a136421dd20873183aef7845a46f` to descendant
`80fc33c7159440e357219903f62ea7fb84914d59`; this branch refreshes the lock to
that revision. The resulting source identity is locked, but runtime mutation is
still unauthorized. Backup-gate pull request 25 merged as `6ab3b36`, but no
backup was executed because the runtime safety prerequisite had failed.

## Stop conditions

The following mission stop conditions are active:

1. Production business writes cannot be proven disabled; live email delivery is
   explicitly enabled in three running containers.
2. General shell access to the core/staging server is unavailable.
3. Fresh core runtime provenance cannot be established with the available
   forced-command interface.

Consequently, backups, OpenBao, Keycloak, migrations, application/Kong/n8n
deployment, observability hookup, E2E, failure injection, rollback proof, and
the production read-only canary were not attempted.

## Scoped safety decision refresh

The stop conditions above record the earlier global evaluation. The owner
subsequently approved a Stage 6 scope limited to the 22 locked staging
workloads on `65.109.65.169`. Klyrow/Postal on `37.27.128.39` is now recorded
as `OUT_OF_SCOPE_ACTIVE_PRODUCTION_DO_NOT_TOUCH`; its activity neither proves
nor authorizes an external write from the Stage 6 path.

This decision does not itself pass preflight. A fresh read-only safety and
provenance read-back of all 22 in-scope workloads is still required before any
staging apply. Keycloak source authority has advanced through reviewed merge 56
to `303e2edef2219c5eb3ac167c309a9717a766d079`. Runtime mutation and production
mutation remain unauthorized.
