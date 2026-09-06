# Stage 6 staging-host provisioning evidence

Status: `CODE_REVIEW_PENDING`

- Authority: `infra/hetzner/stage6-staging/`
- Technology: OpenTofu
- Host count: exactly one
- Host name: `codestra-stage6-staging-01`
- Applications deployed: no
- Production state copied: no
- Production credentials used: no
- Remote state: required; not yet configured
- Hetzner token: required as environment secret `HETZNER_CLOUD_TOKEN`; absent
- Host created: no

Populate immutable IDs, checksums, apply-run URL, outputs, and rollback evidence
only after protected apply. Never place tokens, state, or private keys here.
