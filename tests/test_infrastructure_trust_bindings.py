"""Exercise the actual workflow/executable pins and strict trust normalization."""
import ast
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "appolon1908-hue/Infustruction-repo"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


release = load("infrastructure_release_bindings", ".codestra/validate-release-intent.py")
contract = load("infrastructure_contract_bindings", ".codestra/validate-production-orchestrator-contract.py")


class InfrastructureTrustBindingTests(unittest.TestCase):
    def test_actual_required_workflows_are_bound_and_modified_bytes_fail(self):
        for path in release.EXPECTED_CHECK_WORKFLOW_SHA256[REPOSITORY]:
            raw = (ROOT / path).read_bytes()
            with self.subTest(path=path):
                release.validate_workflow_definition_bytes(REPOSITORY, "a" * 40, path, raw)
                with self.assertRaises(release.PolicyError):
                    release.validate_workflow_definition_bytes(REPOSITORY, "a" * 40, path, raw + b"\n")

    def test_actual_executable_is_bound_and_modified_bytes_fail(self):
        workflow = ".github/workflows/production-orchestrator-contract.yml"
        path = ".codestra/validate-production-orchestrator-contract.py"
        raw = (ROOT / path).read_bytes()
        release.validate_workflow_executable_bytes(REPOSITORY, workflow, path, raw)
        with self.assertRaises(release.PolicyError):
            release.validate_workflow_executable_bytes(REPOSITORY, workflow, path, raw + b"\n")

    def test_release_security_is_bound(self):
        source = (ROOT / ".codestra/validate-release-intent.py").read_text()
        contract.validate_release_validator_trust_root(source, REPOSITORY)
        with self.assertRaises(contract.ContractError):
            contract.validate_release_validator_trust_root(source + "\nINDEPENDENT_REVIEWER_ID = 1\n", REPOSITORY)

    def test_infrastructure_binding_requires_one_static_digest(self):
        source = (ROOT / ".codestra/validate-release-intent.py").read_text()
        name = "INFRASTRUCTURE_PRODUCTION_VALIDATOR_SHA256"
        bindings = [node for node in ast.parse(source).body if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)]
        self.assertEqual(len(bindings), 1)
        binding = ast.get_source_segment(source, bindings[0])
        for replacement in ("", f"{name} = compute_untrusted_hash()", f'{name} = "invalid"',
                            binding + "\n" + binding, binding + "; INDEPENDENT_REVIEWER_ID = 1"):
            with self.subTest(replacement=replacement), self.assertRaises(contract.ContractError):
                contract.validate_release_validator_trust_root(source.replace(binding, replacement, 1), REPOSITORY)


if __name__ == "__main__":
    unittest.main()
