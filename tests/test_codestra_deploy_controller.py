import datetime as dt
import importlib.machinery
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def controller():
    path = ROOT / "operators" / "codestra-deploy"
    loader = importlib.machinery.SourceFileLoader("codestra_deploy", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def args(module):
    return module.parser().parse_args([
        "deploy-staging-readonly",
        "--repository", "appolon1908-hue/Odoo",
        "--source-sha", "a" * 40,
        "--artifact-kind", "source-bundle",
        "--artifact-reference", "release/source.tar.gz",
        "--artifact-digest", "sha256:" + "b" * 64,
        "--environment", "staging-readonly",
        "--health-paths", "/web/health",
        "--evidence-output", "/tmp/evidence.json",
        "--read-only", "--deny-external-effects",
    ])


def approved(module, arguments, now):
    evidence = "sha256:" + "c" * 64
    return {
        "schema": module.SCHEMA,
        "status": "APPROVED",
        "repository": arguments.repository,
        "source_sha": arguments.source_sha,
        "artifact_kind": arguments.artifact_kind,
        "artifact_reference": arguments.artifact_reference,
        "artifact_digest": arguments.artifact_digest,
        "environment": arguments.environment,
        "action": arguments.action,
        "controller_sha256": module.own_sha256(),
        "execution_host": module.socket.getfqdn(),
        "target_host": "middleware",
        "window": {
            "starts_at": (now - dt.timedelta(minutes=5)).isoformat(),
            "ends_at": (now + dt.timedelta(minutes=5)).isoformat(),
        },
        "recovery": {
            name: {"status": "PASS", "evidence_sha256": evidence}
            for name in ("database", "filestore", "configuration", "isolated_restore", "rollback_rehearsal")
        },
        "rollback_target": {"source_sha": "d" * 40, "artifact_digest": "sha256:" + "e" * 64},
        "approval": {
            "status": "APPROVED", "approved_by": "release-owner",
            "approved_at": now.isoformat(),
            "expires_at": (now + dt.timedelta(minutes=5)).isoformat(),
            "evidence_sha256": evidence,
        },
    }


def test_accepts_exact_authorized_tuple():
    module = controller(); arguments = args(module); now = dt.datetime.now(dt.timezone.utc)
    module.validate_authorization(approved(module, arguments, now), arguments, now)


@pytest.mark.parametrize("field,value,match", [
    ("artifact_digest", "sha256:" + "f" * 64, "artifact_digest mismatch"),
    ("target_host", "provider", "target_host mismatch"),
    ("status", "PENDING", "status mismatch"),
])
def test_rejects_wrong_artifact_target_or_missing_approval(field, value, match):
    module = controller(); arguments = args(module); now = dt.datetime.now(dt.timezone.utc)
    authorization = approved(module, arguments, now); authorization[field] = value
    with pytest.raises(module.Blocked, match=match):
        module.validate_authorization(authorization, arguments, now)


def test_rejects_expired_approval():
    module = controller(); arguments = args(module); now = dt.datetime.now(dt.timezone.utc)
    authorization = approved(module, arguments, now)
    authorization["approval"]["expires_at"] = (now - dt.timedelta(seconds=1)).isoformat()
    with pytest.raises(module.Blocked, match="approval expired"):
        module.validate_authorization(authorization, arguments, now)


def test_rejects_incomplete_recovery_evidence():
    module = controller(); arguments = args(module); now = dt.datetime.now(dt.timezone.utc)
    authorization = approved(module, arguments, now)
    authorization["recovery"]["filestore"]["status"] = "PENDING"
    with pytest.raises(module.Blocked, match="filestore"):
        module.validate_authorization(authorization, arguments, now)


def test_concurrent_execution_is_rejected(monkeypatch, tmp_path, capsys):
    module = controller(); arguments = args(module); now = dt.datetime.now(dt.timezone.utc)
    auth_path = tmp_path / "authorization.json"
    auth_path.write_text(json.dumps(approved(module, arguments, now)))
    auth_path.chmod(0o600)
    adapter = tmp_path / "adapter"; adapter.write_text("#!/bin/sh\nexit 0\n"); adapter.chmod(0o755)
    lock_path = tmp_path / "controller.lock"
    lock_path.touch()
    lock_handle = lock_path.open("w")
    module.fcntl.flock(lock_handle, module.fcntl.LOCK_EX | module.fcntl.LOCK_NB)
    monkeypatch.setattr(module, "ROOTS", (tmp_path,))
    monkeypatch.setattr(module, "LOCK", lock_path)
    monkeypatch.setattr(module, "ADAPTER", adapter)
    command = [*sum(([f"--{key.replace('_', '-')}", str(value)] for key, value in vars(arguments).items() if key not in {"action", "authorization"} and not isinstance(value, bool) and value is not None), []), "--authorization", str(auth_path), "--read-only", "--deny-external-effects"]
    assert module.main([arguments.action, *command]) == 1
    assert "another deployment" in capsys.readouterr().err
    lock_handle.close()


def test_pending_template_cannot_validate():
    module = controller(); arguments = args(module); now = dt.datetime.now(dt.timezone.utc)
    template = json.loads((ROOT / "release/templates/odoo-runtime-deployment-authorization.v1.json").read_text())
    with pytest.raises(module.Blocked):
        module.validate_authorization(template, arguments, now)
