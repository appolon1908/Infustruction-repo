from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_stage6_environment_preflight.py"
SPEC = importlib.util.spec_from_file_location("stage6_environment_preflight", SCRIPT)
assert SPEC and SPEC.loader
PREFLIGHT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREFLIGHT)


class Stage6EnvironmentPreflightTests(unittest.TestCase):
    def valid_environment(self) -> dict[str, str]:
        tfvars = {
            "location": "hel1",
            "server_type": "cx43",
            "egress_gateway_server_type": "cx23",
            "network_cidr": "10.250.0.0/16",
            "staging_subnet_cidr": "10.250.6.0/24",
            "private_ip": "10.250.6.10",
            "egress_gateway_private_ip": "10.250.6.2",
            "approved_ssh_key_ids": [118172836],
            "staging_readonly_operator_public_key": (
                "ssh-ed25519 AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= "
                "codestra-staging-readonly"
            ),
            "approved_ssh_source_cidrs": ["192.0.2.10/32"],
            "approved_egress_fqdns": [
                "archive.ubuntu.com",
                "security.ubuntu.com",
                "ghcr.io",
            ],
            "approved_egress_ports": [80, 443],
            "known_internal_production_deny_cidrs": [
                "37.27.128.39/32",
                "65.109.65.169/32",
                "10.40.0.0/24",
            ],
        }
        return {
            "HAS_HETZNER_CLOUD_TOKEN": "true",
            "HAS_TF_STATE_ACCESS_KEY": "true",
            "HAS_TF_STATE_SECRET_KEY": "true",
            "TF_STATE_BUCKET": "codestra-stage6-state",
            "TF_STATE_ENDPOINT": "https://s3.example.invalid",
            "TF_STATE_REGION": "eu-central",
            "STAGE6_TFVARS_JSON": json.dumps(tfvars),
        }

    def test_missing_environment_is_reported_by_name_only(self) -> None:
        errors, evidence = PREFLIGHT.validate_environment({})
        self.assertTrue(errors)
        self.assertEqual(evidence["status"], "BLOCKED")
        self.assertEqual(set(evidence["missing_secrets"]), PREFLIGHT.REQUIRED_SECRETS)
        self.assertEqual(set(evidence["missing_variables"]), PREFLIGHT.REQUIRED_VARIABLES)
        self.assertFalse(evidence["secret_values_recorded"])

    def test_complete_reviewed_environment_passes(self) -> None:
        errors, evidence = PREFLIGHT.validate_environment(self.valid_environment())
        self.assertEqual(errors, [])
        self.assertEqual(evidence["status"], "PASS")
        self.assertFalse(evidence["provider_contacted"])
        self.assertFalse(evidence["remote_state_contacted"])

    def test_global_ssh_source_is_rejected(self) -> None:
        environment = self.valid_environment()
        tfvars = json.loads(environment["STAGE6_TFVARS_JSON"])
        tfvars["approved_ssh_source_cidrs"] = ["0.0.0.0/0"]
        environment["STAGE6_TFVARS_JSON"] = json.dumps(tfvars)
        errors, evidence = PREFLIGHT.validate_environment(environment)
        self.assertTrue(any("global CIDR" in error for error in errors))
        self.assertIn("STAGE6_TFVARS_JSON", evidence["invalid_variables"])

    def test_unreviewed_egress_destination_is_rejected(self) -> None:
        environment = self.valid_environment()
        tfvars = json.loads(environment["STAGE6_TFVARS_JSON"])
        tfvars["approved_egress_fqdns"].append("unreviewed.example")
        environment["STAGE6_TFVARS_JSON"] = json.dumps(tfvars)
        errors, _ = PREFLIGHT.validate_environment(environment)
        self.assertTrue(any("unreviewed destinations" in error for error in errors))

    def test_missing_or_multiline_operator_key_is_rejected(self) -> None:
        environment = self.valid_environment()
        tfvars = json.loads(environment["STAGE6_TFVARS_JSON"])
        tfvars.pop("staging_readonly_operator_public_key")
        environment["STAGE6_TFVARS_JSON"] = json.dumps(tfvars)
        errors, _ = PREFLIGHT.validate_environment(environment)
        self.assertTrue(any("operator_public_key" in error for error in errors))

        tfvars["staging_readonly_operator_public_key"] = (
            "ssh-ed25519 AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= first\n"
            "ssh-ed25519 BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB= second"
        )
        environment["STAGE6_TFVARS_JSON"] = json.dumps(tfvars)
        errors, _ = PREFLIGHT.validate_environment(environment)
        self.assertTrue(any("operator_public_key" in error for error in errors))

    def test_secret_values_never_enter_evidence(self) -> None:
        environment = self.valid_environment()
        environment["HETZNER_CLOUD_TOKEN"] = "must-not-appear"
        environment["TF_STATE_ACCESS_KEY"] = "must-not-appear"
        environment["TF_STATE_SECRET_KEY"] = "must-not-appear"
        _, evidence = PREFLIGHT.validate_environment(environment)
        rendered = json.dumps(evidence)
        self.assertNotIn("must-not-appear", rendered)
        self.assertNotIn("HETZNER_CLOUD_TOKEN\": \"", rendered)


if __name__ == "__main__":
    unittest.main()
