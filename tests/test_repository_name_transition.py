from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "repository_name_transition",
    ROOT / "scripts" / "validate_repository_name_transition.py",
)
assert SPEC is not None and SPEC.loader is not None
TRANSITION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TRANSITION)


class RepositoryRecordTests(unittest.TestCase):
    def test_conflicting_active_repository_field_is_rejected(self) -> None:
        document = {
            "repository_id": 1351353723,
            "current_repository": "appolon1908-hue/Codesrea-Social-",
            "repository": "appolon1908-hue/unapproved-social-fork",
        }
        with self.assertRaises(SystemExit):
            TRANSITION.validate_record_repository_fields(
                document,
                {1351353723: "appolon1908-hue/Codesrea-Social-"},
                "synthetic.json",
            )

    def test_matching_repository_fields_pass(self) -> None:
        expected = "appolon1908-hue/Codesrea-Social-"
        document = {
            "repository_id": 1351353723,
            "current_repository": expected,
            "repository": expected,
        }
        TRANSITION.validate_record_repository_fields(
            document,
            {1351353723: expected},
            "synthetic.json",
        )


class RepositoryTransitionTests(unittest.TestCase):
    @staticmethod
    def manifest(first: str, second: str) -> dict:
        return {
            "mappings": [
                {"repository_id": 1, "status": first},
                {"repository_id": 2, "status": second},
            ]
        }

    def test_zero_transition_is_allowed(self) -> None:
        document = self.manifest("PREPARED_NOT_RENAMED", "PREPARED_NOT_RENAMED")
        TRANSITION.validate_one_repository_transition(document, document)

    def test_prepared_to_renamed_is_allowed(self) -> None:
        base = self.manifest("PREPARED_NOT_RENAMED", "PREPARED_NOT_RENAMED")
        current = self.manifest("RENAMED_VERIFIED", "PREPARED_NOT_RENAMED")
        TRANSITION.validate_one_repository_transition(base, current)

    def test_renamed_to_rolled_back_is_allowed(self) -> None:
        base = self.manifest("RENAMED_VERIFIED", "PREPARED_NOT_RENAMED")
        current = self.manifest("ROLLED_BACK_VERIFIED", "PREPARED_NOT_RENAMED")
        TRANSITION.validate_one_repository_transition(base, current)

    def test_rolled_back_to_renamed_retry_is_allowed(self) -> None:
        base = self.manifest("ROLLED_BACK_VERIFIED", "PREPARED_NOT_RENAMED")
        current = self.manifest("RENAMED_VERIFIED", "PREPARED_NOT_RENAMED")
        TRANSITION.validate_one_repository_transition(base, current)

    def test_renamed_to_prepared_is_rejected(self) -> None:
        base = self.manifest("RENAMED_VERIFIED", "PREPARED_NOT_RENAMED")
        current = self.manifest("PREPARED_NOT_RENAMED", "PREPARED_NOT_RENAMED")
        with self.assertRaises(SystemExit):
            TRANSITION.validate_one_repository_transition(base, current)

    def test_prepared_to_rolled_back_is_rejected(self) -> None:
        base = self.manifest("PREPARED_NOT_RENAMED", "PREPARED_NOT_RENAMED")
        current = self.manifest("ROLLED_BACK_VERIFIED", "PREPARED_NOT_RENAMED")
        with self.assertRaises(SystemExit):
            TRANSITION.validate_one_repository_transition(base, current)

    def test_two_transitions_are_rejected(self) -> None:
        base = self.manifest("PREPARED_NOT_RENAMED", "PREPARED_NOT_RENAMED")
        current = self.manifest("RENAMED_VERIFIED", "RENAMED_VERIFIED")
        with self.assertRaises(SystemExit):
            TRANSITION.validate_one_repository_transition(base, current)

    def test_governed_id_set_cannot_change_during_cutover(self) -> None:
        base = self.manifest("PREPARED_NOT_RENAMED", "PREPARED_NOT_RENAMED")
        current = {
            "mappings": [
                {"repository_id": 1, "status": "RENAMED_VERIFIED"},
            ]
        }
        with self.assertRaises(SystemExit):
            TRANSITION.validate_one_repository_transition(base, current)


if __name__ == "__main__":
    unittest.main()
