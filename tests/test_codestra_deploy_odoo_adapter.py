import hashlib
import importlib.machinery
import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def adapter():
    path = ROOT / "operators/codestra-deploy-odoo"
    loader = importlib.machinery.SourceFileLoader("codestra_deploy_odoo", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec); loader.exec_module(module)
    return module


def arguments(module, artifact="sha256:" + "a" * 64):
    return module.parser().parse_args([
        "deploy-staging-readonly", "--repository", "appolon1908-hue/Odoo",
        "--source-sha", "b" * 40, "--artifact-kind", "source-bundle",
        "--artifact-reference", "file:///tmp/source.tar.gz", "--artifact-digest", artifact,
        "--environment", "staging-readonly", "--health-paths", "/web/health",
        "--evidence-output", "/tmp/evidence.json", "--authorization", "/tmp/auth.json",
        "--validated-target-host", "staging-odoo", "--read-only", "--deny-external-effects",
    ])


def authorization(args):
    return {key: getattr(args, key) for key in ("repository", "source_sha", "artifact_kind", "artifact_reference", "artifact_digest", "environment", "action", "validated_target_host", "evidence_output")} | {"target_host": args.validated_target_host}


def test_dispatcher_handoff_rejects_wrong_artifact_and_target(monkeypatch):
    module = adapter(); args = arguments(module); auth = authorization(args)
    monkeypatch.setattr(module.socket, "gethostname", lambda: "staging-odoo")
    monkeypatch.setattr(module.socket, "getfqdn", lambda: "staging-odoo")
    module.validate_handoff(args, auth)
    auth["artifact_digest"] = "sha256:" + "c" * 64
    with pytest.raises(module.Blocked, match="artifact_digest"):
        module.validate_handoff(args, auth)
    auth = authorization(args); auth["target_host"] = "middleware"
    with pytest.raises(module.Blocked, match="target_host"):
        module.validate_handoff(args, auth)


def test_artifact_digest_mismatch_blocks_before_extract(monkeypatch, tmp_path):
    module = adapter(); source = tmp_path / "source.tar.gz"; source.write_bytes(b"wrong")
    args = arguments(module); args.artifact_reference = source.as_uri()
    auth = authorization(args)
    target = {"release_root": str(tmp_path / "releases"), "current_link": str(tmp_path / "current")}
    with pytest.raises(module.Blocked, match="artifact digest mismatch"):
        module.deploy(args, auth, target)
    assert not (tmp_path / "releases" / args.source_sha).exists()


def test_unsafe_archive_member_is_rejected(tmp_path):
    module = adapter(); archive = tmp_path / "source.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        info = tarfile.TarInfo("../../escape"); payload = b"bad"; info.size = len(payload)
        bundle.addfile(info, io.BytesIO(payload))
    destination = tmp_path / "out"; destination.mkdir()
    with pytest.raises(module.Blocked, match="unsafe member"):
        module.extract_verified(archive, destination)
    assert not (tmp_path / "escape").exists()


def test_recovery_requires_each_exact_evidence_blob(tmp_path):
    module = adapter(); recovery = {}
    for name in ("database", "filestore", "configuration", "isolated_restore", "rollback_rehearsal"):
        body = json.dumps({"scope": name, "status": "PASS"}, sort_keys=True).encode()
        digest = hashlib.sha256(body).hexdigest(); (tmp_path / f"{digest}.json").write_bytes(body)
        recovery[name] = {"status": "PASS", "evidence_sha256": "sha256:" + digest}
    module.validate_recovery_evidence({"recovery": recovery}, tmp_path)
    recovery["filestore"]["evidence_sha256"] = "sha256:" + "0" * 64
    with pytest.raises(module.Blocked, match="filestore"):
        module.validate_recovery_evidence({"recovery": recovery}, tmp_path)


def test_target_requires_exact_no_send_policy(monkeypatch, tmp_path):
    module = adapter(); path = tmp_path / "target.json"
    target = {"schema":"codestra.odoo-deploy-target.v1","target_host":"staging-odoo","release_root":"/srv/releases","current_link":"/srv/current","compose_directory":"/srv/compose","compose_files":["compose.yml"],"service":"odoo","database":"odoo","modules":"codestra_klyrow_smtp","addon_mount":"/mnt/extra-addons","no_send_env":dict(module.NO_SEND_KEYS)}
    path.write_text(json.dumps(target)); path.chmod(0o600)
    loaded = module.load_target(path, "staging-odoo"); assert loaded["target_host"] == "staging-odoo"
    target["no_send_env"]["LIVE_EMAIL_DELIVERY"] = "true"; path.write_text(json.dumps(target))
    with pytest.raises(module.Blocked, match="no-send"):
        module.load_target(path, "staging-odoo")


def test_failed_upgrade_restores_previous_pointer_and_restarts(monkeypatch, tmp_path):
    module = adapter(); source_tree = tmp_path / "tree"; importer = source_tree / "custom-addons/codestra_klyrow_smtp/scripts/provision_klyrow_smtp.py"; importer.parent.mkdir(parents=True); importer.write_text("safe")
    archive = tmp_path / "source.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle: bundle.add(source_tree, arcname=".")
    args = arguments(module, "sha256:" + module.sha256(archive)); args.artifact_reference = archive.as_uri()
    previous = tmp_path / "releases" / ("c" * 40); previous.mkdir(parents=True)
    current = tmp_path / "current"; current.symlink_to(previous)
    target = {"release_root":str(tmp_path / "releases"),"c":"", "current_link":str(current),"compose_files":["compose.yml"],"compose_directory":str(tmp_path),"service":"odoo","database":"odoo","modules":"codestra_klyrow_smtp"}
    calls = []
    def compose(_target, *command, check=True):
        calls.append(command)
        if command[0] == "run": raise module.subprocess.CalledProcessError(1, command)
        return module.subprocess.CompletedProcess(command, 0, "", "")
    monkeypatch.setattr(module, "docker_compose", compose)
    with pytest.raises(module.subprocess.CalledProcessError): module.deploy(args, authorization(args), target)
    assert current.resolve() == previous.resolve()
    assert ("up", "-d", "odoo") in calls
