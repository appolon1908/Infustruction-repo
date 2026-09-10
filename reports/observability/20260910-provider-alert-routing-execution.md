# Provider alert routing and observability execution — 2026-09-10

Evidence refreshed at 14:09 UTC. The full provider-to-Middleware chain is **not complete**.
Core routing repairs are live; provider transport, canonical Middleware activation,
and the remaining production services are still gated.

## Priority status

| Priority | Verified result | Remaining work |
| --- | --- | --- |
| 1 — alerts | Core warning/fallback routing and Caddy metadata repaired; 38/38 core scrape targets up; 41 webhook deliveries and zero failures at readback. | Accept provider source, provision paired mTLS, deploy the protected/signed canonical Middleware incident API, and prove durable firing/replay/resolution ingestion. |
| 2 — Grafana | Confirmed graf.codestra.media resolves to the provider but its certificate fails hostname verification. Existing Klyrow Grafana belongs to app.klyrow.com/ops/. | Accepted canonical Grafana/edge release, matching certificate, Keycloak login and dashboard access proof. |
| 3 — releases/exporters | Infrastructure signing-identity fix PR120 merged; six consumers now have verified signed source commits and green CI. | Required independent reviews, actual signed release verification, staging/rollback evidence and missing provider exporters. |
| 4 — logs/traces | Existing web host Loki/Alloy running; Grafana provisions a Loki data source. Loki /ready recovered from an observed 503 to 200; aggregate query found 1,868 log entries in the preceding five minutes. | Provider Alloy/OTel/Loki/Tempo deployment and authenticated Grafana log/trace readback. No Tempo service was found on the audited web/provider runtimes. |
| 5 — Superset | Confirmed supe.codestra.media certificate hostname mismatch; no provider Superset runtime. | Accepted signed release, HTTPS, Keycloak and a constrained read-only database role/connection. |
| 6 — OpenBao | Existing provider instance remains uninitialized; no initialization/unseal performed. | Offline custody and public recipient keys, production runtime/security/storage/HA prerequisites, swap/recovery/audit/TLS evidence. Existing backup encryption does not designate OpenBao custodians. |

## Live core repairs

- Alertmanager [PR21](https://github.com/appolon1908-hue/Codestra-Alertmanager/pull/21)
  merged as 7d81c848ad7264a84eb33423924c6f81a84febee.
  Production warning alerts select secondary; otherwise unclassified alerts
  retain quarantine and also reach secondary operator review. Critical primary
  and recovery routing and existing authentication are preserved.
- Prometheus [PR62](https://github.com/appolon1908-hue/Codestra-Prometheus/pull/62)
  merged as f0f27f1f9ecad6a4b7e92a35b79a779ed5d408d4.
  All 12 existing Caddy alert expressions/durations remain unchanged; explicit
  production/service/business/owner labels and required annotations were added.
  Natural CaddyMTLSProbeFailure alerts now select primary and recovery.
- Alertmanager configuration SHA-256:
  91193e039cd5b19843822368b72421ee34527999a8c9e3e0b15dbb7f861bcbf1.
- Caddy rule file SHA-256:
  c2fde35c71fd0bcf11f46ee42e334862d8dc711e7c5549948f6397c4a042c32f.
- Native amtool routes and promtool rule/healthy/firing tests passed before
  in-place file updates and reload. Current images/state volumes were retained.
- Encrypted Alertmanager state backup and isolated no-delivery restore passed.
  Ciphertext SHA-256:
  3a3156883439fde89f3e325042504ad4785f4a60ad791dfd2f0195f12c32b0b9.
  A verified ciphertext copy exists off host on the provider. No private key was
  exported. Core recovery evidence is under
  /var/backups/codestra/alert-routing/20260910T132500Z.

The existing authenticated monitoring receiver stores body hashes and routing
audit in SQLite. Its 2xx responses are not proof of canonical Middleware incident
creation. The 41 delivery count above applies to this existing receiver path.

## Complete source preparations for the paired transport

| Repository/PR | Exact source | Result |
| --- | --- | --- |
| [Klyrow PR110](https://github.com/appolon1908-hue/klyrow.com/pull/110) | 101adb79ba1bc2026d1ba9edfd059d02a419c236 | All 15 reported checks complete successfully or intentionally skipped; merge remains blocked. |
| [Telnexa PR32](https://github.com/appolon1908-hue/telnexa/pull/32) | 1b1ba34824c0bef065992e49c3e16e97669d5c73 | Five checks pass; required review outstanding. |
| [Middleware PR224](https://github.com/appolon1908-hue/Middleware-/pull/224) | 3cabe6ccb3ff1a25f4f206437237f10188de75cb | 38 native API regression tests and 27 contract tests pass; required CI succeeds except protected trust gate. |
| [Alertmanager PR22](https://github.com/appolon1908-hue/Codestra-Alertmanager/pull/22) | 762ac7e665739876133e9b39177142a9c010eb1a | Merged to development as 51dfd5fb5526f7a66a9ed811fbb27ff39d371786. |
| [Prometheus PR65](https://github.com/appolon1908-hue/Codestra-Prometheus/pull/65) | c51df10fe64a2b97c6c03a20a41927d46852998c | Merged to development as 1b2a718dc81987ff453f378d8477877153528289. |

The provider overlays add strict mTLS to 10.40.0.1:19093 using server identity
alertmanager.core.codestra.internal, separate client file mounts and complete
routing/host labels. Their default configurations remain unchanged.

The Alertmanager compatibility overlay preserves the existing image/state and
binds native TLS only on 10.40.0.1:19093. The paired core Prometheus preparation
migrates its existing 10.253.127.3:9093 client too, preserving rules, labels and
unrelated jobs. Applying the server overlay alone would break the old HTTP path.

Exact running binaries validated both generated candidates. An isolated
no-delivery Alertmanager accepted an authenticated native mTLS configuration
read and rejected a connection without a client certificate. Both merged Compose
checks preserve original image, command/state identity and existing mounts.
No live 19093 listener or production alert transport certificates were installed.

Middleware native mode supports the principal six receiver names, bounded
batches, static/file-backed headers and derived transport idempotency. Existing
Keycloak client/tenant/audience/scope and semantic incident conflict enforcement
remain. It fixes native Alertmanager compatibility without enabling delivery.
The currently running Middleware image does not include the canonical incident
API modules or endpoint.

The protected-main trust gate rejects its own unchanged workflow:
candidate and protected main b02f29f84e801fb38592be98624790892607964b
have identical trust files. The error is
"candidate trust workflow is not approved by protected main".
Existing remediation PRs [215](https://github.com/appolon1908-hue/Middleware-/pull/215)
and [219](https://github.com/appolon1908-hue/Middleware-/pull/219)
are approved but still have failing gates. This task did not weaken that trust
root, manufacture statuses or use an administrator merge.

## Verified signing workflow consumers

Infrastructure [PR120](https://github.com/appolon1908-hue/Infustruction-repo/pull/120)
was independently approved and merged as
92f731039333846ef067f1ddbcb276463a92d9ba. Each caller below pins that exact source
and grants actions: read for current-run identity verification.

| Component | Review | Verified source commit |
| --- | --- | --- |
| Loki | [PR36](https://github.com/appolon1908-hue/Codestra-Loki/pull/36) | 5c83bfb796b9646f479de34870ac6f33f7573d0d |
| Tempo | [PR29](https://github.com/appolon1908-hue/Codestra-Tempo/pull/29) | f7a8c81a5ab9959d8d434536d50e39369d2467da |
| Alloy | [PR33](https://github.com/appolon1908-hue/Codestra-Alloy/pull/33) | 5e35e0608257d5cc5b435e9840de8c877a319b80 |
| OpenTelemetry | [PR53](https://github.com/appolon1908-hue/Codestra-Telemetry/pull/53) | 7345b3406a3b33068b3209823c44e3454d97afe1 |
| Prometheus | [PR64](https://github.com/appolon1908-hue/Codestra-Prometheus/pull/64) | 4822e97b91a63a1e7d7c9fde9b69d7dd98419254 |
| Alertmanager | [PR24](https://github.com/appolon1908-hue/Codestra-Alertmanager/pull/24) | 6510b4805cb96b82ce536382357d10784d4c9da1 |

All six have green CI and require independent review. The verified commits were
created through GitHub using the authenticated author; each tree was checked
identical to the initial proposed tree. The initial unsigned PRs were closed as
superseded. No source-signature requirement was disabled.

Prometheus PR64 accepted auto-merge enrollment. The other repositories, Klyrow
and Telnexa reject auto-merge because that feature is disabled; their settings
were preserved.

Existing exporter readiness PRs have green checks and approval, but unsigned
source commits block protected-main promotion (confirmed by Node Exporter PR31
and its required-signatures rule). Normal merge and squash attempts were refused.
They need properly signed source and renewed review where required, not bypasses.
Grafana PR27 still requires review; its older canonical PR25 has merge conflicts.
No release digest or readiness flag has been fabricated.

## Next operational order

1. Clear the protected Middleware trust-root repair and required source reviews.
2. Build and verify the actual Middleware image and monitoring artifacts against
   accepted source; satisfy staging, backup/restore and rollback gates.
3. Provision dedicated server/client certificate identities. Apply the paired
   Alertmanager/core Prometheus transport, then provider overlays. Require core
   and both provider destinations active and all existing targets up.
4. Activate canonical Middleware ingestion with delivery disabled; verify a
   durable incident ID, replay deduplication and resolution. Only then certify
   the complete provider alert path.
5. Continue canonical Grafana HTTPS/Keycloak, exporters, provider logs/traces and
   Superset read-only access using accepted artifacts.
6. Complete an explicit OpenBao custody plan and prerequisites before any
   initialize/unseal operation.

Business email/SMS/PSTN and other business mutation flags were preserved.
