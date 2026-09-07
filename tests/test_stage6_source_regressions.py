"""Offline regression tests: no Docker, provider, SSH or production operations."""
from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import resolve_stage6_source_lock as resolver
import validate_stage6_remediation as remediation

DIGEST = "sha256:" + "a" * 64
REVISION = "b" * 40


def registry(reference, digest):
    return {"reference": reference + "@" + digest, "resolved_digest": digest, "registry_resolution": "PASS"}


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.lock = yaml.safe_load((ROOT / "STAGE6-SOURCE-LOCK.yaml").read_text())
        self.registry_patch = patch.object(resolver, "registry_resolution", side_effect=registry)
        self.registry_mock = self.registry_patch.start()
        self.addCleanup(self.registry_patch.stop)
        labels = patch.object(resolver, "local_image_labels", return_value={})
        labels.start()
        self.addCleanup(labels.stop)
        verifier = patch.object(resolver, "middleware_artifact_verification", return_value={"status": "FAIL"})
        verifier.start()
        self.addCleanup(verifier.stop)

    def test_every_committed_component_returns_evidence_without_keyerror(self):
        for name, definition in self.lock["repositories"].items():
            with self.subTest(component=name):
                result = resolver.artifact_evidence(name, definition, {"status": "PASS"})
                self.assertIsInstance(result["status"], str)

    def test_kong_and_keycloak_use_reviewed_vendor_references(self):
        for name, reference in (("kong", "docker.io/kong/kong-gateway"), ("keycloak", "quay.io/keycloak/keycloak")):
            with self.subTest(component=name):
                result = resolver.artifact_evidence(name, {"artifact_class": "official_upstream_image_plus_codestra_config", "image_digest": DIGEST, "revision": REVISION}, {"status": "PASS"})
                self.assertEqual(result["reference"], reference + "@" + DIGEST)
                self.assertEqual(result["status"], "PASS_OFFICIAL_DIGEST_WITH_SEPARATE_CONFIG")
                self.assertTrue(result["image_not_built_from_codestra_config"])

    def test_custom_attestation_is_not_misclassified_as_vendor_provenance(self):
        result = resolver.artifact_evidence("social_runtime", {"artifact_class": "custom_attested_image", "image_digest": DIGEST, "revision": REVISION}, {"status": "PASS"})
        self.assertEqual(result["reference"], "ghcr.io/appolon1908-hue/social.codestra.co@" + DIGEST)
        self.assertEqual(result["status"], "FAIL_ATTESTATION_VERIFICATION_REQUIRED")
        self.assertNotIn("image_not_built_from_codestra_config", result)

    def test_unknown_reference_and_wrong_class_fail_closed(self):
        definition = {"artifact_class": "official_upstream_image_plus_codestra_config", "image_digest": DIGEST, "revision": REVISION}
        result = resolver.artifact_evidence("unreviewed_component", definition, {"status": "PASS"})
        self.assertEqual(result["status"], "FAIL_UNREVIEWED_IMAGE_REFERENCE")
        result = resolver.artifact_evidence("social_runtime", definition, {"status": "PASS"})
        self.assertEqual(result["status"], "FAIL_ARTIFACT_CLASS_MISMATCH")
        self.registry_mock.assert_not_called()

    def test_invalid_digest_types_never_crash_or_query_registry(self):
        for value in (None, 42, [], "latest", "", "UNRESOLVED_NO_REVIEWED_RUNTIME_IMAGE"):
            with self.subTest(value=value):
                result = resolver.artifact_evidence("kong", {"artifact_class": "official_upstream_image_plus_codestra_config", "image_digest": value}, {"status": "PASS"})
                self.assertEqual(result["status"], "FAIL_UNRESOLVED_BLOCKING_ARTIFACT")
        self.registry_mock.assert_not_called()

    def test_fabricated_manifest_does_not_bypass_signature_verification(self):
        definition = self.lock["repositories"]["middleware"]
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            manifest.write_text(json.dumps({"source": {"git_sha": definition["revision"]}, "image": {"digest": definition["image_digest"]}}))
            with patch.object(resolver, "MIDDLEWARE_RELEASE_MANIFEST", manifest):
                result = resolver.artifact_evidence("middleware", definition, {"status": "PASS"})
                self.assertEqual(result["status"], "FAIL_CRYPTOGRAPHIC_PROVENANCE")
                for invalid in ("{", "[]", '{"source": [], "image": 3}'):
                    manifest.write_text(invalid)
                    result = resolver.artifact_evidence("middleware", definition, {"status": "PASS"})
                    self.assertEqual(result["status"], "FAIL_INVALID_RELEASE_MANIFEST")


class RuntimeBoundaryTests(unittest.TestCase):
    def test_wrong_docker_environment_is_rejected_before_inspection(self):
        with patch.dict(os.environ, {"DOCKER_HOST": "tcp://example.invalid:2375"}), patch.object(resolver, "run") as run:
            with self.assertRaises(RuntimeError):
                resolver.verify_inspection_host()
            run.assert_not_called()

    def test_local_address_does_not_authorize_a_remote_context(self):
        interfaces = json.dumps([{"addr_info": [{"family": "inet", "local": resolver.INSPECTION_HOST}]}])
        context = json.dumps([{"Endpoints": {"docker": {"Host": "tcp://example.invalid:2375"}}}])
        with patch.dict(os.environ, {"DOCKER_HOST": ""}), patch.object(resolver, "run", side_effect=[interfaces, "remote", context]):
            with self.assertRaises(RuntimeError):
                resolver.verify_inspection_host()

    def test_runtime_inspection_is_bound_to_local_endpoint(self):
        with patch.object(resolver, "run", return_value="") as run:
            self.assertEqual(resolver.docker_runtime(), [])
            run.assert_called_once_with("docker", "--host", resolver.DOCKER_ENDPOINT, "ps", "-q")

    def test_isolation_reports_actual_ports_and_rejects_missing_expose(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "deploy/staging/intake-observability"
            folder.mkdir(parents=True)
            (folder / "runtime-lock.v1.json").write_text(json.dumps({"external_effects_enabled": False, "activation": {"production_authorized": False}}))
            compose = {"services": {"middleware": {"expose": ["8080"]}}, "networks": {"private": {"internal": True}}}
            with patch.object(resolver, "ROOT", root):
                (folder / "compose.yaml").write_text(yaml.safe_dump(compose))
                self.assertEqual(resolver.isolation_evidence([])["status"], "PASS_SOURCE_ISOLATION_RUNTIME_NOT_ACTIVATED")
                compose["services"]["middleware"]["ports"] = ["8080:8080"]
                (folder / "compose.yaml").write_text(yaml.safe_dump(compose))
                result = resolver.isolation_evidence([])
                self.assertEqual(result["status"], "FAIL_SOURCE_ISOLATION")
                self.assertEqual(result["stage6_middleware_host_ports"], ["8080:8080"])
                self.assertFalse(result["stage6_no_host_ports"])
                compose["services"]["middleware"] = {}
                (folder / "compose.yaml").write_text(yaml.safe_dump(compose))
                self.assertEqual(resolver.isolation_evidence([])["status"], "FAIL_SOURCE_ISOLATION")


class RemediationTests(unittest.TestCase):
    def setUp(self):
        self.lock = yaml.safe_load((ROOT / "STAGE6-SOURCE-LOCK.yaml").read_text())
        folder = ROOT / "deploy/staging/runtime-reconciliation"
        self.middleware = yaml.safe_load((folder / "compose.middleware-source-remediation.yaml").read_text())
        self.odoo = yaml.safe_load((folder / "compose.odoo-source-remediation.yaml").read_text())

    def test_committed_remediation_pins_and_migration_isolation(self):
        remediation.validate_middleware(self.middleware, self.lock["repositories"]["middleware"])
        remediation.validate_odoo(self.odoo, self.lock["repositories"]["odoo"])

    def test_middleware_rejects_stale_images_and_automatic_migrations(self):
        changes = [
            ("middleware-staging", "image", "ghcr.io/appolon1908-hue/codestra-middleware@" + DIGEST),
            ("middleware-migration", "image", "ghcr.io/appolon1908-hue/codestra-middleware:latest"),
            ("middleware-staging", "command", "alembic upgrade head"),
            ("middleware-staging", "command", ["sh", "-c", "python scripts/migrate_runtime.py && uvicorn app:app"]),
            ("middleware-staging", "entrypoint", "python scripts/migrate_runtime.py"),
            ("middleware-migration", "restart", "always"),
            ("middleware-migration", "profiles", []),
            ("middleware-staging", "depends_on", ["middleware-migration"]),
        ]
        for name, key, value in changes:
            with self.subTest(service=name, key=key, value=value):
                compose = copy.deepcopy(self.middleware)
                compose["services"][name][key] = value
                with self.assertRaises(ValueError):
                    remediation.validate_middleware(compose, self.lock["repositories"]["middleware"])

    def test_odoo_rejects_long_short_and_shell_wrapped_module_flags(self):
        for command in ("odoo -i base", "odoo -ubase", "odoo --init=base", ["odoo", "--update", "base"], ["sh", "-c", "odoo --update=base"]):
            with self.subTest(command=command):
                compose = copy.deepcopy(self.odoo)
                compose["services"]["odoo19-staging"]["command"] = command
                with self.assertRaises(ValueError):
                    remediation.validate_odoo(compose, self.lock["repositories"]["odoo"])

    def test_odoo_migration_must_exit_and_safety_flags_cannot_enable(self):
        for key, value in (("restart", "always"), ("profiles", []), ("command", ["odoo", "--update=base", "--no-http"])):
            compose = copy.deepcopy(self.odoo)
            compose["services"]["odoo19-module-migration"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                remediation.validate_odoo(compose, self.lock["repositories"]["odoo"])
        compose = copy.deepcopy(self.middleware)
        compose["services"]["middleware-staging"]["environment"]["LIVE_PSTN_DIALING"] = "true"
        with self.assertRaises(ValueError):
            remediation.validate_middleware(compose, self.lock["repositories"]["middleware"])


if __name__ == "__main__":
    unittest.main()
