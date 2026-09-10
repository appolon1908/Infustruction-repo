# Stage 6 source refresh — September 10, 2026

PR #47's remaining CI failure came from 14 main branches advancing beyond the
release lock. GitHub reported no textual merge conflict. This refresh reconciles
the source revisions, signed Middleware artifact, proposed remediation pins and
generated evidence together.

All 23 main heads were read through GitHub and independently fetched into clean,
detached temporary checkouts. Each of the 14 changed heads descends from its
previous locked revision. The comparison URLs, exact revisions and checkout
results are in [source-refresh-20260910.json](../reports/runtime-reconciliation/source-refresh-20260910.json).
The temporary checkouts were removed after evidence capture.

Middleware source `ab6e28769815f2bc60ca5bb52a4f3aa5818f89a5` is bound to
`sha256:d899b182a414eef7c59e66c7fecb38b1161851b66c43d95e19e890a53f8caf58`
by successful [signed release run 34412423980](https://github.com/appolon1908-hue/Middleware-/actions/runs/34412423980).
The original artifact archive, ID `10127811516`, was downloaded and matched
GitHub's SHA-256 `f411640153a9563f844e3aa013349e235e3bfdb5ad117f116cd693a9605ed393`.
Its manifest and Sigstore bundle were copied byte-for-byte. Independent Cosign
v3.0.6 verification passed for the image signature, SPDX attestation and manifest
bundle, with the existing exact signer identity and transparency-log checks.
The clean checkout's Git tree also matches the signed manifest. The manifest
binds the configuration, contracts and migration inputs to this build.

The resolver was rerun read-only on its explicitly checked host, 37.27.128.39.
It recorded 23/23 source matches, 12/23 artifact-class passes, one verified
runtime digest match and zero components eligible for activation. Social Runtime
attestation remains unverified; unresolved artifacts remain failures.

The core-host runtime observations for 65.109.65.169 retain their original
timestamps and observed revisions. In particular, the recorded Odoo addon SHA
remains unchanged; a separate `expected_addons_sha` identifies the proposed
revision. Recorded running image identities, rollback digests and safety
observations are preserved. The proposed Middleware, n8n and Odoo remediation
targets now agree with the new source lock.

The private staging deployment lock is still stale. Source reconciliation does
not establish runtime compatibility, completed migrations, effective write
denial, rollback readiness or successful email delivery. The final source-lock
and activation gates remain FAIL, and staging/production execution remains held.
No service, database, secret, delivery flag, route or monitoring target was
changed by this refresh.

Recheck live authority immediately before any later promotion: a subsequent
merge in any component repository will correctly make the strict head check
fail again. Historical August 31 reports and their signed artifacts remain
available as historical evidence.
