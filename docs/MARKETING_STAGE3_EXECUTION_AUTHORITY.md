# Codestra Marketing Platform — Stage 3 Execution Authority

## Purpose
This document is the implementation authority for the first production-grade foundation of the Codestra marketing platform. It does not authorize live advertising, social publishing, external messaging, or AI-provider calls.

## Required implementation order
1. Codestra Marketing: campaign, audience, creative, budget, approval, attribution, provider-neutral connector contracts.
2. Codestra AI: governed model gateway, structured outputs, prompt/model policy, audit and usage controls.
3. Codestra Communication: canonical messages, consent, suppression, templates and delivery state.
4. Codestra Social: account/post/scheduling/approval control plane.
5. Middleware: durable canonical commands/events, webhook verification, outbox/inbox and retries.
6. Kong: authenticated route families and promotion gates.
7. Keycloak: service identities, human roles and least-privilege scopes.
8. SDK: typed provider-neutral modules through supported APIs.
9. n8n: orchestration only, never source-of-truth business logic.
10. Odoo: authoritative lead/opportunity state and conversion/revenue feedback.
11. social.codestra.co: publishing runtime adapter and reconciliation.
12. Meta Ads: first paid-media adapter, disabled for live writes until staging certification.

## Mandatory kill switches
- LIVE_ADVERTISING_ENABLED=false
- EXTERNAL_MODEL_CALLS_ENABLED=false
- EXTERNAL_DELIVERY_ENABLED=false
- SOCIAL_PUBLISHING_ENABLED=false

## Promotion gates
A capability may be enabled only after code review, CI, auth tests, idempotency tests, staging contract tests, provider sandbox/read-only validation where available, observability, audit evidence, rollback procedure, and explicit production approval.

## Non-negotiable rules
No service may bypass Kong/identity policy for externally reachable APIs. No service may write directly into another service database. AI may recommend actions but cannot approve spend or bypass human/policy gates. Odoo remains CRM authority. Marketing owns paid-media business state. Communication owns consent-aware messaging. Social owns organic social control. Middleware owns durable integration. n8n owns orchestration only.
