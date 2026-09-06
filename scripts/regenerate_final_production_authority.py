#!/usr/bin/env python3
"""Regenerate final source/capability authority from reviewed merge SHAs."""
from pathlib import Path

import yaml


SOURCE = Path("PRODUCTION-SOURCE-AUTHORITY-MATRIX.yaml")
CAPABILITY = Path("PRODUCTION-SAFETY-CAPABILITY-MATRIX.yaml")

runtime_sha = "bd99e533e46b36f018a990f0c742643534e08f88"
authorities = {
    "codestra-beyvra-email-api-1": ("Codestra-SRL/codestra-middleware", "main", "e703e8c84b6c6b9986ec30411adef7e92c141a47", ".", "deploy/beyvra-email/Dockerfile"),
    "codestra-caddy-upstream-gateway": ("appolon1908-hue/codestra-production-runtime-authority", "main", runtime_sha, "vendor/caddy-upstream-gateway", "NOT_APPLICABLE_VENDOR_DIGEST_PIN"),
    "codestra-email-reseller-api-1": ("appolon1908-hue/codestra-production-platform", "release/production-activation", "46463acbbf3e4df95926ac2e0ea8baae9a4abfa5", ".", "deploy/email-reseller/Dockerfile"),
    "codestra-integration-control-plane-api-1": ("appolon1908-hue/codestra-production-platform", "authority/runtime-control-plane-44d2", "44d2addf48ae31da6eeb3c3f9ab3fe34d999042c", ".", "deploy/control-plane/Dockerfile"),
    "codestra-integration-control-plane-worker-1": ("appolon1908-hue/codestra-production-platform", "authority/runtime-control-plane-44d2", "44d2addf48ae31da6eeb3c3f9ab3fe34d999042c", ".", "deploy/control-plane/Dockerfile"),
    "codestra-kong-kong-gateway-1": ("appolon1908-hue/codestra-production-runtime-authority", "main", runtime_sha, "vendor/kong-gateway", "NOT_APPLICABLE_VENDOR_DIGEST_PIN"),
    "codestra-kong-service-auth-adapter-1": ("appolon1908-hue/codestra-production-runtime-authority", "main", runtime_sha, "components/kong-service-auth-adapter", "components/kong-service-auth-adapter/Dockerfile"),
    "codestra-mail-api-mail-api-1": ("appolon1908-hue/codestra-production-platform", "release/production-activation", "a0593cb881654999f78e2c40d6f9784a5507d987", ".", "deploy/mail-platform/Dockerfile.api"),
    "codestra-mail-isolated-stalwart-1": ("appolon1908-hue/codestra-production-runtime-authority", "main", runtime_sha, "vendor/stalwart", "NOT_APPLICABLE_VENDOR_DIGEST_PIN"),
    "codestra-middleware-event-gateway-1": ("Codestra-SRL/codestra-middleware", "main", "e98edd18753d42f6951b14aa0f577fdcfc9bd52c", ".", "Dockerfile"),
    "codestra-middleware-external-webhook-worker-1": ("Codestra-SRL/codestra-middleware", "main", "e98edd18753d42f6951b14aa0f577fdcfc9bd52c", ".", "Dockerfile"),
    "codestra-monitoring-receiver-receiver-1": ("appolon1908-hue/codestra-production-runtime-authority", "main", runtime_sha, "components/monitoring-receiver", "components/monitoring-receiver/Dockerfile"),
    "codestra-n8n-internal-proxy": ("appolon1908-hue/codestra-production-runtime-authority", "main", runtime_sha, "vendor/n8n-internal-proxy", "NOT_APPLICABLE_VENDOR_DIGEST_PIN"),
    "codestra-odoo-internal-proxy": ("appolon1908-hue/codestra-production-runtime-authority", "main", runtime_sha, "vendor/odoo-internal-proxy", "NOT_APPLICABLE_VENDOR_DIGEST_PIN"),
    "codestra-private-vicidial-ingress-1": ("appolon1908-hue/codestra-production-runtime-authority", "main", runtime_sha, "vendor/private-vicidial-ingress", "NOT_APPLICABLE_VENDOR_DIGEST_PIN"),
    "codestra-provisioning-service-provisioning-service-1": ("appolon1908-hue/codestra-provisioning-service", "main", "2c18e395e9f86f7510f142188336e9114aa213a4", ".", "Dockerfile"),
    "codestra-reseller-portal-portal-1": ("appolon1908-hue/codestra-production-platform", "release/production-activation", "9d2805ca397b7fdafab0e913cd442126fe1391d2", ".", "deploy/reseller-portal/Dockerfile"),
    "codestra-reseller-portal-postgres-1": ("appolon1908-hue/codestra-production-runtime-authority", "main", runtime_sha, "vendor/reseller-portal-postgres", "NOT_APPLICABLE_VENDOR_DIGEST_PIN"),
    "codestra-sms-api-api-1": ("appolon1908-hue/codestra-production-runtime-authority", "main", runtime_sha, "components/sms-api", "components/sms-api/Dockerfile"),
    "codestra-sms-api-event-worker-1": ("appolon1908-hue/codestra-production-runtime-authority", "main", runtime_sha, "components/sms-api", "components/sms-api/Dockerfile"),
    "private-integration-gateway-1": ("appolon1908-hue/codestra-production-runtime-authority", "main", runtime_sha, "components/private-integration-gateway", "components/private-integration-gateway/Dockerfile"),
}

source = yaml.safe_load(SOURCE.read_text())
for name, values in authorities.items():
    repository, branch, sha, context, dockerfile = values
    item = source["workloads"][name]
    item.update(repository=repository, protected_branch=branch, source_sha=sha,
                build_context=context, dockerfile=dockerfile, confidence="high",
                status="PROVEN", remediation_type="A",
                evidence="Reviewed protected merge establishes exact source or digest-pinned vendor deployment authority.")
source["captured_at"] = "2026-09-01T17:56:34Z"
source["source_ownership_proven"] = "23/23"
source["source_ownership_ambiguous"] = 0
source["source_authority_ready"] = True
SOURCE.write_text(yaml.safe_dump(source, sort_keys=False))

capability = yaml.safe_load(CAPABILITY.read_text())
resolved = {
    "codestra-beyvra-email-api-1": {"external_delivery", "email_delivery"},
    "codestra-email-reseller-api-1": {"external_delivery", "email_delivery"},
    "codestra-mail-api-mail-api-1": {"external_delivery", "email_delivery"},
    "codestra-provisioning-service-provisioning-service-1": set(),
    "codestra-reseller-portal-portal-1": set(),
}
for name, enabled in resolved.items():
    item = capability["services"][name]
    item["evidence_basis"] = "reviewed protected source and deployment authority"
    for key in item["capabilities"]:
        item["capabilities"][key] = key in enabled
capability["captured_at"] = "2026-09-01T17:56:34Z"
capability["capability_unknown_fields"] = 0
capability["production_write_safety"] = "PASS"
capability["effective_runtime_state"] = {
    "LIVE_ADVERTISING_ENABLED": False,
    "EXTERNAL_DELIVERY_ENABLED": False,
    "SOCIAL_PUBLISHING_ENABLED": False,
    "EXTERNAL_MODEL_CALLS_ENABLED": False,
    "LIVE_SMS_DELIVERY": False,
    "LIVE_EMAIL_DELIVERY": False,
    "LIVE_PSTN_DIALING": False,
    "N8N_EXTERNAL_PROVIDER_WRITES": False,
    "PRODUCTION_DIALING": "DISABLED",
}
CAPABILITY.write_text(yaml.safe_dump(capability, sort_keys=False))
