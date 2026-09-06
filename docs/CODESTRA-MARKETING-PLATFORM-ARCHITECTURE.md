# Codestra Marketing Platform Architecture

## Purpose
This document is the architecture authority for the Codestra marketing, communications, social, AI, CRM, automation, identity, API gateway, middleware, and SDK integration plane.

## Core principles
- API-first and contract-first.
- Odoo is the business system of record for leads, customers, opportunities, activities, ownership, and commercial outcomes.
- Keycloak is the identity and authorization authority.
- Kong is the controlled API edge.
- Middleware owns integration reliability: validation, provider adapters, webhook verification, idempotency, outbox/inbox, retries, normalized integration events, and synchronization boundaries.
- n8n owns workflow orchestration, not source-of-truth business rules.
- Codestra Marketing owns campaign intent, campaign lifecycle, audiences, creative sets, budgets, attribution, experiments, campaign approvals, optimization recommendations, and advertising-provider abstractions.
- Codestra Communication CC owns customer-channel delivery, templates, consent, suppression, conversation delivery state, and communication history.
- Codestra Social owns social publishing abstractions, scheduling, approvals, engagement, social inbox, analytics ingestion, and the adapter to the existing social publishing platform.
- Codestra AI owns model/provider abstraction, structured generation, scoring, classification, summarization, prompt policy, evaluation, cost control, safety policy, and audit evidence.
- SDK-repository remains one shared Codestra SDK. No per-service SDK repositories are required.
- No direct browser-to-database access and no service bypass of Kong/authorization for externally exposed application capabilities.
- No autonomous unrestricted advertising spend. Campaign activation, account connection, significant targeting changes, and budget/spend increases require deterministic policy checks and human approval thresholds.

## High-level flow
User/Operator -> Codestra SDK -> Kong -> Keycloak authorization -> business service -> Middleware/n8n/Odoo/providers as appropriate.

Lead flow example:
Advertising provider -> verified webhook -> Kong -> Middleware -> Marketing attribution -> Odoo lead/opportunity -> n8n workflow -> Communication follow-up -> AI qualification assistance -> appointment/closer -> Odoo outcome -> attribution and analytics feedback.

## Repository responsibilities
### Codestra-Marketing-
Own campaigns, objectives, audiences, creatives, budgets, experiments, approvals, attribution, lead-source mapping, conversion goals, spend controls, recommendation lifecycle, and provider-neutral advertising contracts.

### Codestra-Communication-CC
Own email/SMS/WhatsApp/push abstractions, templates, consent, suppression, channel preferences, message state, retries exposed as business state, and communication history.

### Codesrea-Social-
Own social account abstractions, calendars, posts, approval workflow, engagement, comments/inbox abstraction, analytics normalization, and adapter boundaries to the existing social platform.

### Codestra-AI
Own shared AI gateway capabilities, model routing, structured outputs, generation policies, prompt/template registry, scoring, classification, evaluation, safety controls, cost controls, and auditability.

### Middleware-
Own integration transport, provider adapters, HMAC/signature verification, idempotency, outbox/inbox, delivery retries, circuit breakers, normalized integration events, and Odoo/provider synchronization.

### N8N
Own workflow orchestration across approved APIs/events. It must not become the authoritative store for leads, campaigns, spend, consent, identity, or customer state.

### Odoo
Own CRM/business records: leads, opportunities, contacts, companies, activities, sales ownership, stages, campaign-linked commercial outcomes, task history, and approved business workflow records.

### Keycloak
Own identity, service accounts, roles, scopes, client credentials, PKCE configuration, token policy, and service-to-service authorization policy.

### Kong
Own API routing, auth enforcement integration, rate limits, request policies, service exposure, versioned ingress routes, and gateway observability.

### SDK-repository
Expose one supported developer interface with modules for auth, marketing, communication, social, AI, CRM, and workflows. SDK clients call supported APIs; they do not bypass service boundaries.

## Required platform contracts
- OpenAPI for synchronous APIs.
- AsyncAPI/event catalog for event-driven integration.
- Canonical IDs for tenant, business unit, campaign, lead, contact, opportunity, ad account, provider campaign, creative, message, workflow execution, and correlation/causation IDs.
- Idempotency-Key for externally triggered mutations where duplicate execution is harmful.
- Optimistic concurrency/version fields on mutable business aggregates where race conditions matter.
- Correlation ID propagated across SDK, Kong, services, middleware, n8n, Odoo, and provider callbacks.
- Explicit error taxonomy and retry classification.
- Audit events for privileged actions and any action affecting spend, targeting, identity, consent, or delivery activation.

## Environments and release model
Use protected main plus development, staging, and production integration/release branches only where repository workflow requires them. Feature work must occur on short-lived branches. Documentation authority is introduced first on `docs/codestra-marketing-platform-architecture-20260830`.

No documentation change may enable live email, SMS, PSTN, social publishing, provider writes, or advertising spend. Production activation requires separate reviewed implementation and release evidence.

## Initial delivery sequence
1. Architecture authority and repository responsibility docs.
2. Marketing domain contracts and data model.
3. AI gateway contracts and policy model.
4. Communication domain contracts and consent model.
5. Social adapter contracts.
6. Middleware integration contracts and webhook/event schemas.
7. Shared SDK modules.
8. n8n workflow contracts.
9. Odoo CRM/campaign attribution mapping.
10. Advertising provider connectors beginning with Meta and Google after policy/approval gates exist.

## Non-negotiable safety rules
- Live spend defaults to disabled.
- Live outbound delivery defaults to disabled unless separately approved.
- Secrets never live in repository documentation or source-controlled environment examples.
- AI may draft and recommend; privileged mutations require policy authorization.
- Provider callbacks must be authenticated/verified and replay-safe.
- Every lead and conversion must be attributable to source/campaign where available.
- Cross-tenant or cross-business data access is denied by default.
