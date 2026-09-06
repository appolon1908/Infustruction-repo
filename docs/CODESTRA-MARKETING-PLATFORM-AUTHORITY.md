# Codestra Marketing Platform — Architecture Authority

## Purpose
This repository is the canonical architecture authority for the Codestra marketing platform. Individual service repositories own their implementation, but cross-repository contracts, boundaries, naming, environments, release gates and platform diagrams are governed here.

## Participating Repositories
- Codestra-Marketing-
- Codestra-AI
- Codestra-Communication-CC
- Codesrea-Social-
- social.codestra.co
- Middleware-
- Odoo
- N8N
- SDK-repository
- Kong
- Keycloak
- Infustruction-repo

## Platform Ownership Matrix
Marketing: paid acquisition, campaign lifecycle, budgets, attribution.
AI: model gateway, AI policy, structured generation/evaluation.
Communication: email/SMS/WhatsApp/push messaging, templates, consent, delivery state.
Social: enterprise social API/control plane.
social.codestra.co: social publishing runtime/provider execution.
Middleware: durable integration, webhooks, adapters, outbox/inbox, retries.
Odoo: CRM/customer/lead/opportunity system of record and sales outcomes.
n8n: workflow orchestration.
SDK: typed client layer for Codestra APIs.
Kong: API edge and policy enforcement.
Keycloak: identity and access management.
Infrastructure authority: cross-repository architecture, environments and release standards.

## Canonical Platform Flow
Users/apps -> SDK -> Kong -> owning business service -> Middleware where integration durability is required -> provider/runtime.
Identity is supplied by Keycloak. Odoo receives CRM records and returns sales outcomes. n8n coordinates workflows without becoming the system of record. Codestra AI supplies shared AI capabilities without owning business decisions.

## Non-Negotiable Rules
1. One authoritative owner per business domain.
2. No direct cross-service database writes.
3. No browser/provider secret exposure.
4. All mutating integrations use idempotency and correlation identifiers.
5. Webhooks are authenticated, deduplicated and durably accepted before business processing.
6. AI cannot bypass spend, publishing, consent, identity or business approval policy.
7. Production writes require explicit capability enablement and release evidence.
8. API and event contracts are versioned.
9. Every service emits auditable state transitions and operational telemetry.
10. Odoo remains authoritative for CRM/customer/opportunity outcomes; Marketing remains authoritative for paid campaign state.

## Environments
Development -> Test -> Staging -> Production. Promotion is artifact-based, reviewed and reversible. Environment secrets and provider credentials are never committed to Git.

## Documentation Gate
Implementation begins only after each participating repository has a reviewed role/integration contract and the cross-repository authority document is approved.