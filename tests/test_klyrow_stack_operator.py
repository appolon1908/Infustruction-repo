import importlib.machinery
import importlib.util
import json
from pathlib import Path
import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_operator():
    path = ROOT / "operators/klyrow-stack"
    loader = importlib.machinery.SourceFileLoader("klyrow_stack", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def record(project="klyrow", service="gateway", volumes=()):
    return {"id": "id", "name": "klyrow-gateway-1", "image": "image@sha256:d", "image_id": "sha256:d", "project": project, "service": service, "working_dir": "/opt/klyrow/current", "config_files": "docker-compose.yml", "restart": "unless-stopped", "health": "healthy", "networks": ["klyrow_backend"], "volumes": list(volumes), "ports": []}


def test_unknown_project_is_blocked(monkeypatch):
    op = load_operator()
    monkeypatch.setattr(op, "inspect_container", lambda name: record(project="other"))
    with pytest.raises(op.Blocked, match="BLOCK_AMBIGUOUS_OWNER"):
        op.ownership()


def test_missing_compose_labels_is_blocked(monkeypatch):
    op = load_operator()
    monkeypatch.setattr(op, "inspect_container", lambda name: record(project=None, service=None))
    with pytest.raises(op.Blocked):
        op.ownership()


def test_rollback_allows_missing_owned_container_when_volume_survives(monkeypatch):
    op = load_operator()

    def inspect(name):
        if name == "klyrow-gateway-1":
            return None
        item = record(service=op.FIXED[name])
        item["name"] = name
        if name == "klyrow-postgres-1":
            item["volumes"] = ["klyrow_postgres_data"]
        return item

    monkeypatch.setattr(op, "inspect_container", inspect)
    monkeypatch.setattr(op, "run", lambda *args, **kwargs: type("R", (), {"returncode": 0})())
    result = op.ownership("ROLLBACK_REPLACE", allow_absent=True)
    assert result["klyrow-gateway-1"]["health"] == "absent"


def test_modified_deployment_input_is_blocked(monkeypatch):
    op = load_operator()
    monkeypatch.setattr(op, "git_sha", lambda: op.TARGET_SHA)

    def fake_run(argv, **kwargs):
        code = 1 if "diff" in argv else 0
        return type("R", (), {"returncode": code})()

    monkeypatch.setattr(op, "run", fake_run)
    with pytest.raises(op.Blocked, match="local modifications"):
        op.clean_approved_worktree()


def test_missing_marker_is_blocked(monkeypatch, tmp_path):
    op = load_operator(); monkeypatch.setattr(op, "MARKER", tmp_path / "absent")
    with pytest.raises(FileNotFoundError):
        op.marker_ok({})


def test_safety_failure_is_blocked():
    op = load_operator()
    with pytest.raises(op.Blocked):
        op.verify_safe({"safe_mode": False}, op.TARGET_SHA)


def test_readback_combines_health_and_version_without_environment(monkeypatch):
    op = load_operator()
    payloads = iter(
        [
            {"safe_mode": True, "production_gate_approved": False, "production_gate_open": False, "outbox_active": 0},
            {"revision": op.TARGET_SHA},
        ]
    )

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    monkeypatch.setattr(op.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    monkeypatch.setattr(op.json, "load", lambda response: next(payloads))
    state = op.readback()
    assert state == {
        "live_email_delivery": False,
        "outbox_active": 0,
        "production_gate_approved": False,
        "production_gate_open": False,
        "revision": op.TARGET_SHA,
        "safe_mode": True,
    }
    op.verify_safe(state, op.TARGET_SHA)


def test_sudoers_has_no_generic_authority():
    text = (ROOT / "operators/klyrow-stack.sudoers").read_text()
    assert "NOPASSWD: ALL" not in text
    assert "/bin/sh" not in text
    assert "docker" not in text
