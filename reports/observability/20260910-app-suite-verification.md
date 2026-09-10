# Live integration verification — 2026-09-10

**Decision: not fully integrated.** This report covers the 19 repositories named in the latest request plus Kong, Caddy, Backstage, Sentry and Wazuh. The separate [design index](../../MONITORING-PR-INDEX.md) records committed onboarding/design changes across 63 repositories. Source records and passing CI do not certify live application synchronization.

Evidence was collected between 17:01 and 17:15 UTC from the four connected servers, public HTTPS endpoints, rendered browser pages and current repository source. Machine-readable observations are in [the evidence file](20260910-app-suite-verification.json). All observations are point-in-time results.

## Verified connections

- Core Prometheus: **38/38 scrape targets healthy**, with **14/14 configured probe_success values equal to 1**. A healthy blackbox scrape alone is insufficient; both scrape health and probe results were checked. This inventory does not cover every named repository or public website.
- Middleware → n8n runtime health: **200**, observed from the running Middleware container.
- Middleware → central Keycloak JWKS: **200**, with two keys returned. This proves key discovery, not every service grant or authenticated user journey.
- Core SMS service → private Telnexa provider: **200** for health and readiness using its mounted mTLS client certificate and CA.
- Public Klyrow and Telnexa API readiness: **200** with certificate verification.
- Backstage and Sentry private health: **200**. Wazuh lists three active remote agents plus its manager-local entry.
- The current monitoring API implementation passes **28 PostgreSQL tests** and the generated contract check confirms **36 operations**, on commit `de3c5239fa1ce9e4fa016b302ccb9063b23f828c`: [verified workflow](https://github.com/appolon1908-hue/Middleware-/actions/runs/34506572911). External adapter tests use test transports. The extension is not deployed at the public gateway.

## Repository-by-repository result

| Repository | Responsibility | Observed evidence | Result |
| --- | --- | --- | --- |
| klyrow.com | Public application + email API | Application login rendered; API health and readiness returned 200 with valid TLS. Provider delivery was not exercised. | Runtime reachable; full email/event synchronization unverified |
| klyrow-Website- | Public marketing and onboarding | Source explicitly says production deployment is inactive. Apex redirects to app.klyrow.com; no separate marketing workload was matched. | Website rollout incomplete |
| telnexa | SMS provider + billing | Public health/readiness returned 200. Core SMS service reached private provider health/readiness using its installed mTLS certificate. | Connectivity verified; delivery disabled |
| Telnexa-web | Public marketing and onboarding | Apex TLS hostname mismatch; www TLS failure; app.telnexa.co does not resolve. PR 15 preserves provider routing and fixes the account handoff. | Source repaired; deployment blocked |
| Vicidialer-Codestra | Voice/contact-center runtime | Asterisk, MariaDB and restricted adapter units are active. Core adapter readiness probe passes. Asterisk health-monitor unit was observed in failed state; remote runtime certification and call reconciliation remain separate. | Partial runtime evidence; calls untested |
| social.codestra.co | Social application | HTTPS redirects to rendered account page. Postiz container is healthy. Publishing, approval synchronization and central SSO were not exercised. | Runtime reachable; business integration unverified |
| Websocket- | Authorized call-state/screen-pop events | Live gateway container is healthy and references the central issuer and exact staff origins. No authenticated event delivery/reconnect test was run. | Runtime present; event integration unverified |
| Odoo | CRM/ERP | Public health and login HTTP checks return 200; production container is healthy. Cloud browser could not render its login. Middleware identity lookup is configured against staging Odoo. | Production identity binding needs reconciliation |
| Middleware- | Cross-system command/event authority | Live readiness 200; n8n health and Keycloak JWKS accessible from the running container. New monitoring route is absent at Kong (404). | Existing runtime reachable; 36-operation extension undeployed |
| N8N | Workflow orchestration | Production health/readiness 200; Middleware can reach it. Public editor 404 matches its private staff access policy. Delivery and internal notification switches remain false. | Private connectivity verified; workflow activation unverified |
| codestra-foundation | Shared tenants, profiles, consent, billing | Source implements shared functions, with mutations/delivery disabled by default. No running service was matched to this repository in the inspected inventories. | Source implemented; runtime binding unverified |
| codestra-provisioning-service | Account/access provisioning | A production-named container is healthy, while source README describes staging-only scope. A container name alone is not release certification. | Runtime present; source/environment reconciliation needed |
| SDK-repository | Contracts, clients and connector helpers | Source authority for consumers; not a standalone service. Consumer versions and runtime use were not exhaustively certified. | Contract repository; consumer alignment required |
| Codestra-Marketing- | Marketing control-plane design | README states architecture/bootstrap only and unverified off-host runtime authority. | Design phase; no verified runtime integration |
| Codestra-Communication-CC | Communications control-plane design | README states architecture/bootstrap only; live delivery disabled. | Design phase; no verified runtime integration |
| Codesrea-Social- | Provider-neutral social control-plane design | README states architecture foundation only; application authority remains social.codestra.co. | Design phase; consumer integration unverified |
| Codestra-AI | Shared AI control-plane design | README states architecture/bootstrap only. A separate live AI console renders, but repository-to-runtime authority was not certified. | Design phase; live console source alignment unverified |
| communication-platform- | Channel contracts and release coordination | Architecture/coordination authority with named runtime owners; intentionally not a second provider implementation. | Contract repository; release coordination required |
| Keycloak | Central identity | Canonical discovery and issuer validated over HTTPS; running Middleware reads two JWKS keys. Authenticated sessions and all service grants were not certified. | Issuer/JWKS connectivity verified; full SSO unverified |
| Kong | API routing and policy | Canonical /healthz returns 200. /health is not its documented health route. /v1/platform/repositories has no route. | Existing gateway reachable; monitoring route rollout pending |
| Caddy | Core/web TLS edge | Core and web edges route the observed services. Provider host uses its separate Nginx edge. Website/provider ownership conflict repaired in Telnexa source. | Partial edge coverage verified |
| Backstage | Catalog and ownership | Private healthcheck 200; public access and catalog API require authentication (401). Mounted catalog has five components, a group and a system. Guest provider is configured behind the edge; OIDC provider absent. | Running; full catalog and Keycloak adoption pending |
| Sentry | Application errors | Private health 200 and public login rendered over valid TLS. Application SDK event ingestion was not exercised. | Running; per-app ingestion unverified |
| Wazuh | Host security telemetry | Public login rendered over valid TLS. Manager lists three active remote agents plus its manager-local entry. Dashboard/API-to-monitoring integration was not exercised. | Running; agent presence verified, full integration pending |

## Committed repair

[Telnexa website PR 15](https://github.com/appolon1908-hue/Telnexa-web/pull/15) repairs a concrete integration conflict. The old deployment claimed `api.telnexa.co` and required its DNS to move to the website server, which would replace the working SMS provider endpoint.

The change preserves the provider hostname, confines website forms to the website's own origin, corrects DNS and deployment-host checks, and adds a bounded TLS-verified GET-only provider regression check before and after rollout. The prior portal link pointed to a hostname with no DNS record; defaults now use the existing provider dashboard. All **24 local tests** passed, including seven deployment/provider regression tests. The exact provider check also passed against the live provider. Final commit: `0462ab8e444078cab6f4433c5bc3b3209d43bdb2`; both [Operations CI](https://github.com/appolon1908-hue/Telnexa-web/actions/runs/34507142139) and [Application CI](https://github.com/appolon1908-hue/Telnexa-web/actions/runs/34507142070) passed on that exact commit.

No DNS, edge, identity, provider capability or production application was changed during this verification. No customer records, emails, SMS messages, calls or social publications were created.

## Remaining release work

1. **Monitoring API:** review and release the current Middleware candidate, approve the migration through the existing schema/release authority, provide approved tenant/service mappings and credentials, and publish Kong routes. The public repositories operation currently returns gateway 404. The existing trust-workflow and protected schema gates must be satisfied, not weakened.
2. **Klyrow public website:** publish the reviewed immutable source to staging, certify it, then complete the approved Nginx apex/www cutover. Existing app/API routes must remain intact.
3. **Telnexa public website:** merge the repaired source after review, satisfy the repository's outstanding publication/compliance and release gates, deploy the approved website image, and complete website DNS/TLS. Provider API DNS must remain under its current owner.
4. **Identity and provisioning:** reconcile Middleware's staging Odoo identity-lookup binding against the intended production contract; certify provisioning's source, target environment and service identities. A working Odoo login page does not resolve this mismatch.
5. **Backstage/Sentry/Wazuh:** adopt the full catalog and approved central identity integration, bind the monitoring adapters, and verify per-application error ingestion and host signals. The current live Backstage catalog contains five components, not the proposed 63 repository resources.
6. **Business synchronization:** certify tenant-scoped workflows, event callbacks, replay/reconciliation and authenticated agent sessions in an approved isolated environment. The listed design repositories and SDK contracts cannot be counted as running integrations merely because they are committed.
7. **Voice:** reconcile the observed health-monitor failure and finish the current signed-release and Server B runtime certification. No call or replay was initiated by this audit.

These are concrete source/release/identity and runtime-certification gaps. Passing health endpoints do not prove durable end-to-end synchronization.

## Browser limits

Klyrow, Social, AI, Telnexa's provider landing page, Sentry and Wazuh rendered in the cloud browser. Odoo showed “Site Unavailable” and Phone navigation timed out there, although the server-side HTTPS checks returned 200. No successful authenticated login is claimed. The Telnexa dashboard returned HTTPS 200 to the server-side check; its browser navigation was not certified.
