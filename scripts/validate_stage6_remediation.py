#!/usr/bin/env python3
"""Validate remediation source pins and migration isolation without runtime access.

These checks stay active under python -O. A source PASS never authorizes apply.
"""
from __future__ import annotations

import re
import shlex
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_DIR = ROOT / "deploy/staging/runtime-reconciliation"
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
ODOO_MUTATION = re.compile(r"(?:^|\s)(?:--(?:init|update)(?:=|\s|$)|-[iu](?:[^\s-]\S*)?(?:\s|$))")
SAFETY_KEYS = (
    "LIVE_ADVERTISING_ENABLED", "EXTERNAL_DELIVERY_ENABLED",
    "SOCIAL_PUBLISHING_ENABLED", "EXTERNAL_MODEL_CALLS_ENABLED",
    "LIVE_SMS_DELIVERY", "LIVE_EMAIL_DELIVERY", "LIVE_PSTN_DIALING",
    "PRODUCTION_DIALING",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def command_text(value: object, name: str, *, optional: bool = False) -> str:
    if value is None and optional:
        return ""
    if isinstance(value, str):
        tokens = shlex.split(value)
    else:
        require(isinstance(value, list) and all(isinstance(item, str) for item in value), f"{name}: command must be a string or string list")
        tokens = value
    require(bool(tokens) or optional, f"{name}: command is missing")
    return " ".join(tokens)


def service_map(compose: dict, expected: tuple[str, ...]) -> dict:
    require(isinstance(compose, dict), "Compose document must be an object")
    services = compose.get("services")
    require(isinstance(services, dict), "Compose services must be an object")
    for name in expected:
        require(isinstance(services.get(name), dict), f"{name}: service is missing")
    return services


def locked_digest(definition: dict) -> str:
    digest = definition.get("image_digest")
    require(isinstance(digest, str) and DIGEST.fullmatch(digest) is not None, "locked image digest is unresolved")
    return digest


def safety(service: dict, name: str) -> None:
    environment = service.get("environment")
    require(isinstance(environment, dict), f"{name}: explicit safety environment is required")
    for key in SAFETY_KEYS:
        require(key in environment and str(environment[key]).strip().lower() in {"false", "disabled", "0", "off", "no"}, f"{name}: {key} must be explicitly disabled")


def migration(service: dict, name: str) -> None:
    require(service.get("restart") == "no", f"{name}: migration must not restart")
    profiles = service.get("profiles")
    require(isinstance(profiles, list) and "one-shot-migration" in profiles, f"{name}: explicit migration profile is required")
    command_text(service.get("command"), name)


def application_command(service: dict, name: str, migration_names: set[str]) -> str:
    dependencies = service.get("depends_on", [])
    require(isinstance(dependencies, (dict, list)), f"{name}: invalid dependencies")
    require(not migration_names.intersection(dependencies), f"{name}: application must not start migration dependencies")
    return command_text(service.get("entrypoint"), name, optional=True) + " " + command_text(service.get("command"), name)


def validate_middleware(compose: dict, definition: dict) -> None:
    names = ("middleware-staging", "middleware-migration")
    services = service_map(compose, names)
    expected = "ghcr.io/appolon1908-hue/codestra-middleware@" + locked_digest(definition)
    for name in names:
        require(services[name].get("image") == expected, f"{name}: image differs from the authoritative source lock")
        safety(services[name], name)
    command = application_command(services[names[0]], names[0], {names[1]})
    require(not re.search(r"alembic|migrat", command, re.I), "middleware-staging: application startup contains a migration")
    migration(services[names[1]], names[1])


def validate_odoo(compose: dict, definition: dict) -> None:
    apps = ("odoo19-staging", "odoo19-master-staging")
    migrations = ("odoo19-module-migration", "odoo19-master-module-migration")
    services = service_map(compose, apps + migrations)
    digest = locked_digest(definition)
    allowed_images = {name + "@" + digest for name in ("odoo", "library/odoo", "docker.io/library/odoo")}
    for name in apps + migrations:
        require(services[name].get("image") in allowed_images, f"{name}: image differs from the authoritative source lock")
        safety(services[name], name)
    for name in apps:
        command = application_command(services[name], name, set(migrations))
        require(ODOO_MUTATION.search(command) is None, f"{name}: application startup contains an Odoo module mutation")
    for name in migrations:
        migration(services[name], name)
        command = command_text(services[name]["command"], name)
        require(re.search(r"(?:^|\s)--stop-after-init(?:\s|$)", command) is not None, f"{name}: one-shot exit is required")
        require(re.search(r"(?:^|\s)--no-http(?:\s|$)", command) is not None, f"{name}: migration must not serve HTTP")


def main() -> None:
    lock = yaml.safe_load((ROOT / "STAGE6-SOURCE-LOCK.yaml").read_text())
    require(lock["production_write_activation"] is False and lock["runtime_mutation_authorized"] is False, "runtime activation remains unauthorized")
    middleware = yaml.safe_load((COMPOSE_DIR / "compose.middleware-source-remediation.yaml").read_text())
    odoo = yaml.safe_load((COMPOSE_DIR / "compose.odoo-source-remediation.yaml").read_text())
    validate_middleware(middleware, lock["repositories"]["middleware"])
    validate_odoo(odoo, lock["repositories"]["odoo"])
    print("STAGE6_REMEDIATION_SOURCE=PASS")
    print("RUNTIME_APPLIED=NO")


if __name__ == "__main__":
    main()
