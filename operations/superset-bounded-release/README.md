# Superset bounded release infrastructure contract

This directory binds `appolon1908-hue/Superset` to the Codestra protected
staging and production-read-only execution environments. It is an infrastructure
control-plane record, not a credential store and not a production activation.

## Ordered authority

The Superset repository must promote reviewed source through:

```text
development -> test -> staging -> production -> main
```

A protected `production` SHA may then execute this immutable chain:

```text
signed image build, scan, SBOM, provenance and signature
  -> hosted artifact staging and rollback proof
  -> self-hosted codestra-staging under staging-readonly
  -> self-hosted codestra-production-canary under production-readonly-canary
  -> mandatory production canary rollback and exact state restoration
```

No release tag, branch merge, image push, or hosted test authorizes production
runtime mutation.

## Required GitHub environments

### `staging-readonly`

The environment must allow only reviewed production releases and an online
runner with both labels:

```text
self-hosted
codestra-staging
```

The runner requires Docker access sufficient only for disposable Superset,
PostgreSQL, and Redis test containers. The workflow publishes no host port and
uses an internal Docker network. It must be able to pull the exact signed GHCR
digest using the workflow package-read identity.

### `production-readonly-canary`

The environment must use an online runner with:

```text
self-hosted
codestra-production-canary
```

Required environment variables:

- `SUPERSET_CANARY_CONTROLLER`: absolute path to the fixed canary controller;
- `SUPERSET_CANARY_CONTROLLER_SHA256`: reviewed SHA-256 of that executable;
- `SUPERSET_PRODUCTION_BASE_URL`: HTTPS Superset edge URL;
- `SUPERSET_CANARY_PERCENT`: greater than zero and no more than `1`.

Optional, separately scoped environment secret:

- `SUPERSET_READONLY_BEARER_TOKEN`: read-only probe identity when the edge
  requires bearer authentication.

The controller must be root-owned, executable, not a symlink, and not writable
by group or world. It must accept only the reviewed status/apply/rollback
contract and return the schemas recorded in `contract.v1.json`.

## Current fail-closed state

Until a new protected Superset production release exists, all candidate identity
fields remain `null`. Until the staging host, runners, environments and
controller checksum are verified, every external binding remains `false`.

```text
DEPLOYMENT_AUTHORIZED=false
PRODUCTION_CERTIFIED=false
LIVE_WRITE=false
ODOO_WRITE=false
EXTERNAL_DELIVERY=false
EMAIL_DELIVERY=false
SMS_DELIVERY=false
PSTN_DIALING=false
PROVIDER_DELIVERY=false
CAMPAIGN_ACTIVATION=false
PAYMENT_EXECUTION=false
FINANCIAL_TRADING=false
```

Never store GitHub tokens, SSH private keys, bearer tokens, database passwords,
OIDC client secrets, Restic passwords, or controller credentials in this
directory. Exact non-secret source, image, evidence and workflow identities may
be recorded only after GitHub Actions has produced and verified them.
