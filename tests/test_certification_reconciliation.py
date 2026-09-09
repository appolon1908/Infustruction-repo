"""Offline regressions: no daemon, host, credential or production operation."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import certification_evidence as evidence
import generate_full_platform_certification as full
import generate_server37_api_matrix as matrix
import yaml


class EvidenceTests(unittest.TestCase):
    def test_running_count_uses_observations(self):
        inventory = {'workloads': [{'health': x} for x in ('RUNNING','HEALTHY','UNHEALTHY','EXITED')], 'host_services': [{'health':'ACTIVE'}]}
        self.assertEqual(evidence.running_services(inventory), 3)

    def test_gate_digest_rejects_changed_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'evidence.md'; p.write_text('observation')
            gates={'gates':{'RESTORE':{'status':'PASS','evidence':p.name,'evidence_sha256':evidence.digest(p)}}}
            self.assertEqual(evidence.gate_bindings(gates,tmp)['RESTORE']['status'],'PASS')
            p.write_text('different observation')
            with self.assertRaises(ValueError): evidence.gate_bindings(gates,tmp)

    def test_rollback_requires_bound_complete_rehearsal(self):
        with tempfile.TemporaryDirectory() as tmp:
            row={'service':'test','after_source_sha':'a'*40,'after_image_digest':'sha256:'+'b'*64}
            doc={'candidate_promotions':[row]}
            self.assertEqual(evidence.rollback_gate(doc,tmp),'FAIL')
            body={'status':'PASS','rollback':'PASS','forward_recovery':'PASS','observed_at':'2026-09-09T00:00:00Z','binding':dict(row)}
            p=Path(tmp)/'receipt.json'; p.write_text(json.dumps(body))
            row['rehearsal_receipt']={'path':p.name,'sha256':evidence.digest(p)}
            self.assertEqual(evidence.rollback_gate(doc,tmp),'PASS')
            row['after_source_sha']='c'*40
            self.assertEqual(evidence.rollback_gate(doc,tmp),'FAIL')
            row['after_source_sha']='a'*40
            body['forward_recovery']='FAIL'; p.write_text(json.dumps(body)); row['rehearsal_receipt']['sha256']=evidence.digest(p)
            self.assertEqual(evidence.rollback_gate(doc,tmp),'FAIL')

    def test_regenerated_matrix_reconciles_required_and_source_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            with patch.object(matrix,'OUTPUT_MATRIX',out/'matrix.yaml'), patch.object(matrix,'OUTPUT_ROLLBACK',out/'rollback.yaml'):
                matrix.main()
            result=yaml.safe_load((out/'matrix.yaml').read_text())
            ops=result['canonical_custom_contract']['operations']
            self.assertEqual(result['authoritative_baseline']['total_source_implemented_not_deployed'],sum(x['classification']=='MISSING_REQUIRED' and x['source_implemented'] for x in ops))
            self.assertEqual(result['live_runtime_classification_counts']['REQUIRED_LIVE'],sum(x['classification']=='REQUIRED_LIVE' for x in ops))
            for row in yaml.safe_load((out/'rollback.yaml').read_text())['candidate_promotions']:
                self.assertEqual(row['after_source_sha'],result['candidate_source_authority'][row['authority_service']]['source_sha'])
                if row.get('historical_artifact'):
                    self.assertIsNone(row['after_image_digest'])
                    self.assertEqual(row['artifact_binding'],'FAIL')

    def test_admin_denial_requires_observed_403(self):
        from urllib.error import HTTPError, URLError
        from unittest.mock import Mock
        for status in (403, 200, 500, None):
            opener = Mock()
            opener.open.side_effect = HTTPError('https://fixture.invalid', status, '', {}, None) if status else URLError('offline')
            with patch.object(full, 'command', return_value='{}'), patch.object(full, 'probe_container_http', return_value=200), patch.object(full.urllib.request, 'build_opener', return_value=opener):
                rows = full.provider_endpoints()
            admin = next(row for row in rows if row['path'] == 'https://admin.telnexa.co/*')
            self.assertEqual(admin['runtime_verification'] == 'INTENTIONAL_HTTPS_403', status == 403)
            self.assertEqual(admin['implementation_status'], 'N/A' if status == 403 else 'PARTIAL')

    def test_recorded_regeneration_never_calls_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            import shutil
            for p in ROOT.glob('*.yaml'): shutil.copy(p,root/p.name)
            for p in ROOT.glob('*.md'): shutil.copy(p,root/p.name)
            def forbidden(*args, **kwargs): raise AssertionError('runtime call during recorded regeneration')
            with patch.object(full, 'ROOT', root), patch.object(full, 'GATE_EVIDENCE_PATH', root/'SERVER-37-PRODUCTION-GATE-EVIDENCE.yaml'), patch.object(full, 'command', side_effect=forbidden), patch.object(sys, 'argv', ['generator', '--from-recorded']):
                full.main()
            report=yaml.safe_load((root/'FULL-PLATFORM-PRODUCTION-CERTIFICATION.yaml').read_text())
            self.assertEqual(report['RESTORE'],'FAIL')
            self.assertTrue(report['EVIDENCE_BINDINGS'])

    def shell_function(self, name):
        text=(ROOT/'operations/server37/klyrow/klyrow-stack').read_text()
        start=text.index(name+'(){')
        # Definitions precede the top-level case and close on their own line,
        # except the compact timestamp selector.
        if name=='latest_dir': return text[start:text.index('\n',start)]
        return text[start:text.index('\n}',start)+2]

    def test_archive_selector_ignores_non_timestamped_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('20260902T235702Z','20260903T004453Z','zz-rollback','20260903T004453Z-extra'):
                p=Path(tmp)/name; p.mkdir(); (p/'backup.tar.gpg').touch()
            run=subprocess.run(['bash','-c',self.shell_function('latest_dir')+'\nlatest_dir'],env={'BACKUPS':tmp,'PATH':'/usr/bin:/bin'},capture_output=True,text=True,check=True)
            self.assertEqual(run.stdout.strip(),'20260903T004453Z')

    def test_mariadb_import_failure_cannot_pass(self):
        script='''set -Eeuo pipefail
docker(){
  if [[ "$1" == inspect ]]; then printf 'sha256:%064d\n' 1
  elif [[ "$*" == *'mariadb --user=root restore_fixture'* ]]; then cat >/dev/null; return 9
  fi
}
gzip(){ printf 'SQL'; }
'''+self.shell_function('restore_mariadb')+'\nrestore_mariadb fixture source dump\necho FALSE_PASS\n'
        run=subprocess.run(['bash','-c',script],capture_output=True,text=True)
        self.assertNotEqual(run.returncode,0)
        self.assertNotIn('FALSE_PASS',run.stdout)

    def test_frontend_failure_restores_previous_service(self):
        script='''set -Eeuo pipefail
ROLLBACK_COMPOSE=(compose)
docker(){ echo "docker $*"; }
compose(){ echo "compose $*"; }
curl(){ return 7; }
'''+self.shell_function('rollback_frontend')+'\nrollback_frontend\necho FALSE_PASS\n'
        run=subprocess.run(['bash','-c',script],capture_output=True,text=True)
        self.assertNotEqual(run.returncode,0)
        self.assertNotIn('FALSE_PASS',run.stdout)
        # Function intentionally suppresses operation output; fake Docker records via stderr.
        script=script.replace('echo "docker $*"','echo "docker $*" >&2')
        run=subprocess.run(['bash','-c',script],capture_output=True,text=True)
        self.assertIn('docker start klyrow-web-production',run.stderr)

if __name__=='__main__': unittest.main()
