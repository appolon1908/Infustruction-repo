from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "repository_name_aliases",
    ROOT / "scripts" / "validate_repository_name_aliases.py",
)
assert SPEC is not None and SPEC.loader is not None
AUTHORITY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUTHORITY)


class RepositoryNameAliasTests(unittest.TestCase):
    def test_runtime_critical_classification_is_exact(self) -> None:
        data = AUTHORITY.load()
        changed = copy.deepcopy(data)
        changed["mappings"][0]["runtime_critical"] = False
        with patch.object(AUTHORITY, "load", return_value=changed):
            with self.assertRaises(SystemExit):
                AUTHORITY.validate()

    def test_planned_target_is_denied_in_operational_source(self) -> None:
        target = "appolon1908-hue/restaurant-frontend"
        fake_path = ROOT / "release" / "synthetic-lock.json"
        with patch.object(
            Path,
            "read_text",
            return_value='{"repository":"' + target + '"}',
        ):
            with self.assertRaises(SystemExit):
                AUTHORITY.validate_planned_targets_absent(
                    [fake_path],
                    {target},
                )

    def test_renamed_mapping_resolves_the_target_slug(self) -> None:
        data = AUTHORITY.load()
        changed = copy.deepcopy(data)
        changed["status"] = "PARTIALLY_RENAMED_VERIFIED"
        social = next(
            item
            for item in changed["mappings"]
            if item["repository_id"] == 1351353723
        )
        social["status"] = "RENAMED_VERIFIED"

        expected = "appolon1908-hue/Codestra-Social-Control-Plane"
        self.assertEqual(
            AUTHORITY.operational_repository_for_mapping(social),
            expected,
        )
        self.assertEqual(
            AUTHORITY.operational_repository_map(changed)[1351353723],
            expected,
        )
        self.assertNotIn(
            expected,
            AUTHORITY.forbidden_non_operational_names(changed),
        )
        self.assertIn(
            "appolon1908-hue/Codesrea-Social-",
            AUTHORITY.forbidden_non_operational_names(changed),
        )

    def test_operational_scan_includes_all_repository_consumers(self) -> None:
        expected = (
            ROOT / ".github" / "workflows" / "release.yml",
            ROOT / ".github" / "actions" / "checkout-source" / "action.yml",
            ROOT / "infra" / "modules" / "source.tf",
            ROOT / "scripts" / "checkout-release.sh",
            ROOT / "main.tf",
            ROOT / "checkout.sh",
            ROOT / ".gitmodules",
        )
        for path in expected:
            with self.subTest(path=path):
                self.assertTrue(AUTHORITY.is_operational_source(path))

    def test_historical_lock_is_not_active_operational_source(self) -> None:
        self.assertFalse(
            AUTHORITY.is_operational_source(AUTHORITY.HISTORICAL_STAGE6_LOCK)
        )

    def test_caddy_fragment_is_discovered_as_operational_source(self) -> None:
        fragment = ROOT / "operations" / "caddy" / "postgres-exporter.caddy"
        self.assertTrue(AUTHORITY.is_operational_source(fragment))

    def test_governed_repository_id_requires_current_name(self) -> None:
        fake_path = ROOT / "release" / "synthetic-source-lock.json"
        payload = (
            '{"repository_id":1351353723,'
            '"repository":"appolon1908-hue/unapproved-social-fork"}'
        )
        with patch.object(Path, "read_text", return_value=payload):
            with self.assertRaises(SystemExit):
                AUTHORITY.validate_repository_id_current_name_pairing([fake_path])

    def test_repository_id_pairing_is_scoped_to_each_json_record(self) -> None:
        fake_path = ROOT / "release" / "synthetic-multi-entry-lock.json"
        payload = json.dumps(
            {
                "entries": [
                    {
                        "repository_id": 1351353723,
                        "repository": "appolon1908-hue/Codesrea-Social-",
                    },
                    {
                        "repository_id": 1351353723,
                        "repository": "appolon1908-hue/unapproved-social-fork",
                    },
                ]
            }
        )
        with patch.object(Path, "read_text", return_value=payload):
            with self.assertRaises(SystemExit):
                AUTHORITY.validate_repository_id_current_name_pairing([fake_path])

    def test_json_record_rejects_conflicting_repository_fields(self) -> None:
        fake_path = ROOT / "release" / "synthetic-conflict.json"
        payload = json.dumps(
            {
                "repository_id": 1351353723,
                "current_repository": "appolon1908-hue/Codesrea-Social-",
                "repository": "appolon1908-hue/unapproved-social-fork",
            }
        )
        with patch.object(Path, "read_text", return_value=payload):
            with self.assertRaises(SystemExit):
                AUTHORITY.validate_repository_id_current_name_pairing([fake_path])

    def test_repository_id_pairing_is_scoped_to_toml_table(self) -> None:
        fake_path = ROOT / "release" / "synthetic-source-lock.toml"
        payload = (
            "[approved]\n"
            "repository_id = 1351353723\n"
            'repository = "appolon1908-hue/Codesrea-Social-"\n'
            "[unapproved]\n"
            'repository = "appolon1908-hue/unapproved-social-fork"\n'
        )
        with patch.object(Path, "read_text", return_value=payload):
            AUTHORITY.validate_repository_id_current_name_pairing([fake_path])

        changed = payload.replace(
            'repository = "appolon1908-hue/Codesrea-Social-"',
            'repository = "appolon1908-hue/unapproved-social-fork"',
        )
        with patch.object(Path, "read_text", return_value=changed):
            with self.assertRaises(SystemExit):
                AUTHORITY.validate_repository_id_current_name_pairing([fake_path])

    def test_text_record_rejects_conflicting_repository_fields(self) -> None:
        fake_path = ROOT / "release" / "synthetic-source-lock.yaml"
        payload = (
            "- repository_id: 1351353723\n"
            "  current_repository: appolon1908-hue/Codesrea-Social-\n"
            "  repository: appolon1908-hue/unapproved-social-fork\n"
        )
        with patch.object(Path, "read_text", return_value=payload):
            with self.assertRaises(SystemExit):
                AUTHORITY.validate_repository_id_current_name_pairing([fake_path])

    def test_text_record_rejects_repository_owned_by_another_account(self) -> None:
        fake_path = ROOT / "production.tf"
        payload = (
            "repository_id = 1351353723\n"
            'current_repository = "appolon1908-hue/Codesrea-Social-"\n'
            'repository = "attacker/unapproved-fork"\n'
        )
        with patch.object(Path, "read_text", return_value=payload):
            with self.assertRaises(SystemExit):
                AUTHORITY.validate_repository_id_current_name_pairing([fake_path])

    def test_known_release_binding_rejects_unapproved_repository(self) -> None:
        release_matrix = ROOT / "release" / "stage6-8-release-matrix.yaml"
        originals = {
            path: path.read_text(encoding="utf-8")
            for path in (
                ROOT / "STAGE6-SOURCE-LOCK.yaml",
                release_matrix,
                ROOT / "config" / "marketing-stage9-readiness.json",
                ROOT
                / "releases"
                / "STAGE6-STAGING-EXACT-SOURCE-LOCK-2026-08-30.json",
                ROOT / "scripts" / "certify_marketing_stage9.py",
            )
        }

        def fake_require(path: Path) -> str:
            text = originals[path]
            if path == release_matrix:
                return text.replace(
                    "appolon1908-hue/Codesrea-Social-",
                    "appolon1908-hue/unapproved-social-fork",
                )
            return text

        with patch.object(AUTHORITY, "require_file", side_effect=fake_require):
            with self.assertRaises(SystemExit):
                AUTHORITY.validate_known_operational_bindings()

    def test_exporter_host_port_publication_is_denied(self) -> None:
        fake_path = ROOT / "deploy" / "compose.yaml"
        payload = (
            "services:\n"
            "  postgres-exporter:\n"
            "    ports:\n"
            "      - '9187:9187'\n"
        )
        with patch.object(Path, "read_text", return_value=payload):
            with self.assertRaises(SystemExit):
                AUTHORITY.validate_postgres_exporter_privacy([fake_path])

    def test_exporter_inline_host_port_publication_is_denied(self) -> None:
        fake_path = ROOT / "deploy" / "compose.yaml"
        payload = (
            "services:\n"
            "  postgres-exporter:\n"
            '    ports: ["0.0.0.0:9187:9187"]\n'
        )
        with patch.object(Path, "read_text", return_value=payload):
            with self.assertRaises(SystemExit):
                AUTHORITY.validate_postgres_exporter_privacy([fake_path])

    def test_private_kubernetes_container_port_is_allowed(self) -> None:
        fake_path = ROOT / "k8s" / "postgres-exporter-deployment.yaml"
        payload = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres-exporter
spec:
  template:
    spec:
      containers:
        - name: postgres-exporter
          ports:
            - name: metrics
              containerPort: 9187
---
apiVersion: v1
kind: Service
metadata:
  name: postgres-exporter
spec:
  type: ClusterIP
  ports:
    - name: metrics
      port: 9187
      targetPort: 9187
"""
        with patch.object(Path, "read_text", return_value=payload):
            AUTHORITY.validate_postgres_exporter_privacy([fake_path])

    def test_kubernetes_host_port_is_denied(self) -> None:
        fake_path = ROOT / "k8s" / "postgres-exporter-deployment.yaml"
        payload = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres-exporter
spec:
  template:
    spec:
      containers:
        - name: postgres-exporter
          ports:
            - containerPort: 9187
              hostPort: 9187
"""
        with patch.object(Path, "read_text", return_value=payload):
            with self.assertRaises(SystemExit):
                AUTHORITY.validate_postgres_exporter_privacy([fake_path])

    def test_public_exporter_service_with_named_target_port_is_denied(self) -> None:
        fake_path = ROOT / "k8s" / "postgres-exporter-service.yaml"
        payload = """apiVersion: v1
kind: Service
metadata:
  name: postgres-exporter
spec:
  type: LoadBalancer
  selector:
    app: postgres-exporter
  ports:
    - name: web
      port: 80
      targetPort: metrics
"""
        with patch.object(Path, "read_text", return_value=payload):
            with self.assertRaises(SystemExit):
                AUTHORITY.validate_postgres_exporter_privacy([fake_path])

    def test_unrelated_public_service_in_exporter_manifest_is_allowed(self) -> None:
        fake_path = ROOT / "k8s" / "combined-services.yaml"
        payload = """apiVersion: v1
kind: Service
metadata:
  name: postgres-exporter
spec:
  type: ClusterIP
  ports:
    - name: metrics
      port: 9187
      targetPort: metrics
---
apiVersion: v1
kind: Service
metadata:
  name: unrelated-public-ui
spec:
  type: LoadBalancer
  ports:
    - name: web
      port: 80
      targetPort: http
"""
        with patch.object(Path, "read_text", return_value=payload):
            AUTHORITY.validate_postgres_exporter_privacy([fake_path])

    def test_historical_source_lock_digest_is_complete(self) -> None:
        original = AUTHORITY.HISTORICAL_STAGE6_LOCK.read_text(encoding="utf-8")

        def fake_require(path: Path) -> str:
            if path == AUTHORITY.HISTORICAL_STAGE6_LOCK:
                return original.replace(
                    '"environment": "staging"',
                    '"environment": "test"',
                )
            return path.read_text(encoding="utf-8")

        with patch.object(AUTHORITY, "require_file", side_effect=fake_require):
            with self.assertRaises(SystemExit):
                AUTHORITY.validate_known_operational_bindings()

    def test_exporter_gateway_route_is_denied(self) -> None:
        fake_path = ROOT / "operations" / "caddy" / "postgres-exporter.caddy"
        payload = "metrics.example.test { reverse_proxy postgres-exporter:9187 }\n"
        with patch.object(Path, "read_text", return_value=payload):
            with self.assertRaises(SystemExit):
                AUTHORITY.validate_postgres_exporter_privacy([fake_path])

    def test_exporter_kubernetes_httproute_is_denied(self) -> None:
        fake_path = ROOT / "k8s" / "metrics-route.yaml"
        payload = """apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: postgres-exporter-public
spec:
  parentRefs:
    - name: public-gateway
  rules:
    - backendRefs:
        - name: postgres-exporter
          port: 9187
"""
        with patch.object(Path, "read_text", return_value=payload):
            with self.assertRaises(SystemExit):
                AUTHORITY.validate_postgres_exporter_privacy([fake_path])


if __name__ == "__main__":
    unittest.main()
