#!/usr/bin/env python3
"""Entry point for the single-run staging -> rollback -> canary chain."""

from __future__ import annotations

import os
import re

import release_control_v2 as controller


workflow_path = os.environ.get("CODESTRA_RELEASE_WORKFLOW_PATH", "")
if not re.fullmatch(r"\.github/workflows/[A-Za-z0-9._/-]+\.ya?ml", workflow_path):
    raise SystemExit("CODESTRA_RELEASE_WORKFLOW_PATH is missing or invalid")
controller.PRODUCER_WORKFLOW = workflow_path


if __name__ == "__main__":
    raise SystemExit(controller.main())
