# Reusable workflow signing identity repair — 2026-09-10

The approved source-readiness PRs were normally merged for Loki, Tempo, Alloy,
Telemetry, Prometheus, and Alertmanager. Their main publication runs passed source
and secret checks, then failed Cosign verification because the expected certificate
identity named the caller instead of the pinned reusable signing workflow.

Evidence examples:
- Loki run 34478920792, source d914fd53a72ffeb57a63ca39ac761abc285e33bf.
- Tempo run 34478960508, source de5e9d56a0607719facc4341cc95aa175528a69d.
- Prometheus run 34478974564, source a4816e255b5ccac6ad475e52f01e601d9cffcdd2.
- Observed signing identity ends in
  `Infustruction-repo/.github/workflows/reusable-codestra-upstream-deploy-readiness.yml@f509d61a6207c7cd9e5f2562de0c2b32a85b6cca`.

The repair reads GitHub's metadata for the current run using the invocation token.
It requires the exact run ID, caller repository, and checked-out source SHA, then
resolves exactly one allowlisted reusable workflow pinned to a full commit SHA.
The resolved SHA must equal that pin. Cosign still requires the exact certificate
identity and GitHub's fixed OIDC issuer; no wildcard, skip-verification switch, or
identity derived from an untrusted release artifact is accepted. The resulting
manifest records the signing workflow identity alongside source and bundle hashes.

After this fix is independently reviewed and merged, update each consumer's
immutable `uses:` reference to the accepted infrastructure commit and add
`actions: read` to its caller workflow permissions. GitHub prevents a reusable
workflow from elevating permissions beyond its caller. Re-run the release from
the accepted source, verify the resulting signature and source binding, then
complete the existing artifact, staging, backup, restore, and production gates.
Do not deploy a source archive as if it were a runnable monitoring image.

Ten regression tests exercise the embedded production resolver, including absent,
mutable, ambiguous, wrong-repository, wrong-run, wrong-source, and mismatched-pin
evidence. Tests perform no network requests, signing, release upload, or deployment.
