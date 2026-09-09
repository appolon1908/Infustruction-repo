#!/usr/bin/env python3
"""Build deterministic controller/adapter source package and manifest."""
import argparse, gzip, hashlib, io, json, tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "operators/codestra-deploy", "operators/codestra-deploy-odoo",
    "operators/install-codestra-deploy-package", "operators/codestra-deploy.sudoers",
    "operators/klyrow-odoo-smtp-export.sudoers", "operators/install-klyrow-odoo-smtp-export-policy",
    "release/templates/deploy-targets.v1.json", "release/templates/odoo-deploy-target.v1.json",
    "release/templates/odoo-runtime-deployment-authorization.v1.json",
    "docs/ODOO-KLYROW-AUTHORIZED-DEPLOYMENT-PACKAGE.md",
)

def digest(data): return hashlib.sha256(data).hexdigest()

def build(output: Path, source_sha: str):
    records = []
    with output.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as bundle:
            for relative in FILES:
                data = (ROOT / relative).read_bytes(); records.append({"path": relative, "sha256": digest(data)})
                info = tarfile.TarInfo(relative); info.size = len(data); info.mtime = 0; info.uid = info.gid = 0; info.uname = info.gname = "root"
                info.mode = 0o755 if relative.startswith(("operators/codestra-", "operators/install-")) and not relative.endswith(".sudoers") else 0o644
                bundle.addfile(info, io.BytesIO(data))
    manifest = {
        "schema": "codestra.deploy-controller-package.v1", "source_sha": source_sha,
        "package_sha256": digest(output.read_bytes()), "controller_sha256": digest((ROOT/"operators/codestra-deploy").read_bytes()),
        "adapter_sha256": digest((ROOT/"operators/codestra-deploy-odoo").read_bytes()), "files": records,
        "dependencies": {"python": ">=3.11", "bash": ">=5", "docker_compose": "reviewed target dependency", "cosign": "release-workflow identity"},
        "runtime_deployment_authorized": False, "external_effects_authorized": False,
    }
    manifest_path = output.with_suffix(output.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest_path

if __name__ == "__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--output",type=Path,required=True); parser.add_argument("--source-sha",required=True)
    values=parser.parse_args(); build(values.output, values.source_sha)
