#!/usr/bin/env python3
"""Validate stable repository identities, controlled renames, and exporter privacy."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config" / "repository-name-aliases.v1.json"
RUNBOOK = ROOT / "REPOSITORY_NAME_MIGRATION.md"
VALIDATOR = Path(__file__).resolve()

EXPECTED = {
    1221155447: (
        "appolon1908-hue/Frontend-Resturant-",
        "appolon1908-hue/restaurant-frontend",
        True,
    ),
    1343761049: (
        "appolon1908-hue/transportaion-Frontend",
        "appolon1908-hue/freight-platform-frontend",
        True,
    ),
    1343962199: (
        "appolon1908-hue/LARIM-A-Fornt-end",
        "appolon1908-hue/LARIM-A-Frontend",
        True,
    ),
    1351353723: (
        "appolon1908-hue/Codesrea-Social-",
        "appolon1908-hue/Codestra-Social-Control-Plane",
        False,
    ),
    1350724356: (
        "appolon1908-hue/documentaions",
        "appolon1908-hue/Codestra-Documentation",
        False,
    ),
    1350724865: (
        "appolon1908-hue/Infustruction-repo",
        "appolon1908-hue/Codestra-Infrastructure",
        True,
    ),
}

MAPPING_STATUSES = {
    "PREPARED_NOT_RENAMED",
    "RENAMED_VERIFIED",
    "ROLLED_BACK_VERIFIED",
}
ACCOUNT_STATUSES = {
    "PREPARED_NOT_RENAMED",
    "PARTIALLY_RENAMED_VERIFIED",
    "RENAMED_VERIFIED",
    "ROLLED_BACK_VERIFIED",
}
REPOSITORY_FIELDS = {
    "current_repository",
    "principal_repository",
    "repo",
    "repository",
    "repository_full_name",
}

TEXT_SUFFIXES = {
    ".bash",
    ".caddy",
    ".cfg",
    ".conf",
    ".env",
    ".hcl",
    ".ini",
    ".js",
    ".json",
    ".mjs",
    ".cjs",
    ".properties",
    ".ps1",
    ".py",
    ".sh",
    ".tf",
    ".tfvars",
    ".toml",
    ".ts",
    ".xml",
    ".yaml",
    ".yml",
    ".zsh",
}
OPERATIONAL_ROOTS = {
    "ansible",
    "compose",
    "config",
    "deploy",
    "deployment",
    "helm",
    "hosts",
    "infra",
    "infrastructure",
    "k8s",
    "kubernetes",
    "manifests",
    "operations",
    "opentofu",
    "release",
    "releases",
    "scripts",
    "terraform",
}
EXCLUDED_ROOTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "backups",
    "build",
    "coverage",
    "dist",
    "docs",
    "evidence",
    "node_modules",
    "reports",
    "tests",
    "vendor",
}
ROOT_OPERATIONAL_NAMES = {
    ".gitmodules",
    "Caddyfile",
    "Dockerfile",
    "Makefile",
    "STAGE6-SOURCE-LOCK.yaml",
}
STAGE9_BASE_EXPECTED_REPOS = {
    "Codestra-Marketing-",
    "Codestra-AI",
    "Codestra-Communication-CC",
    "Middleware-",
    "Odoo",
    "SDK-repository",
    "N8N",
    "Kong",
    "Keycloak",
    "social.codestra.co",
}
HISTORICAL_STAGE6_LOCK = (
    ROOT / "releases" / "STAGE6-STAGING-EXACT-SOURCE-LOCK-2026-08-30.json"
)
HISTORICAL_STAGE6_LOCK_SHA256 = (
    "46f0b40e8c07828d3299306d707ff5b9f859ea1a56536b262de82ef36f0741af"
)

STRUCTURED_TEXT_SUFFIXES = {
    ".cfg",
    ".conf",
    ".env",
    ".hcl",
    ".ini",
    ".properties",
    ".tf",
    ".tfvars",
    ".toml",
    ".yaml",
    ".yml",
}
KUBERNETES_PUBLIC_ROUTE_KINDS = {
    "gateway",
    "httproute",
    "grpcroute",
    "tcproute",
    "tlsroute",
    "ingress",
}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load() -> dict[str, Any]:
    try:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid manifest: {exc}")
    if not isinstance(data, dict):
        fail("manifest root must be an object")
    return data


def mapping_index(data: dict[str, Any]) -> dict[int, dict[str, Any]]:
    mappings = data.get("mappings")
    if not isinstance(mappings, list):
        fail("repository mappings must be a list")

    result: dict[int, dict[str, Any]] = {}
    for item in mappings:
        if not isinstance(item, dict):
            fail("each repository mapping must be an object")
        repository_id = item.get("repository_id")
        if not isinstance(repository_id, int) or repository_id <= 0:
            fail("repository mapping contains an invalid repository ID")
        if repository_id in result:
            fail(f"duplicate repository ID: {repository_id}")
        result[repository_id] = item
    return result


def operational_repository_for_mapping(mapping: dict[str, Any]) -> str:
    status = mapping.get("status")
    if status in {"PREPARED_NOT_RENAMED", "ROLLED_BACK_VERIFIED"}:
        value = mapping.get("current_repository")
    elif status == "RENAMED_VERIFIED":
        value = mapping.get("target_repository_after_cutover")
    else:
        fail(f"unsupported repository rename status: {status}")

    if not isinstance(value, str) or not value.startswith("appolon1908-hue/"):
        fail("resolved operational repository is invalid")
    return value


def operational_repository_map(data: dict[str, Any]) -> dict[int, str]:
    return {
        repository_id: operational_repository_for_mapping(mapping)
        for repository_id, mapping in mapping_index(data).items()
    }


def forbidden_non_operational_names(data: dict[str, Any]) -> set[str]:
    """Return the inactive side of every governed repository rename."""

    forbidden: set[str] = set()
    for mapping in mapping_index(data).values():
        if mapping.get("status") == "RENAMED_VERIFIED":
            inactive = mapping.get("current_repository")
        else:
            inactive = mapping.get("target_repository_after_cutover")
        if not isinstance(inactive, str):
            fail("inactive repository name is invalid")
        forbidden.add(inactive)
    return forbidden


def forbidden_pre_cutover_targets(data: dict[str, Any]) -> set[str]:
    """Compatibility alias retained for existing tests and callers."""

    return forbidden_non_operational_names(data)


def is_operational_source(path: Path) -> bool:
    """Return whether a text file can control a current checkout or deployment."""

    try:
        relative = path.resolve().relative_to(ROOT.resolve())
    except ValueError:
        return False

    resolved = path.resolve()
    if resolved == HISTORICAL_STAGE6_LOCK.resolve():
        return False
    if resolved in {MANIFEST.resolve(), RUNBOOK.resolve(), VALIDATOR}:
        return False
    if any(part in EXCLUDED_ROOTS for part in relative.parts):
        return False
    if relative.name in ROOT_OPERATIONAL_NAMES:
        return True
    if relative.parts[:2] == (".github", "workflows"):
        return relative.suffix.lower() in {".yaml", ".yml"}
    if relative.parts[:2] == (".github", "actions"):
        return relative.suffix.lower() in TEXT_SUFFIXES or relative.name in {
            "Dockerfile",
            "Makefile",
        }
    if not relative.parts:
        return False
    if relative.parts[0] in OPERATIONAL_ROOTS:
        return relative.suffix.lower() in TEXT_SUFFIXES or relative.name in {
            "Caddyfile",
            "Dockerfile",
            "Makefile",
        }
    if len(relative.parts) == 1:
        return relative.suffix.lower() in TEXT_SUFFIXES
    return False


def operational_sources() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file() and is_operational_source(path)
    )


def validate_planned_targets_absent(
    paths: list[Path],
    planned_targets: set[str],
) -> None:
    lowered_targets = {target.lower() for target in planned_targets}
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for target in lowered_targets:
            if target in text:
                fail(
                    "planned repository target appears in active operational "
                    f"source before cutover: {target} in {path.relative_to(ROOT)}"
                )


def iter_dicts(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_dicts(child)


def _record_repository_values(record: dict[str, Any]) -> dict[str, str]:
    return {
        field: value
        for field, value in record.items()
        if field in REPOSITORY_FIELDS and isinstance(value, str)
    }


def _validate_repository_values(
    repository_id: int,
    expected: str,
    values: dict[str, str],
    source: str,
) -> None:
    if not values:
        fail(
            f"{source} binds repository ID {repository_id} without a recognized "
            "repository field"
        )
    conflicts = {field: value for field, value in values.items() if value != expected}
    if conflicts:
        rendered = ", ".join(
            f"{field}={value}" for field, value in sorted(conflicts.items())
        )
        fail(
            f"{source} binds repository ID {repository_id} to conflicting "
            f"repository fields ({rendered}); expected {expected}"
        )


def validate_json_repository_pairs(
    path: Path,
    text: str,
    operational_by_id: dict[int, str],
) -> None:
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        fail(f"invalid operational JSON in {path.relative_to(ROOT)}: {exc}")

    for record in iter_dicts(document):
        repository_id = record.get(
            "github_repository_id",
            record.get("repository_id"),
        )
        if repository_id not in operational_by_id:
            continue
        _validate_repository_values(
            repository_id,
            operational_by_id[repository_id],
            _record_repository_values(record),
            str(path.relative_to(ROOT)),
        )


def explicit_id_pattern(repository_id: int) -> re.Pattern[str]:
    return re.compile(
        rf'(?<![A-Za-z0-9_])["\']?(?:github_)?repository_id["\']?'
        rf"\s*[:=]\s*{repository_id}\b",
        re.IGNORECASE,
    )


def generic_id_pattern() -> re.Pattern[str]:
    return re.compile(
        r'(?<![A-Za-z0-9_])["\']?(?:github_)?repository_id["\']?\s*[:=]',
        re.IGNORECASE,
    )


def repository_field_pattern(expected: str) -> re.Pattern[str]:
    field_names = "|".join(sorted(REPOSITORY_FIELDS))
    return re.compile(
        rf'(?<![A-Za-z0-9_])["\']?(?:{field_names})["\']?\s*[:=]\s*'
        rf'["\']?{re.escape(expected)}(?=["\'\s,\}}\]]|$)',
        re.IGNORECASE,
    )


def repository_field_values(record: str) -> dict[str, str]:
    """Extract all recognized repository assignments from one text record."""

    field_names = "|".join(sorted(REPOSITORY_FIELDS))
    pattern = re.compile(
        rf'(?<![A-Za-z0-9_])["\']?(?P<field>{field_names})["\']?\s*[:=]\s*'
        r'(?P<value>"[^"\r\n]*"|\'[^\'\r\n]*\'|[^\s,\}\]#]+)',
        re.IGNORECASE,
    )
    values: dict[str, str] = {}
    material = "\n".join(
        line for line in record.splitlines() if not line.lstrip().startswith("#")
    )
    for match in pattern.finditer(material):
        field = match.group("field").lower()
        value = match.group("value")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        previous = values.get(field)
        if previous is not None and previous != value:
            fail(
                f"text record assigns conflicting values to {field}: "
                f"{previous} and {value}"
            )
        values[field] = value
    return values


def line_indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def textual_record(lines: list[str], index: int) -> str:
    """Return one local YAML/TOML/HCL-style record around an explicit ID."""

    current_indent = line_indent(lines[index])
    toml_table = re.compile(r"^\s*\[\[?[^\]]+\]\]?\s*(?:#.*)?$")
    start = index
    for cursor in range(index - 1, -1, -1):
        line = lines[cursor]
        if (
            not line.strip()
            or generic_id_pattern().search(line)
            or toml_table.match(line)
        ):
            break
        indent = line_indent(line)
        if re.match(r"^\s*-\s+", line) and indent <= current_indent:
            start = cursor
            break
        if indent < current_indent:
            start = cursor
            break
        start = cursor

    end = index + 1
    for cursor in range(index + 1, len(lines)):
        line = lines[cursor]
        if (
            not line.strip()
            or generic_id_pattern().search(line)
            or toml_table.match(line)
        ):
            break
        indent = line_indent(line)
        if re.match(r"^\s*-\s+", line) and indent <= current_indent:
            break
        if indent < current_indent:
            break
        end = cursor + 1

    return "\n".join(lines[start:end])


def validate_text_repository_pairs(
    path: Path,
    text: str,
    operational_by_id: dict[int, str],
) -> None:
    lines = text.splitlines()
    for repository_id, expected in operational_by_id.items():
        pattern = explicit_id_pattern(repository_id)
        for index, line in enumerate(lines):
            if pattern.search(line) is None:
                continue
            record = textual_record(lines, index)
            _validate_repository_values(
                repository_id,
                expected,
                repository_field_values(record),
                str(path.relative_to(ROOT)),
            )


def validate_repository_id_current_name_pairing(
    paths: list[Path],
    operational_by_id: dict[int, str] | None = None,
) -> None:
    """Pair each structured stable-ID record with its approved repository."""

    expected = operational_by_id or {
        repository_id: values[0] for repository_id, values in EXPECTED.items()
    }

    for path in paths:
        text = path.read_text(encoding="utf-8", errors="ignore")
        suffix = path.suffix.lower()
        if suffix == ".json":
            validate_json_repository_pairs(path, text, expected)
        elif suffix in STRUCTURED_TEXT_SUFFIXES:
            validate_text_repository_pairs(path, text, expected)


def require_file(path: Path) -> str:
    if not path.is_file():
        fail(f"required operational authority file is missing: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def require_regex_binding(
    path: Path,
    pattern: str,
    expected_repository: str,
    description: str,
) -> None:
    text = require_file(path)
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    if match is None:
        fail(f"required operational binding is missing: {description}")
    if match.group(1) != expected_repository:
        fail(f"{description} must use {expected_repository}, found {match.group(1)}")


def assigned_string_set(source: str, variable: str) -> set[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        fail(f"invalid Python source while checking {variable}: {exc}")

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(
            isinstance(target, ast.Name) and target.id == variable
            for target in targets
        ):
            continue

        value = node.value
        if not isinstance(value, (ast.Set, ast.List, ast.Tuple)):
            fail(f"{variable} must be a literal string collection")
        result: set[str] = set()
        for item in value.elts:
            if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
                fail(f"{variable} must contain only literal strings")
            result.add(item.value)
        return result

    fail(f"required Python authority collection is missing: {variable}")
    return set()


def validate_known_operational_bindings(
    data: dict[str, Any] | None = None,
) -> None:
    """Protect source-lock entries that do not yet carry stable IDs."""

    document = data or load()
    operational_by_id = operational_repository_map(document)
    social_operational = operational_by_id[1351353723]
    infrastructure_operational = operational_by_id[1350724865]

    require_regex_binding(
        ROOT / "STAGE6-SOURCE-LOCK.yaml",
        r"^\s*social_control:\s*\{[^}\n]*\brepository:\s*([^,\s}]+)",
        social_operational,
        "STAGE6 social-control repository",
    )
    require_regex_binding(
        ROOT / "STAGE6-SOURCE-LOCK.yaml",
        r"^\s*authority_issue:\s*https://github\.com/([^/]+/[^/]+)/issues/\d+",
        infrastructure_operational,
        "STAGE6 infrastructure authority issue repository",
    )
    require_regex_binding(
        ROOT / "release" / "stage6-8-release-matrix.yaml",
        r"^\s*-\s+name:\s*social_control\s*$.*?^\s+repo:\s*(\S+)",
        social_operational,
        "Stage 6-8 social-control release repository",
    )

    stage9 = json.loads(
        require_file(ROOT / "config" / "marketing-stage9-readiness.json")
    )
    stage9_social = [
        item
        for item in stage9.get("repositories", [])
        if isinstance(item, dict) and item.get("role") == "social control plane"
    ]
    expected_social_slug = social_operational.split("/", 1)[1]
    if len(stage9_social) != 1 or stage9_social[0].get("repo") != expected_social_slug:
        fail(
            "marketing Stage 9 social-control repository does not match "
            "the active alias status"
        )

    historical_text = require_file(HISTORICAL_STAGE6_LOCK)
    historical_digest = hashlib.sha256(historical_text.encode("utf-8")).hexdigest()
    if historical_digest != HISTORICAL_STAGE6_LOCK_SHA256:
        fail("historical Stage 6 source lock content changed")
    historical = json.loads(historical_text)
    historical_social = (
        historical.get("repositories", {}).get("social_control", {}).get("repo")
    )
    if historical_social != EXPECTED[1351353723][0]:
        fail("historical Stage 6 source lock social-control repository changed")

    certifier = require_file(ROOT / "scripts" / "certify_marketing_stage9.py")
    if assigned_string_set(certifier, "BASE_EXPECTED_REPOS") != STAGE9_BASE_EXPECTED_REPOS:
        fail("marketing Stage 9 base repository set drifted from authority")

    id_match = re.search(
        r"(?m)^SOCIAL_CONTROL_REPOSITORY_ID\s*=\s*(\d+)\s*$",
        certifier,
    )
    if id_match is None or int(id_match.group(1)) != 1351353723:
        fail(
            "marketing Stage 9 certifier is not bound to the stable "
            "social-control repository ID"
        )

    dynamic_binding = re.compile(
        r"expected_repos\s*=\s*BASE_EXPECTED_REPOS\s*\|\s*"
        r"\{\s*social_control_slug\(\)\s*\}"
    )
    if dynamic_binding.search(certifier) is None:
        fail(
            "marketing Stage 9 certifier no longer resolves social control "
            "through repository aliases"
        )


def is_compose_source(path: Path, text: str | None = None) -> bool:
    """Return true only for Docker/Podman Compose configuration sources."""

    if path.suffix.lower() not in {".yaml", ".yml"}:
        return False
    name = path.name.lower()
    parts = {part.lower() for part in path.parts}
    named_compose = (
        name in {
            "compose.yaml",
            "compose.yml",
            "docker-compose.yaml",
            "docker-compose.yml",
            "podman-compose.yaml",
            "podman-compose.yml",
        }
        or "compose" in name
        or "compose" in parts
    )
    if named_compose:
        return True
    if text is None:
        return False
    return (
        re.search(r"(?mi)^services\s*:", text) is not None
        and not is_kubernetes_source(path, text)
    )


def is_kubernetes_source(path: Path, text: str) -> bool:
    parts = {part.lower() for part in path.parts}
    if parts & {"k8s", "kubernetes", "helm"}:
        return True
    lowered = text.lower()
    return "apiversion:" in lowered and re.search(r"(?mi)^\s*kind\s*:", text) is not None


def compose_ports_blocks(text: str) -> list[str]:
    """Return Compose `ports` keys and their nested values."""

    lines = text.splitlines()
    blocks: list[str] = []
    for index, line in enumerate(lines):
        match = re.match(r'^(?P<indent>\s*)["\']?ports["\']?\s*:(?P<tail>.*)$', line, re.IGNORECASE)
        if match is None:
            continue

        indent = len(match.group("indent"))
        selected = [line]
        tail = match.group("tail").strip()
        if tail and not tail.startswith("#"):
            blocks.append(line)
            continue
        for following in lines[index + 1 :]:
            if not following.strip() or following.lstrip().startswith("#"):
                selected.append(following)
                continue
            if line_indent(following) <= indent:
                break
            selected.append(following)
        blocks.append("\n".join(selected))
    return blocks


def is_gateway_source(path: Path, text: str) -> bool:
    lowered_parts = {part.lower() for part in path.relative_to(ROOT).parts}
    gateway_tokens = {
        "caddy",
        "kong",
        "gateway",
        "ingress",
        "nginx",
        "proxy",
        "traefik",
    }
    if lowered_parts & gateway_tokens:
        return True

    name = path.name.lower()
    if any(token in name for token in gateway_tokens):
        return True

    lowered = text.lower()
    if "reverse_proxy" in lowered or (
        "_format_version:" in lowered and "services:" in lowered
    ):
        return True
    kind_match = re.search(r"(?mi)^\s*kind\s*:\s*([A-Za-z]+)\s*$", text)
    if kind_match and kind_match.group(1).lower() in KUBERNETES_PUBLIC_ROUTE_KINDS:
        return True
    if re.search(r"(?mi)^\s*(?:backendrefs|parentrefs)\s*:", text):
        return True
    return False


def _kubernetes_public_service_exposes_exporter(text: str) -> bool:
    """Detect public Service or hostPort exposure while allowing private ports."""

    lowered = text.lower()
    if "postgres-exporter" not in lowered and "9187" not in lowered:
        return False
    if re.search(r"(?mi)^\s*hostport\s*:\s*9187\s*$", text):
        return True

    for document in re.split(r"(?m)^\s*---\s*$", text):
        kind = re.search(r"(?mi)^\s*kind\s*:\s*([A-Za-z]+)\s*$", document)
        if kind is None or kind.group(1).lower() != "service":
            continue
        service_type = re.search(
            r"(?mi)^\s*type\s*:\s*(LoadBalancer|NodePort)\s*$",
            document,
        )
        exporter_identity = "postgres-exporter" in document.lower()
        exporter_port = re.search(
            r"(?mi)^\s*(?:port|targetPort|nodePort)\s*:\s*9187\s*$",
            document,
        )
        if service_type and (exporter_identity or exporter_port):
            return True
    return False


def validate_postgres_exporter_privacy(paths: list[Path]) -> None:
    """Reject public routing or host publication of PostgreSQL Exporter."""

    forbidden_hostname = "pgex.codestra.media"
    private_identity = "postgres-exporter:9187"

    for path in paths:
        text = path.read_text(encoding="utf-8", errors="ignore")
        lowered = text.lower()
        relative = path.relative_to(ROOT)

        if forbidden_hostname in lowered:
            fail(f"retired PostgreSQL Exporter hostname appears in {relative}")

        if is_compose_source(path, text):
            for block in compose_ports_blocks(text):
                if re.search(r"\b9187\b", block):
                    fail(f"PostgreSQL Exporter port is host-published in {relative}")

        if re.search(
            r"(?:docker|podman)\s+(?:run|create)[^\n]*(?:-p|--publish)(?:=|\s+)"
            r"[^\n]*\b9187\b",
            lowered,
        ):
            fail(
                "PostgreSQL Exporter port is published by a runtime command "
                f"in {relative}"
            )

        if is_kubernetes_source(path, text) and _kubernetes_public_service_exposes_exporter(text):
            fail(
                "PostgreSQL Exporter is exposed by a public Kubernetes "
                f"service or hostPort in {relative}"
            )

        if (
            "9187" in lowered
            and ("0.0.0.0/0" in lowered or "::/0" in lowered)
            and re.search(r"(?:from_port|to_port|port|port_range)[^\n]*9187", lowered)
        ):
            fail(
                "PostgreSQL Exporter is allowed by a public network rule "
                f"in {relative}"
            )

        if (
            private_identity in lowered or "postgres-exporter" in lowered
        ) and is_gateway_source(path, text):
            fail(
                "PostgreSQL Exporter is referenced by gateway source "
                f"in {relative}"
            )


def validate_account_status(
    data: dict[str, Any],
    mappings: dict[int, dict[str, Any]],
) -> None:
    account_status = data.get("status")
    if account_status not in ACCOUNT_STATUSES:
        fail(f"unsupported account migration status: {account_status}")

    statuses = {mapping.get("status") for mapping in mappings.values()}
    if not statuses <= MAPPING_STATUSES:
        fail("one or more repository mappings has an unsupported status")
    if account_status == "PREPARED_NOT_RENAMED" and statuses != {"PREPARED_NOT_RENAMED"}:
        fail("prepared account status requires every repository to remain pre-cutover")
    if account_status == "RENAMED_VERIFIED" and statuses != {"RENAMED_VERIFIED"}:
        fail("renamed account status requires every repository to be verified")
    if account_status == "PARTIALLY_RENAMED_VERIFIED" and (
        "RENAMED_VERIFIED" not in statuses or statuses == {"RENAMED_VERIFIED"}
    ):
        fail("partial account status requires both renamed and non-renamed mappings")
    if account_status == "ROLLED_BACK_VERIFIED" and "ROLLED_BACK_VERIFIED" not in statuses:
        fail("rolled-back account status requires rollback evidence in a mapping")


def validate() -> None:
    data = load()
    if data.get("schema_version") != "1.0":
        fail("schema_version must be 1.0")
    if data.get("identity_key") != "repository_id":
        fail("repository_id must be the stable identity key")

    mappings_by_id = mapping_index(data)
    validate_account_status(data, mappings_by_id)

    documentation = data.get("documentation_authority", {})
    if documentation.get("repository_id") != 1350724356:
        fail("documentation authority repository ID is incorrect")
    if documentation.get("current_repository") != "appolon1908-hue/documentaions":
        fail("documentation authority current repository is incorrect")
    if documentation.get("target_repository_after_cutover") != (
        "appolon1908-hue/Codestra-Documentation"
    ):
        fail("documentation authority target repository is incorrect")

    infrastructure = data.get("infrastructure_authority", {})
    if infrastructure.get("repository_id") != 1350724865:
        fail("infrastructure authority repository ID is incorrect")
    if infrastructure.get("current_repository") != "appolon1908-hue/Infustruction-repo":
        fail("infrastructure current repository is incorrect")
    if infrastructure.get("target_repository_after_cutover") != (
        "appolon1908-hue/Codestra-Infrastructure"
    ):
        fail("infrastructure target repository is incorrect")

    infrastructure_mapping = mappings_by_id.get(1350724865, {})
    if infrastructure.get("status") != infrastructure_mapping.get("status"):
        fail("infrastructure authority and mapping status disagree")
    infrastructure_status = infrastructure_mapping.get("status")
    runtime_state = infrastructure.get("runtime_state")
    if infrastructure_status in {"PREPARED_NOT_RENAMED", "ROLLED_BACK_VERIFIED"} and (
        runtime_state != "REQUIRES_PRE_CUTOVER_DISCOVERY"
    ):
        fail("pre-cutover infrastructure runtime state must require discovery")
    if infrastructure_status == "RENAMED_VERIFIED" and runtime_state not in {
        "DEPLOYED_UNCHANGED",
        "NOT_DEPLOYED_NA",
    }:
        fail("renamed infrastructure authority requires verified runtime state")

    postgres = data.get("postgres_exporter_authority", {})
    expected_postgres = {
        "repository_id": 1350839865,
        "repository": "appolon1908-hue/Codestra-Postgres-Exporter",
        "public_hostname": None,
        "private_service_identity": "postgres-exporter:9187",
        "forbidden_public_hostname": "pgex.codestra.media",
        "exposure": "PRIVATE_INTERNAL_ONLY",
        "caddy_publication_allowed": False,
        "kong_publication_allowed": False,
        "host_public_port_allowed": False,
    }
    for field, expected_value in expected_postgres.items():
        if postgres.get(field) != expected_value:
            fail(f"PostgreSQL Exporter {field} is incorrect")

    if len(mappings_by_id) != len(EXPECTED):
        fail("manifest must contain exactly the six approved mappings")

    seen_current: set[str] = set()
    seen_target: set[str] = set()
    actual: dict[int, tuple[str, str, bool]] = {}
    for repository_id, item in mappings_by_id.items():
        current = item.get("current_repository")
        target = item.get("target_repository_after_cutover")
        runtime_critical = item.get("runtime_critical")
        if not isinstance(current, str) or not current.startswith("appolon1908-hue/"):
            fail(f"invalid current repository for ID {repository_id}")
        if not isinstance(target, str) or not target.startswith("appolon1908-hue/"):
            fail(f"invalid target repository for ID {repository_id}")
        if current == target:
            fail(f"current and target repository are identical for ID {repository_id}")
        if current in seen_current or target in seen_target:
            fail("duplicate current or target repository name")
        if not isinstance(runtime_critical, bool):
            fail(f"mapping runtime_critical must be boolean: {current}")

        seen_current.add(current)
        seen_target.add(target)
        actual[repository_id] = (current, target, runtime_critical)

    if actual != EXPECTED:
        fail("repository mappings do not exactly match the approved migration set")

    policy = data.get("policy", {})
    required_true = {
        "current_names_required_before_cutover",
        "target_names_forbidden_as_operational_sources_before_cutover",
        "historical_evidence_immutable",
        "one_repository_per_cutover",
        "same_repository_id_required_after_rename",
        "all_inventoried_integrations_require_post_rename_readback",
        "runtime_digest_must_remain_unchanged_when_deployed",
        "absent_runtime_digest_must_be_recorded_as_not_applicable",
        "success_path_must_restore_freeze_state",
        "rollback_path_must_restore_freeze_state",
    }
    for key in required_true:
        if policy.get(key) is not True:
            fail(f"required fail-closed policy is not true: {key}")
    if policy.get("rename_authorizes_deployment") is not False:
        fail("repository rename must not authorize deployment")

    runbook = RUNBOOK.read_text(encoding="utf-8")
    for required in (
        "POST_RENAME_INTEGRATION_READBACK=PASS",
        "CURRENT_RUNTIME_STATE=DEPLOYED|NOT_DEPLOYED",
        "DEPLOYED_IMAGE_DIGEST=<immutable-digest>|N/A",
        "RUNTIME_DIGEST_UNCHANGED=PASS|N/A",
        "MERGES_UNFROZEN=PASS",
        "WORKFLOW_DISPATCH_UNFROZEN=PASS|N/A",
        "ROLLBACK_UNFREEZE=PASS|N/A",
        "Do not leave the infrastructure authority frozen.",
        "do not fabricate runtime evidence.",
        "WORKLOADS_RESTARTED=0",
        "IMAGES_REBUILT=0",
        "CONFIG_APPLIES=0",
        "DATABASE_MIGRATIONS=0",
        "SECRETS_ROTATED=0",
        "DNS_CHANGES=0",
        "PRODUCTION_TRAFFIC_CHANGED=NO",
    ):
        if required not in runbook:
            fail(f"infrastructure rename runbook is missing required evidence: {required}")

    sources = operational_sources()
    operational_by_id = operational_repository_map(data)
    validate_planned_targets_absent(sources, forbidden_non_operational_names(data))
    validate_repository_id_current_name_pairing(sources, operational_by_id)
    validate_known_operational_bindings(data)
    validate_postgres_exporter_privacy(sources)


def main() -> None:
    validate()
    print("Codestra repository-name authority validation: PASS")


if __name__ == "__main__":
    main()
