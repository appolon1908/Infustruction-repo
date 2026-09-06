from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "operations/superset-bounded-release/contract.v1.json"
VALIDATOR = ROOT / "scripts/validate_superset_bounded_release_contract.py"


def load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("superset_bounded_validator", VALIDATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("validator module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SupersetBoundedReleaseContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validator = load_validator()

    def setUp(self) -> None:
        self.data = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def validate(self, data: dict) -> str:
        return self.validator.validate(data, json.dumps(data, sort_keys=True))

    def release_identity(self) -> dict:
        digest = "sha256:" + "b" * 64
        return {
            "source_sha": "a" * 40,
            "release_tag": "codestra-superset-v2026.9.1",
            "image": f"ghcr.io/appolon1908-hue/superset-superset@{digest}",
            "image_digest": digest,
            "release_run_id": 33800000000,
            "release_evidence_sha256": "c" * 64,
        }

    def test_canonical_contract_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(VALIDATOR)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("SUPERSET_BOUNDED_RELEASE_CONTRACT=PASS", completed.stdout)

    def test_release_cannot_activate_runtime(self) -> None:
        self.assertFalse(self.data["release"]["runtime_activation_by_release"])
        self.assertFalse(self.data["safety_state"]["deployment_authorized"])
        self.assertFalse(self.data["safety_state"]["production_certified"])

    def test_runner_and_environment_contract_is_exact(self) -> None:
        staging = self.data["staging"]
        production = self.data["production_readonly_canary"]
        self.assertEqual(staging["runner_labels"], ["self-hosted", "codestra-staging"])
        self.assertEqual(staging["environment"], "staging-readonly")
        self.assertEqual(
            production["runner_labels"],
            ["self-hosted", "codestra-production-canary"],
        )
        self.assertEqual(production["environment"], "production-readonly-canary")

    def test_canary_is_one_percent_get_head_only_and_rolls_back(self) -> None:
        canary = self.data["production_readonly_canary"]
        self.assertEqual(canary["maximum_percent"], 1)
        self.assertEqual(canary["methods"], ["GET", "HEAD"])
        self.assertTrue(canary["read_only"])
        self.assertTrue(canary["runtime_must_be_restored_after_canary"])
        self.assertEqual(canary["controller"]["required_owner_uid"], 0)
        self.assertFalse(canary["controller"]["group_world_writable"])

    def test_pending_candidate_has_no_fabricated_identity(self) -> None:
        candidate = self.data["candidate"]
        self.assertEqual(candidate["status"], "PENDING_PROTECTED_SUPERSET_RELEASE")
        for key, value in candidate.items():
            if key != "status":
                self.assertIsNone(value, key)
        self.assertEqual(self.validate(self.data), "PENDING_PROTECTED_SUPERSET_RELEASE")

    def test_signed_release_state_accepts_only_release_evidence(self) -> None:
        data = copy.deepcopy(self.data)
        data["candidate"].update(self.release_identity())
        data["candidate"]["status"] = "SIGNED_RELEASE_READY"
        self.assertEqual(self.validate(data), "SIGNED_RELEASE_READY")

        data["candidate"]["hosted_staging_evidence_sha256"] = "d" * 64
        with self.assertRaisesRegex(SystemExit, "must_be_null"):
            self.validate(data)

    def test_hosted_staging_state_requires_hosted_evidence_only(self) -> None:
        data = copy.deepcopy(self.data)
        data["candidate"].update(self.release_identity())
        data["candidate"].update(
            {
                "status": "HOSTED_STAGING_CERTIFIED",
                "hosted_staging_evidence_sha256": "d" * 64,
            }
        )
        self.assertEqual(self.validate(data), "HOSTED_STAGING_CERTIFIED")
        data["candidate"]["bounded_staging_evidence_sha256"] = "e" * 64
        with self.assertRaisesRegex(SystemExit, "must_be_null"):
            self.validate(data)

    def test_bounded_staging_state_requires_real_staging_bindings(self) -> None:
        data = copy.deepcopy(self.data)
        data["candidate"].update(self.release_identity())
        data["candidate"].update(
            {
                "status": "BOUNDED_STAGING_CERTIFIED",
                "hosted_staging_evidence_sha256": "d" * 64,
                "bounded_staging_evidence_sha256": "e" * 64,
            }
        )
        with self.assertRaisesRegex(SystemExit, "bounded_staging_without_stage6_host_created"):
            self.validate(data)

        for key in (
            "stage6_host_created",
            "codestra_staging_runner_registered",
            "staging_readonly_environment_configured",
        ):
            data["required_external_bindings"][key] = True
        self.assertEqual(self.validate(data), "BOUNDED_STAGING_CERTIFIED")

    def test_final_readonly_certification_is_valid_without_authorizing_writes(self) -> None:
        data = copy.deepcopy(self.data)
        data["candidate"].update(self.release_identity())
        data["candidate"].update(
            {
                "status": "PRODUCTION_READONLY_CERTIFIED",
                "hosted_staging_evidence_sha256": "d" * 64,
                "bounded_staging_evidence_sha256": "e" * 64,
                "production_canary_evidence_sha256": "f" * 64,
            }
        )
        for key in data["required_external_bindings"]:
            data["required_external_bindings"][key] = True
        data["safety_state"]["production_certified"] = True

        self.assertEqual(self.validate(data), "PRODUCTION_READONLY_CERTIFIED")
        self.assertFalse(data["safety_state"]["deployment_authorized"])
        for key, value in data["safety_state"].items():
            if key != "production_certified":
                self.assertFalse(value, key)

    def test_final_certification_rejects_missing_binding_or_live_effect(self) -> None:
        data = copy.deepcopy(self.data)
        data["candidate"].update(self.release_identity())
        data["candidate"].update(
            {
                "status": "PRODUCTION_READONLY_CERTIFIED",
                "hosted_staging_evidence_sha256": "d" * 64,
                "bounded_staging_evidence_sha256": "e" * 64,
                "production_canary_evidence_sha256": "f" * 64,
            }
        )
        for key in data["required_external_bindings"]:
            data["required_external_bindings"][key] = True
        data["safety_state"]["production_certified"] = True

        data["required_external_bindings"]["superset_canary_controller_checksum_bound"] = False
        with self.assertRaisesRegex(SystemExit, "production_certified_without_external_bindings"):
            self.validate(data)

        data["required_external_bindings"]["superset_canary_controller_checksum_bound"] = True
        data["safety_state"]["live_write"] = True
        with self.assertRaisesRegex(SystemExit, "live_effects_not_fail_closed"):
            self.validate(data)

    def test_intermediate_state_cannot_claim_production_certification(self) -> None:
        data = copy.deepcopy(self.data)
        data["candidate"].update(self.release_identity())
        data["candidate"]["status"] = "SIGNED_RELEASE_READY"
        data["safety_state"]["production_certified"] = True
        with self.assertRaisesRegex(SystemExit, "production_certified_flag_state_mismatch"):
            self.validate(data)

    def test_every_current_external_binding_and_live_effect_is_fail_closed(self) -> None:
        self.assertTrue(self.data["required_external_bindings"])
        self.assertTrue(self.data["safety_state"])
        self.assertTrue(all(value is False for value in self.data["required_external_bindings"].values()))
        self.assertTrue(all(value is False for value in self.data["safety_state"].values()))


if __name__ == "__main__":
    unittest.main()
