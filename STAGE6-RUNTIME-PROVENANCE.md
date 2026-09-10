# Stage 6 Runtime Provenance Reconciliation

Captured: 2026-08-31T22:10:00Z. This was a read-only source-lock mission. No deployment, migration, workflow activation, monitoring-target activation, failure injection, or production canary occurred.

Historical snapshot: the authority revisions below describe that capture. Current
source and artifact pins are recorded in [the September 10 refresh](docs/STAGE6-SOURCE-REFRESH-20260910.md).
That refresh does not recertify these core-host runtime observations.

## Decision

`RUNTIME_PROVENANCE=FAIL`

`RUNTIME_READBACK=FAIL`

The core host is reachable and Docker read-back now succeeds, replacing the former access-unknown condition with concrete evidence. The evidence does not support promotion.

## Component findings

| Component | Authority | Artifact model | Runtime evidence | Result |
|---|---|---|---|---|
| Middleware | `9152a04ed8df52269b30d7a9c6b18ef00a0caf75` | source-built image | Reviewed older candidate `f6748a58...` / `sha256:695fa3ce...` is running but unhealthy; current authority candidate is not running | FAIL |
| Marketing | `460ff98f...` | source-built application candidate | No identifiable Stage 6 container | FAIL |
| AI | `94d990e2...` | source-built application candidate | No identifiable Stage 6 container | FAIL |
| Communication | `0ee0dcbd...` | source-built application candidate | No identifiable Stage 6 container | FAIL |
| Social Control | `7bc0dd9e...` | source-built application candidate | No identifiable Stage 6 container | FAIL |
| Social Runtime | `4f7817f6...` | source-built image | Release run `33444745623` produced digest `sha256:8576f49a...`, SPDX 2.3 SBOM, and BuildKit SLSA provenance; no prior rollback digest or running container exists | FAIL rollback/runtime |
| Odoo | `3eeb17f8...` | addon/module plus vendor image | Vendor digest is immutable; mounted addon paths are not Git checkouts and do not match the lock | FAIL |
| n8n | `b620860c...` | workflow/config authority plus vendor image | Immutable vendor digest matches; all four Stage 6 processes are unhealthy and runtime config-to-Git binding is unproven | FAIL |
| Kong | `961edbf5...` | vendor image with Git configuration | Local RepoDigest is immutable, configured image reference is mutable, and DB-backed config cannot be tied to authority checksum | FAIL |
| Keycloak | `7aef62a0...` | vendor image with Git configuration | Runtime vendor digest is immutable, but mounted realm/deployment checksums differ from current Git authority; prior apply run failed | FAIL |

## Kong chain

- Authority SHA: `961edbf56e29ce78f305273c3efeec386a2bba62`
- Authority configuration checksum: `sha256:a25c619b252922b6c6f8ca99fd0f2874e03c987da45a2adc1f70bc57b7c33eb8`
- Runtime image RepoDigest: `sha256:9cb0429e4641d29189118b20ef0a195569b9d65ef0536bc57907797874071689`
- Runtime configured reference: mutable `kong/kong-gateway:3.14.0.1-ubuntu`
- Runtime config binding: unproven; the gateway is database-backed and the runtime config authority paths are not readable by the inspection identity.

`KONG_SOURCE_TO_RUNTIME_BINDING=FAIL`

## Social Runtime chain

- Source SHA: `4f7817f6c6d1bb38fa7d85bb1656eb41865283d5`
- Build workflow run: `33444745623`
- Build job: `99661206524`
- Image: `ghcr.io/appolon1908-hue/social.codestra.co`
- Image digest: `sha256:8576f49ae136c87efbd87827958a6b3b70e4fc597a3eedbacdaddbd7d3474e87`
- Evidence manifest checksum: `sha256:4a2555f29c332bf14a651feba0797fe2831949283b8aed09bd48c10cc2946b7b`
- SBOM: PASS, SPDX 2.3 OCI attestation
- Provenance: PASS, BuildKit SLSA statement binds the Git source URL, exact SHA, Dockerfile, build run, and digest
- Signature: `NOT_SUPPORTED_WITH_EXPLICIT_EVIDENCE`; the workflow emits OCI SBOM/provenance attestations but does not perform Cosign signing and does not have GitHub `attestations: write`
- Runtime version label: source/build version `4f7817f6c6d1bb38fa7d85bb1656eb41865283d5`
- Rollback digest: unavailable because this is the first reviewed immutable release
- Runtime: no Social Runtime Stage 6 container is present

`SOCIAL_RUNTIME_SOURCE_TO_IMAGE_BINDING=PASS`

`SOCIAL_RUNTIME_PROVENANCE=FAIL` because rollback and artifact-to-runtime evidence remain mandatory.

## Keycloak chain

- Authority SHA: `7aef62a020c87ffcbf0fbb2f8c4890a8e9d13098`
- Runtime image: `quay.io/keycloak/keycloak`
- Runtime image digest: `sha256:2eb3cd316835c990e69e26ade292ffa78f6fb0db7d5fc6377463c162e1979ac0`
- Authority realm checksum: `sha256:ffa948f9d77bf45c5a85bd856294a142d708b6138e060a3c1d3a4173f7eac593`
- Runtime realm checksum: `sha256:801296d239ec8d6b3ee4352081abe9c7dd2ce1ec648c35dbf8a03c97933c9ddd`
- Authority deployment checksum: `sha256:ee1c96287e58e46e87af2aef55b932b886f006b62e976c4005c4daf1b35517ce`
- Runtime compose checksum: `sha256:6920f305b39dc5b9297edab849ffa866752956ab733dbb1137ec90f0fe662d75`
- Apply workflow run `33438086421` reached reconciliation but failed with HTTP 403; later successful runs were check mode only.

`KEYCLOAK_SOURCE_TO_RUNTIME_BINDING=FAIL`

## Runner authorization

- Runner service: `actions.runner.appolon1908-hue-Keycloak.kazan555.service`
- Service user: `keycloak-deploy`
- Service group and supplementary groups: unset
- Runtime identity: `uid=988(keycloak-deploy) gid=987(keycloak-deploy)` with no Docker group
- Docker socket: `root:docker`, mode `0660`
- Read-only `docker ps` as the runner user: denied

`RUNNER_DOCKER_AUTHORIZATION=FAIL`

No Docker permission was changed and the runner was not switched to root.

## Source-lock CI read-back

PR #47 produced structural-validation run `33446411176`, which passed. The
authority-head validation run `33446411259` failed because its PR-scoped token
cannot query the private Keycloak and Kong repositories (HTTP 404). This is an
expected fail-closed credential-boundary blocker, not a runtime test failure.

`SOURCE_LOCK_CI=FAIL`

## Rollback readiness

Existing current images remain available for Middleware, n8n, Odoo, Kong, and Keycloak. Rollback configuration cannot be certified for Kong/Keycloak, and no current runtime or rollback runtime exists for Marketing, AI, Communication, Social Control, or Social Runtime. Therefore component rollback readiness is incomplete.

## Evidence hygiene incident

An initial runtime sanitizer used a broad name pattern and emitted two credential values in transient command output. Those values are excluded from Git evidence. Rotation through the approved secret authority is required before a future passing gate.
