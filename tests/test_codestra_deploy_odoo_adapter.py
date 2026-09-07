import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
import tarfile
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def protected_fixture_ownership(monkeypatch):
    """Model root-owned protected evidence without privileged CI operations."""
    if os.geteuid() == 0 and os.environ.get("CODESTRA_TEST_UNPRIVILEGED") != "1":
        return
    original = Path.lstat
    def root_lstat(path):
        values=list(original(path)); values[4]=values[5]=0
        return os.stat_result(values)
    monkeypatch.setattr(Path,"lstat",root_lstat)


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
    module = adapter(); recovery = {}; binding={"source_sha":"b"*40,"artifact_digest":"sha256:"+"a"*64,"target_host":"staging-odoo","recovery_set_id":"set-1","rollback_source_sha":"c"*40,"rollback_artifact_digest":"sha256:"+"d"*64}
    for name in ("database", "filestore", "configuration", "isolated_restore", "rollback_rehearsal"):
        body = json.dumps({"scope": name, "status": "PASS", **binding}, sort_keys=True).encode()
        digest = hashlib.sha256(body).hexdigest(); (tmp_path / f"{digest}.json").write_bytes(body)
        recovery[name] = {"status": "PASS", "evidence_sha256": "sha256:" + digest}
    auth={"recovery":recovery,"source_sha":binding["source_sha"],"artifact_digest":binding["artifact_digest"],"target_host":binding["target_host"],"recovery_set_id":binding["recovery_set_id"],"rollback_target":{"source_sha":binding["rollback_source_sha"],"artifact_digest":binding["rollback_artifact_digest"]}}
    module.validate_recovery_evidence(auth, tmp_path)
    recovery["filestore"]["evidence_sha256"] = "sha256:" + "0" * 64
    with pytest.raises(module.Blocked, match="filestore"):
        module.validate_recovery_evidence(auth, tmp_path)


def test_target_requires_exact_no_send_policy(monkeypatch, tmp_path):
    module = adapter(); path = tmp_path / "target.json"
    target = {"schema":"codestra.odoo-deploy-target.v2","target_host":"staging-odoo","release_root":"/srv/releases","current_link":"/srv/current","compose_directory":"/srv/compose","compose_files":["compose.yml"],"service":"odoo","database":"odoo","modules":"codestra_klyrow_smtp","addon_mount":"/mnt/extra-addons","no_send_env":dict(module.NO_SEND_KEYS),"service_image":"odoo@sha256:"+"1"*64,"internal_networks":["private"],"health_base_url":"http://127.0.0.1:8069","health":{"/web/health":{"status":200,"json_field":"status","json_value":"ok"}}}
    path.write_text(json.dumps(target)); path.chmod(0o600)
    loaded = module.load_target(path, "staging-odoo"); assert loaded["target_host"] == "staging-odoo"
    target["no_send_env"]["LIVE_EMAIL_DELIVERY"] = "true"; path.write_text(json.dumps(target))
    with pytest.raises(module.Blocked, match="no-send"):
        module.load_target(path, "staging-odoo")


def test_failed_upgrade_enters_needs_recovery_without_old_restart(monkeypatch, tmp_path):
    module = adapter(); source_tree = tmp_path / "tree"; importer = source_tree / "custom-addons/codestra_klyrow_smtp/scripts/provision_klyrow_smtp.py"; importer.parent.mkdir(parents=True); importer.write_text("safe")
    archive = tmp_path / "source.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle: bundle.add(source_tree, arcname=".")
    args = arguments(module, "sha256:" + module.sha256(archive)); args.artifact_reference = archive.as_uri()
    previous = tmp_path / "releases" / ("c" * 40); previous.mkdir(parents=True)
    current = tmp_path / "current"; current.symlink_to(previous)
    target = {"release_root":str(tmp_path / "releases"),"current_link":str(current),"compose_files":["compose.yml"],"compose_directory":str(tmp_path),"service":"odoo","database":"odoo","modules":"codestra_klyrow_smtp","service_image":"odoo@sha256:"+"1"*64,"internal_networks":["private"],"addon_mount":"/mnt/extra-addons"}
    calls = []
    monkeypatch.setattr(module, "validate_effective_compose", lambda *_: None)
    def compose(_target, *command, check=True):
        calls.append(command)
        if command[0] == "config":
            release = source_tree if len(calls)==1 else tmp_path/"releases"/args.source_sha
            body={"services":{"odoo":{"image":target["service_image"],"environment":dict(module.NO_SEND_KEYS),"networks":{"private":{}},"volumes":[{"source":str(release/"custom-addons"),"target":"/mnt/extra-addons","read_only":True}]}},"networks":{"private":{"internal":True,"name":"project_private"}}}
            return module.subprocess.CompletedProcess(command,0,json.dumps(body),"")
        if command[0] == "run": raise module.subprocess.CalledProcessError(1, command)
        return module.subprocess.CompletedProcess(command, 0, "", "")
    monkeypatch.setattr(module, "docker_compose", compose)
    with pytest.raises(module.NeedsRecovery): module.deploy(args, authorization(args), target)
    assert current.resolve() != previous.resolve()
    assert ("up", "-d", "odoo") not in calls


def test_production_is_rejected_before_any_mutation(monkeypatch, tmp_path):
    module=adapter(); args=arguments(module); args.action="promote-production-readonly"
    calls=[]; monkeypatch.setattr(module,"docker_compose",lambda *_a,**_k: calls.append(_a))
    with pytest.raises(module.Blocked,match="traffic canary"):
        module.deploy(args,authorization(args),{})
    assert calls == []


def test_effective_configuration_rejects_send_before_mutation(monkeypatch, tmp_path):
    module=adapter(); target={"service":"odoo","service_image":"odoo@sha256:"+"1"*64,"internal_networks":["private"],"addon_mount":"/mnt/extra-addons","current_link":str(tmp_path/"current")}
    document={"services":{"odoo":{"image":target["service_image"],"environment":dict(module.NO_SEND_KEYS)|{"EMAIL_DELIVERY":"true"},"networks":{"private":{}},"volumes":[]}},"networks":{"private":{"internal":True,"name":"project_private"}}}
    monkeypatch.setattr(module,"docker_compose",lambda *_a,**_k: subprocess.CompletedProcess([],0,json.dumps(document),""))
    with pytest.raises(module.Blocked,match="no-send"):
        module.validate_effective_compose(target)


def test_streaming_limit_removes_partial_file(monkeypatch,tmp_path):
    module=adapter(); module.MAX_ARCHIVE_BYTES=8
    source=tmp_path/"large"; source.write_bytes(b"x"*9); destination=tmp_path/"partial"
    with pytest.raises(module.Blocked,match="maximum size"):
        module.acquire_artifact(source.as_uri(),destination)
    assert not destination.exists()


def test_cumulative_archive_and_member_count_limits_cleanup(tmp_path):
    module=adapter(); archive=tmp_path/"a.tar.gz"; destination=tmp_path/"out"; destination.mkdir()
    with tarfile.open(archive,"w:gz") as bundle:
        for name in ("one","two"):
            info=tarfile.TarInfo(name); info.size=6; bundle.addfile(info,io.BytesIO(b"x"*6))
    module.MAX_EXPANDED_BYTES=10
    with pytest.raises(module.Blocked,match="expansion"):
        module.extract_verified(archive,destination)
    assert not destination.exists()


def test_in_container_importer_must_match_verified_bytes(monkeypatch,tmp_path):
    module=adapter(); release=tmp_path/"release"; (release/"custom-addons").mkdir(parents=True)
    image="odoo@sha256:"+"1"*64
    target={"service":"odoo","addon_mount":"/mnt/extra-addons","health":{},"health_base_url":"http://127.0.0.1","service_image":image,"internal_networks":["private"]}
    monkeypatch.setattr(module,"docker_compose",lambda *_a,**_k: subprocess.CompletedProcess([],0,"cid\n",""))
    def run(argv,**kwargs):
        if argv[1]=="inspect": return subprocess.CompletedProcess(argv,0,json.dumps([{"Mounts":[{"Destination":"/mnt/extra-addons","Source":str(release/"custom-addons"),"RW":False}],"Config":{"Image":image,"Env":[f"{k}={v}" for k,v in module.NO_SEND_KEYS.items()]},"NetworkSettings":{"Networks":{"private":{}}}}]),"")
        return subprocess.CompletedProcess(argv,0,"f"*64+"  importer\n","")
    monkeypatch.setattr(module,"validate_effective_compose",lambda _target: {"private":"private"})
    monkeypatch.setattr(module,"validate_runtime_networks",lambda *_args: None)
    monkeypatch.setattr(module.subprocess,"run",run)
    with pytest.raises(module.Blocked,match="differs"):
        module.readback(target,release,"b"*40,"e"*64,arguments(module))


def test_each_health_endpoint_is_required_and_redirects_are_disabled(monkeypatch):
    module=adapter(); target={"health":{"/live":{"status":200,"json_field":"status","json_value":"ok"},"/ready":{"status":200,"json_field":"status","json_value":"ok"}},"health_base_url":"http://127.0.0.1"}
    with pytest.raises(module.Blocked,match="set differs"):
        module.check_health(target,"/live")
    assert module.NoRedirect().redirect_request(None,None,None,None,None,None,None) is None


def test_target_rejects_non_loopback_health_origin(tmp_path):
    module=adapter(); path=tmp_path/"target.json"
    target={"schema":"codestra.odoo-deploy-target.v2","target_host":"staging-odoo","release_root":"/srv/releases","current_link":"/srv/current","compose_directory":"/srv/compose","compose_files":["compose.yml"],"service":"odoo","database":"odoo","modules":"codestra_klyrow_smtp","addon_mount":"/mnt/extra-addons","no_send_env":dict(module.NO_SEND_KEYS),"service_image":"odoo@sha256:"+"1"*64,"internal_networks":["private"],"health_base_url":"https://example.com","health":{}}
    path.write_text(json.dumps(target)); path.chmod(0o600)
    with pytest.raises(module.Blocked,match="loopback"):
        module.load_target(path,"staging-odoo")


def test_effective_compose_uses_stable_current_path(monkeypatch,tmp_path):
    module=adapter(); current=tmp_path/"current"; image="odoo@sha256:"+"1"*64
    target={"service":"odoo","service_image":image,"internal_networks":["private"],"addon_mount":"/mnt/extra-addons","current_link":str(current)}
    document={"services":{"odoo":{"image":image,"environment":dict(module.NO_SEND_KEYS),"networks":{"private":{}},"volumes":[f"{current}/custom-addons:/mnt/extra-addons:ro"]}},"networks":{"private":{"internal":True,"name":"project_private"}}}
    monkeypatch.setattr(module,"docker_compose",lambda *_a,**_k: subprocess.CompletedProcess([],0,json.dumps(document),""))
    assert module.validate_effective_compose(target)=={"private":"project_private"}


def test_readback_rejects_running_send_enabled(monkeypatch,tmp_path):
    module=adapter(); release=tmp_path/"release"; (release/"custom-addons").mkdir(parents=True); image="odoo@sha256:"+"1"*64
    target={"service":"odoo","addon_mount":"/mnt/extra-addons","health":{},"health_base_url":"http://127.0.0.1","service_image":image,"internal_networks":["private"]}
    monkeypatch.setattr(module,"docker_compose",lambda *_a,**_k: subprocess.CompletedProcess([],0,"cid\n",""))
    inspection={"Mounts":[{"Destination":"/mnt/extra-addons","Source":str(release/"custom-addons"),"RW":False}],"Config":{"Image":image,"Env":["ENABLE_EXTERNAL_DELIVERY=false","EMAIL_DELIVERY=true","LIVE_EMAIL_DELIVERY=false"]},"NetworkSettings":{"Networks":{"private":{}}}}
    monkeypatch.setattr(module.subprocess,"run",lambda argv,**kwargs: subprocess.CompletedProcess(argv,0,json.dumps([inspection]),""))
    with pytest.raises(module.Blocked,match="no-send"):
        module.readback(target,release,"b"*40,"e"*64,arguments(module))


def test_recovery_evidence_is_candidate_bound(tmp_path):
    module=adapter(); recovery={}; base={"source_sha":"b"*40,"artifact_digest":"sha256:"+"a"*64,"target_host":"staging-odoo","recovery_set_id":"set-1","rollback_source_sha":"c"*40,"rollback_artifact_digest":"sha256:"+"d"*64}
    for name in ("database","filestore","configuration","isolated_restore","rollback_rehearsal"):
        body={"scope":name,"status":"PASS",**base}; raw=json.dumps(body,sort_keys=True).encode(); digest=hashlib.sha256(raw).hexdigest(); (tmp_path/f"{digest}.json").write_bytes(raw); recovery[name]={"status":"PASS","evidence_sha256":"sha256:"+digest}
    auth={"source_sha":"9"*40,"artifact_digest":base["artifact_digest"],"target_host":base["target_host"],"recovery_set_id":base["recovery_set_id"],"rollback_target":{"source_sha":base["rollback_source_sha"],"artifact_digest":base["rollback_artifact_digest"]},"recovery":recovery}
    with pytest.raises(module.Blocked,match="content mismatch"):
        module.validate_recovery_evidence(auth,tmp_path)


def test_health_rejects_empty_set_and_origin_escape(monkeypatch):
    module=adapter(); target={"health":{},"health_base_url":"http://127.0.0.1:8069"}
    with pytest.raises(module.Blocked,match="at least one"):
        module.check_health(target,"")
    target["health"]={"@example.com/x":{"status":200,"json_field":"status","json_value":"ok"}}
    monkeypatch.setattr(module.urllib.request,"build_opener",lambda *_: pytest.fail("network must not be reached"))
    with pytest.raises(module.Blocked,match="origin-relative"):
        module.check_health(target,"@example.com/x")


def test_runtime_network_uses_compose_resolved_name(monkeypatch,tmp_path):
    module=adapter(); release=tmp_path/"release"; (release/"custom-addons").mkdir(parents=True); image="odoo@sha256:"+"1"*64
    target={"service":"odoo","addon_mount":"/mnt/extra-addons","health":{"/live":{"status":200,"json_field":"status","json_value":"ok"}},"health_base_url":"http://127.0.0.1","service_image":image,"internal_networks":["private"]}
    monkeypatch.setattr(module,"docker_compose",lambda *_a,**_k: subprocess.CompletedProcess([],0,"cid\n",""))
    inspection={"Mounts":[{"Destination":"/mnt/extra-addons","Source":str(release/"custom-addons"),"RW":False}],"Config":{"Image":image,"Env":[f"{k}={v}" for k,v in module.NO_SEND_KEYS.items()]},"NetworkSettings":{"Networks":{"project_private":{"NetworkID":"net-id-1"}}}}
    def run(argv,**kwargs):
        if argv[1]=="inspect": return subprocess.CompletedProcess(argv,0,json.dumps([inspection]),"")
        if argv[1:3]==["network","inspect"]: return subprocess.CompletedProcess(argv,0,json.dumps([{"Name":"project_private","Id":"net-id-1","Internal":True}]),"")
        return subprocess.CompletedProcess(argv,0,"e"*64+"  importer\n","")
    monkeypatch.setattr(module,"validate_effective_compose",lambda _target:{"private":"project_private"})
    monkeypatch.setattr(module.subprocess,"run",run); monkeypatch.setattr(module,"check_health",lambda *_:{"/live":"PASS"})
    result=module.readback(target,release,"b"*40,"e"*64,arguments(module),{"private":"project_private"})
    assert result["health"]=={"/live":"PASS"}
