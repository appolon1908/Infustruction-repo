# Monitoring release follow-up — 10 September 2026

Backstage's merged catalog configuration is deployed and verified. Middleware PR 226 is synchronized with main and has no content conflict. The 36-operation monitoring API is still awaiting protected schema approval and is not deployed.

## Middleware PR 226

Merged main `5baf3faf25fb791f4d8ea171357a2d9af96009c1` into [PR 226](https://github.com/appolon1908-hue/Middleware-/pull/226) as `e9ec06ac02f9b3ffe3149b8e266f023813be59fb`. The server-side commit tree exactly matches the locally tested merge tree `475ebb70ab83d861bea635360473f93306cbb4f7`. GitHub reports mergeable=true and mergeable_state=blocked; source synchronization is complete.

- 115 local monitoring, alert adapter, alert contract, production route and entrypoint tests passed.
- [Exact-source monitoring CI](https://github.com/appolon1908-hue/Middleware-/actions/runs/34509648747) passed all 31 tests on PostgreSQL, including migration and replay concurrency.
- Ruff, generated OpenAPI (36 operations), and the observability alert contract passed.
- [Trusted production orchestrator evidence](https://github.com/appolon1908-hue/Middleware-/actions/runs/34509646016) and [production orchestrator contract](https://github.com/appolon1908-hue/Middleware-/actions/runs/34509645974) passed for the new source.

The [approved order workflow](https://github.com/appolon1908-hue/Middleware-/actions/runs/34509648695) still rejects the production migration head: current protected authority requires `0057_platform_service_catalog`, while the repository has `0058_integrated_monitoring`. The history hash remains `sha256:02c6394a883ac817afe00b40b8f0d72555645cfb4d31d8c6e6167716a953df0c`; the new migration hash remains `sha256:7e9ecbe7563d8449f273ce5339f90b2939c5d8e045a0dede87836a19b6da6884`. Existing signed evidence has not been relabeled. See [the separate review packet](../../MONITORING-MIGRATION-REVIEW.md).

## Backstage production deployment

Deployed exact merged source `2cc079e8e126bc3a8a929afc66d49edfb42a6538`, whose [main CI](https://github.com/appolon1908-hue/Backstage/actions/runs/34504649954) passed. The pinned image remains `sha256:0979a2355650b0ac5f085e4c250c3ff5925ad61ba2b749354ec122da6e1557bf`.

Configuration and both catalog/auth databases were backed up at `/var/backups/codestra/backstage-catalog/20260910T173236Z` before recreating only the Backstage service. PostgreSQL was not restarted.

Readback at 2026-09-10T17:39:43.471879+00:00:

| Check | Verified result |
| --- | --- |
| Internal healthcheck | HTTP 200 |
| Public HTTPS | TLS verification passed; HTTP 401 from the existing authentication gate |
| Catalog resources | 63 expected, 63 actual; no missing or unexpected resource references |
| Entire catalog | 75 entities; 67 from monitoring catalog source |
| Catalog entity errors | 0 |
| Keycloak SSO | Not deployed; existing Basic Auth remains |

Catalog ingestion proves repository registration. It does not prove application telemetry, SSO sessions, or the availability of the new Middleware APIs.

## Other release gates

Telnexa website PR 13 has passing CI but GitHub rejected its merge because it requires approval from someone other than its last pusher. PR 15 has passing source CI and approval, but its normal merge was rejected because the prerequisite `orchestrator-contract` check is expected. These controls were not bypassed.

Public website TLS repairs and Odoo production identity bindings remain undeployed. No monitoring API activation, external customer traffic, email, SMS or calls were triggered by this execution.
