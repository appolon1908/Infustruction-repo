#!/usr/bin/env python3
"""Regression tests for fail-closed production evidence helpers."""

from __future__ import annotations

import json
import inspect
import re
import unittest
from unittest.mock import patch

import generate_full_platform_certification as generator


class CertificationHelperTests(unittest.TestCase):
    def test_host_identity_requires_both_expected_addresses(self) -> None:
        addresses = json.dumps(
            [
                {
                    "addr_info": [
                        {"family": "inet", "local": generator.EXPECTED_PUBLIC_IPV4},
                        {"family": "inet", "local": generator.EXPECTED_PRIVATE_IPV4},
                    ]
                }
            ]
        )

        def command(*arguments: str, check: bool = True) -> str:
            del check
            return "server-37\n" if arguments == ("hostname",) else addresses

        with patch.object(generator, "command", side_effect=command):
            self.assertEqual(
                generator.verified_host_identity(),
                {
                    "hostname": "server-37",
                    "public_ipv4": generator.EXPECTED_PUBLIC_IPV4,
                    "private_ipv4": generator.EXPECTED_PRIVATE_IPV4,
                },
            )

        missing_private = json.dumps(
            [{"addr_info": [{"family": "inet", "local": generator.EXPECTED_PUBLIC_IPV4}]}]
        )
        with patch.object(generator, "command", return_value=missing_private):
            with self.assertRaisesRegex(RuntimeError, "host identity mismatch"):
                generator.verified_host_identity()

    def test_edge_gate_rejects_unreachable_and_server_errors(self) -> None:
        for status in ("LIVE_HTTPS_200", "LIVE_HTTPS_302", "LIVE_HTTPS_401", "LIVE_HTTPS_404"):
            self.assertTrue(generator.live_https_without_server_error(status))
        for status in ("LIVE_HTTPS_500", "LIVE_HTTPS_503", "LIVE_HTTPS_UNREACHABLE", "SOURCE_ONLY"):
            self.assertFalse(generator.live_https_without_server_error(status))

    def test_openapi_contract_comparison_detects_schema_drift(self) -> None:
        source = {
            "paths": {
                "/v1/items": {
                    "post": {
                        "requestBody": {"content": {"application/json": {"schema": {"type": "object"}}}},
                        "responses": {"202": {"description": "accepted"}},
                    }
                }
            }
        }
        live = json.loads(json.dumps(source))
        live["paths"]["/v1/items"]["post"]["responses"] = {
            "200": {"description": "unexpected synchronous response"}
        }
        self.assertNotEqual(
            generator.operation_contracts("KLYROW", source),
            generator.operation_contracts("KLYROW", live),
        )

    def test_repository_head_rejects_dirty_worktree(self) -> None:
        with patch.object(generator, "command", return_value=" M changed.py\n"):
            with self.assertRaisesRegex(RuntimeError, "source worktree is dirty"):
                generator.repository_head("/tmp/source")

    def test_kyqra_extraction_is_clean_and_source_read_only(self) -> None:
        self.assertRegex(
            generator.KYQRA_BUILD_IMAGE,
            re.compile(r"^node:22-alpine@sha256:[0-9a-f]{64}$"),
        )
        source = inspect.getsource(generator.source_openapi)
        self.assertIn('f"{kyqra_directory}:/source:ro"', source)
        self.assertIn("npm ci --ignore-scripts --no-audit --no-fund", source)
        self.assertNotIn('f"{kyqra_directory}:/work"', source)


if __name__ == "__main__":
    unittest.main()
