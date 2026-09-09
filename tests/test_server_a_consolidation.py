"""Offline regressions for the immutable September 1 inventory snapshot."""
from pathlib import Path
import importlib.util
import json
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('inventory', ROOT / 'scripts/validate_server_a_consolidation.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class InventoryTests(unittest.TestCase):
    def test_committed_snapshot_retains_all_102_containers(self):
        m.validate()
        self.assertEqual(len(json.loads((m.EVIDENCE / 'PRODUCTION-RUNTIME-INVENTORY.json').read_text())), 102)

    def test_bindings_distinguish_loopback_private_public_and_ipv6(self):
        for address in ('127.0.0.1', '10.40.0.1', '0.0.0.0', '[::1]', '[::]'):
            with self.subTest(address=address):
                binding = f'{address}:18080->8080/tcp'
                self.assertEqual(m.parse_ports(f'8081/tcp, {binding}'), ([binding], ['8081/tcp']))

    def test_ranges_are_preserved_without_loss(self):
        binding = '127.0.0.1:18101-18116->18101-18116/tcp'
        self.assertEqual(m.parse_ports(binding), ([binding], []))
        with self.assertRaises(ValueError):
            m.parse_ports('127.0.0.1:1-3->1-2/tcp')

    def test_empty_and_exposed_only_are_not_published(self):
        self.assertEqual(m.parse_ports(''), ([], []))
        self.assertEqual(m.read_port_snapshot('container\tNONE\n'), {'container': ([], [])})
        with self.assertRaises(ValueError):
            m.read_port_snapshot('container\n')
        self.assertEqual(m.parse_ports('80/tcp, 443/udp'), ([], ['80/tcp', '443/udp']))

    def test_duplicate_missing_header_or_host_binding_fails(self):
        for mutation in ('header', 'binding', 'duplicate', 'self-checksum', 'missing-checksum'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                target = Path(temp) / 'evidence'
                shutil.copytree(m.EVIDENCE, target)
                if mutation == 'header':
                    p = target / 'PRODUCTION-CONTAINER-INVENTORY.csv'
                    p.write_text(p.read_text().split('\n', 1)[1])
                elif mutation in ('binding', 'duplicate'):
                    p = target / 'PRODUCTION-RUNTIME-INVENTORY.json'
                    value = json.loads(p.read_text())
                    if mutation == 'binding':
                        value[0]['published_ports'] = ['80/tcp']
                    else:
                        value.append(value[0])
                    p.write_text(json.dumps(value))
                else:
                    p = target / 'SHA256SUMS'
                    p.write_text(('0' * 64 + '  SHA256SUMS\n') if mutation == 'self-checksum' else '')
                with self.assertRaises(ValueError):
                    m.validate(target)

    def test_duplicate_port_rows_are_rejected(self):
        with self.assertRaises(ValueError):
            m.read_port_snapshot('same\t80/tcp\nsame\t80/tcp\n')


if __name__ == '__main__':
    unittest.main()
