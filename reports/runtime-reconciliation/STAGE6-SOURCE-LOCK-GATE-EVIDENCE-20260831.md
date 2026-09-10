# Stage 6 Source Lock Gate Evidence

Captured: `2026-08-31T18:54:22Z`

Historical snapshot: current source and artifact pins are documented in
[the September 10 refresh](../../docs/STAGE6-SOURCE-REFRESH-20260910.md).
The original signed release evidence is retained unchanged.

This is source and read-only evidence. It performed no deployment, restart,
migration, secret change, monitoring activation, production activation, or
Klyrow/Postal mutation.

## Preserved pre-rebase state

The original uncommitted evidence remains preserved at
`/root/stage6-evidence-pre-rebase-20260831T130546Z`.

| Evidence | SHA-256 |
|---|---|
| Original Git status | `7db1598c8e882c5542feac9cd7daf7619331738ddd0e7327b0b6ca829f1d2c19` |
| Original four-file checksum list | `26d2f5b0a4c62d1126b8f86841969243325e9832d5dc3d50d42f1a77c3f9f220` |
| Original uncommitted patch | `a3814b55d62654737ad1da154b0866e76a0ad1cf306bfb12e66d8e1ea12b612f` |
| Original resolved YAML | `01e1ed2cf2fd72c9aadac413cc031784575d7229f99d4d8e4ee2bbe51e283c2b` |

The original branch remains
`release/stage6-stage8-runtime-certification-20260831-rerun` at
`0328efbbd55ea5de32d8f3e4aba8600afb8a68e1`, with the same four untracked
files. The reconciliation branch was created independently from exact
Infrastructure `main` at
`244a743a771d1f93c1445392bb45f8325908ca72`.

## Protected-head refresh

All 23 component repositories were fetched into dedicated detached checkouts.
Every checkout is clean, its `HEAD` equals the lock, and the lock equals the
freshly fetched authoritative `main` head.

Seven heads advanced relative to the Infrastructure evidence base lock:

| Component | Current authoritative `main` | Rollback Git SHA |
|---|---|---|
| Middleware | `9152a04ed8df52269b30d7a9c6b18ef00a0caf75` | `eaf3967ee050a5beb3400ae50fe2ba5fe0ab2a94` |
| n8n | `b620860c04bf0fe6998c5fc25857262aa5c89d74` | `4d35472772f60c5af616ffac1f902d626643d02d` |
| Kong | `961edbf56e29ce78f305273c3efeec386a2bba62` | `3594fe25b8fe36633c1de95a8e485c72f32a60f8` |
| Keycloak | `6ce1806c5d3ba63fd89c3b0168181f944c0d7c4f` | `303e2edef2219c5eb3ac167c309a9717a766d079` |
| SDK | `833b79207b59a8451ea6e7dbfafe8fb64cdb33c0` | `ee8cec5d19cc5c3e03a12f5714031b86b58b4efb` |
| Prometheus | `12b79875cf01033d1a5bd29462fc70bed0e4bbfb` | `eec6ea7d7a63d7debef16de92ef5b6d34395d013` |
| Grafana | `ab06c5c42352a2d14f6b54fe6bf13b6cebdfaca6` | `30b736f98e7bbf16f54280251c6d51a877ff2d8a` |

No newer development or floating head replaced an authoritative `main` SHA.
The exact-head validator re-queries all 23 GitHub refs. Kong and Keycloak are
private, and the repository-scoped workflow token cannot certify them. No
cross-repository secret is exposed to pull-request-controlled code. Exact-head
CI therefore remains fail-closed until private-head verification is provided
by a trusted, non-PR-controlled broker or workflow; the authorized local
`23/23` check is evidence, not a substitute for that required CI gate.
The workflow also runs for merge-queue candidates and on a 15-minute drift
schedule, so an external protected-head advance cannot rely indefinitely on a
stale pull-request result.

## Independent gates

| Gate | Result | Evidence |
|---|---|---|
| Repository integrity | `PASS` | `23/23` authoritative-head matches and clean detached checkouts |
| Artifact provenance | `FAIL_PARTIAL` | `10/23` source-only or immutable artifacts pass; unresolved runtime artifacts remain |
| Runtime read-back | `FAIL_INCOMPLETE_CORE_READBACK` | one fresh OpenBao digest match; fresh core-host inventory remains blocked |
| Activation eligibility | `FAIL` | Middleware staging held, Prometheus review pending, Blackbox pending, production disabled |

`SOURCE_LOCK=FAIL`. Repository integrity passing does not promote the combined
source lock while the other three gates remain incomplete.

## Component classifications

- Source-only: Marketing, AI, Communication, Social Control, SDK, Telemetry,
  and this Infrastructure evidence base.
- Custom signed image: Middleware. Exact-head release run `33427334862`
  produced `sha256:91b91b6ba1c828919c86102806eb2cfe6da1295cd7b4fe34df3121dd0bbff1b2`.
  Independent Cosign verification confirms the image signature, digest-bound
  SPDX attestation, and signed release-manifest bundle against the pinned
  GitHub Actions certificate identity and OIDC issuer.
- Official upstream image plus Codestra config: Odoo, n8n, Prometheus, Grafana,
  Loki, Tempo, Alloy, Node Exporter, cAdvisor, Redis Exporter, Blackbox
  Exporter, Superset, and OpenBao. A class does not pass provenance when its
  immutable upstream digest is still unresolved.
- Unresolved blocking artifact: Social Runtime, Kong, and Keycloak.
- Frozen observed digest: the 22 historical core staging workloads until a
  fresh bounded read-back supplies current container IDs and digest matches.
- Out-of-batch: Klyrow/Postal on `37.27.128.39`.

## OpenBao provenance

The running container is
`389d7605c2a62685e70ac5834121eda9b0919d51eafed51077e51f25749eb4b6`
on `37.27.128.39`. Docker read-back shows
`ghcr.io/openbao/openbao@sha256:5b2486ab0fb90bbc788cc345b0a08616dfb375873ee8be5df3a2fd4d378a67e0`.
Its OCI revision is upstream OpenBao
`ba7ad8861d0578cd4da4f7b9e5a6756d30484f8f`. The separate Codestra
configuration authority remains
`appolon1908-hue/Codestra-OpenBao@5f5e3583585081e450f945440a1fab503bfa8399`.
The digest matches the running upstream artifact, but binding of that runtime
to the locked Codestra configuration is unproven and recorded as drift. The
rollback target is absent runtime plus Nginx backup
`/root/openbao-runtime-backups/20260831T120111Z`.

## Bounded inventory and Klyrow/Postal isolation

The local bounded Docker inventory inspected running container identity,
configured image digest, OCI revision, Compose identity, networks, and named
safety flags. Every Docker read is explicitly bound to the verified local
`unix:///var/run/docker.sock` endpoint; remote contexts and conflicting
`DOCKER_HOST` values are rejected. It found one verified digest match:
OpenBao. This satisfies the nonzero-match floor but not the complete runtime
read-back gate.

The core host `65.109.65.169` still returns
`DENIED: unsupported forced command` for the available bounded credential, so
the 22 Stage 6 core workloads remain frozen historical observations. Their
current container IDs cannot be certified by this run.

Klyrow/Postal is isolated from the Stage 6 source path by a distinct host, a
distinct Compose project, an internal private network, no Middleware host
ports, no declared Klyrow/Postal endpoint in the Stage 6 runtime lock,
`external_effects_enabled=false`, and `production_authorized=false`. The deploy
script creates an inbound Klyrow webhook secret name, but declares no outbound
Klyrow/Postal route. All observed Klyrow/Postal containers were left untouched.

## Held operations

- Private Middleware staging remains held. Its deployment lock still points to
  older digest `sha256:695fa3ce3f50ba4d0ae0784976b946a0a683ca731155e4bd3bd9e90a4670b820`,
  and fresh scoped runtime safety read-back is unavailable.
- The reviewed kernel-maintenance source is present on `main`, but
  `execution_authorized=false`. The owner explicitly withdrew the earlier
  conditional authorization in PR #36 pending package-causality review and
  prohibited reboot, console-access work, kernel changes, and execution of the
  merged plan. No approved window or working console rollback has been
  evidenced. No reboot or host change was attempted.
- Prometheus activation must be a separate PR changing only the private staging
  target from pending to active. Blackbox remains pending and production remains
  unchanged.
- Stage 6 remains staging integration. Stage 7 observability and operational
  readiness is separate. Controlled production activation remains prohibited.

The machine-generated package checksums are in
`reports/runtime-reconciliation/STAGE6-EVIDENCE-SHA256SUMS`.

## Final source-lock reconciliation update

Captured: `2026-08-31T22:10:00Z`

The former core-host access blocker is resolved: the authorized SSH identity
can now run read-only Docker inspection on `65.109.65.169`. Fresh read-back did
not clear the gate. It established the following concrete failures:

1. No identifiable Stage 6 runtime container exists for Marketing, AI,
   Communication, Social Control, or Social Runtime. Social Runtime release
   run `33444745623` subsequently produced immutable digest
   `sha256:8576f49a...` with SPDX and BuildKit SLSA attestations, but no prior
   immutable rollback digest exists and nothing is running.
2. The reviewed Middleware image for source `f6748a58...` and digest
   `sha256:695fa3ce...` is present but unhealthy. Protected `main` is now
   `9152a04e...`; its independently signed candidate is not running.
3. Kong runs an immutable local RepoDigest but is configured by a mutable tag.
   Its database-backed configuration cannot be tied to the current Git
   authority checksum by this read-back.
4. Keycloak runs an immutable vendor digest, but its mounted realm and compose
   checksums differ from the current Git authority. The apply run that reached
   reconciliation failed; later successful runs were check-only.
5. The Stage 6 n8n processes and staging Keycloak/Kong containers are unhealthy.
6. The self-hosted runner user is not a member of the Docker group and cannot
   perform a read-only `docker ps` against the `root:docker` mode `0660` socket.
7. Complete fail-closed safety cannot be established for absent/unbound
   workloads. Missing runtime controls remain unknown, never false.
8. Two credential values entered transient command output because an initial
   sanitizer matched secret-bearing variable names. They are not included in
   Git evidence and require approved rotation before certification.

Downstream gates were not executed and are classified as
`NOT_RUN_ENTRY_GATE_BLOCKED`: BACKUPS, STAGING_DEPLOYMENT, OPENBAO_BINDING,
KEYCLOAK_CERTIFICATION, MIGRATIONS, APPLICATION_HEALTH, KONG_CERTIFICATION,
N8N_BINDINGS, OBSERVABILITY, E2E_STAGING, FAILURE_TESTS, and ROLLBACK.

```text
SOCIAL_RUNTIME_PROVENANCE=FAIL
KONG_PROVENANCE=FAIL
KEYCLOAK_PROVENANCE=FAIL
CORE_RUNTIME_READBACK=FAIL
SAFETY_STATE=FAIL
RUNNER_DOCKER_AUTHORIZATION=FAIL
SOURCE_LOCK_CI=FAIL
FINAL_SOURCE_LOCK=FAIL
PRODUCTION_BUSINESS_WRITES=NOT_PROVEN_DISABLED
NEXT_ALLOWED_STAGE=STOP
```

PR #47 CI read-back: run `33446411176` passed the structural validation job.
Run `33446411259` failed the authority-head job because the PR-scoped
`GITHUB_TOKEN` receives HTTP 404 for the private Keycloak and Kong repositories.
The failure is fail-closed and is not bypassed; a trusted, non-PR-controlled,
read-only credential boundary is still required.
