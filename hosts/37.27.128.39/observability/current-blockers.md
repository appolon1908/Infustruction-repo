# Current blockers

1. Independent reviewers must approve the product API and promotion PRs.
2. Repository owners must protect the complete release branch chain and attach
   exact-production-head CI; local validation is not a substitute.
3. The proxy/TLS owner must publish reviewed matching certificates and private
   access boundaries for the eleven failing hostnames.
4. The Klyrow owner must resolve the two firing critical delivery alerts.
5. Release owners must publish digest-only signed images with SBOM, provenance,
   clean vulnerability evidence, and exact source revision labels.
6. Recovery owners must provide state snapshots, encrypted off-host backups,
   isolated restores, and measured rollback for every stateful component.
7. OpenBao recovery custodians must approve an initialization or recovery
   ceremony; no unseal shares or root authority may be invented.
8. Identity owners must provide approved OIDC/mTLS service and canary identities
   for negative and cross-business tests without exposing their values.
9. Alertmanager and PostgreSQL Exporter require complete protected source,
   image, runtime, network, API, recovery, and rollback evidence; registry
   membership alone does not establish any of those operational gates.
10. The Node Exporter owner must replace or formally retire the unmanaged host
   package service and approve an explicit collector allowlist.
