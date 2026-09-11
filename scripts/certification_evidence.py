"""Pure reconciliation of recorded evidence; never probes or changes runtime."""
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def running_services(inventory):
    return sum(str(row.get('health', '')).upper() in {'RUNNING', 'HEALTHY', 'ACTIVE'}
               for row in inventory['workloads'] + inventory['host_services'])


def rollback_gate(document, root):
    rows = document.get('candidate_promotions', []) + document.get('production_configuration_changes', [])
    if not rows:
        return 'FAIL'
    for row in rows:
        receipt = row.get('rehearsal_receipt', {})
        try:
            path = Path(root) / receipt['path']
            path.resolve().relative_to(Path(root).resolve())
            if digest(path) != receipt['sha256']:
                return 'FAIL'
            evidence = json.loads(path.read_text())
            expected = {key: row[key] for key in ('service', 'before_state', 'after_state',
                        'after_source_sha', 'after_image_digest') if key in row}
            if (evidence.get('status') != 'PASS' or evidence.get('rollback') != 'PASS'
                    or evidence.get('forward_recovery') != 'PASS'
                    or not evidence.get('observed_at')
                    or evidence.get('binding') != expected
                    or row.get('artifact_binding') == 'FAIL'):
                return 'FAIL'
        except (KeyError, TypeError, ValueError, OSError):
            return 'FAIL'
    return 'PASS'


def gate_bindings(document, root):
    bindings = {}
    for name, row in document['gates'].items():
        if row['evidence'] == 'EXTERNAL_AUTHORITY_REQUIRED':
            if row['status'] != 'FAIL':
                raise ValueError('missing authority cannot pass')
            continue
        observed = digest(Path(root) / row['evidence'])
        if observed != row.get('evidence_sha256'):
            raise ValueError(f'{name}: evidence digest mismatch')
        bindings[name] = {'path': row['evidence'], 'sha256': observed, 'status': row['status']}
    return bindings
