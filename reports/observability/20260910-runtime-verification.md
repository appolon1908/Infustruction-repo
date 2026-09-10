# Monitoring runtime verification — 10 September 2026

**37.27.128.39 is not a fully deployed or integrated production observability server.**

The live audit covered all 14 component roles and the central monitoring connection
to 65.109.65.169. Evidence below is runtime observation, not a claim that passing
source checks constitute production certification.

## Completed live repair

[Alertmanager PR #20](https://github.com/appolon1908-hue/Codestra-Alertmanager/pull/20)
merged as `99bb8e2075c925634100e8ed4e60dbfac4b9f0f8`.
The effective core configuration referenced a bearer credential and staging
receiver URL absent from the container. The existing verifier only inspected
mounts that already existed and therefore missed both omissions.

The source verifier now checks configured receiver/authentication/TLS file
references. A compatibility override supplies the two existing files as read-only
mounts. Seventeen unit tests and all three GitHub checks passed. The merged
configuration comparison proved only those two mounts were added.

The repair was applied only to core Alertmanager after a protected state backup,
encryption with the existing backup recipient, verified encrypted copy to the
provider server, and a successful isolated restore using the exact current image
with networking disabled. The current image, state volume, route policy and
credential values were preserved.

At 12:13:22 UTC, six configured file references were readable under the existing
non-root identity, readiness returned HTTP 200, and **10 naturally occurring
webhook notifications succeeded with zero failures** since recreation.
No synthetic notification or business-delivery flag change was used. Webhook
transport success is not proof of downstream email receipt.

## Provider component inventory

| Component | Status on 37.27.128.39 | Live evidence |
| --- | --- | --- |
| grafana | PARTIAL | Klyrow Grafana health HTTP 200/database ok; provisioned Prometheus reachable from Grafana container with sum(up)=2; canonical graf.codestra.media TLS verification fails (curl 60). Authenticated browser session not verified. |
| prometheus | PARTIAL | Klyrow 2/2 and Telnexa 3/3 targets up with fresh samples. Both instances have zero active Alertmanager destinations. Klyrow has two firing delivery-stalled alerts. |
| alertmanager | MISSING | No local container or host service found. Central core instance repaired separately. |
| loki | MISSING | No local container or host service found. Host port 3100 belongs to Kyqra crawler, not Loki. |
| tempo | MISSING | No local container or host service found. |
| opentelemetry | MISSING | No local collector container or host service found. |
| alloy | MISSING | No local collection agent container or host service found. |
| node-exporter | PARTIAL | Two provider exporter containers are scraped successfully; host exporter listens on loopback 9100. Three instances need reviewed collection ownership to avoid duplicate series. |
| cadvisor | MISSING | No local container or host service found. A separate core instance is scraped successfully. |
| postgres-exporter | MISSING | No provider exporter found. Core PostgreSQL exporter reports pg_up=1 for its configured database. |
| redis-exporter | MISSING | No provider exporter found. Core Redis exporter reports redis_up=1 for its configured database. |
| blackbox-exporter | MISSING | No provider exporter found. Core exporter has eight successful HTTPS/TLS probes and two failing application readiness probes. |
| superset | MISSING | No local container or host service found; supe.codestra.media TLS verification fails (curl 60). |
| openbao | BLOCKED | Live health HTTP 501, initialized=false, sealed=true. Container version/liveness check says healthy. Offline custody, release and production preflight remain unresolved; no initialization/unseal performed. |

All 53 provider containers were inventoried, along with host services/listeners.
Six monitoring containers were running: two Prometheus, two Node Exporter,
Klyrow Grafana and uninitialized OpenBao. Port 3100 belongs to Kyqra crawler.

## Connections and remaining faults

- Klyrow Prometheus: 2/2 fresh targets; no Alertmanager destination. Delivery-stalled event and usage alerts are firing locally.
- Telnexa Prometheus: 3/3 fresh targets; no Alertmanager destination.
- Grafana container to its provisioned Prometheus endpoint: query succeeds with two up targets. Authenticated UI login and dashboard queries through Grafana's API remain unverified.
- Core Prometheus: 34/34 fresh scrape targets. PostgreSQL and Redis report their actual upstream status as 1.
- Core Blackbox: eight HTTPS/TLS probes succeed, but mail API and reseller portal readiness probes return `probe_success=0`. The exporter scrape itself remains up, so scrape counts cannot certify application readiness.
- Core alert routes still send Caddy alerts lacking environment/service labels and the production disk warning to the fallback receiver. Successful webhook transport does not establish correct incident routing.
- No log ingestion, trace ingestion, log/trace correlation or Superset dataset check can pass while the relevant provider services are absent.

## Release blocker and next deployment work

Current infrastructure authority
`ee47a144ec4c9144ff064336743e6b215f559582` records
`releaseReady=false` and `deploymentEnabled=false`.
The shared manifest has **zero accepted image digests across 14 components**.
All 14 component GitHub release lists were also empty when queried. This does
not assert that no OCI artifact exists; it establishes that the accepted
cross-component deployment bundle is not available in the inspected authority.

Publish and verify accepted component releases through their protected
workflows, reconcile the shared lock with actual image/configuration digests and
rollback identities, then use the installation order in the infrastructure
runbook. Install the missing private services; connect provider Prometheus to
the authenticated alert path; certify logs, traces, exporters and UI identity/TLS.
OpenBao custody and initialization remain separately blocked.

User authorization to complete the deployment is already recorded. Missing
release identities, credentials/custody references and protected approvals must
be satisfied with real evidence; repeating blanket approval is not the remedy.

Machine-readable evidence:
[20260910-runtime-verification.json](20260910-runtime-verification.json).

No provider application was restarted or reconfigured by this audit. The
provider host received the protected encrypted Alertmanager backup only.
