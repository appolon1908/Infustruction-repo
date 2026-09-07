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
        "adapter_sha256": "f" * 64,
        "execution_host": module.socket.getfqdn(),
        "target_host": "middleware",
        "evidence_output": arguments.evidence_output,
        "window": {
            "starts_at": (now - dt.timedelta(minutes=5)).isoformat(),
            "ends_at": (now + dt.timedelta(minutes=5)).isoformat(),
        },
        "recovery_set_id": "recovery-set-20260907-001",
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
    module.validate_authorization(approved(module, arguments, now), arguments, now, "middleware")


@pytest.mark.parametrize("field,value,match", [
    ("artifact_digest", "sha256:" + "f" * 64, "artifact_digest mismatch"),
    ("target_host", "provider", "target_host mismatch"),
    ("status", "PENDING", "status mismatch"),
])
def test_rejects_wrong_artifact_target_or_missing_approval(field, value, match):
    module = controller(); arguments = args(module); now = dt.datetime.now(dt.timezone.utc)
    authorization = approved(module, arguments, now); authorization[field] = value
    with pytest.raises(module.Blocked, match=match):
        module.validate_authorization(authorization, arguments, now, "middleware")


def test_rejects_expired_approval():
    module = controller(); arguments = args(module); now = dt.datetime.now(dt.timezone.utc)
    authorization = approved(module, arguments, now)
    authorization["approval"]["approved_at"] = (now - dt.timedelta(minutes=5)).isoformat()
    authorization["approval"]["expires_at"] = (now - dt.timedelta(seconds=1)).isoformat()
    with pytest.raises(module.Blocked, match="approval expired"):
        module.validate_authorization(authorization, arguments, now, "middleware")


def test_rejects_incomplete_recovery_evidence():
    module = controller(); arguments = args(module); now = dt.datetime.now(dt.timezone.utc)
    authorization = approved(module, arguments, now)
    authorization["recovery"]["filestore"]["status"] = "PENDING"
    with pytest.raises(module.Blocked, match="filestore"):
        module.validate_authorization(authorization, arguments, now, "middleware")


def test_concurrent_execution_is_rejected(tmp_path):
    module = controller(); tmp_path.chmod(0o700)
    lock_path = tmp_path / "locks" / "controller.lock"
    with module.deployment_lock(lock_path, tmp_path):
        with pytest.raises(module.Blocked, match="another deployment"):
            with module.deployment_lock(lock_path, tmp_path):
                pass


def test_lock_rejects_symlink_without_truncating_target(tmp_path):
    module = controller(); tmp_path.chmod(0o700)
    directory = tmp_path / "locks"; directory.mkdir(mode=0o700)
    sentinel = tmp_path / "sentinel"; sentinel.write_bytes(b"preserve-me")
    (directory / "controller.lock").symlink_to(sentinel)
    with pytest.raises(module.Blocked, match="cannot be opened safely"):
        with module.deployment_lock(directory / "controller.lock", tmp_path):
            pass
    assert sentinel.read_bytes() == b"preserve-me"


def test_lock_rejects_hardlink_and_unsafe_parent(tmp_path):
    module = controller(); tmp_path.chmod(0o700)
    directory = tmp_path / "locks"; directory.mkdir(mode=0o700)
    sentinel = tmp_path / "sentinel"; sentinel.write_bytes(b"preserve-me")
    (directory / "controller.lock").hardlink_to(sentinel)
    with pytest.raises(module.Blocked, match="metadata is unsafe"):
        with module.deployment_lock(directory / "controller.lock", tmp_path):
            pass
    (directory / "controller.lock").unlink(); directory.chmod(0o777)
    with pytest.raises(module.Blocked, match="directory is unsafe"):
        with module.deployment_lock(directory / "controller.lock", tmp_path):
            pass


def test_adapter_digest_and_trusted_ancestors_are_enforced(tmp_path):
    module = controller(); tmp_path.chmod(0o700)
    adapter = tmp_path / "adapter"; adapter.write_text("#!/bin/sh\nexit 0\n"); adapter.chmod(0o755)
    digest = module.hashlib.sha256(adapter.read_bytes()).hexdigest()
    assert module.validate_trusted_executable(adapter, digest, tmp_path) == adapter
    with pytest.raises(module.Blocked, match="digest mismatch"):
        module.validate_trusted_executable(adapter, "0" * 64, tmp_path)
    adapter.write_text("#!/bin/sh\nexit 1\n")
    with pytest.raises(module.Blocked, match="digest mismatch"):
        module.validate_trusted_executable(adapter, digest, tmp_path)


def test_pending_template_cannot_validate():
    module = controller(); arguments = args(module); now = dt.datetime.now(dt.timezone.utc)
    template = json.loads((ROOT / "release/templates/odoo-runtime-deployment-authorization.v1.json").read_text())
    with pytest.raises(module.Blocked):
        module.validate_authorization(template, arguments, now, "middleware")


@pytest.mark.parametrize("approved_at", [None, "malformed"])
def test_rejects_missing_or_malformed_approval_time(approved_at):
    module = controller(); arguments = args(module); now = dt.datetime.now(dt.timezone.utc)
    authorization = approved(module, arguments, now); authorization["approval"]["approved_at"] = approved_at
    with pytest.raises(module.Blocked, match="approval.approved_at"):
        module.validate_authorization(authorization, arguments, now, "middleware")


def test_rejects_future_approval_and_incoherent_window():
    module = controller(); arguments = args(module); now = dt.datetime.now(dt.timezone.utc)
    authorization = approved(module, arguments, now)
    authorization["approval"]["approved_at"] = (now + dt.timedelta(minutes=1)).isoformat()
    with pytest.raises(module.Blocked, match="interval is incoherent"):
        module.validate_authorization(authorization, arguments, now, "middleware")
    authorization = approved(module, arguments, now)
    authorization["window"]["starts_at"], authorization["window"]["ends_at"] = authorization["window"]["ends_at"], authorization["window"]["starts_at"]
    with pytest.raises(module.Blocked, match="execution window"):
        module.validate_authorization(authorization, arguments, now, "middleware")


def production_args(module, percentage="1"):
    value = args(module)
    value.action = "promote-production-readonly"; value.environment = "production-readonly-canary"
    value.require_staging_certification = True; value.require_backup = True
    value.require_isolated_restore = True; value.require_rollback_rehearsal = True
    value.allowed_methods = "GET,HEAD"; value.canary_percent = percentage
    return value


@pytest.mark.parametrize("percentage", ["100", "NaN", "Infinity", "-1", "0"])
def test_rejects_unsafe_production_canary_values(percentage):
    module = controller()
    with pytest.raises(module.Blocked, match="canary percentage"):
        module.validate_invocation(production_args(module, percentage))


def test_rejects_each_missing_production_safeguard():
    module = controller()
    for field in ("require_staging_certification", "require_backup", "require_isolated_restore", "require_rollback_rehearsal"):
        arguments = production_args(module); setattr(arguments, field, False)
        with pytest.raises(module.Blocked, match="safeguards"):
            module.validate_invocation(arguments)
    arguments = production_args(module); arguments.allowed_methods = "GET,HEAD,POST"
    with pytest.raises(module.Blocked, match="safeguards"):
        module.validate_invocation(arguments)


def test_target_map_separates_staging_and_production():
    module = controller()
    mapping = {"schema": "codestra.deploy-target-map.v1", "targets": {"staging-readonly": "staging-odoo", "production-readonly-canary": "middleware"}}
    assert module.validate_target_map(mapping, "staging-readonly") == "staging-odoo"
    mapping["targets"]["staging-readonly"] = "PENDING_STAGING_TARGET_HOST"
    with pytest.raises(module.Blocked, match="unassigned"):
        module.validate_target_map(mapping, "staging-readonly")


def test_actual_production_workflow_command_parses_and_enforces_safety():
    module = controller()
    command = [
        "promote-production-readonly", "--repository", "appolon1908-hue/Odoo",
        "--source-sha", "a" * 40, "--artifact-kind", "source-bundle",
        "--artifact-reference", "release/source.tar.gz", "--artifact-digest", "sha256:" + "b" * 64,
        "--environment", "production-readonly-canary", "--health-paths", "/web/health",
        "--read-only", "--canary-percent", "1", "--allowed-methods", "GET,HEAD",
        "--require-staging-certification", "--require-backup", "--require-isolated-restore",
        "--require-rollback-rehearsal", "--deny-external-effects", "--evidence-output", "/tmp/evidence.json",
    ]
    arguments = module.parser().parse_args(command)
    module.validate_invocation(arguments)


def test_evidence_output_must_match_authorization_and_be_safe():
    module = controller(); arguments = args(module); now = dt.datetime.now(dt.timezone.utc)
    authorization = approved(module, arguments, now); authorization["evidence_output"] = "/tmp/other.json"
    with pytest.raises(module.Blocked, match="evidence_output mismatch"):
        module.validate_authorization(authorization, arguments, now, "middleware")
    arguments.evidence_output = "../../etc/passwd"
    with pytest.raises(module.Blocked, match="evidence output path"):
        module.validate_invocation(arguments)


def test_adapter_receives_canonical_validated_authorization_and_target(tmp_path):
    module = controller(); arguments = production_args(module)
    authorization = tmp_path / "authorization.json"; authorization.touch()
    forwarded = module.build_adapter_arguments(arguments, authorization, "middleware")
    assert forwarded.count("--authorization") == 1
    assert forwarded[forwarded.index("--authorization") + 1] == str(authorization.resolve())
    assert forwarded[forwarded.index("--validated-target-host") + 1] == "middleware"
    assert "--require-isolated-restore" in forwarded
    assert "POST" not in forwarded
