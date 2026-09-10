import importlib.machinery
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def module():
    loader = importlib.machinery.SourceFileLoader(
        "odoo_environment_isolation_adapter", str(ROOT / "operators/codestra-deploy-odoo")
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    loaded = importlib.util.module_from_spec(spec)
    loader.exec_module(loaded)
    return loaded


def target(module, environment: str):
    staging = environment == "staging-readonly"
    suffix = "staging" if staging else "production"
    port = 18069 if staging else 28069
    return {
        "schema": "codestra.odoo-deploy-target.v3",
        "target_host": "middleware",
        "environment": environment,
        "release_root": f"/srv/codestra/{suffix}/releases",
        "current_link": f"/srv/codestra/{suffix}/current",
        "compose_directory": f"/srv/codestra/{suffix}/compose",
        "compose_files": ["compose.yaml"],
        "service": f"odoo-{suffix}",
        "database": f"codestra_{suffix}",
        "modules": "codestra_klyrow_smtp",
        "addon_mount": "/mnt/extra-addons",
        "no_send_env": dict(module.NO_SEND_KEYS),
        "service_image": "odoo@sha256:" + "1" * 64,
        "internal_networks": [f"{suffix}-private"],
        "health_base_url": f"http://127.0.0.1:{port}",
        "health": {
            "/web/health": {
                "status": 200,
                "json_field": "status",
                "json_value": "ok",
                "timeout_seconds": 3,
            }
        },
    }


def install_config(root: Path, value: dict) -> Path:
    path = root / f"middleware.{value['environment']}.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def plain_root_regular(path: Path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError("fixture must be an object")
    return value


@pytest.mark.parametrize(
    "field",
    [
        "release_root",
        "current_link",
        "compose_directory",
        "service",
        "database",
        "health_base_url",
    ],
)
def test_same_host_environment_resource_collision_fails_closed(module, monkeypatch, tmp_path, field):
    staging = target(module, "staging-readonly")
    production = target(module, "production-readonly-canary")
    production[field] = staging[field]
    staging_path = install_config(tmp_path, staging)
    install_config(tmp_path, production)

    monkeypatch.setattr(module, "CONFIG_ROOT", tmp_path)
    monkeypatch.setattr(module, "root_regular", plain_root_regular)

    with pytest.raises(module.Blocked, match=rf"environment resource collision on middleware: {field}"):
        module.load_target(staging_path, "middleware", "staging-readonly")


def test_distinct_same_host_environment_resources_are_accepted(module, monkeypatch, tmp_path):
    staging = target(module, "staging-readonly")
    production = target(module, "production-readonly-canary")
    staging_path = install_config(tmp_path, staging)
    install_config(tmp_path, production)

    monkeypatch.setattr(module, "CONFIG_ROOT", tmp_path)
    monkeypatch.setattr(module, "root_regular", plain_root_regular)

    assert module.load_target(staging_path, "middleware", "staging-readonly") == staging


def test_malformed_or_wrong_environment_sibling_fails_closed(module, monkeypatch, tmp_path):
    staging = target(module, "staging-readonly")
    sibling = target(module, "production-readonly-canary")
    sibling["environment"] = "staging-readonly"
    staging_path = install_config(tmp_path, staging)
    sibling_path = tmp_path / "middleware.production-readonly-canary.json"
    sibling_path.write_text(json.dumps(sibling), encoding="utf-8")

    monkeypatch.setattr(module, "CONFIG_ROOT", tmp_path)
    monkeypatch.setattr(module, "root_regular", plain_root_regular)

    with pytest.raises(module.Blocked, match="sibling Odoo target configuration mismatch"):
        module.load_target(staging_path, "middleware", "staging-readonly")


def test_parser_rejects_environment_outside_closed_set(module):
    argv = [
        "deploy-staging-readonly",
        "--repository", "appolon1908-hue/Odoo",
        "--source-sha", "b" * 40,
        "--artifact-kind", "source-bundle",
        "--artifact-reference", "file:///fixture.tar.gz",
        "--artifact-digest", "sha256:" + "a" * 64,
        "--environment", "../../production",
        "--health-paths", "/web/health",
        "--evidence-output", "/tmp/evidence.json",
        "--authorization", "/tmp/auth.json",
        "--validated-target-host", "middleware",
    ]
    with pytest.raises(SystemExit):
        module.parser().parse_args(argv)
