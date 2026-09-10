# Server 37 private integration gateway release evidence

Generated for `37.27.128.39` on 2026-09-03 UTC. This file contains no secret values, client certificates, customer payloads, or tenant identifiers.

## Protected release authority

- Repository: `https://github.com/appolon1908-hue/codestra-production-platform`
- Protected source: `9ec227d6a2b5c14217d88c33a8cfd4e057486c56`
- Workflow run: `https://github.com/appolon1908-hue/codestra-production-platform/actions/runs/33697779715`
- Workflow result: `success`
- Published subject: `ghcr.io/appolon1908-hue/codestra-private-integration-gateway@sha256:8f963929c600baa03435e9c5d7bc7bfa9af152fe26736ca201c586a7b6c0db6b`
- Local Cosign signature verification: `PASS`
- Local SLSA provenance verification: `PASS`
- Local SPDX 2.3 attestation verification: `PASS`
- Published release evidence checksum-manifest checksum: `2aad1dfbef7bff217757dc28051dfc5e125908896b8cb27e339f9ea2986dad1a`
- Local verification checksum-manifest checksum: `269c8b06252b56fe78f3667c2f7dcd7ded074f039508ab129777f85722e7094a`

## Before state and recovery authority

- Previous source: `a3dbfd6b464d2ba4c130e360f8ad73338bdd9fbb`
- Previous image: `sha256:6d6d8cefa4a32796c85a1d6505d74fefdd2e1646421f387f126a2d0ecd03ed88`
- Root-only recovery bundle: `/var/backups/codestra-operators/private-gateway-rollout-20260903T000922Z`
- Before Compose checksum: `5e604f484dc92943675ddf0cae607e0b707ed91d817cd413e7328c9c4de5ecd2`
- After Compose checksum: `dcb736e65c8cb7f32eab8b72bf775447cedfa03057b6b2bc3ca01bd11e242f54`
- Consistent SQLite backup checksum: `d1f3e0d632779b7a9e23a0db59a6a33ebdd4d697d388e730c96551e5586d1871`
- SQLite backup integrity check: `PASS`

## Controlled promotion and rollback result

- Isolated candidate health and OpenAPI validation: `PASS`
- Exact digest read-back after deployment: `PASS`
- Exact source SHA read-back after deployment: `PASS`
- Non-root user, read-only root filesystem, dropped capabilities, loopback-only host port, and restart policy read-back: `PASS`
- Persistent live SQLite integrity after promotion: `PASS`
- Rollback to the exact prior source and digest: `PASS`
- Forward recovery to the protected source and signed digest: `PASS`
- Persistent live SQLite integrity after the rollback/forward rehearsal: `PASS`

The final runtime is healthy in `shared` mode at protected source `9ec227d6a2b5c14217d88c33a8cfd4e057486c56`. Live carrier submission, generic command intake, and middleware forwarding remain disabled. The public host has no listener for port `18443`; the only direct host binding is `127.0.0.1:18443`.

## Private edge promotion

The live Telnexa private edge was reconciled to the Nginx authority in the same protected source. The obsolete leaf-certificate serial pin and caller-controlled identity ambiguity were removed. The edge now uses its dedicated client CA plus CRL, retains the exact approved client subject, overwrites verified certificate identity and service scope headers, and proxies only to the loopback gateway.

- Root-only edge rollback bundle: `/var/backups/codestra-operators/private-gateway-edge-20260903T002126Z`
- Before Nginx checksum: `390839d0d142e335e722d7127e30eebc68c32314849ff145468a28794bdafca3`
- After/protected-source Nginx checksum: `66c66dab3d1e67c230687af6d58e2fefe32d85e2ec9d44c2d0de9ea5b2d05231`
- Client CRL parse and validity-window check: `PASS`
- `nginx -t` before reload: `PASS`
- Nginx reload and gateway health: `PASS`
- Request without a client certificate after reload: HTTP 400, `PASS`

## Remaining boundary

The Telnexa private Nginx listener rejected a request without a client certificate with HTTP 400. A positive mTLS transaction remains externally blocked because no approved client identity is present on this server. The eight general provider-ingress operations belong to the separately governed `middleware` mode and are not exposed by the reviewed `shared` deployment; adding that topology requires its own protected source review and release.
