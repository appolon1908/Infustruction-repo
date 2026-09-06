# Server B shared status — 2026-09-05

The timestamped shared record is [status.json](status.json). Its values distinguish
direct observations, coordinated reports, tests, not-run checks and blockers.
This packet is not a deployment or account-creation authorization.

Server B is `static`, `65.21.67.207` / `10.40.0.2`, running under the existing
restricted `codestra-admin` administrative path. On-disk current source is
`a6bc9de3b010e3b2978425d3f787ce7f61826c67`. The source archive checksum matches
`SOURCE.SHA256`; it is not an OCI digest. Current-root RELEASE_MANIFEST.json and
BUILD_INFO.json were not found. The process interpreter path still refers to
`b7ffe4d60a364f00411852aa327e2c424fb2f56a`, and live `/version` reports only
`0.1.0`: full process/source equivalence remains unverified.

Health and readiness passed, writes are false, and the observed Asterisk,
MariaDB, VICIdial and restricted-adapter units remained active/enabled. No
production service, configuration, account, grant, firewall, SSH or feature gate
was changed. Authorized inspection commands generated their normal audit logs.

## Source and release state

- [VICIdial PR #19](https://github.com/appolon1908-hue/Vicidialer-Codestra/pull/19)
  merged at `d2165e0615953de296dc80edab989f17137f7f45`.
- Protected run `33960984914` failed because Docker context was the nested
  Dockerfile directory while COPY needed the repository root. It did not reach
  scanning/publishing/signing; the failure was not a libuuid scan finding.
- The coordinated context fix merged as PR #20 at
  `c3f34f4f5adf23c1175c3c18a039a958f43ed4e3`. Its run `33962326270`, job
  `101296261576`, cleared COPY and failed the UTC-Z build timestamp validator.
- [Infrastructure PR #85](https://github.com/appolon1908-hue/Infustruction-repo/pull/85)
  now contains the coordinated UTC correction at
  `13916e5d3b17145351d771e16a9c4ef45fc82dfc`.
  [VICIdial PR #22](https://github.com/appolon1908-hue/Vicidialer-Codestra/pull/22)
  owns its consumer pin and administrative packet. They are not an installed
  production release. No new signed protected-source OCI digest is verified.
- [Provisioning PR #28](https://github.com/appolon1908-hue/codestra-provisioning-service/pull/28)
  is open at `d49e54459f4a489f33d74b87b4f9d4c03785e543`. The coordinated code
  preserves SIP's legacy contract, validates the canonical VICIdial payload,
  and requires exact disabled readback.

Independent follow-ups adopt the coordinated implementations unchanged:
[infrastructure PR #95](https://github.com/appolon1908-hue/Infustruction-repo/pull/95)
adds actual workflow-shell regression coverage, including offset-to-UTC build
metadata, and [provisioning PR #29](https://github.com/appolon1908-hue/codestra-provisioning-service/pull/29)
adds nine SIP lifecycle and browser rotation/revocation regressions. The combined
provisioning tree passed 108 tests and lint under Python 3.12.14. Infrastructure
shell tests passed, including a demonstrated failing timestamp case before the
repair. Tests use synthetic transports/fake Docker, not production requests.
Independent reviewer `kazan555` was requested; no renewed approval is claimed.
Redundant consumer PR #21 was closed in favor of coordinated PR #22.

## Backup, runtime and authority

The already completed backup `20260905T103726Z` passed fresh authorized validation.
No new backup was started. The restore log path and checksum were obtained via
`collect-evidence`. PR #22's packet reports isolated restore PASS, zero public
ports/residual resources and a confirmed off-server copy. This session could not
read the protected restore log contents, so those results remain **reported**,
not independently reverified. Backup validation alone is not restore proof.

Server A's supplied revision/digest and disabled flags remain historical. An
authorized access path and actual service/container discovery were not available
here. The paired preflight records those limitations and the previous Server B
source/backup tuple; missing candidate digests are null, not placeholders presented
as verified artifacts. The combined rollback tuple is not certified.

The readable Apache include strips `/restricted-vicidial/` before forwarding to
`127.0.0.1:8097`. The v2 signature binds `/v1/agents/provision-disabled`, not the
ingress prefix. No authenticated provisioning request was sent.

The merged runbook's protected expiring policy, exact user/role/payload/release
binding, backup binding, dedicated scope, v2 signing and separate database
grant/revoke prerequisites are not instructions to enable them. Runtime policy
and database grants are unverified; the current authorized operator exposes no
grant or provision-user operation. Level 9 is not approved for Ralph by this
handoff. Ralph was reported not created and was not queried or created here.

SentinelX remains separate: zero connected hosts were observed; no installation
or enrollment was performed. Root access and the prior script/upload policy
enforcement gap remain unresolved. No enrollment token was requested or handled.

## Completion gates

Review/protected promotion, successful immutable builds and artifact verification,
fresh Server A runtime inspection, Server B process/manifest reconciliation,
independently accessible restore proof and exact backup artifact binding remain
open. Actual account creation additionally requires the separately approved
request, effective bounded policy, database permissions and authorized execution
interface. No generic SQL/shell/API workaround or global write enablement was used.

## Approval follow-up

The [approval follow-up](approval-followup.json) records a newer source snapshot.
The owner approved continuation; GitHub still requires current-head reviews and
checks. A normal PR #96 merge attempt was rejected by repository rules; no bypass
was used. PR #95 is closed because the coordinated PR #85 incorporated its tests.
PR #29 now adopts PR #28 canonical browser identity changes; the combined suite
passes 110 tests and Ruff. Runtime observations above were not repeated, and no
production changes were made.

## Release blocker fixes

The [release-fix follow-up](release-fix-followup.json) records PR #23 for
runtime-readable policy generation and PR #29 for strict disabled-state
readback. Local tests passed (17 policy tests; 117 provisioning tests plus
Ruff). Renewed review was requested. No production action occurred.

## Final integration checkpoint

The [final integration record](final-integration.json) supersedes source status
above while preserving historical observations. PR #96 is repaired and merged;
PR #29 preserves unique tests against the newer canonical code (119 passed plus
Ruff). PR #23 now addresses restrictive umask after adopting coordinated policy
cleanup. Current-head review and protected release proof remain outstanding.
Server B was rechecked at 11:59:28 UTC: ready, writes false, live version 0.1.0;
running source/digest remain unverified. No production changes occurred.

## Verified-release continuation (12:07:50 UTC snapshot)

The [verified-release continuation](verified-release-continuation.json) records the
one-owner branch topology, finding closure evidence, exact-head CI, and remaining
review gates as of its recorded timestamp; it does not supersede later snapshots.
It also records a failed key-only SSH authorization attempt without promoting any
prior runtime value: Server B running source remains blocked, Server A remains
historical/unverified, restore proof remains `REPORTED_PASS`, the paired rollback
tuple remains uncertified, and the protected release is `NOT_RUN` in this snapshot.
The Server B observation is an archive checksum only, not proof of installation,
running-source equivalence, or an OCI image digest.

VICIdial PR #23 was closed after its restrictive-umask regression was incorporated
into canonical PR #22. SentinelX remains separately blocked by the installation-policy
finding recorded in production-platform PR #269; `SENTINELX_SKIP_SUDO=1` does not
disable the script/upload handlers. No deployment, restart, enrollment, grant,
account, activation, call, live-call-control, or external-delivery action occurred.

## Latest release verification refresh

The [release verification refresh](release-verification-refresh.json) records
the latest PR and protected-run observations. No verified paired release is
established: canonical PRs #22 and #28 remain unmerged, and the latest protected
VICIdial run failed. The older successful provisioning immutable build is
identified separately and is not substituted for this integration. PR #23 is
closed after coordinated incorporation; PR #29 retains unique tests. Artifact,
signature and deployment fields remain unverified. Runtime was not rechecked
during this documentation-only update.
