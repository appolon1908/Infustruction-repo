# Stage 6 Keycloak Read-back

Captured: 2026-08-31 (Europe/Berlin)

`KEYCLOAK_CERTIFICATION=FAIL`

The mission stopped before Keycloak CHECK/PLAN/APPLY/READ-BACK. A Telnexa-local
Keycloak container was observed on `37.27.128.39`, but it is not evidence of the
Git-controlled Codestra staging realm required by this release. No client,
secret, scope, audience, role, redirect URI, realm, or service account was
created or changed.

No-token, bad-token, expired-token, wrong-issuer, wrong-audience, wrong-scope,
n8n advertising-authority, AI activation-authority, and Social paid-media
negative tests were not executed.

`KEYCLOAK_APPLY=NOT_EXECUTED`

`KEYCLOAK_NEGATIVE_TESTS=NOT_EXECUTED`
