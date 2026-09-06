"""Exercise the exact embedded release gate, without signing or publishing anything."""
from __future__ import annotations

import base64
import copy
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/reusable-codestra-deploy-readiness.yml'
DOCUMENT = yaml.safe_load(WORKFLOW.read_text())
RELEASE = next(step['run'] for step in DOCUMENT['jobs']['immutable-candidate']['steps'] if step.get('id') == 'release')
BLOCKS = re.findall(r"<<'(PY|PROVENANCE_PY)'\n(.*?)\n\1", RELEASE, re.S)
GENERATOR = next(code for _, code in BLOCKS if 'Path("evidence/provenance.json").write_text' in code)
VALIDATOR = next(code for label, code in BLOCKS if label == 'PROVENANCE_PY')
NAMESPACE = {'__name__': 'provenance_test'}
exec(compile(VALIDATOR, str(WORKFLOW), 'exec'), NAMESPACE)
ENV = {
    'GITHUB_REPOSITORY': 'appolon1908-hue/example-service', 'GITHUB_SHA': 'a' * 40,
    'GITHUB_RUN_ID': '12345', 'GITHUB_RUN_ATTEMPT': '2',
    'REPOSITORY_CLASS': 'backend', 'ARTIFACT_STRATEGY': 'oci',
}
IMAGE = 'ghcr.io/appolon1908-hue/example-service'
DIGEST = 'sha256:' + 'b' * 64


def generated(tmp_path):
    (tmp_path / 'evidence').mkdir(exist_ok=True)
    subprocess.run([sys.executable, '-c', GENERATOR], cwd=tmp_path, env={**os.environ, **ENV}, check=True)
    return json.loads((tmp_path / 'evidence/provenance.json').read_text())


def statement(predicate):
    return {'_type': 'https://in-toto.io/Statement/v0.1',
            'predicateType': 'https://slsa.dev/provenance/v1',
            'subject': [{'name': IMAGE, 'digest': {'sha256': DIGEST[7:]}}], 'predicate': predicate}


def envelope(value):
    # Signatures are verified by Cosign upstream of this semantic-only validator.
    return {'payloadType': 'application/vnd.in-toto+json',
            'payload': base64.b64encode(json.dumps(value).encode()).decode()}


def validate(data, expected, **env):
    NAMESPACE['validate_provenance'](data, expected, IMAGE, DIGEST, {**ENV, **env})


@pytest.mark.parametrize('form', ['object', 'array', 'jsonl'])
def test_exact_generated_document_survives(tmp_path, form):
    expected = generated(tmp_path)
    value = envelope(statement(expected))
    data = json.dumps([value]) if form == 'array' else json.dumps(value)
    if form == 'jsonl':
        data += '\n' + data
    validate(data, expected)


@pytest.mark.parametrize('field,value', [
    ('predicate', {}), ('predicate', None), ('predicate', []),
    ('predicateType', 'https://slsa.dev/provenance/v0.2'),
    ('_type', 'wrong'), ('subject', []),
    ('subject', [{'name': IMAGE, 'digest': {'sha256': 'c' * 64}}]),
    ('subject', [{'name': IMAGE + '-other', 'digest': {'sha256': DIGEST[7:]}}]),
])
def test_empty_wrong_type_or_wrong_image_rejected(tmp_path, field, value):
    expected = generated(tmp_path)
    bad = {**statement(expected), field: value}
    with pytest.raises(ValueError):
        validate(json.dumps(envelope(bad)), expected)


@pytest.mark.parametrize('path', [
    ('buildDefinition',), ('runDetails',),
    ('buildDefinition', 'externalParameters', 'source_sha'),
    ('buildDefinition', 'externalParameters', 'repository'),
    ('buildDefinition', 'resolvedDependencies'),
    ('runDetails', 'builder'), ('runDetails', 'metadata', 'invocationId'),
    ('buildDefinition', 'internalParameters'), ('runDetails', 'byproducts'),
])
def test_every_generated_field_must_be_preserved(tmp_path, path):
    expected = generated(tmp_path)
    bad = copy.deepcopy(expected)
    parent = bad
    for key in path[:-1]:
        parent = parent[key]
    del parent[path[-1]]
    with pytest.raises(ValueError):
        validate(json.dumps(envelope(statement(bad))), expected)


@pytest.mark.parametrize('key', ['GITHUB_SHA', 'GITHUB_REPOSITORY', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT', 'REPOSITORY_CLASS', 'ARTIFACT_STRATEGY'])
def test_generated_sidecar_cannot_override_expected_runtime(tmp_path, key):
    expected = generated(tmp_path)
    with pytest.raises(ValueError):
        validate(json.dumps(envelope(statement(expected))), expected, **{key: '999' if key in {'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT'} else 'wrong'})


@pytest.mark.parametrize('data', ['', '[]', 'null', 'true', '{', '[]junk',
    '{"payloadType":"application/vnd.in-toto+json","payload":"%%%"}',
    '{"payloadType":"application/vnd.in-toto+json","payload":7}',
    '{"payloadType":"application/vnd.in-toto+json","payload":"e30=","payload":"e30="}',
    '{"payloadType":"wrong","payload":"e30="}',
])
def test_malformed_verification_is_fail_closed(tmp_path, data):
    with pytest.raises((ValueError, TypeError)):
        validate(data, generated(tmp_path))


@pytest.mark.parametrize('raw', [b'[]', b'null', b'{"predicate":{},"predicate":{}}', b'{"number":NaN}', b'\xff'])
def test_invalid_decoded_payload_rejected(tmp_path, raw):
    data = {'payloadType': 'application/vnd.in-toto+json', 'payload': base64.b64encode(raw).decode()}
    with pytest.raises(ValueError):
        validate(json.dumps(data), generated(tmp_path))


def test_correct_signed_document_not_unsigned_sidecar_is_required(tmp_path):
    expected = generated(tmp_path)
    with pytest.raises(ValueError):
        validate(json.dumps(expected), expected)


def test_gate_precedes_outputs_without_weakening_crypto_or_release_controls():
    assert '--type slsaprovenance ' not in RELEASE
    assert RELEASE.count('--type https://slsa.dev/provenance/v1') == 2
    assert RELEASE.index('> evidence/provenance-attestation-verification.json') < RELEASE.index('# BEGIN CODESTRA_PROVENANCE_VALIDATOR') < RELEASE.index('artifact_kind=oci-image')
    assert RELEASE.index('# END CODESTRA_PROVENANCE_VALIDATOR') < RELEASE.index('echo "artifact_kind=')
    assert RELEASE.count('--certificate-oidc-issuer "https://token.actions.githubusercontent.com"') == 4
    assert '--severity HIGH,CRITICAL' in RELEASE
    assert '"runtime_deployment_authorized": False' in RELEASE
    assert '"external_effects_authorized": False' in RELEASE
    assert 'sha256sum --check --strict checksums.sha256' in RELEASE


def test_cli_reports_sanitized_failure_and_no_success(tmp_path):
    generated(tmp_path)
    (tmp_path / 'evidence/provenance-attestation-verification.json').write_text('private-malformed-body')
    result = subprocess.run([sys.executable, '-c', VALIDATOR, IMAGE, DIGEST], cwd=tmp_path,
                            env={**os.environ, **ENV}, text=True, capture_output=True)
    assert result.returncode != 0
    assert result.stdout == ''
    assert result.stderr.strip() == 'RELEASE_ERROR=invalid_provenance_evidence'


def test_actual_pinned_cosign_serialization(tmp_path):
    fixture = os.environ.get('CODESTRA_COSIGN_OUTPUT')
    if not fixture:
        pytest.skip('requires pinned Cosign Go generator; mandatory in provenance CI')
    expected = generated(tmp_path)
    actual = json.loads(Path(fixture).read_text())
    validate(json.dumps(envelope(actual)), expected)
    assert actual['predicate'] == expected
    legacy = json.loads(Path(fixture + '.legacy').read_text())
    with pytest.raises(ValueError):
        validate(json.dumps(envelope(legacy)), expected)
