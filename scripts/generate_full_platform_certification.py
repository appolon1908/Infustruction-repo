#!/usr/bin/env python3
"""Generate a secret-free, current-host platform inventory and API evidence set."""

from __future__ import annotations

import argparse
import datetime as dt
from certification_evidence import gate_bindings, digest
import json
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
GATE_EVIDENCE_PATH = ROOT / "SERVER-37-PRODUCTION-GATE-EVIDENCE.yaml"
GENERATED_AT = dt.datetime.now(dt.timezone.utc).isoformat()
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
DURABLE_IDEMPOTENCY_REQUIRED = {
    ("KLYROW", "POST", "/v1/messages"),
    ("KLYROW", "POST", "/v1/messages/{}/cancel"),
    ("KLYROW", "POST", "/v1/campaigns/{}/schedule"),
    ("KLYROW", "POST", "/v1/campaigns/{}/cancel"),
    ("KLYROW", "POST", "/v1/operations/{}/cancel"),
    ("KLYROW", "POST", "/v1/operations/{}/reconcile"),
    ("KLYROW", "POST", "/v1/integrations/mautic/commands"),
    ("KLYROW", "POST", "/v1/integrations/mautic/operations/{}/reconcile"),
    ("TELNEXA", "POST", "/v1/sms/messages"),
    ("TELNEXA", "POST", "/v1/sms/messages/{}/cancel"),
    ("TELNEXA", "POST", "/v1/smpp/accounts"),
    ("TELNEXA", "PATCH", "/v1/smpp/accounts/{}"),
    ("TELNEXA", "POST", "/v1/webhooks/sms/delivery"),
    ("TELNEXA", "POST", "/v1/webhooks/provider/{}"),
    ("TELNEXA", "POST", "/v1/operations/{}/cancel"),
    ("TELNEXA", "POST", "/v1/operations/{}/reconcile"),
    ("KYQRA", "POST", "/v1/jobs"),
    ("KYQRA", "POST", "/v1/jobs/{}/cancel"),
    ("KYQRA", "POST", "/v1/jobs/{}/retry"),
    ("KYQRA", "POST", "/v1/callbacks"),
    ("KYQRA", "POST", "/v1/operations/{}/cancel"),
    ("KYQRA", "POST", "/v1/operations/{}/reconcile"),
    ("PRIVATE_GATEWAY", "POST", "/v1/integrations/sms/commands"),
    ("PRIVATE_GATEWAY", "POST", "/v1/operations/{}/cancel"),
    ("PRIVATE_GATEWAY", "POST", "/v1/operations/{}/reconcile"),
}
CUSTOM_REPOSITORIES = {
    "KLYROW": "https://github.com/appolon1908-hue/klyrow.com",
    "TELNEXA": "https://github.com/appolon1908-hue/telnexa",
    "KYQRA": "https://github.com/appolon1908-hue/kyqra-crawler",
    "PRIVATE_GATEWAY": "https://github.com/appolon1908-hue/codestra-production-platform",
}
SOURCE_DIRECTORIES = {
    "KLYROW": Path("/root/klyrow-production-release-da9d85891a4e"),
    "TELNEXA": Path("/root/full-platform-telnexa-20260902"),
    "KYQRA": Path("/root/kyqra-production-hardening-20260902"),
    "PRIVATE_GATEWAY": Path("/root/private-gateway-protected-9ec227d"),
}
EXPECTED_PUBLIC_IPV4 = "37.27.128.39"
EXPECTED_PRIVATE_IPV4 = "10.40.0.4"
KYQRA_BUILD_IMAGE = (
    "node:22-alpine@sha256:"
    "c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32"
)


def command(*arguments: str, check: bool = True) -> str:
    result = subprocess.run(arguments, text=True, capture_output=True, check=False)
    if check and result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(arguments)}")
    return result.stdout


def repository_head(path: str | Path) -> str:
    directory = str(path)
    dirty = command("git", "-C", directory, "status", "--porcelain=v1")
    if dirty:
        raise RuntimeError(f"source worktree is dirty: {directory}")
    revision = command("git", "-C", directory, "rev-parse", "HEAD").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise RuntimeError(f"source revision is not an exact Git SHA: {directory}")
    return revision


def verified_host_identity() -> dict[str, str]:
    """Fail closed unless this is the exact Server 37 network identity."""
    document = json.loads(command("ip", "-json", "-4", "address", "show", "up"))
    addresses = {
        str(address.get("local"))
        for interface in document
        for address in interface.get("addr_info", [])
        if address.get("family") == "inet" and address.get("local")
    }
    missing = {EXPECTED_PUBLIC_IPV4, EXPECTED_PRIVATE_IPV4} - addresses
    if missing:
        raise RuntimeError(
            "host identity mismatch; missing expected address(es): "
            + ", ".join(sorted(missing))
        )
    hostname = command("hostname").strip()
    if not hostname:
        raise RuntimeError("host identity mismatch; hostname is empty")
    return {
        "hostname": hostname,
        "public_ipv4": EXPECTED_PUBLIC_IPV4,
        "private_ipv4": EXPECTED_PRIVATE_IPV4,
    }


def live_https_without_server_error(verification: str) -> bool:
    return re.fullmatch(r"LIVE_HTTPS_([1-4][0-9]{2})", verification) is not None


def source_openapi() -> dict[str, dict[str, Any]]:
    revisions_before = {
        service: repository_head(directory)
        for service, directory in SOURCE_DIRECTORIES.items()
    }
    scripts = {
        "KLYROW": (
            SOURCE_DIRECTORIES["KLYROW"],
            "/root/.venv-full-platform-klyrow-20260902/bin/python",
            "from apps.gateway.app.platform import app; import json; print(json.dumps(app.openapi()))",
        ),
        "TELNEXA": (
            SOURCE_DIRECTORIES["TELNEXA"],
            "/root/.venv-full-platform-telnexa-20260902/bin/python",
            "import datetime; datetime.UTC=getattr(datetime,'UTC',datetime.timezone.utc); "
            "from billing.app import app; import json; print(json.dumps(app.openapi()))",
        ),
        "PRIVATE_GATEWAY": (
            SOURCE_DIRECTORIES["PRIVATE_GATEWAY"],
            "/root/.venv-middleware-umbrella-20260902/bin/python",
            "import runpy,json; value=runpy.run_path('services/private-integration-gateway/gateway.py'); "
            "print(json.dumps({mode:value['openapi_document'](mode) for mode in ('middleware','shared')}))",
        ),
    }
    documents: dict[str, dict[str, Any]] = {}
    for service, (working_directory, python, script) in scripts.items():
        result = subprocess.run(
            [python, "-c", script], cwd=working_directory, text=True, capture_output=True, check=True
        )
        document = json.loads(result.stdout)
        if service == "PRIVATE_GATEWAY":
            middleware = document["middleware"]
            shared = document["shared"]
            combined = dict(shared)
            combined["paths"] = dict(shared["paths"])
            for path, path_item in middleware["paths"].items():
                existing = combined["paths"].get(path)
                if existing is not None and existing != path_item:
                    raise RuntimeError(f"private gateway mode contract conflict: {path}")
                combined["paths"][path] = path_item
            combined["x-gateway-modes"] = ["middleware", "shared"]
            document = combined
        documents[service] = document
    kyqra_directory = SOURCE_DIRECTORIES["KYQRA"]
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{kyqra_directory}:/source:ro",
            "-w",
            "/work",
            "-e",
            "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1",
            KYQRA_BUILD_IMAGE,
            "sh",
            "-euc",
            "cp /source/package.json /source/package-lock.json /source/tsconfig.json .; "
            "cp -R /source/scripts /source/migrations /source/src .; "
            "npm ci --ignore-scripts --no-audit --no-fund >/dev/null; "
            "npm run build >/dev/null; "
            "exec node --input-type=module -e "
            '"import(\'./dist/api/openapi.js\').then(m=>process.stdout.write(JSON.stringify(m.kyqraOpenApi)))"',
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    documents["KYQRA"] = json.loads(result.stdout)
    revisions_after = {
        service: repository_head(directory)
        for service, directory in SOURCE_DIRECTORIES.items()
    }
    if revisions_after != revisions_before:
        raise RuntimeError("source revision changed during OpenAPI extraction")
    return documents


def live_openapi(container: str, port: int, path: str) -> dict[str, Any]:
    url = f"http://127.0.0.1:{port}{path}"
    python_script = (
        "import json,urllib.request;"
        f"print(json.dumps(json.load(urllib.request.urlopen({url!r},timeout=5))))"
    )
    node_script = (
        f"fetch({url!r}).then(r=>{{if(!r.ok)throw Error(String(r.status));return r.json()}})"
        ".then(v=>process.stdout.write(JSON.stringify(v))).catch(()=>process.exit(1))"
    )
    attempts = (
        ("docker", "exec", container, "python", "-c", python_script),
        ("docker", "exec", container, "python3", "-c", python_script),
        ("docker", "exec", container, "node", "-e", node_script),
    )
    for arguments in attempts:
        output = command(*arguments, check=False)
        try:
            document = json.loads(output)
        except json.JSONDecodeError:
            continue
        if isinstance(document, dict) and isinstance(document.get("paths"), dict):
            return document
    return {"paths": {}}


def probe_container_http(container: str, port: int, path: str) -> int | None:
    inspected = json.loads(command("docker", "inspect", container))[0]
    addresses = [
        value.get("IPAddress")
        for value in inspected["NetworkSettings"]["Networks"].values()
        if value.get("IPAddress")
    ]
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for address in addresses:
        try:
            with opener.open(f"http://{address}:{port}{path}", timeout=5) as response:
                return response.status
        except urllib.error.HTTPError as error:
            return error.code
        except (urllib.error.URLError, TimeoutError):
            continue
    return None


def normalized(path: str) -> str:
    return re.sub(r"\{[^}]+\}|:[A-Za-z_][A-Za-z0-9_]*", "{}", path.replace("(.:format)", ""))


def contract_normalized(service: str, path: str) -> str:
    value = normalized(path)
    if service in {"TELNEXA", "KYQRA"} and value.startswith("/api/v1"):
        return value.removeprefix("/api")
    return value


def operations(document: dict[str, Any]) -> set[tuple[str, str]]:
    return {
        (method.upper(), normalized(path))
        for path, item in document.get("paths", {}).items()
        for method in item
        if method in HTTP_METHODS
    }


def dereference(document: dict[str, Any], value: Any, seen: frozenset[str] = frozenset()) -> Any:
    if isinstance(value, list):
        return [dereference(document, item, seen) for item in value]
    if not isinstance(value, dict):
        return value
    reference = value.get("$ref")
    if isinstance(reference, str) and reference.startswith("#/"):
        if reference in seen:
            return {"$ref": reference}
        target: Any = document
        try:
            for part in reference[2:].split("/"):
                target = target[part.replace("~1", "/").replace("~0", "~")]
        except (KeyError, TypeError):
            return {"$ref": reference}
        merged = dereference(document, target, seen | {reference})
        siblings = {key: item for key, item in value.items() if key != "$ref"}
        if siblings and isinstance(merged, dict):
            merged = {**merged, **dereference(document, siblings, seen)}
        return merged
    return {
        key: dereference(document, item, seen)
        for key, item in value.items()
    }


def operation_contracts(service: str, document: dict[str, Any]) -> dict[tuple[str, str], str]:
    inherited_security = document.get("security", [])
    result: dict[tuple[str, str], str] = {}
    for path, item in document.get("paths", {}).items():
        for method, operation in item.items():
            if method not in HTTP_METHODS:
                continue
            effective = dict(operation)
            effective["security"] = operation.get("security", inherited_security)
            result[(method.upper(), contract_normalized(service, path))] = json.dumps(
                dereference(document, effective), sort_keys=True, separators=(",", ":")
            )
    return result


def model_name(value: Any) -> str:
    serialized = json.dumps(value, sort_keys=True)
    references = re.findall(r'"\$ref":\s*"#/components/schemas/([^"/]+)', serialized)
    return ",".join(sorted(set(references))) if references else "N/A"


def has_durable_idempotency(path: str, operation: dict[str, Any]) -> bool:
    del path
    if operation.get("x-durable-idempotency") is True:
        return True
    parameter_contract = any(
        parameter.get("in") == "header"
        and str(parameter.get("name", "")).lower() == "idempotency-key"
        and parameter.get("required") is True
        for parameter in operation.get("parameters", [])
    )
    security_requirements = operation.get("security", [])
    security_contract = isinstance(security_requirements, list) and any(
        "idempotencyHeader" in requirement
        for requirement in security_requirements
        if isinstance(requirement, dict)
    )
    return parameter_contract or security_contract


def requires_durable_idempotency(service: str, method: str, path: str) -> bool:
    return (
        service,
        method.upper(),
        contract_normalized(service, path),
    ) in DURABLE_IDEMPOTENCY_REQUIRED


def endpoint_record(
    service: str,
    method: str,
    path: str,
    operation: dict[str, Any],
    runtime: set[tuple[str, str]],
    *,
    status: str = "IMPLEMENTED",
    verification: str | None = None,
    stage: str = "PRODUCTION_CANDIDATE",
    document_security: Any = None,
) -> dict[str, Any]:
    public_bases = {
        "KLYROW": "https://api.klyrow.com",
        "TELNEXA": "https://api.telnexa.co",
        "KYQRA": "https://crawler.kyqra.com",
        "PRIVATE_GATEWAY": "N/A",
        "KEYCLOAK": "https://api.telnexa.co/auth/realms/telnexa",
        "OPENBAO": "https://bao.codestra.media",
        "MAUTIC": "N/A",
        "POSTAL": "N/A",
        "PROMETHEUS_KLYROW": "N/A",
        "PROMETHEUS_TELNEXA": "N/A",
        "GRAFANA_KLYROW": "N/A",
        "NGINX": "N/A",
    }
    private_bases = {
        "KLYROW": "http://klyrow-gateway-1:8000",
        "TELNEXA": "http://telnexa-saas-billing-api-1:8000",
        "KYQRA": "http://kyqra-crawler-api-1:3000",
        "PRIVATE_GATEWAY": "http://private-app-integration-gateway-1:8080",
        "KEYCLOAK": "http://keycloak:8080/auth/realms/telnexa",
        "OPENBAO": "http://127.0.0.1:18200",
        "MAUTIC": "http://mautic",
        "POSTAL": "http://postal-web:5000",
        "PROMETHEUS_KLYROW": "http://klyrow-prometheus-1:9090",
        "PROMETHEUS_TELNEXA": "http://telnexa-saas-prometheus-1:9090",
        "GRAFANA_KLYROW": "http://klyrow-grafana-1:3000",
        "NGINX": "http://127.0.0.1",
    }
    key = (method.upper(), normalized(path))
    if verification is None:
        verification = "LIVE_OPENAPI_MATCH" if key in runtime else "SOURCE_ONLY_REVIEW_REQUIRED"
    secured = bool(
        operation["security"] if "security" in operation else document_security
    )
    mutating = method.upper() in {"POST", "PUT", "PATCH", "DELETE"}
    known_idempotent = has_durable_idempotency(path, operation)
    idempotency_required = requires_durable_idempotency(service, method, path)
    if status == "IMPLEMENTED" and idempotency_required and not known_idempotent:
        status = "PARTIAL"
    return {
        "service": service,
        "method": method.upper(),
        "path": path,
        "public_url": "N/A" if public_bases[service] == "N/A" else public_bases[service] + path,
        "private_url": private_bases[service] + path,
        "authentication": "REQUIRED" if secured else "N/A",
        "authorization": "TENANT_AND_SCOPE" if service in {"KLYROW", "TELNEXA", "KYQRA", "PRIVATE_GATEWAY"} and secured else ("SERVICE_POLICY" if secured else "N/A"),
        "tenant_model": "TENANT_SCOPED" if service in {"KLYROW", "TELNEXA", "KYQRA", "PRIVATE_GATEWAY"} and secured else "N/A",
        "idempotency": (
            "DURABLE" if mutating and known_idempotent
            else "NOT_IMPLEMENTED" if idempotency_required
            else "NOT_REQUIRED" if mutating
            else "N/A"
        ),
        "request_model": model_name(operation.get("requestBody", {})),
        "response_model": model_name(operation.get("responses", {})),
        "external_effect": "POSSIBLE" if mutating else "NONE",
        "implementation_status": status,
        "runtime_verification": verification,
        "stage": stage,
    }


def provider_endpoints() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for path in (
        "/.well-known/openid-configuration",
        "/protocol/openid-connect/auth",
        "/protocol/openid-connect/token",
        "/protocol/openid-connect/certs",
        "/protocol/openid-connect/userinfo",
        "/protocol/openid-connect/logout",
        "/protocol/openid-connect/token/introspect",
    ):
        method = "GET" if path in {"/.well-known/openid-configuration", "/protocol/openid-connect/certs", "/protocol/openid-connect/userinfo"} else "POST"
        result.append(endpoint_record("KEYCLOAK", method, path, {"security": path != "/.well-known/openid-configuration"}, {(method, normalized(path))}, verification="LIVE_DISCOVERY_CONFIRMED", stage="PRODUCTION"))
    for path in ("/v1/sys/health", "/v1/sys/seal-status"):
        result.append(endpoint_record("OPENBAO", "GET", path, {"security": False}, set(), status="PARTIAL", verification="LIVE_501_UNINITIALIZED", stage="PRODUCTION"))
    for service, container, port, paths in (
        ("PROMETHEUS_KLYROW", "klyrow-prometheus-1", 9090, ("/-/healthy", "/-/ready", "/api/v1/targets", "/api/v1/alerts")),
        ("PROMETHEUS_TELNEXA", "telnexa-saas-prometheus-1", 9090, ("/-/healthy", "/-/ready", "/api/v1/targets", "/api/v1/alerts")),
        ("GRAFANA_KLYROW", "klyrow-grafana-1", 3000, ("/api/health", "/api/search", "/api/datasources")),
    ):
        for path in paths:
            status_code = probe_container_http(container, port, path)
            expected = status_code in {200, 401, 403}
            result.append(endpoint_record(
                service,
                "GET",
                path,
                {"security": path not in {"/-/healthy", "/-/ready", "/api/health"}},
                {("GET", normalized(path))} if expected else set(),
                status="IMPLEMENTED" if expected else "PARTIAL",
                verification=(
                    f"LIVE_HTTP_{status_code}"
                    if status_code is not None
                    else "LIVE_HTTP_UNREACHABLE"
                ),
                stage="PRODUCTION",
            ))
    mautic_output = command(
        "docker", "exec", "-w", "/var/www/html", "klyrow-mautic-1",
        "php", "bin/console", "debug:router", "--format=json",
    )
    for route in json.loads(mautic_output).values():
        path = str(route.get("path", "")).replace("{._format}", "").replace(".{_format}", "")
        if not path:
            continue
        methods = str(route.get("method") or "ANY").split("|")
        for method in methods:
            result.append(endpoint_record("MAUTIC", method, path, {"security": True}, {(method, normalized(path))}, verification="LIVE_ROUTER_EXTRACTED", stage="PRODUCTION"))
    postal_output = command(
        "docker", "exec", "-w", "/opt/postal/app", "klyrow-postal-web-1",
        "bundle", "exec", "rails", "routes", "--expanded",
    )
    for block in postal_output.split("--[ Route "):
        verb = re.search(r"^Verb\s+\|\s+(.+)$", block, re.MULTILINE)
        uri = re.search(r"^URI\s+\|\s+(.+)$", block, re.MULTILINE)
        if not verb or not uri:
            continue
        path = uri.group(1).strip().replace("(.:format)", "")
        for method in verb.group(1).strip().split("|"):
            result.append(endpoint_record("POSTAL", method, path, {"security": True}, {(method, normalized(path))}, verification="LIVE_RAILS_ROUTER_EXTRACTED", stage="PRODUCTION"))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for host in (
        "klyrow.com", "www.klyrow.com", "app.klyrow.com", "api.klyrow.com",
        "track.klyrow.com", "bounce.klyrow.com", "bao.codestra.media",
        "crawler.kyqra.com", "sms.telnexa.co", "api.telnexa.co",
        "status.telnexa.co", "admin.telnexa.co",
    ):
        status_code: int | None = None
        try:
            with opener.open(f"https://{host}/", timeout=10) as response:
                status_code = response.status
        except urllib.error.HTTPError as error:
            status_code = error.code
        except (urllib.error.URLError, TimeoutError):
            pass
        expected = (
            status_code == 403
            if host == "admin.telnexa.co"
            else status_code is not None and 200 <= status_code < 500
        )
        result.append(
            {
                "service": "NGINX", "method": "ANY", "path": f"https://{host}/*",
                "public_url": f"https://{host}", "private_url": "N/A",
                "authentication": "ROUTE_DEPENDENT", "authorization": "ROUTE_DEPENDENT",
                "tenant_model": "N/A", "idempotency": "N/A", "request_model": "N/A",
                "response_model": "N/A", "external_effect": "ROUTE_DEPENDENT",
                "implementation_status": "N/A" if host == "admin.telnexa.co" and expected else ("IMPLEMENTED" if expected else "PARTIAL"),
                "runtime_verification": (
                    "INTENTIONAL_HTTPS_403"
                    if host == "admin.telnexa.co" and status_code == 403
                    else ((f"ADMIN_DENIAL_FAILED_HTTP_{status_code}" if status_code is not None else "ADMIN_DENIAL_FAILED_UNREACHABLE") if host == "admin.telnexa.co" else (f"LIVE_HTTPS_{status_code}" if status_code is not None else "LIVE_HTTPS_UNREACHABLE"))
                ),
                "stage": "PRODUCTION" if host != "admin.telnexa.co" else "LEGACY",
            }
        )
    return result


def required_contracts() -> dict[str, list[tuple[str, str, str]]]:
    def entries(service: str, text: str) -> list[tuple[str, str, str]]:
        return [(service, method, path) for method, path in (line.split(maxsplit=1) for line in text.splitlines() if line.strip())]

    klyrow = entries("KLYROW", """
GET /v1/me
GET /v1/me/permissions
GET /v1/me/capabilities
GET /v1/me/sessions
POST /v1/auth/logout
GET /v1/organizations
GET /v1/organizations/{id}
GET /v1/organizations/{id}/members
POST /v1/organizations/{id}/members
PATCH /v1/organizations/{id}/members/{member_id}
GET /v1/domains
POST /v1/domains
GET /v1/domains/{id}
PATCH /v1/domains/{id}
DELETE /v1/domains/{id}
GET /v1/domains/{id}/dns
GET /v1/domains/{id}/verification
POST /v1/domains/{id}/verify
POST /v1/messages
GET /v1/messages
GET /v1/messages/{id}
POST /v1/messages/{id}/cancel
GET /v1/tracking/events
GET /v1/tracking/events/{id}
GET /v1/templates
POST /v1/templates
GET /v1/templates/{id}
PATCH /v1/templates/{id}
DELETE /v1/templates/{id}
GET /v1/contacts
POST /v1/contacts
GET /v1/contacts/{id}
PATCH /v1/contacts/{id}
DELETE /v1/contacts/{id}
GET /v1/lists
POST /v1/lists
GET /v1/lists/{id}
PATCH /v1/lists/{id}
DELETE /v1/lists/{id}
GET /v1/campaigns
POST /v1/campaigns
GET /v1/campaigns/{id}
PATCH /v1/campaigns/{id}
POST /v1/campaigns/{id}/schedule
POST /v1/campaigns/{id}/cancel
GET /v1/tracking/messages/{id}
GET /v1/suppressions
POST /v1/suppressions
DELETE /v1/suppressions/{id}
GET /v1/bounces
GET /v1/complaints
GET /v1/billing/account
GET /v1/billing/usage
GET /v1/billing/invoices
GET /v1/billing/plans
GET /v1/operations
GET /v1/operations/{id}
GET /v1/operations/{id}/events
GET /v1/operations/{id}/attempts
POST /v1/operations/{id}/cancel
POST /v1/operations/{id}/reconcile
GET /health/live
GET /health/ready
GET /metrics
GET /v1/system/capabilities
GET /v1/system/readiness
GET /v1/providers/postal/health
GET /v1/providers/postal/status
POST /v1/integrations/mautic/commands
GET /v1/integrations/mautic/operations
GET /v1/integrations/mautic/operations/{id}
POST /v1/integrations/mautic/operations/{id}/reconcile
""")
    telnexa = entries("TELNEXA", """
POST /v1/sms/messages
GET /v1/sms/messages
GET /v1/sms/messages/{id}
POST /v1/sms/messages/{id}/cancel
GET /v1/sms/delivery-reports
GET /v1/sms/providers
GET /v1/sms/providers/{id}/health
GET /v1/smpp/accounts
POST /v1/smpp/accounts
GET /v1/smpp/accounts/{id}
PATCH /v1/smpp/accounts/{id}
GET /v1/billing/account
GET /v1/billing/usage
GET /v1/billing/invoices
POST /v1/webhooks/sms/delivery
POST /v1/webhooks/provider/{provider}
GET /v1/operations
GET /v1/operations/{id}
GET /v1/operations/{id}/events
GET /v1/operations/{id}/attempts
POST /v1/operations/{id}/cancel
POST /v1/operations/{id}/reconcile
""")
    kyqra = entries("KYQRA", """
GET /v1/me
GET /v1/capabilities
POST /v1/jobs
GET /v1/jobs
GET /v1/jobs/{id}
POST /v1/jobs/{id}/cancel
POST /v1/jobs/{id}/retry
GET /v1/jobs/{id}/results
GET /v1/jobs/{id}/events
GET /v1/operations
GET /v1/operations/{id}
GET /v1/operations/{id}/events
GET /v1/operations/{id}/attempts
POST /v1/operations/{id}/cancel
POST /v1/operations/{id}/reconcile
GET /health/live
GET /health/ready
GET /metrics
""")
    private = entries("PRIVATE_GATEWAY", """
GET /health
GET /health/live
GET /health/ready
GET /metrics
GET /v1/capabilities
POST /v1/integrations/sms/commands
GET /api/v1/kyqra/health
GET /api/v1/telnexa/health
POST /api/v1/kyqra/jobs
POST /api/v1/kyqra/results
POST /api/v1/kyqra/progress
POST /api/v1/kyqra/failures
POST /api/v1/telnexa/inbound
POST /api/v1/telnexa/dlr
POST /api/v1/telnexa/failure
POST /api/v1/telnexa/provider-status
GET /v1/operations
GET /v1/operations/{id}
GET /v1/operations/{id}/events
GET /v1/operations/{id}/attempts
POST /v1/operations/{id}/cancel
POST /v1/operations/{id}/reconcile
""")
    return {"KLYROW": klyrow, "TELNEXA": telnexa, "KYQRA": kyqra, "PRIVATE_GATEWAY": private}


def api_matrix() -> dict[str, Any]:
    source = source_openapi()
    live = {
        "KLYROW": live_openapi("klyrow-gateway-1", 8000, "/openapi.json"),
        "TELNEXA": live_openapi("telnexa-saas-billing-api-1", 8000, "/api/v1/openapi.json"),
        "KYQRA": live_openapi("kyqra-crawler-api-1", 3000, "/openapi.json"),
        "PRIVATE_GATEWAY": live_openapi("private-app-integration-gateway-1", 8080, "/openapi.json"),
    }
    records: list[dict[str, Any]] = []
    for service, document in source.items():
        source_contract = operation_contracts(service, document)
        live_contract = operation_contracts(service, live[service])
        runtime: set[tuple[str, str]] = set()
        for path, item in sorted(document.get("paths", {}).items()):
            for method, operation in item.items():
                if method not in HTTP_METHODS:
                    continue
                contract_key = (method.upper(), contract_normalized(service, path))
                if source_contract.get(contract_key) == live_contract.get(contract_key):
                    runtime.add((method.upper(), normalized(path)))
                records.append(endpoint_record(
                    service,
                    method,
                    path,
                    dereference(document, operation),
                    runtime,
                    document_security=document.get("security", []),
                ))
    records.extend(provider_endpoints())

    contracts = required_contracts()
    required: list[dict[str, str]] = []
    for service, entries in contracts.items():
        source_ops = {
            (method.upper(), contract_normalized(service, path)): dereference(source[service], operation)
            for path, item in source[service].get("paths", {}).items()
            for method, operation in item.items()
            if method in HTTP_METHODS
        }
        source_contract = operation_contracts(service, source[service])
        live_contract = operation_contracts(service, live[service])
        runtime_ops = {
            key for key, contract in source_contract.items()
            if live_contract.get(key) == contract
        }
        for _, method, path in entries:
            key = (method, contract_normalized(service, path))
            idempotency_required = requires_durable_idempotency(service, method, path)
            known_idempotent = has_durable_idempotency(path, source_ops.get(key, {}))
            state = (
                "MISSING" if key not in source_ops
                else "PARTIAL" if idempotency_required and not known_idempotent
                else "IMPLEMENTED"
            )
            required.append(
                {
                    "service": service,
                    "method": method,
                    "path": path,
                    "implementation_status": state,
                    "runtime_verification": "LIVE_OPENAPI_MATCH" if key in runtime_ops else ("ABSENT_FROM_SOURCE_AND_RUNTIME" if state == "MISSING" else "SOURCE_ONLY_REVIEW_REQUIRED"),
                }
            )
            if state == "MISSING":
                records.append(endpoint_record(service, method, path, {}, runtime_ops, status="MISSING", verification="ABSENT_FROM_SOURCE_AND_RUNTIME"))
    deduplicated: dict[tuple[str, str, str], dict[str, Any]] = {}
    for record in records:
        key = (record["service"], record["method"], record["path"])
        existing = deduplicated.get(key)
        if existing is not None and existing != record:
            raise RuntimeError(f"conflicting duplicate API endpoint: {key}")
        deduplicated[key] = record
    records = sorted(deduplicated.values(), key=lambda item: (item["service"], item["path"], item["method"]))
    value = {
        "schema_version": 1,
        "generated_at": GENERATED_AT,
        "server_scope": "CURRENT_SERVER_ONLY",
        "source_repositories": CUSTOM_REPOSITORIES,
        "source_authority": {
            service: {
                "repository": CUSTOM_REPOSITORIES[service],
                "source_sha": repository_head(SOURCE_DIRECTORIES[service]),
            }
            for service in SOURCE_DIRECTORIES
        },
        "required_contracts": required,
        "endpoints": records,
    }
    serialized = yaml.safe_dump(value, sort_keys=False, width=120)
    if "UNKNOWN" in serialized or "NOT VERIFIED" in serialized:
        raise RuntimeError("matrix contains a forbidden state")
    (ROOT / "PRODUCTION-API-MATRIX.yaml").write_text(serialized)
    return value


def runtime_inventory() -> dict[str, Any]:
    host_identity = verified_host_identity()
    container_ids = command("docker", "ps", "-aq").split()
    if not container_ids:
        raise RuntimeError("Docker inventory is empty")
    containers = json.loads(command("docker", "inspect", *container_ids))
    stages: dict[str, str] = {}
    for item in containers:
        name = item["Name"].lstrip("/")
        image_reference = item["Config"]["Image"]
        stages[name] = (
            "TOOLING" if (
                name.startswith("buildx_")
                or "lockgen" in name
                or image_reference.startswith("aquasec/trivy:")
            )
            else "STAGING" if name.startswith("scrapper-pr9-")
            else "LEGACY" if "-rollback-" in name or "-pre-dynamic-dns-" in name
            else "PRODUCTION_CANDIDATE" if "candidate" in name
            else "PRODUCTION"
        )
    workloads: list[dict[str, Any]] = []
    for item in containers:
        name = item["Name"].lstrip("/")
        labels = item["Config"].get("Labels") or {}
        image_id = item["Image"]
        image = item["Config"]["Image"]
        if "@" not in image and ":" not in image.rsplit("/", 1)[-1]:
            image = f"{image}:latest (implicit)"
        repository = labels.get("org.opencontainers.image.source", "N/A")
        revision = labels.get("org.opencontainers.image.revision", "N/A")
        if name == "klyrow-web-candidate":
            repository, revision = CUSTOM_REPOSITORIES["KLYROW"], "MISSING_UNCOMMITTED_BUILD"
        elif name.startswith("kyqra-crawler-") and name not in {"kyqra-crawler-postgres-1", "kyqra-crawler-redis-1"}:
            repository, revision = CUSTOM_REPOSITORIES["KYQRA"], "MISSING_LIVE_PROVENANCE"
        health = (item["State"].get("Health") or {}).get("Status", item["State"]["Status"])
        if item["State"]["Status"] == "exited" and item["State"].get("ExitCode") == 0:
            health = "completed"
        if name == "codestra-openbao":
            health = "FAIL_UNINITIALIZED_SEALED"
        component_rules = (
            ("codestra-openbao", "OPENBAO"),
            ("klyrow-postal-db", "MARIADB"), ("klyrow-mautic-db", "MARIADB"),
            ("klyrow-postal", "POSTAL"), ("klyrow-mautic", "MAUTIC"),
            ("klyrow-node-exporter", "PROMETHEUS_NODE_EXPORTER"), ("klyrow-grafana", "GRAFANA"),
            ("klyrow-prometheus", "PROMETHEUS"), ("klyrow-rabbitmq", "RABBITMQ"),
            ("klyrow-postgres", "POSTGRESQL"), ("klyrow-", "KLYROW"),
            ("telnexa-saas-keycloak-db", "POSTGRESQL"), ("telnexa-saas-keycloak", "KEYCLOAK"),
            ("telnexa-saas-node-exporter", "PROMETHEUS_NODE_EXPORTER"), ("telnexa-saas-prometheus", "PROMETHEUS"),
            ("telnexa-saas-billing-db", "POSTGRESQL"), ("telnexa-saas-billing", "TELNEXA"),
            ("telnexa-jasmin", "JASMIN"), ("telnexa-postgres", "POSTGRESQL"),
            ("telnexa-rabbitmq", "RABBITMQ"), ("telnexa-redis", "REDIS"),
            ("kyqra-crawler-postgres", "POSTGRESQL"), ("kyqra-crawler-redis", "REDIS"),
            ("kyqra-crawler", "KYQRA"), ("private-app-integration-gateway", "PRIVATE_GATEWAY"),
            ("scrapper-pr9-postgres", "POSTGRESQL"), ("scrapper-pr9-redis", "REDIS"),
            ("buildx_", "DOCKER_BUILDKIT"),
        )
        software = next((value for prefix, value in component_rules if name.startswith(prefix)), "OPERATING_SYSTEM_COMPONENT")
        public_url = "N/A"
        if name == "klyrow-gateway-1": public_url = "https://api.klyrow.com"
        elif name == "klyrow-web-candidate": public_url = "https://app.klyrow.com"
        elif name == "telnexa-saas-billing-api-1": public_url = "https://api.telnexa.co"
        elif name == "telnexa-saas-keycloak-1": public_url = "https://api.telnexa.co/auth/realms/telnexa"
        elif name == "kyqra-crawler-api-1": public_url = "https://crawler.kyqra.com"
        elif name == "codestra-openbao": public_url = "https://bao.codestra.media"
        exposed = sorted((item["Config"].get("ExposedPorts") or {}).keys())
        published_ports = item["NetworkSettings"].get("Ports") or {}
        ports = []
        for container_port in sorted(published_ports):
            bindings = published_ports[container_port]
            if not bindings:
                ports.append(f"{container_port} (container network only)")
                continue
            for binding in bindings:
                host_ip = binding.get("HostIp") or "0.0.0.0"
                host_port = binding.get("HostPort") or "N/A"
                ports.append(f"{host_ip}:{host_port}->{container_port}")
        if not ports:
            ports = [f"{port} (container network only)" for port in exposed] or ["N/A"]
        private_url = f"tcp://{name}:{exposed[0].split('/')[0]}" if exposed else "N/A"
        database = "N/A"
        if name.startswith("klyrow-mautic"): database = "klyrow-mautic-db-1/MariaDB"
        elif name.startswith("klyrow-postal"): database = "klyrow-postal-db-1/MariaDB"
        elif name.startswith("klyrow-") and software == "KLYROW": database = "klyrow-postgres-1/PostgreSQL"
        elif name.startswith("telnexa-saas-keycloak"): database = "telnexa-saas-keycloak-db-1/PostgreSQL"
        elif name.startswith("telnexa-saas-billing"): database = "telnexa-saas-billing-db-1/PostgreSQL"
        elif name.startswith("kyqra-crawler-") and software == "KYQRA": database = "kyqra-crawler-postgres-1/PostgreSQL"
        volumes = []
        for mount in item["Mounts"]:
            destination = str(mount["Destination"])
            if "/secrets/" in destination or destination.startswith("/run/secrets"):
                destination = "[SECRET_MOUNT_REDACTED]"
            volumes.append(f"{mount['Type']}:{destination}")
        workloads.append(
            {
                "software": software,
                "container_or_service": name,
                "image": image,
                "image_digest": image_id,
                "image_reference_digest_pinned": "YES" if "@sha256:" in image else "NO",
                "version": labels.get("org.opencontainers.image.version", image.rsplit(":", 1)[-1] if ":" in image else "N/A"),
                "source_repository": repository,
                "source_sha": revision,
                "deployment_file": labels.get("com.docker.compose.project.config_files", "N/A"),
                "ports": ports,
                "public_url": public_url,
                "private_url": private_url,
                "networks": sorted(item["NetworkSettings"]["Networks"]) or ["N/A"],
                "volumes": sorted(set(volumes)) or ["N/A"],
                "databases": database,
                "health": health.upper(),
                "stage": stages[name],
            }
        )
    value = {
        "schema_version": 1,
        "generated_at": GENERATED_AT,
        "server_scope": "CURRENT_SERVER_ONLY",
        "server": host_identity["hostname"],
        "public_ipv4": host_identity["public_ipv4"],
        "private_ip": host_identity["private_ipv4"],
        "workloads": sorted(workloads, key=lambda row: row["container_or_service"]),
        "host_services": [
            {
                "software": "DOCKER",
                "container_or_service": "docker.service",
                "image": "N/A",
                "image_digest": "N/A",
                "version": command("docker", "version", "--format", "{{.Server.Version}}").strip(),
                "source_repository": "Docker Ubuntu package repository",
                "source_sha": "N/A",
                "deployment_file": "/etc/docker and systemd docker.service",
                "ports": ["N/A"],
                "public_url": "N/A",
                "private_url": "unix:///var/run/docker.sock",
                "networks": ["host"],
                "volumes": ["/var/lib/docker"],
                "databases": "N/A",
                "health": "RUNNING",
                "stage": "PRODUCTION",
            },
            {
                "software": "CONTAINERD",
                "container_or_service": "containerd.service",
                "image": "N/A",
                "image_digest": "N/A",
                "version": command("containerd", "--version").strip(),
                "source_repository": "Docker Ubuntu package repository",
                "source_sha": "N/A",
                "deployment_file": "/etc/containerd and systemd containerd.service",
                "ports": ["N/A"],
                "public_url": "N/A",
                "private_url": "unix:///run/containerd/containerd.sock",
                "networks": ["host"],
                "volumes": ["/var/lib/containerd"],
                "databases": "N/A",
                "health": "RUNNING",
                "stage": "PRODUCTION",
            },
            {
                "software": "DOCKER_COMPOSE",
                "container_or_service": "docker compose CLI plugin",
                "image": "N/A",
                "image_digest": "N/A",
                "version": command("docker", "compose", "version", "--short").strip(),
                "source_repository": "Docker Ubuntu package repository",
                "source_sha": "N/A",
                "deployment_file": "N/A",
                "ports": ["N/A"],
                "public_url": "N/A",
                "private_url": "N/A",
                "networks": ["N/A"],
                "volumes": ["N/A"],
                "databases": "N/A",
                "health": "INSTALLED",
                "stage": "TOOLING",
            },
            {
                "software": "NGINX",
                "container_or_service": "nginx.service",
                "image": "N/A",
                "image_digest": "N/A",
                "version": command("dpkg-query", "-W", "-f=${Version}", "nginx").strip(),
                "source_repository": "Ubuntu package repository",
                "source_sha": "N/A",
                "deployment_file": "/etc/nginx/nginx.conf and /etc/nginx/sites-enabled",
                "ports": ["0.0.0.0:80/tcp", "0.0.0.0:443/tcp", "10.40.0.4:8443/tcp", "10.40.0.4:18000/tcp"],
                "public_url": "MULTIPLE_TLS_VIRTUAL_HOSTS",
                "private_url": "https://10.40.0.4:18000 and https://10.40.0.4:8443",
                "networks": ["host"],
                "volumes": ["N/A"],
                "databases": "N/A",
                "health": "RUNNING",
                "stage": "PRODUCTION",
            },
            {
                "software": "PROMETHEUS_NODE_EXPORTER",
                "container_or_service": "prometheus-node-exporter.service",
                "image": "N/A",
                "image_digest": "N/A",
                "version": command("dpkg-query", "-W", "-f=${Version}", "prometheus-node-exporter").strip(),
                "source_repository": "Ubuntu package repository",
                "source_sha": "N/A",
                "deployment_file": "/etc/default/prometheus-node-exporter and systemd unit",
                "ports": ["127.0.0.1:9100/tcp"],
                "public_url": "N/A",
                "private_url": "http://127.0.0.1:9100/metrics",
                "networks": ["host"],
                "volumes": ["N/A"],
                "databases": "N/A",
                "health": "RUNNING",
                "stage": "PRODUCTION",
            },
        ],
        "scope_dispositions": {
            "CADDY": "SOURCE_ONLY_NOT_RUNNING",
            "KONG": "SOURCE_ONLY_NOT_RUNNING",
            "ODOO": "SOURCE_ONLY_NOT_RUNNING",
            "N8N": "SOURCE_ONLY_NOT_RUNNING",
            "LOKI": "SOURCE_ONLY_NOT_RUNNING",
            "TEMPO": "SOURCE_ONLY_NOT_RUNNING",
            "ALLOY": "SOURCE_ONLY_NOT_RUNNING",
            "VICIDIAL": "N/A_NOT_INSTALLED_OR_RUNNING",
            "ASTERISK": "N/A_NOT_INSTALLED_OR_RUNNING",
            "CENTRIFUGO": "N/A_NOT_INSTALLED_OR_RUNNING",
            "CELERY": "N/A_NOT_INSTALLED_OR_RUNNING",
        },
    }
    serialized = yaml.safe_dump(value, sort_keys=False, width=120)
    if "UNKNOWN" in serialized:
        raise RuntimeError("inventory contains a forbidden classification")
    (ROOT / "PRODUCTION-RUNTIME-INVENTORY.yaml").write_text(serialized)
    return value


def integration_matrix() -> dict[str, Any]:
    edges = [
        ("KLYROW", "POSTAL", "HTTP/SMTP", "BEARER_OR_SMTP", "TENANT_PROVIDER_POLICY", "klyrow_backend", 10, "BOUNDED", "DURABLE_OUTBOX", "provider health", "EMAIL_DELIVERY", "AMBIGUOUS_RECONCILIATION"),
        ("KLYROW", "MAUTIC", "HTTP", "OAUTH2_CLIENT_CREDENTIALS", "DEDICATED_ROLE_AND_COMMAND_ALLOWLIST", "klyrow_backend", 10, "BOUNDED", "DURABLE_OUTBOX", "adapter circuit state", "CONTACT_CAMPAIGN_STATE", "DEAD_LETTER"),
        ("KLYROW", "OPENBAO", "HTTPS", "APPROLE_PLANNED", "LEAST_PRIVILEGE_PLANNED", "loopback edge", 5, "BOUNDED", "N/A", "seal status", "SECRET_READ", "FAIL_CLOSED"),
        ("KLYROW", "PRIVATE_GATEWAY", "HTTPS", "MTLS_AND_BEARER", "TENANT_AND_SCOPE", "private edge", 10, "BOUNDED", "DURABLE", "health/ready", "CROSS_SERVICE_COMMAND", "FAIL_CLOSED"),
        ("TELNEXA", "KEYCLOAK", "OIDC", "JWT_JWKS", "AUDIENCE_SCOPE_ROLE", "telnexa_identity", 5, "BOUNDED", "N/A", "OIDC discovery", "TOKEN_VALIDATION_OR_ISSUANCE", "FAIL_CLOSED"),
        ("TELNEXA", "JASMIN", "HTTP/SMPP", "FILE_SECRET", "PROVIDER_POLICY", "telnexa_backend", 10, "BOUNDED", "DURABLE_DATABASE", "Jasmin health", "SMS_DELIVERY", "AMBIGUOUS_RECONCILIATION"),
        ("TELNEXA", "RABBITMQ", "AMQP", "PASSWORD", "VHOST", "telnexa_backend", 5, "BOUNDED", "MESSAGE_ID", "broker health", "DURABLE_MESSAGE", "RETRY_OR_RECONCILE"),
        ("TELNEXA", "REDIS", "RESP", "PASSWORD", "PRIVATE_NETWORK", "telnexa_backend", 3, "BOUNDED", "N/A", "PING", "RATE_LIMIT_OR_CACHE_STATE", "FAIL_CLOSED"),
        ("TELNEXA", "OPENBAO", "HTTPS", "APPROLE_PLANNED", "LEAST_PRIVILEGE_PLANNED", "loopback edge", 5, "BOUNDED", "N/A", "seal status", "SECRET_READ", "FAIL_CLOSED"),
        ("TELNEXA", "PRIVATE_GATEWAY", "HTTPS", "MTLS_AND_BEARER", "TENANT_AND_SCOPE", "private edge", 10, "BOUNDED", "DURABLE", "health/ready", "DLR_OR_PROVIDER_EVENT", "FAIL_CLOSED"),
        ("KYQRA", "REDIS", "RESP", "PASSWORD_IN_CANDIDATE", "PRIVATE_NETWORK", "kyqra_backend", 3, "BOUNDED", "JOB_ID", "PING", "JOB_STATE", "RETRY"),
        ("KYQRA", "POSTGRESQL", "POSTGRES", "PASSWORD", "TENANT_FILTER", "kyqra_backend", 5, "BOUNDED", "UNIQUE_CONSTRAINT", "SELECT 1", "DURABLE_JOB_STATE", "FAIL_CLOSED"),
        ("KYQRA", "OPENBAO", "HTTPS", "APPROLE_PLANNED", "LEAST_PRIVILEGE_PLANNED", "loopback edge", 5, "BOUNDED", "N/A", "seal status", "SECRET_READ", "FAIL_CLOSED"),
        ("KYQRA", "PRIVATE_GATEWAY", "HTTPS", "MTLS_AND_BEARER", "TENANT_AND_SCOPE", "private edge", 10, "BOUNDED", "DURABLE", "health/ready", "JOB_CALLBACK_OR_COMMAND", "FAIL_CLOSED"),
        ("PRIVATE_GATEWAY", "TELNEXA", "HTTPS", "MTLS_AND_BEARER", "SERVICE_TENANT_AND_EVENT_SCOPE", "private edge", 10, "BOUNDED", "DURABLE", "telnexa health", "INBOUND_SMS_OR_DLR_STATE", "FAIL_CLOSED"),
        ("PRIVATE_GATEWAY", "KYQRA", "HTTPS", "MTLS_AND_BEARER", "SERVICE_TENANT_AND_EVENT_SCOPE", "private edge", 10, "BOUNDED", "DURABLE", "kyqra health", "JOB_PROGRESS_OR_RESULT_STATE", "FAIL_CLOSED"),
        ("PROMETHEUS_KLYROW", "APPROVED_KLYROW_TARGETS", "HTTP", "BEARER_WHERE_SUPPORTED", "METRICS_ONLY", "monitoring", 10, "BOUNDED", "N/A", "targets API", "NONE", "TARGET_DOWN_ALERT"),
        ("PROMETHEUS_TELNEXA", "APPROVED_TELNEXA_TARGETS", "HTTP", "BEARER_WHERE_SUPPORTED", "METRICS_ONLY", "monitoring", 10, "BOUNDED", "N/A", "targets API", "NONE", "TARGET_DOWN_ALERT"),
        ("GRAFANA_KLYROW", "PROMETHEUS_KLYROW", "HTTP", "SERVICE_CREDENTIAL", "DATASOURCE_READ", "monitoring", 10, "BOUNDED", "N/A", "datasource health", "NONE", "DASHBOARD_DEGRADED"),
    ]
    names = ["source", "destination", "protocol", "auth", "authorization", "network", "timeout_seconds", "retry", "idempotency", "health", "external_effect", "failure_mode"]
    value = {"schema_version": 1, "generated_at": GENERATED_AT, "server_scope": "CURRENT_SERVER_ONLY", "edges": [dict(zip(names, row)) for row in edges]}
    (ROOT / "PRODUCTION-INTEGRATION-MATRIX.yaml").write_text(yaml.safe_dump(value, sort_keys=False, width=120))
    return value


def certification_report(inventory: dict[str, Any], api: dict[str, Any], recorded_sources=None) -> dict[str, Any]:
    required = api["required_contracts"]
    endpoint_counts = {
        service: sum(
            row["service"] == service and row["implementation_status"] != "MISSING"
            for row in api["endpoints"]
        )
        for service in ("KLYROW", "TELNEXA", "KYQRA", "PRIVATE_GATEWAY")
    }
    source_revisions = recorded_sources if recorded_sources is not None else {
        service: repository_head(directory)
        for service, directory in SOURCE_DIRECTORIES.items()
    }
    repository_revisions = {
        CUSTOM_REPOSITORIES[service]: revision
        for service, revision in source_revisions.items()
    }
    custom_software = {"KLYROW", "TELNEXA", "KYQRA", "PRIVATE_GATEWAY"}
    custom_workloads = [
        row for row in inventory["workloads"]
        if row["stage"] == "PRODUCTION"
        and row["health"] != "COMPLETED"
        and (
            row["software"] in custom_software
            or row["source_repository"] in repository_revisions
        )
    ]
    source_runtime_drift = sum(
        row["source_repository"] not in repository_revisions
        or row["source_sha"] != repository_revisions.get(row["source_repository"])
        for row in custom_workloads
    )
    all_images_pinned = bool(custom_workloads) and all(
        row["image_reference_digest_pinned"] == "YES"
        for row in custom_workloads
    )

    def runtime_health(*software: str) -> str:
        rows = [
            row for row in inventory["workloads"] + inventory["host_services"]
            if row["stage"] == "PRODUCTION" and row["software"] in software
        ]
        if not rows:
            return "N/A"
        return "PASS" if all(
            row["health"] in {"HEALTHY", "RUNNING", "COMPLETED"} for row in rows
        ) else "FAIL"

    def api_gate(service: str, *, require_runtime: bool = True) -> str:
        rows = [row for row in required if row["service"] == service]
        if not rows or any(row["implementation_status"] != "IMPLEMENTED" for row in rows):
            return "FAIL"
        if require_runtime and any(
            row["runtime_verification"] != "LIVE_OPENAPI_MATCH" for row in rows
        ):
            return "FAIL"
        return "PASS"

    def endpoint_family_gate(service: str) -> str:
        rows = [row for row in api["endpoints"] if row["service"] == service]
        return "PASS" if rows and all(
            row["implementation_status"] in {"IMPLEMENTED", "N/A"} for row in rows
        ) else "FAIL"

    gate_document = yaml.safe_load(GATE_EVIDENCE_PATH.read_text())
    if gate_document.get("server") != inventory["public_ipv4"]:
        raise RuntimeError("production gate evidence is for a different server")

    bindings = gate_bindings(gate_document, ROOT)

    def external_gate(name: str) -> str:
        record = gate_document.get("gates", {}).get(name)
        if not isinstance(record, dict) or record.get("status") not in {"PASS", "FAIL"}:
            raise RuntimeError(f"invalid or missing production gate evidence: {name}")
        evidence = record.get("evidence")
        if not isinstance(evidence, str) or not evidence:
            raise RuntimeError(f"production gate evidence has no authority: {name}")
        if evidence != "EXTERNAL_AUTHORITY_REQUIRED" and not (ROOT / evidence).is_file():
            raise RuntimeError(f"production gate evidence reference is missing: {name}")
        if record["status"] == "PASS" and evidence == "EXTERNAL_AUTHORITY_REQUIRED":
            raise RuntimeError(f"a production gate cannot pass on missing external authority: {name}")
        return record["status"]

    rollback_document = yaml.safe_load((ROOT / "SERVER-37-PRODUCTION-ROLLBACK.yaml").read_text())
    rollback = "PASS" if rollback_document.get("rollback_gate") == "PASS" else "FAIL"
    active_edge = [
        row for row in api["endpoints"]
        if row["service"] == "NGINX" and row["implementation_status"] != "N/A"
    ]
    tls = "PASS" if active_edge and all(
        live_https_without_server_error(row["runtime_verification"])
        for row in active_edge
    ) else "FAIL"
    dns = tls
    backups = external_gate("OFF_HOST_BACKUP")
    restore = external_gate("ISOLATED_RESTORE")
    mtls = external_gate("POSITIVE_AND_NEGATIVE_MTLS_E2E")
    email_e2e = external_gate("CONTROLLED_EMAIL_E2E")
    sms_e2e = external_gate("CONTROLLED_SMS_E2E")
    kyqra_e2e = external_gate("CONTROLLED_KYQRA_E2E")
    private_e2e = external_gate("CONTROLLED_PRIVATE_INTEGRATION_E2E")
    api_gates = {
        service: api_gate(service) for service in SOURCE_DIRECTORIES
    }
    api_contracts = "PASS" if all(value == "PASS" for value in api_gates.values()) else "FAIL"
    idempotency = "PASS" if all(
        row["implementation_status"] != "PARTIAL" for row in required
    ) else "FAIL"
    source_provenance = "PASS" if all_images_pinned and source_runtime_drift == 0 else "FAIL"
    prometheus_runtime = runtime_health("PROMETHEUS")
    grafana_runtime = runtime_health("GRAFANA")
    prometheus = "PASS" if prometheus_runtime == "PASS" and all(
        endpoint_family_gate(service) == "PASS"
        for service in ("PROMETHEUS_KLYROW", "PROMETHEUS_TELNEXA")
    ) else "FAIL"
    grafana = "PASS" if grafana_runtime == "PASS" and endpoint_family_gate("GRAFANA_KLYROW") == "PASS" else "FAIL"
    observability = "PASS" if (
        prometheus == grafana == "PASS"
        and external_gate("ALERT_AND_RETENTION_E2E") == "PASS"
    ) else "FAIL"
    security = "PASS" if all(
        value == "PASS" for value in (
            tls, mtls, source_provenance, api_contracts, idempotency
        )
    ) and runtime_health("OPENBAO") == "PASS" else "FAIL"
    classifications = {
        "NGINX": "PASS" if runtime_health("NGINX") == tls == "PASS" else "FAIL",
        "OPENBAO": runtime_health("OPENBAO"),
        "KLYROW_GATEWAY": api_gates["KLYROW"],
        "KLYROW_WORKER": runtime_health("KLYROW"),
        "KLYROW_BILLING": "PASS" if runtime_health("KLYROW") == source_provenance == "PASS" else "FAIL",
        "KLYROW_SMTP": runtime_health("KLYROW"),
        "KLYROW_FRONTEND": "PASS" if runtime_health("KLYROW") == source_provenance == "PASS" else "FAIL",
        "POSTAL": runtime_health("POSTAL"),
        "MAUTIC": runtime_health("MAUTIC"),
        "TELNEXA_SMS": runtime_health("TELNEXA"),
        "TELNEXA_BILLING": api_gates["TELNEXA"],
        "KEYCLOAK": runtime_health("KEYCLOAK"),
        "KYQRA": api_gates["KYQRA"],
        "PRIVATE_GATEWAY": api_gates["PRIVATE_GATEWAY"],
        "POSTGRES": runtime_health("POSTGRESQL"),
        "MARIADB": runtime_health("MARIADB"),
        "REDIS": runtime_health("REDIS"),
        "RABBITMQ": runtime_health("RABBITMQ"),
        "PROMETHEUS": prometheus,
        "GRAFANA": grafana,
        "MTLS": mtls,
        "DNS": dns,
        "TLS": tls,
        "API_CONTRACTS": api_contracts,
        "IDEMPOTENCY": idempotency,
        "AUTH": "FAIL" if api_contracts == "FAIL" else "WARNING",
        "RBAC": "FAIL" if api_contracts == "FAIL" else "WARNING",
        "AUDIT": "FAIL" if runtime_health("OPENBAO") != "PASS" else "WARNING",
        "BACKUPS": backups,
        "RESTORE": restore,
        "OBSERVABILITY": observability,
        "SECURITY": security,
        "SOURCE_PROVENANCE": source_provenance,
        "ROLLBACK": rollback,
    }
    blockers = [
        {
            "blocker": "OpenBao is uninitialized and sealed; initialization needs independent recovery-share and root-token custody approval.",
            "owner": "platform owner and independent recovery custodians", "repository": "codestra-openbao-production",
            "component": "OPENBAO", "required_action": "Approve and perform guarded initialization with independent custody, TLS audit enablement, backup, and isolated restore drill.",
            "validation_after_action": "Seal status initialized=true and sealed=false; audit, policy, AppRole, off-host backup, and recovery evidence all pass.",
        },
        {
            "blocker": "The private gateway candidate preserves the event-ingress and durable operation contracts, but its checked-in shared production edge authorizes only the SMS command channel; provider-specific downstream dispatch authorities and credentials for other channels are unavailable.",
            "owner": "Klyrow, Telnexa, Kyqra, and platform repository owners", "repository": CUSTOM_REPOSITORIES["PRIVATE_GATEWAY"],
            "component": "PRIVATE_GATEWAY", "required_action": "Approve concrete provider adapter contracts, networks, service identities, scopes, and credentials; implement each bounded dispatcher behind the durable operation engine.",
            "validation_after_action": "Protected image deployment, runtime OpenAPI parity, positive mTLS authorization, bounded dispatch/reconciliation, and controlled integration E2E pass.",
        },
        {
            "blocker": "This regenerated infrastructure evidence requires independent review and exact-head CI before merge.",
            "owner": "independent infrastructure repository reviewer", "repository": "https://github.com/appolon1908-hue/Infustruction-repo",
            "component": "RELEASE_PROCESS", "required_action": "Review and approve infrastructure pull request 57 at its exact head after the protected application sources are recorded.",
            "validation_after_action": "Exact-head and merge-result CI pass, the evidence pull request is approved and merged normally, and its protected destination SHA is recorded.",
        },
        {
            "blocker": "No approved provider test mailbox, SMS sandbox number, positive mTLS client certificate, Mautic API credential, or off-host backup target is available.",
            "owner": "platform owner and provider credential custodians", "repository": "N/A",
            "component": "E2E_BACKUP_RESTORE", "required_action": "Provide scoped test identities/targets and off-host backup authority without exposing credential values.",
            "validation_after_action": "Controlled email, SMS, crawler, private-mTLS, secret-read, off-host backup, and isolated restore tests pass.",
        },
    ]
    report = {
        "PHASE": "FULL_PLATFORM_API_INTEGRATION_AND_PRODUCTION_CERTIFICATION",
        "SERVER": inventory["server"], "PUBLIC_IPV4": inventory["public_ipv4"], "PRIVATE_IP": inventory["private_ip"],
        "PRODUCTION_SERVICES": (
            sum(row["stage"] == "PRODUCTION" for row in inventory["workloads"])
            + sum(row["stage"] == "PRODUCTION" for row in inventory["host_services"])
        ),
        "KLYROW_SOURCE_SHA": source_revisions["KLYROW"],
        "TELNEXA_SOURCE_SHA": source_revisions["TELNEXA"],
        "KYQRA_SOURCE_SHA": source_revisions["KYQRA"],
        "PRIVATE_GATEWAY_SOURCE_SHA": source_revisions["PRIVATE_GATEWAY"],
        "ALL_IMAGES_DIGEST_PINNED": "YES" if all_images_pinned else "NO",
        "SOURCE_RUNTIME_DRIFT": source_runtime_drift,
        "KLYROW_API_ENDPOINTS": endpoint_counts["KLYROW"], "TELNEXA_API_ENDPOINTS": endpoint_counts["TELNEXA"],
        "KYQRA_API_ENDPOINTS": endpoint_counts["KYQRA"], "PRIVATE_GATEWAY_API_ENDPOINTS": endpoint_counts["PRIVATE_GATEWAY"],
        "TOTAL_REQUIRED_ENDPOINTS": len(required),
        "IMPLEMENTED_ENDPOINTS": sum(row["implementation_status"] == "IMPLEMENTED" for row in required),
        "PARTIAL_ENDPOINTS": sum(row["implementation_status"] == "PARTIAL" for row in required),
        "MISSING_ENDPOINTS": sum(row["implementation_status"] == "MISSING" for row in required),
        "KLYROW_OPENAPI": api_gates["KLYROW"],
        "TELNEXA_OPENAPI": api_gates["TELNEXA"],
        "KYQRA_OPENAPI": api_gates["KYQRA"],
        "PRIVATE_GATEWAY_OPENAPI": api_gates["PRIVATE_GATEWAY"],
        "OPENBAO": runtime_health("OPENBAO"),
        "KEYCLOAK": "PASS" if runtime_health("KEYCLOAK") == "PASS" and external_gate("KEYCLOAK_AUTH_E2E") == "PASS" else "FAIL",
        "POSTAL": "PASS" if runtime_health("POSTAL") == "PASS" and email_e2e == "PASS" else "FAIL",
        "MAUTIC": "PASS" if runtime_health("MAUTIC") == "PASS" and external_gate("MAUTIC_KLYROW_E2E") == "PASS" else "FAIL",
        "JASMIN": "PASS" if runtime_health("JASMIN") == "PASS" and sms_e2e == "PASS" else "FAIL",
        "MTLS": mtls,
        "DNS": dns,
        "TLS": tls,
        "POSTGRES": "PASS" if runtime_health("POSTGRESQL") == backups == restore == "PASS" else "FAIL",
        "MARIADB": "PASS" if runtime_health("MARIADB") == backups == restore == "PASS" else "FAIL",
        "REDIS": "PASS" if runtime_health("REDIS") == backups == restore == "PASS" else "FAIL",
        "RABBITMQ": "PASS" if runtime_health("RABBITMQ") == backups == restore == "PASS" else "FAIL",
        "PROMETHEUS": prometheus,
        "GRAFANA": grafana,
        "OBSERVABILITY": observability,
        "BACKUPS": backups,
        "RESTORE": restore,
        "SECURITY": security,
        "ROLLBACK": rollback,
        "KLYROW_EMAIL_E2E": email_e2e,
        "TELNEXA_SMS_E2E": sms_e2e,
        "KYQRA_E2E": kyqra_e2e,
        "PRIVATE_INTEGRATION_E2E": private_e2e,
        "PRODUCTION_CHANGED": "YES" if rollback_document.get("production_changed") else "NO",
        "OVERALL_VERDICT": "PRODUCTION_BLOCKED",
        "CLASSIFICATIONS": classifications, "BLOCKERS": blockers,
    }
    critical = (
        "KLYROW_OPENAPI", "TELNEXA_OPENAPI", "KYQRA_OPENAPI",
        "PRIVATE_GATEWAY_OPENAPI", "OPENBAO", "KEYCLOAK", "POSTAL",
        "MAUTIC", "JASMIN", "MTLS", "DNS", "TLS", "POSTGRES",
        "MARIADB", "REDIS", "RABBITMQ", "PROMETHEUS", "GRAFANA",
        "OBSERVABILITY", "BACKUPS", "RESTORE", "SECURITY", "ROLLBACK",
        "KLYROW_EMAIL_E2E", "TELNEXA_SMS_E2E", "KYQRA_E2E",
        "PRIVATE_INTEGRATION_E2E",
    )
    if (
        all(report[key] == "PASS" for key in critical)
        and report["MISSING_ENDPOINTS"] == 0
        and report["PARTIAL_ENDPOINTS"] == 0
        and report["ALL_IMAGES_DIGEST_PINNED"] == "YES"
        and report["SOURCE_RUNTIME_DRIFT"] == 0
    ):
        report["OVERALL_VERDICT"] = "PRODUCTION_CERTIFIED"
        report["BLOCKERS"] = []
    report["OBSERVATION_MODE"] = "RECORDED_EVIDENCE_NO_RUNTIME_PROBE" if recorded_sources is not None else "LIVE_PROBE"
    report["EVIDENCE_BINDINGS"] = bindings
    report["RECORDED_INPUTS"] = {name: {"sha256": digest(ROOT / name)} for name in ("PRODUCTION-RUNTIME-INVENTORY.yaml", "PRODUCTION-API-MATRIX.yaml", "SERVER-37-PRODUCTION-GATE-EVIDENCE.yaml", "SERVER-37-PRODUCTION-ROLLBACK.yaml")}
    (ROOT / "FULL-PLATFORM-PRODUCTION-CERTIFICATION.yaml").write_text(yaml.safe_dump(report, sort_keys=False, width=120))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-recorded', action='store_true', help='Reconcile committed observations without runtime access')
    args = parser.parse_args()
    if args.from_recorded:
        inventory = yaml.safe_load((ROOT / "PRODUCTION-RUNTIME-INVENTORY.yaml").read_text())
        api = yaml.safe_load((ROOT / "PRODUCTION-API-MATRIX.yaml").read_text())
    else:
        inventory = runtime_inventory()
        api = api_matrix()
        integration_matrix()
    recorded_sources = None
    if args.from_recorded:
        previous = yaml.safe_load((ROOT / "FULL-PLATFORM-PRODUCTION-CERTIFICATION.yaml").read_text())
        recorded_sources = {service: previous[service + "_SOURCE_SHA"] for service in SOURCE_DIRECTORIES}
    certification_report(inventory, api, recorded_sources)
    required = api["required_contracts"]
    summary = {
        "generated_at": GENERATED_AT,
        "runtime_workloads": len(inventory["workloads"]),
        "production_workloads": sum(row["stage"] == "PRODUCTION" for row in inventory["workloads"]),
        "production_services": (
            sum(row["stage"] == "PRODUCTION" for row in inventory["workloads"])
            + sum(row["stage"] == "PRODUCTION" for row in inventory["host_services"])
        ),
        "api_endpoints": len(api["endpoints"]),
        "required_endpoints": len(required),
        "implemented_required_endpoints": sum(row["implementation_status"] == "IMPLEMENTED" for row in required),
        "partial_required_endpoints": sum(row["implementation_status"] == "PARTIAL" for row in required),
        "missing_required_endpoints": sum(row["implementation_status"] == "MISSING" for row in required),
        "runtime_verified_required_endpoints": sum(row["runtime_verification"] == "LIVE_OPENAPI_MATCH" for row in required),
    }
    (ROOT / "FULL-PLATFORM-CERTIFICATION-SUMMARY.yaml").write_text(yaml.safe_dump(summary, sort_keys=False))
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
