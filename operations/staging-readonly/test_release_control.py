from __future__ import annotations

import copy
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("release_control", ROOT / "release_control.py")
assert SPEC and SPEC.loader
release_control = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = release_control
SPEC.loader.exec_module(release_control)


def valid_candidate() -> dict:
    workloads = [
        {
            "name": "middleware",
            "service": "middleware",
            "repository": "appolon1908-hue/Middleware-",
            "source_sha": "1" * 40,
            "image": "ghcr.io/appolon1908-hue/middleware@sha256:" + "2" * 64,
            "version_endpoint": "https://staging.invalid/version",
            "readiness_endpoint": "https://staging.invalid/readyz",
            "capabilities_endpoint": "https://staging.invalid/api/v1/platform/capabilities",
            "metrics_endpoint": "https://staging.invalid/metrics",
            "migration_endpoint": "https://staging.invalid/api/v1/system/migrations",
            "expected_migration": "0008_durable_communications",
        }
    ]
    return {
        "schema": release_control.SCHEMA,
        "candidate_id": "candidate-20260903",
        "candidate_source_lock_sha": "3" * 40,
        "environment": "staging-readonly",
        "compose": {
            "project_name": "codestra-staging-readonly",
            "files": ["/srv/codestra/runtime/compose.staging.yml"],
            "working_directory": "/srv/codestra/runtime",
        },
        "workloads": workloads,
        "safety": copy.deepcopy(release_control.SAFETY_EXPECTED),
        "keycloak": {
            "discovery_endpoint": "https://auth-staging.invalid/realms/codestra/.well-known/openid-configuration",
            "expected_issuer": "https://auth-staging.invalid/realms/codestra",
        },
        "kong": {
            "expected_route_count": 29,
            "smoke_routes": [
                {
                    "name": f"route-{index:02d}",
                    "url": f"https://api-staging.invalid/v1/route-{index:02d}",
                    "expected_statuses": [200, 401, 403, 404],
                }
                for index in range(1, 30)
            ],
        },
        "backups": {
            "directory": "/var/backups/codestra/staging-readonly",
            "postgres": {
                "service": "postgres",
                "database": "codestra",
                "username": "codestra_backup",
            },
            "odoo_filestore": "/srv/codestra/runtime/odoo-filestore",
            "configuration": ["/srv/codestra/runtime/config"],
            "off_host": {
                "required": True,
                "restic_repository_environment": "RESTIC_REPOSITORY",
            },
        },
        "rollback": {
            "previous_source_lock_sha": "4" * 40,
            "workloads": [
                {
                    "service": "middleware",
                    "source_sha": "5" * 40,
                    "image": "ghcr.io/appolon1908-hue/middleware@sha256:" + "6" * 64,
                }
            ],
        },
        "canary": {
            "maximum_percent": 1,
            "methods": ["GET", "HEAD"],
            "controller": "/srv/codestra/bin/apply-readonly-canary",
            "controller_sha256": "7" * 64,
        },
    }


def valid_manifest() -> dict:
    return {
        "schema": release_control.ENDPOINT_SCHEMA,
        "candidate_id": "candidate-20260903",
        "bearer_token_environment": "STAGING_READONLY_BEARER_TOKEN",
        "metrics_token_environment": "STAGING_METRICS_BEARER_TOKEN",
        "counters": [
            {
                "name": name,
                "url": f"https://metrics-staging.invalid/api/v1/safety/counters/{name}",
                "json_pointer": "/value",
                "expected": 0,
            }
            for name in ("calls", "emails", "sms")
        ],
        "probe": {
            "requests": 50,
            "maximum_error_rate": 0,
            "maximum_p95_ms": 500,
            "maximum_regression_percent": 10,
        },
    }


def expect_gate_error(function, *args, **kwargs) -> None:
    try:
        function(*args, **kwargs)
    except release_control.GateError:
        return
    raise AssertionError("expected GateError")


def test_dynamic_import_is_registered_for_dataclass_resolution() -> None:
    assert sys.modules[SPEC.name] is release_control


def test_valid_complete_candidate_passes() -> None:
    release_control.validate_candidate(valid_candidate())


def test_mutable_image_is_rejected() -> None:
    candidate = valid_candidate()
    candidate["workloads"][0]["image"] = "ghcr.io/appolon1908-hue/middleware:latest"
    expect_gate_error(release_control.validate_candidate, candidate)


def test_placeholder_candidate_is_rejected() -> None:
    candidate = valid_candidate()
    candidate["candidate_id"] = "REPLACE_WITH_CANDIDATE"
    expect_gate_error(release_control.validate_candidate, candidate)


def test_live_effect_flag_is_rejected() -> None:
    candidate = valid_candidate()
    candidate["safety"]["LIVE_EMAIL_DELIVERY"] = True
    expect_gate_error(release_control.validate_candidate, candidate)


def test_kong_denominator_must_remain_29() -> None:
    candidate = valid_candidate()
    candidate["kong"]["smoke_routes"].pop()
    expect_gate_error(release_control.validate_candidate, candidate)


def test_rollback_must_cover_exact_candidate_services() -> None:
    candidate = valid_candidate()
    candidate["rollback"]["workloads"][0]["service"] = "other"
    expect_gate_error(release_control.validate_candidate, candidate)


def test_canary_cannot_exceed_one_percent() -> None:
    candidate = valid_candidate()
    candidate["canary"]["maximum_percent"] = 1.01
    expect_gate_error(release_control.validate_candidate, candidate)


def test_endpoint_manifest_requires_protected_credentials() -> None:
    candidate = valid_candidate()
    manifest = valid_manifest()
    old_bearer = os.environ.pop("STAGING_READONLY_BEARER_TOKEN", None)
    old_metrics = os.environ.pop("STAGING_METRICS_BEARER_TOKEN", None)
    try:
        expect_gate_error(release_control.validate_endpoint_manifest, manifest, candidate)
        os.environ["STAGING_READONLY_BEARER_TOKEN"] = "synthetic-readonly"
        os.environ["STAGING_METRICS_BEARER_TOKEN"] = "synthetic-metrics"
        release_control.validate_endpoint_manifest(manifest, candidate)
    finally:
        if old_bearer is None:
            os.environ.pop("STAGING_READONLY_BEARER_TOKEN", None)
        else:
            os.environ["STAGING_READONLY_BEARER_TOKEN"] = old_bearer
        if old_metrics is None:
            os.environ.pop("STAGING_METRICS_BEARER_TOKEN", None)
        else:
            os.environ["STAGING_METRICS_BEARER_TOKEN"] = old_metrics


def test_live_effect_counters_must_stay_zero() -> None:
    release_control.assert_zero_and_unchanged(
        {"calls": 0, "emails": 0, "sms": 0},
        {"calls": 0, "emails": 0, "sms": 0},
    )
    expect_gate_error(
        release_control.assert_zero_and_unchanged,
        {"calls": 0, "emails": 0, "sms": 0},
        {"calls": 1, "emails": 0, "sms": 0},
    )


def test_json_pointer_is_strict() -> None:
    assert release_control.json_pointer({"nested": {"value": 0}}, "/nested/value") == 0
    expect_gate_error(release_control.json_pointer, {"nested": {}}, "/nested/value")


def test_http_client_rejects_write_methods_before_network() -> None:
    expect_gate_error(release_control.request, "https://example.invalid", token=None, method="POST")


if __name__ == "__main__":
    executed = 0
    for name in sorted(globals()):
        value = globals()[name]
        if name.startswith("test_") and callable(value):
            value()
            executed += 1
    if executed == 0:
        raise SystemExit("no release-control tests executed")
    print(f"RELEASE_CONTROL_TESTS={executed}")
    print("RELEASE_CONTROL_TESTS_RESULT=PASS")
