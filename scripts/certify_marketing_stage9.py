#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'config/marketing-stage9-readiness.json'
REPOSITORY_ALIASES = ROOT / 'config/repository-name-aliases.v1.json'
SOCIAL_CONTROL_REPOSITORY_ID = 1351353723

BASE_EXPECTED_REPOS = {
    'Codestra-Marketing-', 'Codestra-AI', 'Codestra-Communication-CC',
    'Middleware-', 'Odoo', 'SDK-repository', 'N8N', 'Kong', 'Keycloak',
    'social.codestra.co'
}
EXPECTED_FLOW = [
    'provider.test_lead',
    'kong.authenticated_ingress',
    'middleware.inbox.accepted',
    'marketing.attribution.recorded',
    'odoo.crm.lead_upserted',
    'n8n.workflow.received',
    'communication.dry_run_created',
    'odoo.outcome.recorded',
    'marketing.conversion_feedback_recorded',
]


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding='utf-8'))
    assert isinstance(value, dict), f'{path.name} root must be an object'
    return value


def social_control_slug() -> str:
    aliases = load_json(REPOSITORY_ALIASES)
    assert aliases['schema_version'] == '1.0'
    assert aliases['identity_key'] == 'repository_id'
    assert aliases['policy']['historical_evidence_immutable'] is True

    matches = [
        item for item in aliases['mappings']
        if item.get('repository_id') == SOCIAL_CONTROL_REPOSITORY_ID
    ]
    assert len(matches) == 1, 'social-control repository ID must resolve exactly once'
    mapping = matches[0]
    status = mapping.get('status')
    assert status in {
        'PREPARED_NOT_RENAMED',
        'RENAMED_VERIFIED',
        'ROLLED_BACK_VERIFIED',
    }, 'social-control rename state is invalid'

    repository = (
        mapping['target_repository_after_cutover']
        if status == 'RENAMED_VERIFIED'
        else mapping['current_repository']
    )
    owner, slug = repository.split('/', 1)
    assert owner == 'appolon1908-hue'
    assert slug
    return slug


def event(event_type: str, tenant_id: str, correlation_id: str, payload: dict) -> dict:
    semantic = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return {
        'event_id': hashlib.sha256(f'{event_type}:{tenant_id}:{semantic}'.encode()).hexdigest()[:32],
        'tenant_id': tenant_id,
        'event_type': event_type,
        'idempotency_key': hashlib.sha256(f'{tenant_id}:{event_type}:{semantic}'.encode()).hexdigest(),
        'correlation_id': correlation_id,
        'payload': payload,
    }


def main() -> None:
    data = load_json(MANIFEST)
    assert data['productionWritesAuthorized'] is False
    assert all(value is False for value in data['capabilities'].values()), 'all live capabilities must remain false'

    expected_repos = BASE_EXPECTED_REPOS | {social_control_slug()}
    repos = {entry['repo'] for entry in data['repositories']}
    assert expected_repos == repos, f'repository manifest mismatch: {sorted(expected_repos ^ repos)}'
    assert data['syntheticFlow'] == EXPECTED_FLOW, 'stage9 flow order changed'
    assert len(data['stage9ExitRequiresExternalEvidence']) >= 7, 'external evidence blockers must remain explicit'

    tenant = 'tenant-stage9-synthetic'
    correlation = 'corr-stage9-synthetic-0001'
    lead = event('provider.test_lead', tenant, correlation, {'email': 'synthetic@example.invalid', 'source': 'meta-test'})
    ingress = event('kong.authenticated_ingress', tenant, correlation, {'source_event_id': lead['event_id']})
    inbox = event('middleware.inbox.accepted', tenant, correlation, {'source_event_id': ingress['event_id']})
    attribution = event('marketing.attribution.recorded', tenant, correlation, {'source_event_id': inbox['event_id'], 'campaign': 'synthetic'})
    crm = event('odoo.crm.lead_upserted', tenant, correlation, {'source_event_id': attribution['event_id'], 'external_writes': False})
    workflow = event('n8n.workflow.received', tenant, correlation, {'source_event_id': crm['event_id'], 'active': False})
    dry_run = event('communication.dry_run_created', tenant, correlation, {'source_event_id': workflow['event_id'], 'external_delivery': False})
    outcome = event('odoo.outcome.recorded', tenant, correlation, {'source_event_id': dry_run['event_id'], 'status': 'synthetic-qualified'})
    feedback = event('marketing.conversion_feedback_recorded', tenant, correlation, {'source_event_id': outcome['event_id'], 'provider_write': False})
    events = [lead, ingress, inbox, attribution, crm, workflow, dry_run, outcome, feedback]

    assert all(e['tenant_id'] == tenant for e in events)
    assert all(e['correlation_id'] == correlation for e in events)
    assert len({e['idempotency_key'] for e in events}) == len(events)
    assert dry_run['payload']['external_delivery'] is False
    assert feedback['payload']['provider_write'] is False
    print('MARKETING_STAGE9_SYNTHETIC_CERTIFICATION=PASS')
    print('PRODUCTION_WRITES_AUTHORIZED=NO')
    print('EXTERNAL_RUNTIME_EVIDENCE_REQUIRED=YES')


if __name__ == '__main__':
    main()
