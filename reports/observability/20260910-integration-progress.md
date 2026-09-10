# Observability integration progress — 10 September 2026

Core monitoring is deployed and healthy: **38 of 38 targets** were up at 13:27 UTC. Provider observability, certificates and SSO remain incomplete.

The [application monitoring change](https://github.com/appolon1908-hue/codestra-production-platform/pull/338) is merged and live. Odoo, n8n, Middleware and the VICIdial adapter worker all return successful private health probes. The VICIdial check covers the core adapter worker, not remote Asterisk or calls. Prometheus reloaded successfully without an image change or restart. Blackbox was recreated to apply its already accepted backend/edge network configuration. Backup locations and exact source identities are in the companion JSON.

| Component | Verified progress | Remaining requirement |
| --- | --- | --- |
| Shared release signing | [PR #120](https://github.com/appolon1908-hue/Infustruction-repo/pull/120): 9 checks pass; exact immutable reusable signer identity correction pushed | Independent review, accepted commit, consumer repins and caller actions:read |
| Grafana | PR #25 conflict resolved locally; 15 tests and both Compose renders pass | GitHub rejected the push because the provider OAuth credential lacks workflow-write scope; then fresh protected review |
| Tempo | [PR #27](https://github.com/appolon1908-hue/Codestra-Tempo/pull/27) merged as 234cae81d2b760044409e3965e28c00423a023ca; 10 tests and both real PR image builds pass | Protected source checks passed; release retry failed on two HIGH gRPC findings before publication |
| Loki | [PR #34](https://github.com/appolon1908-hue/Codestra-Loki/pull/34) merged as f15b898a16faa4dd25ca071e50f51792fa8bfc44; 11 local tests and both CI checks pass; bundle review finding closed | Authenticated native API boundary, upstream source restoration/verification and accepted signed bundle |
| Alloy | PR #30 has seven green checks and is ready for review | Fresh independent approval is explicitly required before merge; promotion chain and release are not complete |
| Superset | Failed image release diagnosed | Compatible dependency/base update and a passing vulnerability scan; no scan waiver applied |
| Grafana/Superset HTTPS | Both names resolve to 37.27.128.39; nginx default certificate mismatch identified | Matching service deployment, virtual hosts and certificates |
| Keycloak/OpenBao | Desired identity contract identified; no live identity mutation | Existing admin inventory authentication returned HTTP 400; dedicated clients/flows/secrets and approved offline recovery-key custody remain unresolved |

The Grafana workflow resolution is included as a **review-only workflow record** beside this report. It is not installed or executed, and the Grafana remote branch has not been updated.

Loki's official locked upstream tree was fetched and compared. Seven entries are absent from the imported source, including three Logstash Ruby files. The exact entries and tree identities are in the JSON. This audit did **not** restore those entries or close that review finding.

No Loki, Tempo, Alloy, OpenTelemetry collector or Superset provider runtime was deployed during this work. Existing Klyrow Grafana remains a separate deployment. No business call, mail, SMS or workflow was triggered.

## Release verification at 13:37 UTC

[Tempo release retry 34483210673](https://github.com/appolon1908-hue/Codestra-Tempo/actions/runs/34483210673) passed source/manifest authority and the source secret scan. The candidate image scan then rejected gRPC v1.82.1 for CVE-2026-84304 and CVE-2026-84445 (two HIGH findings). Version v1.83.2 covers both reported fixes. Registry publication, signatures and release-label creation were skipped; no provider runtime was changed. The existing upstream-sync PR #26 still imports v1.82.1, so that PR alone will not clear this gate.

The native Telemetry configuration-bundle publisher also retains its separate caller-versus-reusable signing-identity defect. It needs a source correction and accepted immutable consumer repins; Infra PR #120 fixes a different shared publisher. No native publisher workflow was changed in this audit.
