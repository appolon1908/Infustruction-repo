"""PR #106 regressions: disposable fixtures; no Docker, network, or root actions."""
from copy import deepcopy
import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import urllib.parse

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_reusable_workflows_upload_recovery_evidence_even_after_failure():
    for name in ("reusable-codestra-deploy-readiness.yml", "reusable-codestra-upstream-deploy-readiness.yml"):
        text=(ROOT/".github/workflows"/name).read_text()
        for marker in ("Upload sanitized staging evidence", "Upload sanitized production-canary evidence"):
            section=text.split(f"- name: {marker}",1)[1].split("\n      - name:",1)[0]
            assert "if: ${{ always() }}" in section


@pytest.fixture
def module():
    loader = importlib.machinery.SourceFileLoader(
        "odoo_review_regressions_adapter", str(ROOT / "operators/codestra-deploy-odoo")
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    loaded = importlib.util.module_from_spec(spec)
    loader.exec_module(loaded)
    return loaded


def rule():
    return {"status": 200, "json_field": "status", "json_value": "ok", "timeout_seconds": 3}


def health_target():
    return {"health_base_url": "http://127.0.0.1:8069", "health": {"/web/health": rule()}}


class Response(io.BytesIO):
    status = 200


def mock_http(monkeypatch, module, *, status=200, body=b'{"status":"ok"}'):
    calls = []
    class Opener:
        def open(self, url, timeout):
            calls.append((url, timeout))
            response = Response(body)
            response.status = status
            return response
    handlers = []
    def build(*args):
        handlers.extend(args)
        return Opener()
    monkeypatch.setattr(module.urllib.request, "build_opener", build)
    return calls, handlers


@pytest.mark.parametrize("path", [
    "@example.invalid/x", "//example.invalid/x", "https://example.invalid/x",
    "web/health", "/\\example.invalid/x", "/web/health?next=external",
    "/web/health#fragment", "/%2f%2fexample.invalid/x", "/../x", "/./web/health",
    "/web\n/health", "/web/health ", "",
])
def test_malformed_health_paths_never_open_a_request(module, monkeypatch, path):
    target = health_target(); target["health"] = {path: rule()}
    calls, _ = mock_http(monkeypatch, module)
    with pytest.raises(module.Blocked):
        module.check_health(target, path)
    assert calls == []


@pytest.mark.parametrize("supplied", ["", ",", "/web/health,", ",/web/health", "/web/health,/web/health"])
def test_empty_or_duplicate_requested_health_paths_fail_closed(module, monkeypatch, supplied):
    target = health_target()
    if supplied in {"", ","}: target["health"] = {}
    calls, _ = mock_http(monkeypatch, module)
    with pytest.raises(module.Blocked):
        module.check_health(target, supplied)
    assert calls == []


def test_every_path_validates_before_the_first_probe(module, monkeypatch):
    target = health_target(); target["health"]["@example.invalid/x"] = rule()
    calls, _ = mock_http(monkeypatch, module)
    with pytest.raises(module.Blocked):
        module.check_health(target, "/web/health,@example.invalid/x")
    assert calls == []


@pytest.mark.parametrize("origin", ["http://127.0.0.1:8069", "https://[::1]:8069/"])
def test_valid_ipv4_and_ipv6_origins_probe_all_endpoints_without_proxy(module, monkeypatch, origin):
    target = health_target(); target["health_base_url"] = origin; target["health"]["/ready"] = rule()
    calls, handlers = mock_http(monkeypatch, module)
    monkeypatch.setenv("http_proxy", "http://example.invalid:8080")
    assert module.check_health(target, "/web/health,/ready") == {"/web/health": "PASS", "/ready": "PASS"}
    expected = urllib.parse.urlsplit(origin)
    assert len(calls) == 2
    for url, timeout in calls:
        parsed = urllib.parse.urlsplit(url)
        assert (parsed.scheme, parsed.netloc) == (expected.scheme, expected.netloc)
        assert 0 < timeout <= 3
    assert any(isinstance(handler, module.urllib.request.ProxyHandler) and handler.proxies == {} for handler in handlers)
    assert module.NoRedirect in handlers


@pytest.mark.parametrize("origin", [
    "http://example.invalid", "http://127.0.0.1:8069@example.invalid",
    "http://localhost:8069", "http://127.0.0.1:99999", "http://127.0.0.1:0",
    "http://127.0.0.1/a", "http://127.0.0.1?x=1", "http://127.0.0.1#x",
    "\nhttp://127.0.0.1", "http://[::1%25eth0]:8069", "file:///tmp/health",
])
def test_noncanonical_health_origins_fail_before_requests(module, monkeypatch, origin):
    target = health_target(); target["health_base_url"] = origin
    calls, _ = mock_http(monkeypatch, module)
    with pytest.raises(module.Blocked): module.check_health(target, "/web/health")
    assert calls == []


@pytest.mark.parametrize("timeout", [0, -1, 31, float("nan"), float("inf"), True, None, "5"])
def test_invalid_health_timeouts_fail_before_requests(module, monkeypatch, timeout):
    target = health_target(); target["health"]["/web/health"]["timeout_seconds"] = timeout
    calls, _ = mock_http(monkeypatch, module)
    with pytest.raises(module.Blocked): module.check_health(target, "/web/health")
    assert calls == []


@pytest.mark.parametrize("status,body", [(302, b'{"status":"ok"}'), (503, b'{"status":"ok"}'),
                                         (200, b'[]'), (200, b'{}'), (200, b'{"status":"bad"}'),
                                         (200, b'not-json')])
def test_invalid_health_responses_never_certify(module, monkeypatch, status, body):
    mock_http(monkeypatch, module, status=status, body=body)
    with pytest.raises(module.Blocked): module.check_health(health_target(), "/web/health")


def deployment_fixture(module, tmp_path, runtime_name):
    release = tmp_path / "releases" / ("b" * 40)
    (release / "custom-addons").mkdir(parents=True)
    target = {
        "schema": "codestra.odoo-deploy-target.v2", "target_host": "fixture-staging",
        "release_root": str(release.parent), "current_link": str(tmp_path / "current"),
        "compose_directory": str(tmp_path), "compose_files": ["compose.yaml"],
        "service": "odoo", "database": "fixture", "modules": "codestra_klyrow_smtp",
        "addon_mount": "/mnt/extra-addons", "service_image": "odoo@sha256:" + "1" * 64,
        "internal_networks": ["private"], "no_send_env": dict(module.NO_SEND_KEYS), **health_target(),
    }
    compose = {
        "name": "fixture-project",
        "services": {"odoo": {"image": target["service_image"], "environment": dict(module.NO_SEND_KEYS),
                               "networks": {"private": {}}, "volumes": [{"type": "bind",
                               "source": str(tmp_path / "current/custom-addons"),
                               "target": "/mnt/extra-addons", "read_only": True}]}},
        "networks": {"private": {"name": runtime_name, "internal": True}},
    }
    container = {
        "Mounts": [{"Destination": "/mnt/extra-addons", "Source": str(release / "custom-addons"), "RW": False}],
        "Config": {"Image": target["service_image"], "Env": [f"{k}={v}" for k, v in module.NO_SEND_KEYS.items()]},
        "NetworkSettings": {"Networks": {runtime_name: {"NetworkID": "net-id-1"}}},
    }
    network = {"Name": runtime_name, "Id": "net-id-1", "Internal": True}
    return target, compose, container, network, release


def mock_docker(module, monkeypatch, compose, container, network):
    calls = []
    def compose_call(_target, *command, **_kwargs):
        calls.append(("compose", *command))
        assert command in {("config", "--format", "json"), ("ps", "-q", "odoo")}, "mutation is prohibited"
        return subprocess.CompletedProcess([], 0, json.dumps(compose) if command[0] == "config" else "container-id\n", "")
    def run(argv, **kwargs):
        calls.append(tuple(argv))
        if argv[:2] == ["docker", "inspect"]: output = json.dumps([container])
        elif argv[:3] == ["docker", "network", "inspect"]:
            assert kwargs.get("timeout") == 30
            output = json.dumps([network])
        elif argv[:2] == ["docker", "exec"]:
            assert argv[3] == "sha256sum"
            output = "e" * 64 + "  importer\n"
        else: raise AssertionError(f"unexpected external operation: {argv}")
        return subprocess.CompletedProcess(argv, 0, output, "")
    monkeypatch.setattr(module, "docker_compose", compose_call)
    monkeypatch.setattr(module.subprocess, "run", run)
    return calls


@pytest.mark.parametrize("name", ["fixture-project_private", "custom-private-network", "private"])
def test_readback_resolves_logical_to_actual_network_names(module, monkeypatch, tmp_path, name):
    target, compose, container, network, release = deployment_fixture(module, tmp_path, name)
    calls = mock_docker(module, monkeypatch, compose, container, network)
    http_calls, _ = mock_http(monkeypatch, module)
    result = module.readback(target, release, "b" * 40, "e" * 64, SimpleNamespace(health_paths="/web/health"))
    assert result["no_send"] is True
    assert result["health"] == {"/web/health": "PASS"}
    assert ("docker", "network", "inspect", name) in calls
    assert len(http_calls) == 1


@pytest.mark.parametrize("fault", ["missing-name", "not-internal", "extra-network", "wrong-name", "wrong-id", "runtime-external"])
def test_network_mapping_or_isolation_drift_cannot_certify(module, monkeypatch, tmp_path, fault):
    target, compose, container, network, release = deployment_fixture(module, tmp_path, "fixture-project_private")
    if fault == "missing-name": del compose["networks"]["private"]["name"]
    elif fault == "not-internal": compose["networks"]["private"]["internal"] = False
    elif fault == "extra-network": container["NetworkSettings"]["Networks"]["public"] = {"NetworkID": "other"}
    elif fault == "wrong-name": container["NetworkSettings"]["Networks"] = {"private": {"NetworkID": "net-id-1"}}
    elif fault == "wrong-id": network["Id"] = "wrong-id"
    elif fault == "runtime-external": network["Internal"] = False
    calls = mock_docker(module, monkeypatch, compose, container, network)
    http_calls, _ = mock_http(monkeypatch, module)
    with pytest.raises(module.Blocked):
        module.readback(target, release, "b" * 40, "e" * 64, SimpleNamespace(health_paths="/web/health"))
    assert http_calls == []
    assert not any(call[:2] == ("docker", "exec") for call in calls)


def test_pending_empty_health_contract_is_rejected_at_target_load(module, monkeypatch, tmp_path):
    target, *_ = deployment_fixture(module, tmp_path, "fixture-project_private")
    target["health"] = {}
    monkeypatch.setattr(module, "root_regular", lambda _path: deepcopy(target))
    with pytest.raises(module.Blocked): module.load_target(tmp_path / "target.json", "fixture-staging")


def test_invalid_health_target_causes_no_artifact_or_compose_operation(module, monkeypatch, tmp_path):
    target, *_ = deployment_fixture(module, tmp_path, "fixture-project_private")
    target["health"] = {"@example.invalid/x": rule()}
    monkeypatch.setattr(module.os, "geteuid", lambda: 0)
    monkeypatch.setattr(module, "validate_handoff", lambda *_: None)
    monkeypatch.setattr(module, "validate_recovery_evidence", lambda *_: None)
    monkeypatch.setattr(module, "root_regular", lambda path: target if str(path).endswith("fixture-staging.json") else {})
    def prohibited(*_args, **_kwargs): raise AssertionError("preflight failure must precede operations")
    for name in ("verify_artifact", "docker_compose", "write_evidence", "deploy"):
        monkeypatch.setattr(module, name, prohibited)
    command = ["deploy-staging-readonly", "--read-only", "--deny-external-effects"]
    values = {"repository": "appolon1908-hue/Odoo", "source-sha": "b" * 40,
              "artifact-kind": "source-bundle", "artifact-reference": "file:///fixture.tar.gz",
              "artifact-digest": "sha256:" + "a" * 64, "environment": "staging-readonly",
              "health-paths": "@example.invalid/x", "evidence-output": str(tmp_path / "evidence.json"),
              "authorization": str(tmp_path / "auth.json"), "validated-target-host": "fixture-staging"}
    for key, value in values.items(): command.extend(["--" + key, value])
    assert module.main(command) == 1
