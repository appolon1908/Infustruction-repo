#!/usr/bin/env python3
"""Regression tests for fail-closed observability network policy validation."""

from __future__ import annotations

import copy
import importlib.util
import pathlib
import sys
from types import ModuleType

ROOT = pathlib.Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate-observability-topology.py"


def load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("codestra_observability_topology", VALIDATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load topology validator")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def must_reject(callback, message: str) -> None:
    try:
        callback()
    except SystemExit as exc:
        if exc.code != 1:
            raise AssertionError(f"{message}: unexpected exit code {exc.code}") from exc
    else:
        raise AssertionError(message)


def main() -> None:
    validator = load_validator()
    topology = validator.load(validator.TOPOLOGY)
    communication = validator.load(validator.COMMUNICATION)
    firewall = validator.load(validator.FIREWALL)

    wildcard_topology = copy.deepcopy(topology)
    wildcard_topology["components"][0]["nativeListener"] = "[::]:3000"
    must_reject(
        lambda: validator.validate_topology(wildcard_topology),
        "bracketed IPv6 wildcard listener was accepted",
    )

    for destination, source in (("prometheus", "otel-collector"), ("otel-collector", "alloy")):
        incomplete_firewall = copy.deepcopy(firewall)
        entry = next(
            item
            for item in incomplete_firewall["loopbackOrPrivateOnly"]
            if item["component"] == destination
        )
        entry["allowedSources"].remove(source)
        must_reject(
            lambda value=incomplete_firewall: validator.validate_firewall(value, communication),
            f"approved {source} -> {destination} flow was absent but accepted",
        )

    print("OBSERVABILITY_NEGATIVE_POLICY_TESTS=PASS")


if __name__ == "__main__":
    main()
