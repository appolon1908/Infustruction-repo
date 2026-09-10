# Server 37 Klyrow production controls

These files are the Git authority for the host-side Klyrow release, boot, backup,
restore-test, and rollback controls on Server 37. They contain no credentials or
private key material.

- `klyrow-protected-release.override.yaml` binds all owned workloads to protected
  digest references, injects production secrets only through root-owned files,
  and gives the approved frontend a distinct production identity.
- `klyrow-production-containers` starts and validates the exact production
  container inventory at boot without asking Compose to recreate stale services.
- `klyrow-stack.service` binds that fixed inventory to systemd.
- `klyrow-stack` creates an encrypted application/data/runtime recovery archive,
  validates its checksums, and restores into an isolated no-network target.
- `rollback-digests.json` and the rollback override retain the exact prior source
  and per-service digests without relying on mutable tags.

The overlay is not self-authorizing. Deployment requires the exact protected-main
source SHA, signed GHCR digests, checksummed publisher evidence, a rendered-config
checksum, and a prior-source rollback manifest. Secret values, OpenBao recovery
material, and client private keys remain host-managed and must never be committed.
The mutating rollback action additionally requires the root-only
`ROLLBACK_KLYROW_KNOWN_GOOD` approval marker; `rollback-plan` is read-only.

## Deployed release identity

- Protected source SHA: `da9d85891a4e313748e309aed86662d6c03d26bb`
- Gateway-family digest: `sha256:1b0caed0283f03bf3e1f05e8411ca7e28f30ab42c4b854b570471a22671a740b`
- Web digest: `sha256:7227cf01cf5ac998bf15321c70546c2c8e1e25e9ca2b37f31cb8151f8aa6a6c1`
- Migration digest: `sha256:5065cdaf57586699310ced8a6667ba4006df61f3d5173d2eed559178e69ad6f2`
- Postal provisioner digest: `sha256:d30d3065c5f4a87fc793a422dfd4e66d938b83d9562f9f9b0cb247cf3c704cd8`
- Rendered configuration SHA-256: `185035b6520cec94e68bb182ed31f37c689e3e3ddff70b9f7de1f3b155a6d437`

The former `klyrow-web-candidate` is retained stopped as the exact frontend
rollback artifact. The boot inventory starts only `klyrow-web-production` and
includes the durable provisioning worker introduced by this release.
