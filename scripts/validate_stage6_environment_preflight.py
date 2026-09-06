#!/usr/bin/env python3
"""Validate the protected Stage 6 infrastructure environment without API calls.

The script checks only whether required encrypted secrets exist and whether the
non-secret environment variables satisfy the reviewed Stage 6 input boundary.
It never prints, stores, or hashes secret values and never contacts Hetzner,
object storage, SSH, or production.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

REQUIRED_SECRETS = {
    "HETZNER_CLOUD_TOKEN",
    "TF_STATE_ACCESS_KEY",
    "TF_STATE_SECRET_KEY",
}
REQUIRED_VARIABLES = {
    "TF_STATE_BUCKET",
    "TF_STATE_ENDPOINT",
    "TF_STATE_REGION",
    "STAGE6_TFVARS_JSON",
}
APPROVED_SSH_KEY_IDS = {118172836}
APPROVED_EGRESS_FQDNS = {
    "api.github.com",
    "archive.ubuntu.com",
    "azure.archive.ubuntu.com",
    "github.com",
    "ghcr.io",
    "objects.githubusercontent.com",
    "pkg-containers.githubusercontent.com",
    "release-assets.githubusercontent.com",
    "security.ubuntu.com",
}
REQUIRED_EGRESS_FQDNS = {"archive.ubuntu.com", "security.ubuntu.com"}
APPROVED_PRODUCTION_DENY_CIDRS = {
    "37.27.128.39/32",
    "65.109.65.169/32",
    "10.40.0.0/24",
}
BUCKET_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")
REGION_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
ED25519_PUBLIC_KEY_RE = re.compile(
    r"^ssh-ed25519 [A-Za-z0-9+/]{40,}={0,2}( [A-Za-z0-9_.@-]{1,64})?$"
)


class PreflightError(ValueError):
    """Raised for malformed non-secret configuration."""


def presence_flag(name: str, environment: dict[str, str]) -> bool:
    return environment.get(f"HAS_{name}", "").strip().lower() == "true"


def _list_of_strings(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise PreflightError(f"{label} must be a non-empty string list")
    return [item.strip() for item in value]


def _list_of_ints(value: object, label: str) -> list[int]:
    if not isinstance(value, list) or not value or not all(
        isinstance(item, int) and not isinstance(item, bool) and item > 0
        for item in value
    ):
        raise PreflightError(f"{label} must be a non-empty positive-integer list")
    return value


def validate_tfvars(raw: str) -> list[str]:
    errors: list[str] = []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        return [f"STAGE6_TFVARS_JSON is invalid JSON: {exc.msg}"]
    if not isinstance(value, dict):
        return ["STAGE6_TFVARS_JSON must be a JSON object"]

    try:
        key_ids = set(
            _list_of_ints(
                value.get("approved_ssh_key_ids"),
                "approved_ssh_key_ids",
            )
        )
        if key_ids != APPROVED_SSH_KEY_IDS:
            errors.append("approved_ssh_key_ids must equal the reviewed Stage 6 key set")
    except PreflightError as exc:
        errors.append(str(exc))

    operator_key = value.get("staging_readonly_operator_public_key")
    if (
        not isinstance(operator_key, str)
        or "\n" in operator_key.strip()
        or not ED25519_PUBLIC_KEY_RE.fullmatch(operator_key.strip())
    ):
        errors.append(
            "staging_readonly_operator_public_key must contain exactly one reviewed Ed25519 public key"
        )

    try:
        cidrs = _list_of_strings(
            value.get("approved_ssh_source_cidrs"),
            "approved_ssh_source_cidrs",
        )
        for cidr in cidrs:
            try:
                network = ipaddress.ip_network(cidr, strict=False)
            except ValueError:
                errors.append(f"approved_ssh_source_cidrs contains invalid CIDR: {cidr}")
                continue
            if network.prefixlen == 0:
                errors.append("approved_ssh_source_cidrs must not contain a global CIDR")
    except PreflightError as exc:
        errors.append(str(exc))

    try:
        egress = set(
            _list_of_strings(
                value.get("approved_egress_fqdns"),
                "approved_egress_fqdns",
            )
        )
        missing = REQUIRED_EGRESS_FQDNS - egress
        extra = egress - APPROVED_EGRESS_FQDNS
        if missing:
            errors.append(
                "approved_egress_fqdns is missing required Ubuntu mirrors: "
                + ", ".join(sorted(missing))
            )
        if extra:
            errors.append(
                "approved_egress_fqdns contains unreviewed destinations: "
                + ", ".join(sorted(extra))
            )
    except PreflightError as exc:
        errors.append(str(exc))

    ports = value.get("approved_egress_ports", [80, 443])
    if not isinstance(ports, list) or set(ports) != {80, 443}:
        errors.append("approved_egress_ports must equal 80 and 443")

    deny = value.get("known_internal_production_deny_cidrs")
    if deny is not None:
        try:
            deny_set = set(
                _list_of_strings(
                    deny,
                    "known_internal_production_deny_cidrs",
                )
            )
            missing_deny = APPROVED_PRODUCTION_DENY_CIDRS - deny_set
            if missing_deny:
                errors.append(
                    "known_internal_production_deny_cidrs is missing protected targets: "
                    + ", ".join(sorted(missing_deny))
                )
        except PreflightError as exc:
            errors.append(str(exc))

    expected_scalars: dict[str, object] = {
        "location": "hel1",
        "server_type": "cx43",
        "egress_gateway_server_type": "cx23",
        "network_cidr": "10.250.0.0/16",
        "staging_subnet_cidr": "10.250.6.0/24",
        "private_ip": "10.250.6.10",
        "egress_gateway_private_ip": "10.250.6.2",
    }
    for name, expected in expected_scalars.items():
        if name in value and value.get(name) != expected:
            errors.append(f"{name} must remain {expected}")
    return errors


def validate_environment(environment: dict[str, str]) -> tuple[list[str], dict[str, Any]]:
    missing_secrets = sorted(
        name for name in REQUIRED_SECRETS if not presence_flag(name, environment)
    )
    missing_variables = sorted(
        name for name in REQUIRED_VARIABLES if not environment.get(name, "").strip()
    )
    invalid_variables: list[str] = []
    errors: list[str] = []

    bucket = environment.get("TF_STATE_BUCKET", "").strip()
    if bucket and not BUCKET_RE.fullmatch(bucket):
        invalid_variables.append("TF_STATE_BUCKET")
        errors.append("TF_STATE_BUCKET is not a valid reviewed bucket name")

    endpoint = environment.get("TF_STATE_ENDPOINT", "").strip()
    if endpoint:
        parsed = urlsplit(endpoint)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            invalid_variables.append("TF_STATE_ENDPOINT")
            errors.append(
                "TF_STATE_ENDPOINT must be credential-free HTTPS without query or fragment"
            )

    region = environment.get("TF_STATE_REGION", "").strip()
    if region and not REGION_RE.fullmatch(region):
        invalid_variables.append("TF_STATE_REGION")
        errors.append("TF_STATE_REGION is invalid")

    tfvars = environment.get("STAGE6_TFVARS_JSON", "").strip()
    if tfvars:
        tfvar_errors = validate_tfvars(tfvars)
        if tfvar_errors:
            invalid_variables.append("STAGE6_TFVARS_JSON")
            errors.extend(tfvar_errors)

    if missing_secrets:
        errors.append("required encrypted infrastructure secrets are missing")
    if missing_variables:
        errors.append("required infrastructure variables are missing")

    evidence = {
        "schema_version": 1,
        "environment": "stage6-infrastructure-provisioning",
        "status": "PASS" if not errors else "BLOCKED",
        "production_changed": False,
        "provider_contacted": False,
        "remote_state_contacted": False,
        "ssh_attempted": False,
        "secret_values_recorded": False,
        "missing_secrets": missing_secrets,
        "missing_variables": missing_variables,
        "invalid_variables": sorted(set(invalid_variables)),
        "blockers": sorted(set(errors)),
    }
    return errors, evidence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors, evidence = validate_environment(dict(os.environ))
    if args.evidence_output:
        args.evidence_output.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_output.write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if errors:
        for error in errors:
            print(f"STAGE6_ENVIRONMENT_BLOCKER={error}", file=sys.stderr)
        print("STAGE6_INFRASTRUCTURE_ENVIRONMENT=BLOCKED")
        return 1
    print("STAGE6_INFRASTRUCTURE_ENVIRONMENT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
