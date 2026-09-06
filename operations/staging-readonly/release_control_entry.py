#!/usr/bin/env python3
"""Stable entry point for the hardened immutable release controller."""

from __future__ import annotations

from release_control_v2 import main


if __name__ == "__main__":
    raise SystemExit(main())
