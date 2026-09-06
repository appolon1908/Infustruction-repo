# Codestra Production Readiness Wave — 2026-09-01

Status: ACTIVE / NOT PRODUCTION CERTIFIED

## Objective
Bring the canonical Codestra platform repositories to a single production-certification standard without enabling external business effects before staging, recovery, rollback, source-lock, and runtime read-back gates pass.

## Global safety invariants
- These controls apply only to the explicitly reviewed workload and operation scope. Klyrow/Postal is `OUT_OF_SCOPE_ACTIVE_PRODUCTION_DO_NOT_TOUCH` under the canonical Stage 6 lock; this wave does not authorize disabling or changing that separate production email path. No in-scope Stage 6 route, credential, queue, webhook, or request may reach it before separate authorization.
- Do not modify SSH access, sshd configuration, authorized keys, SSH ports, or emergency operator access.
- Keep LIVE_EMAIL_DELIVERY, LIVE_SMS_DELIVERY, PRODUCTION_DIALING, CALLBACK_DISPATCH, ODOO_WRITE, LIVE_WRITE, N8N_EXTERNAL_EFFECTS, SOCIAL_PUBLISHING, LIVE_ADVERTISING and equivalent provider/business-effect switches disabled until separately certified.
- Never bypass branch protection, required reviews, CODEOWNERS, required Actions checks, or protected-environment approvals.
- Never deploy mutable tags such as latest. Production artifacts must be immutable and attributable to exact source SHAs.
- Never place credentials, recovery keys, root tokens, private keys, production .env files, database dumps, or secret values in Git, logs, PRs, Actions artifacts, or evidence.

## Canonical remediation lane
Use `prod-readiness-20260901` as the cross-repository hardening branch where compatible with each repository's existing release model. Reconcile existing production-critical PRs into the repository's governed promotion path rather than discarding or blindly merging them.

## Required repository gates
Each deployable repository must prove, as applicable:
1. canonical repository/source authority and no unresolved duplicate runtime authority;
2. exact-head CI green;
3. Critical=0 and High=0 unresolved production defects;
4. secret scanning and dependency/container security gates;
5. pinned dependencies/actions/images and immutable release identity;
6. SBOM and provenance for production artifacts;
7. least-privilege identity and service-to-service authorization;
8. no direct provider bypass around Kong/Middleware where the architecture requires the controlled path;
9. durable idempotent effect handling and no blind retry for unknown outcomes;
10. metrics, structured logs, traces/alerts as appropriate;
11. backup/restore and RPO/RTO evidence for stateful workloads;
12. rollback rehearsal/evidence;
13. staging deployment from exact protected source and immutable artifacts;
14. end-to-end staging certification;
15. runtime read-back matching the protected source lock;
16. production read-only canary before any business-effect activation.

## Platform entry gates
Production activation remains blocked until at minimum:
- STAGE6_SOURCE_LOCK=PASS
- RUNTIME_READBACK=PASS
- OPENBAO_SECRETS_AUTHORITY=PASS
- KEYCLOAK_IDENTITY=PASS
- KONG_POLICY=PASS
- MIDDLEWARE_POLICY=PASS
- OBSERVABILITY=PASS
- BACKUP_RESTORE=PASS
- ROLLBACK=PASS
- STAGING_E2E=PASS
- PRODUCTION_READ_ONLY_CANARY=PASS

## Core repositories in this wave
- Caddy
- Kong
- Keycloak
- Middleware-
- N8N
- Odoo
- SDK-repository
- Codestra-AI
- Codestra-Marketing-
- Codestra-Communication-CC
- Codesrea-Social-
- social.codestra.co
- communication-platform-
- codestra-foundation
- Vicidialer-Codestra
- Codestra-OpenBao
- codestra-production-runtime-authority
- Infustruction-repo

## Observability/security repositories in this wave
- Codestra-Prometheus
- Codestra-Grafana-
- Codestra-Loki
- Codestra-Tempo
- Codestra-Telemetry
- Codestra-Alloy
- Codestra-Alertmanager
- Codestra-Node-Exporter
- Codestra-cAdvisor
- Codestra-Redis-Exporter
- Codestra-Postgres-Exporter
- Codestra-Blackbox-Exporter
- Superset

## Per-repository remediation loop
For each repository: inventory -> reconcile open production PRs -> fix Critical/High findings -> add regression tests -> validate exact head -> build immutable artifact where deployable -> generate security/provenance evidence -> promote through governed branches -> stage -> certify -> rollback test -> production read-only canary -> only then authorize separately owned business effects.

## Certification vocabulary
Use only PASS, WARNING, FAIL, N/A for production-critical categories. Do not use NOT VERIFIED as a successful result.

`OVERALL_VERDICT=PRODUCTION_CERTIFIED` is allowed only when every production-critical gate is PASS or explicitly justified N/A.
