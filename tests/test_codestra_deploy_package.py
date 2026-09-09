import importlib.util, json, tarfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("builder",ROOT/"scripts/build_codestra_deploy_package.py"); builder=importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)

def test_package_is_reproducible_and_non_authorizing(tmp_path):
    one=tmp_path/"one.tar.gz"; two=tmp_path/"two.tar.gz"
    first=builder.build(one,"a"*40); second=builder.build(two,"a"*40)
    assert one.read_bytes()==two.read_bytes()
    manifest=json.loads(first.read_text()); assert manifest["package_sha256"]==builder.digest(one.read_bytes())
    assert manifest["runtime_deployment_authorized"] is False and manifest["external_effects_authorized"] is False
    assert manifest["adapter_sha256"]==builder.digest((ROOT/"operators/codestra-deploy-odoo").read_bytes())
    with tarfile.open(one) as package:
        assert set(package.getnames())==set(builder.FILES)
        assert all(not member.issym() and not member.islnk() for member in package.getmembers())
