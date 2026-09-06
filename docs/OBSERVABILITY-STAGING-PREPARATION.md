# Codestra Observability Staging Preparation

## Authority and safety boundary

This package prepares the fourteen Codestra observability, analytics, exporter, telemetry, and secrets authorities for a future staging change. **No deployment is authorized by this package.**

The permanent promotion path is:

`development → test → staging → production → main`

A source merge is not permission to install software, start a process, mount host paths, open a port, issue a certificate, create a client secret, initialize OpenBao, or carry production traffic.

Keycloak remains plan-only. Caddy and firewall changes remain render-only. OpenBao initialization and unseal remain prohibited.

## Current source position

All fourteen component authorities are recorded at exact `test` SHAs with green exact-head and merge-result CI. The refreshed OpenTelemetry compatibility gate covers all fourteen authorities, and Alloy's locked-source corporate-agent workflow is accepted at `test`.

The staging decision remains `NO_GO_PREPARATION_INCOMPLETE`.

## Phase A — source train complete

1. Alloy's exact-head policy, formatter, locked-source build, configuration validation, and enterprise-profile workflows passed.
2. Alloy promoted through `development` to `test`, with merge-result CI verified.
3. The Telemetry suite contract now covers all fourteen authorities, including Alertmanager and PostgreSQL Exporter.
4. Exact repository, ref, SHA, workflow result, and unresolved-review evidence was required for promotion.
5. Telemetry promoted through `development` to `test`, with merge-result CI verified.
6. All fourteen immutable test SHAs are recorded in the staging-preparation manifest.

No `test → staging` promotion may merge until every later gate in this document is evidenced.

## Phase B — build immutable artifacts

For each component:

1. Build from the exact accepted `test` SHA.
2. Resolve the final OCI reference as `repository@sha256:<64-lowercase-hex>`.
3. Generate an SPDX or CycloneDX SBOM.
4. Generate SLSA-compatible provenance tied to the source SHA and build inputs.
5. Sign the image and verify the signature with the approved trust root.
6. Compute the final configuration checksum.
7. Store only digests, checksums, and redacted metadata in Git. Never store credentials or private keys.

Mutable tags, `latest`, branch names in runtime image fields, and unverified locally built images are release blockers.

## Phase C — capture read-only server inventory

Inventory is evidence only and must not mutate the target:

- operating system and kernel;
- CPU, memory, filesystems, free capacity, and inode state;
- Docker or container runtime version and storage driver;
- existing networks, listeners, volumes, containers, and systemd services;
- current Caddy configuration hash and validation result;
- current firewall, forwarding, and Docker-chain policy;
- existing `/srv`, `/opt`, `/etc`, and backup locations relevant to the stack;
- current DNS and TLS observations;
- current Keycloak, database, and OpenBao reachability without changing them.

Secrets, environment values, tokens, passwords, private keys, database DSNs, and unredacted configuration must not be collected.

## Phase D — backup, restore, and rollback evidence

Before staging installation:

1. Create pre-change backups using the separately approved operator procedure.
2. Record object counts, sizes, timestamps, and SHA-256 checksums.
3. Validate restore in an isolated disposable location.
4. Measure restore time and document missing or degraded data.
5. Define a component-level rollback procedure and a full-stack rollback order.
6. Rehearse rollback in the disposable integration lab.
7. Prove that rollback does not require an unavailable secret, mutable image, undocumented network, or hidden server state.

A backup file without isolated restore validation is not acceptable evidence.

## Phase E — render control-plane changes without applying them

### Keycloak

Generate a deterministic unchanged-plan for:

- `grafana-observability`;
- `superset-analytics`;
- `openbao-secrets`;
- the approved observability and secrets realm roles.

Bind the plan hash to the exact Keycloak repository SHA and obtain independent review. Do not dispatch apply, generate or export client secrets, assign users, or modify the realm.

### Caddy

Render the proposed routes, headers, upstreams, access controls, and TLS policy. Run configuration validation and produce a before/after diff. Do not reload Caddy or activate certificates.

### Firewall

Render an additive default-deny plan, Docker forwarding safeguards, source CIDRs, destination ports, and rollback commands. Prove SSH administration and unrelated approved services remain reachable. Do not apply UFW, nftables, iptables, or cloud-firewall changes.

### OpenBao

Review storage, seal, Raft, TLS, audit, OIDC, workload identity, policy, backup, and recovery configuration. Do not initialize, unseal, mount auth methods, apply policies, issue certificates, or write secrets.

## Phase F — disposable integration laboratory

The lab must use the exact immutable images and configuration checksums proposed for staging. It must prove:

- startup and health behavior;
- private listener and mTLS boundaries;
- Prometheus scrape and alert evaluation;
- Alertmanager Middleware-only routing with delivery disabled;
- Alloy and OpenTelemetry redaction and business attribution;
- Loki and Tempo business isolation;
- Grafana fixed datasource and role boundaries;
- Superset read-only datasource and row-level isolation;
- exporter least-privilege and no-mutation behavior;
- OpenBao configuration safety without initialization;
- backup, restore, upgrade, and rollback behavior;
- no public native service ports;
- no business, communications, financial, trading, or provider mutation authority.

## Phase G — staging change decision

A staging `GO` requires all machine-readable gates to be true, every artifact evidence field populated with a verified digest, all blockers removed, and an independent change approval recorded.

Production remains a separate decision after staging deployment, staging smoke tests, soak evidence, rollback evidence, and a new production go/no-go review.
