#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUEST = ROOT / "config" / "stage6-staging-host-provisioning-request.v1.json"
VALIDATOR = ROOT / "tools" / "validate_stage6_staging_host_request.py"
spec = importlib.util.spec_from_file_location("stage6_host_request", VALIDATOR)
assert spec and spec.loader
validator = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = validator
spec.loader.exec_module(validator)


class StagingHostRequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.request = json.loads(REQUEST.read_text(encoding="utf-8"))

    def run_validator(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR)], cwd=ROOT, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        )

    def test_repository_request_is_fail_closed_and_valid(self) -> None:
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("STAGE6_STAGING_HOST_REQUEST_AUTHORITY=PASS", result.stdout)
        self.assertIn("PROVISIONED_PENDING_CURRENT_VERIFICATION", result.stdout)
        self.assertIn("STAGE6_HOST_CREATED=YES", result.stdout)
        self.assertIn("STAGE6_HOST_VERIFIED=NO", result.stdout)
        self.assertIn("PRODUCTION_CERTIFIED=NO", result.stdout)

    def test_provisioning_is_recorded_without_false_verification(self) -> None:
        data = self.request
        self.assertTrue(data["host_created"])
        self.assertFalse(data["host_verified"])
        self.assertFalse(data["deployment_authorized"])
        self.assertFalse(data["production_certified"])
        self.assertIn("observed_evidence", data)

    def test_pending_evidence_is_checksum_bound(self) -> None:
        reference = self.request["observed_evidence"]
        evidence = validator.evidence_from_reference(reference)
        self.assertEqual(evidence["workflow"]["run_id"], 33455510182)
        self.assertEqual(evidence["workflow"]["source_sha"], "9a81bcca5a00f2e543a90594c2e7590efd527abf")
        self.assertTrue(evidence["current_verification_required"])
        self.assertTrue(any(value is None for value in evidence["provisioning_outputs"].values()))
        self.assertTrue(all(value == validator.PENDING for value in evidence["verification_results"].values()))

    def test_request_cannot_set_production_certified_true(self) -> None:
        data = copy.deepcopy(self.request)
        data["production_certified"] = True
        with self.assertRaisesRegex(validator.ValidationError, "cannot certify production"):
            validator.validate_request(data)

    def test_pending_request_cannot_claim_host_verified(self) -> None:
        data = copy.deepcopy(self.request)
        data["host_verified"] = True
        with self.assertRaisesRegex(validator.ValidationError, "pending status requires host_verified=false"):
            validator.validate_request(data)

    def test_verified_state_rejects_missing_outputs_and_pending_checks(self) -> None:
        data = copy.deepcopy(self.request)
        data["status"] = "CREATED_AND_VERIFIED"
        data["host_verified"] = True
        with self.assertRaisesRegex(validator.ValidationError, "outputs are incomplete|verification is incomplete|pending"):
            validator.validate_request(data)

    def test_blocked_state_cannot_keep_provisioning_evidence(self) -> None:
        data = copy.deepcopy(self.request)
        data["status"] = "BLOCKED_ACCOUNT_CREDENTIALS_REQUIRED"
        data["host_created"] = False
        with self.assertRaisesRegex(validator.ValidationError, "blocked request cannot claim"):
            validator.validate_request(data)

    def test_required_outputs_bind_identity_and_provenance(self) -> None:
        outputs = set(self.request["required_provisioning_outputs"])
        self.assertTrue({
            "provider_resource_id", "private_ip", "ssh_host_key_fingerprint",
            "workflow_run_id", "workflow_source_sha", "configuration_checksum",
        }.issubset(outputs))

    def test_safety_controls_are_all_false(self) -> None:
        self.assertTrue(self.request["safety_controls"])
        self.assertTrue(all(value is False for value in self.request["safety_controls"].values()))


if __name__ == "__main__":
    unittest.main()
