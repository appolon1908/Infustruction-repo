# Klyrow restricted stack operator

`klyrow-stack` is the Infrastructure-owned, fail-closed authority installed at
`/usr/local/sbin/klyrow-stack` as `root:root` mode `0755`. Its only accepted
subcommands are `status`, `rollback-plan`, `preflight`, `plan`, `stage`,
`deploy`, and `rollback`; extra arguments are rejected.

The installer must be run from the exact reviewed Infrastructure commit. The
root administrator separately creates the short-lived, mode `0600` JSON marker
shown by `rollback-plan`; merging this source never creates live approval. The
marker schema and values are validated against the source SHA, current runtime
SHA, backup reference, known-good override checksum, and canonical rollback
fingerprint. No secret belongs in the marker.

The operator owns reconciliation only for Compose project `klyrow`. Existing
fixed-name containers without matching Compose project/service labels block the
operation. PostgreSQL and Postal named volumes are retained. Deployment runs no
SMTP probe and automatically invokes the restricted rollback if health/safety
readback fails.
