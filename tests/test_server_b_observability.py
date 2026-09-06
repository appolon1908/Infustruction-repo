"""Offline regressions for complete, non-activatable Server B source evidence."""
from pathlib import Path
import contextlib
import importlib.util
import io
import json
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REL = Path('hosts/37.27.128.39/observability')
HOST = ROOT / REL


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class AuthorityTests(unittest.TestCase):
    def prepare(self, temp):
        repo = Path(temp)
        shutil.copytree(HOST, repo / REL, ignore=shutil.ignore_patterns('__pycache__'))
        registry = repo / 'config/observability/repository-registry.v1.json'
        registry.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / 'config/observability/repository-registry.v1.json', registry)
        return repo

    def test_all_fourteen_components_are_in_every_authority_matrix(self):
        validator = module('authority', HOST / 'validate.py')
        with contextlib.redirect_stdout(io.StringIO()):
            validator.main()
        for name in ('repository-inventory.json', 'production-source-lock.json', 'production-image-lock.json',
                     'runtime-inventory.json', 'api-certification.json', 'network-inventory.json',
                     'backup-restore-matrix.json', 'rollback-matrix.json'):
            with self.subTest(name=name):
                value = json.loads((HOST / name).read_text())
                self.assertEqual(len(value['components']), 14)
                self.assertEqual({row['component'] for row in value['components']}, validator.EXPECTED)
        source = json.loads((HOST / 'production-source-lock.json').read_text())
        for row in source['components']:
            if row['component'] in {'Alertmanager', 'PostgreSQL Exporter'}:
                self.assertIsNone(row['source_sha'])
                self.assertIsNone(row['staging_sha'])
                self.assertEqual(row['source_evidence_status'], 'NOT_CAPTURED')
                self.assertIs(row['activation_allowed'], False)

    def test_layout_activation_and_wrong_host_fail_under_normal_and_optimized_python(self):
        for key, replacement in (('activation_allowed', True), ('activation_allowed', 0),
                                 ('activation_allowed', 'false'), ('server', 'other-host')):
            with self.subTest(key=key, value=replacement), tempfile.TemporaryDirectory() as temp:
                repo = self.prepare(temp)
                path = repo / REL / 'release-layout.json'
                value = json.loads(path.read_text()); value[key] = replacement
                path.write_text(json.dumps(value))
                for args in (['python3'], ['python3', '-O']):
                    result = subprocess.run(args + [str(repo / REL / 'validate.py')], capture_output=True, text=True)
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn('authority=FAIL', result.stderr)

    def test_missing_or_duplicate_component_cannot_validate(self):
        for kind in ('missing', 'duplicate'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                repo = self.prepare(temp)
                path = repo / REL / 'production-source-lock.json'
                value = json.loads(path.read_text())
                if kind == 'missing': value['components'].pop()
                else: value['components'].append(value['components'][0])
                path.write_text(json.dumps(value))
                result = subprocess.run(['python3', str(repo / REL / 'validate.py')], capture_output=True)
                self.assertNotEqual(result.returncode, 0)

    def test_generator_is_deterministic(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self.prepare(temp)
            before = {p.name: p.read_bytes() for p in (repo / REL).iterdir() if p.is_file()}
            subprocess.run(['python3', str(repo / REL / 'generate_evidence.py')], check=True)
            after = {p.name: p.read_bytes() for p in (repo / REL).iterdir() if p.is_file()}
            self.assertEqual(before, after)

    def test_regenerated_deleted_file_is_detected_as_untracked(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self.prepare(temp)
            def git(*args):
                return subprocess.run(['git', '-C', str(repo), *args], check=True, text=True, capture_output=True)
            git('init', '-q'); git('config', 'user.name', 'Test'); git('config', 'user.email', 'test@example.invalid')
            git('add', '.'); git('commit', '-qm', 'base')
            git('rm', str(REL / 'release-layout.json')); git('commit', '-qm', 'delete generated evidence')
            subprocess.run(['python3', str(repo / REL / 'generate_evidence.py')], check=True)
            # Reproduce the old check's false success, then exercise the fixed one.
            git('diff', '--exit-code', '--', str(REL))
            status = git('status', '--porcelain=v1', '--untracked-files=all', '--', str(REL)).stdout
            self.assertIn('?? ' + str(REL / 'release-layout.json'), status)
            self.assertNotEqual(status.strip(), '')


if __name__ == '__main__':
    unittest.main()
