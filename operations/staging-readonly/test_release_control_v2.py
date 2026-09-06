from __future__ import annotations

import copy
import json
import os
import tempfile
from pathlib import Path

import release_control as core
import release_control_v2 as release


def valid_candidate() -> dict:
    return {
        "schema": core.SCHEMA,
        "candidate_id": "candidate-20260903",
        "candidate_source_lock_sha": "1" * 40,
        "environment": "staging-readonly",
        "compose": {
            "project_name": "codestra-staging-readonly",
            "files": ["/srv/codestra/runtime/compose.staging.yml"],
            "working_directory": "/srv/codestra/runtime",
        },
        "workloads": [
            {
                "name": "middleware",
                "service": "middleware",
                "repository": "appolon1908-hue/Middleware-",
                "source_sha": "2" * 40,
                "image": "ghcr.io/appolon1908-hue/middleware@sha256:" + "3" * 64,
                "version_endpoint": "https://staging.invalid/version",
                "readiness_endpoint": "https://staging.invalid/readyz",
                "capabilities_endpoint": "https://staging.invalid/api/v1/platform/capabilities",
                "metrics_endpoint": "https://staging.invalid/metrics",
                "migration_endpoint": "https://staging.invalid/api/v1/system/migrations",
                "expected_migration": "0008_durable_communications",
            }
        ],
        "safety": copy.deepcopy(core.SAFETY_EXPECTED),
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
                    "expected_statuses": [200, 401, 403],
                }
                for index in range(1, 30)
            ],
        },
        "backups": {
            "directory": "/var/backups/codestra/staging-readonly",
            "postgres": {
                "service": "middleware",
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
                    "expected_migration": "0007_previous",
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


def endpoint_manifest(environment: str) -> dict:
    staging = environment == release.STAGING_ENVIRONMENT
    host = "staging.invalid" if staging else "canary.invalid"
    auth_host = "auth-staging.invalid" if staging else "auth.invalid"
    api_host = "api-staging.invalid" if staging else "api.invalid"
    bearer, metrics = release.EXPECTED_TOKEN_NAMES[environment]
    probe = {
        "requests": 50,
        "maximum_error_rate": 0,
        "maximum_p95_ms": 500,
        "maximum_regression_percent": 10,
    }
    if not staging:
        probe.update(
            baseline_url="https://api.invalid/readyz",
            canary_url="https://canary.invalid/readyz",
        )
    return {
        "schema": core.ENDPOINT_SCHEMA,
        "candidate_id": "candidate-20260903",
        "environment": environment,
        "bearer_token_environment": bearer,
        "metrics_token_environment": metrics,
        "workloads": [
            {
                "name": "middleware",
                "version_endpoint": f"https://{host}/version",
                "readiness_endpoint": f"https://{host}/readyz",
                "capabilities_endpoint": f"https://{host}/api/v1/platform/capabilities",
                "metrics_endpoint": f"https://{host}/metrics",
                "migration_endpoint": f"https://{host}/api/v1/system/migrations",
            }
        ],
        "keycloak": {
            "discovery_endpoint": f"https://{auth_host}/realms/codestra/.well-known/openid-configuration",
            "expected_issuer": f"https://{auth_host}/realms/codestra",
        },
        "kong": {
            "smoke_routes": [
                {
                    "name": f"route-{index:02d}",
                    "url": f"https://{api_host}/v1/route-{index:02d}",
                    "expected_statuses": [200, 401, 403],
                }
                for index in range(1, 30)
            ]
        },
        "counters": [
            {
                "name": name,
                "url": f"https://{host}/api/v1/safety/counters/{name}",
                "json_pointer": "/value",
                "expected": 0,
            }
            for name in ("calls", "emails", "sms")
        ],
        "probe": probe,
    }


def expect_gate_error(function, *args, **kwargs) -> None:
    try:
        function(*args, **kwargs)
    except core.GateError:
        return
    raise AssertionError("expected GateError")


def bind_tokens(environment: str):
    names = release.EXPECTED_TOKEN_NAMES[environment]
    previous = {name: os.environ.get(name) for name in names}
    for name in names:
        os.environ[name] = f"synthetic-{name.lower()}"
    return names, previous


def restore_tokens(names, previous) -> None:
    for name in names:
        value = previous[name]
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def test_valid_candidate_and_previous_migration_pass() -> None:
    release.validate_candidate(valid_candidate())


def test_zero_candidate_and_runtime_identities_fail_closed() -> None:
    candidate = valid_candidate()
    candidate["candidate_source_lock_sha"] = release.ZERO_SHA
    expect_gate_error(release.validate_candidate, candidate)
    candidate = valid_candidate()
    candidate["workloads"][0]["source_sha"] = release.ZERO_SHA
    expect_gate_error(release.validate_candidate, candidate)
    candidate = valid_candidate()
    candidate["workloads"][0]["image"] = (
        "ghcr.io/appolon1908-hue/middleware@" + release.ZERO_DIGEST
    )
    expect_gate_error(release.validate_candidate, candidate)


def test_kong_404_cannot_be_a_success_status() -> None:
    candidate = valid_candidate()
    candidate["kong"]["smoke_routes"][0]["expected_statuses"].append(404)
    expect_gate_error(release.validate_candidate, candidate)


def test_staging_target_must_equal_canonical_candidate_urls() -> None:
    candidate = valid_candidate()
    manifest = endpoint_manifest(release.STAGING_ENVIRONMENT)
    names, previous = bind_tokens(release.STAGING_ENVIRONMENT)
    try:
        release.validate_endpoint_manifest(
            manifest, candidate, release.STAGING_ENVIRONMENT
        )
        manifest["workloads"][0]["version_endpoint"] = "https://other.invalid/version"
        expect_gate_error(
            release.validate_endpoint_manifest,
            manifest,
            candidate,
            release.STAGING_ENVIRONMENT,
        )
    finally:
        restore_tokens(names, previous)


def test_production_target_is_separate_and_requires_canary_probe_urls() -> None:
    candidate = valid_candidate()
    manifest = endpoint_manifest(release.CANARY_ENVIRONMENT)
    names, previous = bind_tokens(release.CANARY_ENVIRONMENT)
    try:
        release.validate_endpoint_manifest(
            manifest, candidate, release.CANARY_ENVIRONMENT
        )
        manifest["probe"].pop("canary_url")
        expect_gate_error(
            release.validate_endpoint_manifest,
            manifest,
            candidate,
            release.CANARY_ENVIRONMENT,
        )
    finally:
        restore_tokens(names, previous)


def test_environment_specific_tokens_cannot_be_swapped() -> None:
    candidate = valid_candidate()
    manifest = endpoint_manifest(release.CANARY_ENVIRONMENT)
    names, previous = bind_tokens(release.CANARY_ENVIRONMENT)
    try:
        manifest["bearer_token_environment"] = "STAGING_READONLY_BEARER_TOKEN"
        expect_gate_error(
            release.validate_endpoint_manifest,
            manifest,
            candidate,
            release.CANARY_ENVIRONMENT,
        )
    finally:
        restore_tokens(names, previous)


def test_no_redirect_handler_rejects_every_redirect() -> None:
    handler = release._NoRedirectHandler()
    assert (
        handler.redirect_request(
            urllib_request(), None, 302, "Found", {}, "https://other.invalid"
        )
        is None
    )


def urllib_request():
    from urllib.request import Request

    return Request("https://origin.invalid/version")


def fake_result(status: int, payload: object) -> core.HttpResult:
    return core.HttpResult(
        status=status,
        elapsed_ms=1.0,
        body=json.dumps(payload).encode(),
        headers={},
    )


def test_workload_requires_exact_source_and_image_digest_readback() -> None:
    workload = valid_candidate()["workloads"][0]
    original = release.request

    def synthetic(url: str, *, token: str | None, method: str = "GET", timeout=15):
        if url.endswith("/version"):
            return fake_result(
                200,
                {
                    "source_sha": workload["source_sha"],
                    "image_digest": release.image_digest(workload["image"]),
                },
            )
        if url.endswith("/readyz"):
            return fake_result(200, {"ready": True})
        if "capabilities" in url:
            return fake_result(200, copy.deepcopy(core.SAFETY_EXPECTED))
        if "migrations" in url:
            return fake_result(200, {"migration_head": workload["expected_migration"]})
        if url.endswith("/metrics"):
            return fake_result(200 if token else 401, {})
        raise AssertionError(url)

    release.request = synthetic
    try:
        result = release.check_workload(workload, "bearer", "metrics")
        assert result["source_sha"] == workload["source_sha"]
        assert result["image_digest"] == release.image_digest(workload["image"])

        def wrong_digest(url: str, *, token: str | None, method: str = "GET", timeout=15):
            result = synthetic(url, token=token, method=method, timeout=timeout)
            if url.endswith("/version"):
                return fake_result(
                    200,
                    {
                        "source_sha": workload["source_sha"],
                        "image_digest": "sha256:" + "f" * 64,
                    },
                )
            return result

        release.request = wrong_digest
        expect_gate_error(release.check_workload, workload, "bearer", "metrics")
    finally:
        release.request = original


def test_staging_evidence_is_bound_to_candidate_and_authenticated_run() -> None:
    candidate = valid_candidate()
    payload = json.dumps(candidate, sort_keys=True).encode()
    digest = __import__("hashlib").sha256(payload).hexdigest()
    evidence = release.new_evidence(candidate, digest, "staging").as_dict()
    evidence["verdict"] = "GO"
    evidence["gates"] = [{"gate": "all", "status": "PASS"}]
    evidence["producer"] = {
        "repository": "appolon1908-hue/Infustruction-repo",
        "workflow": release.PRODUCER_WORKFLOW,
        "head_sha": "8" * 40,
        "run_id": 123,
        "run_attempt": 1,
    }
    previous = {
        key: os.environ.get(key)
        for key in (
            "STAGING_EVIDENCE_RUN_ID",
            "STAGING_EVIDENCE_RUN_ATTEMPT",
            "STAGING_EVIDENCE_HEAD_SHA",
        )
    }
    try:
        os.environ["STAGING_EVIDENCE_RUN_ID"] = "123"
        os.environ["STAGING_EVIDENCE_RUN_ATTEMPT"] = "1"
        os.environ["STAGING_EVIDENCE_HEAD_SHA"] = "8" * 40
        release.validate_run_evidence(
            evidence, candidate, digest,
            expected_mode="staging",
            environment_prefix="STAGING",
            required_gates={"all"},
        )
        evidence["producer"]["run_id"] = 124
        expect_gate_error(
            release.validate_run_evidence, evidence, candidate, digest,
            expected_mode="staging",
            environment_prefix="STAGING",
            required_gates={"all"},
        )
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_canary_controller_receipt_binds_percent_methods_and_digests() -> None:
    candidate = valid_candidate()
    digest = "8" * 64
    receipt = {
        "schema": "codestra.readonly-canary-receipt.v1",
        "candidate_id": candidate["candidate_id"],
        "source_lock_sha": candidate["candidate_source_lock_sha"],
        "candidate_manifest_sha256": digest,
        "percent": 1.0,
        "methods": ["GET", "HEAD"],
        "read_only": True,
        "workloads": [
            {
                "service": item["service"],
                "source_sha": item["source_sha"],
                "image": item["image"],
            }
            for item in candidate["workloads"]
        ],
    }
    release.validate_canary_receipt(receipt, candidate, digest, 1.0)
    broken = copy.deepcopy(receipt)
    broken["percent"] = 1.1
    expect_gate_error(
        release.validate_canary_receipt,
        broken,
        candidate,
        digest,
        1.0,
    )
    broken = copy.deepcopy(receipt)
    broken["methods"] = ["GET", "POST"]
    expect_gate_error(
        release.validate_canary_receipt,
        broken,
        candidate,
        digest,
        1.0,
    )


def test_canary_rollback_receipt_is_exact() -> None:
    candidate = valid_candidate()
    receipt = {
        "schema": "codestra.readonly-canary-rollback.v1",
        "candidate_id": candidate["candidate_id"],
        "source_lock_sha": candidate["candidate_source_lock_sha"],
        "rolled_back": True,
    }
    release.validate_rollback_receipt(receipt, candidate)
    receipt["rolled_back"] = False
    expect_gate_error(release.validate_rollback_receipt, receipt, candidate)


def test_safe_archive_extraction_rejects_links_and_traversal() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        bad = root / "bad.tar.gz"
        import io
        import tarfile

        with tarfile.open(bad, "w:gz") as archive:
            member = tarfile.TarInfo("../escape")
            payload = b"bad"
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))
        expect_gate_error(release._safe_extract, bad, root / "restore")


if __name__ == "__main__":
    executed = 0
    for name in sorted(globals()):
        value = globals()[name]
        if name.startswith("test_") and callable(value):
            value()
            executed += 1
    if executed == 0:
        raise SystemExit("no release-control v2 tests executed")
    print(f"RELEASE_CONTROL_V2_TESTS={executed}")
    print("RELEASE_CONTROL_V2_TESTS_RESULT=PASS")
