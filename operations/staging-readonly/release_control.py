#!/usr/bin/env python3
"""Compatibility entry point for the immutable staging release controller.

The reviewed controller implementation remains byte-identical in
``release_control_core.py``. This module re-exports that implementation and
adds the fail-closed candidate-identity guard required by the public import
contract. Keeping the original blob intact makes this narrowly scoped repair
auditable while all callers continue importing ``release_control``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Mapping

_CORE_NAME = "_codestra_release_control_core"
_CORE_PATH = Path(__file__).with_name("release_control_core.py")
_CORE_SPEC = importlib.util.spec_from_file_location(_CORE_NAME, _CORE_PATH)
if _CORE_SPEC is None or _CORE_SPEC.loader is None:
    raise ImportError(f"cannot load release controller implementation: {_CORE_PATH}")
_CORE = importlib.util.module_from_spec(_CORE_SPEC)
sys.modules[_CORE_NAME] = _CORE
_CORE_SPEC.loader.exec_module(_CORE)

for _name in dir(_CORE):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_CORE, _name)

_ORIGINAL_VALIDATE_CANDIDATE = _CORE.validate_candidate


def validate_candidate(candidate: Mapping[str, Any]) -> None:
    """Validate the complete candidate and reject placeholder identities."""

    _ORIGINAL_VALIDATE_CANDIDATE(candidate)
    no_placeholder(candidate.get("candidate_id"), "candidate_id")


# The implementation's main() resolves validate_candidate in its own module
# namespace. Bind the hardened wrapper there as well so CLI and imported use
# enforce exactly the same fail-closed contract.
_CORE.validate_candidate = validate_candidate


if __name__ == "__main__":
    raise SystemExit(main())
