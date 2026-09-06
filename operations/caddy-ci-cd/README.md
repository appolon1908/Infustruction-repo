# Caddy CI/CD runner bootstrap

This package closes the repository-to-runner handoff for the protected Caddy
release chain without turning an untrusted pull request into a host command.

The Caddy repository builds, scans, signs, attests, and publishes one exact
production image. Its bounded runtime workflow uses two separate one-job runner
identities:

| Target | Required label | Caddy environment |
|---|---|---|
| isolated staging | `codestra-staging` | `staging-readonly` |
| production read-only canary | `codestra-production-canary` | `production-readonly-canary` |

## Security model

The runner is repository-scoped to `appolon1908-hue/Caddy`, configured with
`--ephemeral`, and accepts one job. The runner application is pinned to version
`2.337.0` and the reviewed Linux x64 archive SHA-256 in
`runner-contract.v1.json`.

The bootstrap never:

- accepts the GitHub registration token as a command-line argument;
- stores that token in Git, Terraform state, cloud-init, an artifact, or a file;
- disables SSH host-key validation;
- adds a user to the Docker group;
- creates a broad sudo rule;
- runs the Actions runner as root;
- creates, updates, retires, or deletes a repository ruleset;
- starts, reloads, replaces, or retags Caddy;
- authorizes application writes or production traffic movement.

The target host must already provide reviewed Docker authorization for the
dedicated runner identity. The installer fails before registration when that
authorization is absent. This preserves the host security boundary instead of
silently granting root-equivalent Docker access.

Before registering a runner, the controller reads the exact canonical ruleset
JSON from the current Caddy `production` SHA and independently reads the live
`Protect Caddy promotion branches` ruleset. Both must agree on:

- all five protected branches;
- no bypass actors;
- one exact-head approval;
- stale-review dismissal and last-push approval;
- resolved review conversations;
- squash-only merging and linear history;
- deletion and non-fast-forward protection;
- the four actual required CI contexts.

A mismatch is a hard failure. Ruleset application belongs to the separate,
protected Caddy governance workflow. This runner bootstrap verifies governance
but does not mutate it.

## Protected bootstrap environments

Create these environments on `appolon1908-hue/Infustruction-repo` and restrict
them to protected `main`:

- `caddy-staging-runner-bootstrap`
- `caddy-production-canary-runner-bootstrap`

Both require these secrets:

- `CODESTRA_REPOSITORY_ADMIN_TOKEN`: fine-grained token restricted to Caddy with
  **Administration: read and write**, **Environments: read and write**, and
  **Actions: read**. It is used for exact runner registration, environment
  readback, and queued-job identity verification.
- `CADDY_RUNNER_SSH_PRIVATE_KEY`: private key for the existing restricted
  operator identity.
- `CADDY_RUNNER_KNOWN_HOSTS`: pinned known-hosts line for the exact target.

Both require these variables:

- `CADDY_RUNNER_HOST`
- `CADDY_RUNNER_SSH_USER`
- `CADDY_RUNNER_SSH_PORT`

Staging additionally requires:

- `CADDY_STAGING_ENV_FILE`
- `CADDY_STAGING_DATA_SOURCE`
- `CADDY_STAGING_MTLS_CLIENT_CERT`
- `CADDY_STAGING_MTLS_CLIENT_KEY`
- `CADDY_STAGING_MTLS_CA_CERT`
- `CADDY_STAGING_N8N_CLIENT_SECRET_FILE`

`CADDY_STAGING_N8N_CLIENT_SECRET_FILE` contains only an absolute host path. The
default reviewed path is:

```text
/etc/codestra/caddy/secrets/n8n-automation-client-secret
```

### Client-secret file contract

The secret value must never be placed in Git, an Actions secret or variable used
as a plain environment value, a workflow input, a command line, a log, or an
artifact. Only the absolute file path crosses the bootstrap boundary.

Because the Actions runner is deliberately non-root, the file must use one of
these two readable, non-world-accessible ownership models:

1. **Dedicated runner ownership:** owner is the exact ephemeral runner account,
   mode `0400` or `0600`.
2. **Root plus dedicated runner group:** owner is `root`, group is a non-root
   group assigned to the exact ephemeral runner account, mode `0440` or `0640`.

In both models the file must be a regular non-symlink file, have no world bits,
contain between 8 and 4096 bytes, and contain the exact client secret with no
leading or trailing whitespace. Root-owned `0400` or `0600` is intentionally
invalid for the non-root runner because it is unreadable and would deadlock the
certification job. World-readable modes are always rejected.

The bounded staging proof uses the file through curl's file-reading form so the
secret value never appears in the process argument list. It mints a maximum
five-minute token from **`auth-staging.codestra.co`**, then validates:

- the staging issuer;
- client `n8n-automation`;
- audience `middleware-api`;
- scope `middleware.status.read`;
- a non-wildcard `tenant_id` service-account claim;
- issued-at, expiry, and maximum token lifetime.

It then sends exactly one authenticated GET through
Caddy → Kong → Middleware and requires Middleware's distinctive
`404 command_not_found` response. It separately verifies Middleware `/version`
against the pinned protected-main SHA, immutable image digest, configuration
checksum, and staging environment. The proof sends zero application mutations
and enables no provider effects.

Production additionally requires:

- `CADDY_PRODUCTION_MTLS_CLIENT_CERT`
- `CADDY_PRODUCTION_MTLS_CLIENT_KEY`
- `CADDY_PRODUCTION_MTLS_CA_CERT`

Every path must be absolute. The bootstrap verifies the target contract before
minting a short-lived repository runner-registration token.

## Execution

Dispatch `Caddy CI/CD runner bootstrap` from protected `main`.

For staging:

```text
target=staging
confirmation=BOOTSTRAP_CADDY_STAGING_RUNNER
bounded_runtime_run_id=<exact queued Caddy bounded-runtime run>
```

For the production read-only canary:

```text
target=production-readonly-canary
confirmation=BOOTSTRAP_CADDY_PRODUCTION_CANARY_RUNNER
bounded_runtime_run_id=<same run after its production canary job is queued>
```

Register the staging runner only while the exact bounded staging job is already
queued for the current Caddy `production` SHA. Register the production canary
runner only after that same run queues `production-readonly-canary`; speculative
registration is rejected. The production job remains GET/HEAD-only, requires
byte-identical production runtime readback before and after, and verifies the
staging packet that binds exact Caddy source/image/configuration to the
staging-Keycloak-authenticated Caddy → Kong → Middleware proof.

`replace_stale_registration=true` deletes only the exact named, non-busy Caddy
runner record. It never deletes a differently named runner and refuses a busy
runner.

## Restricted-operator execution

Where GitHub-hosted SSH is intentionally blocked, run
`scripts/configure_caddy_ci_cd_runner.sh` from the pre-approved management
station using owner-only credential files. The command contract is printed by:

```bash
scripts/configure_caddy_ci_cd_runner.sh --help
```

Generated evidence contains runner identity, labels, online status, installer
checksum, environment, exact queued job, and governance-readback assertions. It
records that canonical rulesets, unrelated rulesets, and Caddy runtime were not
changed by the bootstrap and contains no credential values.
