#!/usr/bin/env python3
"""Compare saved-plan prior state with the protected backend state."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def require(condition: bool, label: str) -> None:
    if not condition:
        raise SystemExit(f"STAGE6_STATE_CURRENCY_ERROR={label}")


prior = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if sys.argv[2] == "NONE":
    require(prior.get("serial", 0) == 0, "missing_state_serial")
    require(not prior.get("lineage"), "missing_state_lineage")
    require(len(prior.get("resources", [])) == 0, "missing_state_resources")
else:
    current = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    require(prior.get("serial") == current.get("serial"), "serial")
    require(prior.get("lineage") == current.get("lineage"), "lineage")

print("REMOTE_STATE=PASS")
print("SAVED_PLAN_STATE_CURRENT=YES")
