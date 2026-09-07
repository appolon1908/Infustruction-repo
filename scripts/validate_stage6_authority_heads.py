#!/usr/bin/env python3
"""Compare locked revisions with live main heads; never rewrite release evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

import yaml


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "STAGE6-SOURCE-LOCK.yaml"
FULL_SHA = re.compile(r"[0-9a-f]{40}")
COMPONENT = re.compile(r"[a-z][a-z0-9_]*")
REPOSITORY = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]+")
ATTEMPTS = 3
TIMEOUT = 15
MAX_RESPONSE_BYTES = 64 * 1024


class LockError(ValueError):
    """Invalid or ambiguous lock input (safe to display without its contents)."""


class UniqueSafeLoader(yaml.SafeLoader):
    """Reject duplicate keys instead of silently dropping locked components."""

    def construct_mapping(self, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in mapping:
                raise LockError("lock mapping keys must be unique strings")
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


class NoRedirect(HTTPRedirectHandler):
    """Never forward a read credential to a redirected host or endpoint."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class Result:
    component: str
    repository: str
    expected: str
    status: str
    observed: str = ""
    detail: str = ""


def validate_definition(component: str, definition: dict) -> None:
    if not isinstance(component, str) or not COMPONENT.fullmatch(component):
        raise LockError("component names must use lowercase letters, digits and underscores")
    if not isinstance(definition, dict):
        raise LockError(f"{component}: repository definition must be a mapping")
    repository = definition.get("repository")
    if (not isinstance(repository, str) or not REPOSITORY.fullmatch(repository)
            or repository.split("/")[-1] in {".", ".."}):
        raise LockError(f"{component}: repository must be an owner/name, not a URL or path")
    revision = definition.get("revision")
    if not isinstance(revision, str) or not FULL_SHA.fullmatch(revision):
        raise LockError(f"{component}: revision must be a full lowercase 40-character SHA")


def load_repositories(raw: bytes) -> dict:
    try:
        lock = yaml.load(raw, Loader=UniqueSafeLoader)
    except (yaml.YAMLError, UnicodeError, RecursionError) as exc:
        # Parser exceptions can embed source lines; do not echo their contents.
        raise LockError("lock is not valid unambiguous YAML") from exc
    if not isinstance(lock, dict):
        raise LockError("lock must be a mapping")
    repositories = lock.get("repositories")
    if not isinstance(repositories, dict) or not repositories:
        raise LockError("repositories must be a non-empty mapping")
    for component, definition in repositories.items():
        validate_definition(component, definition)
    return repositories


def inspect_head(component: str, definition: dict) -> Result:
    validate_definition(component, definition)
    repository, expected = definition["repository"], definition["revision"]

    def result(status: str, detail: str = "", observed: str = "") -> Result:
        return Result(component, repository, expected, status, observed, detail)

    token = os.environ.get("STAGE6_SOURCE_READ_TOKEN", "").strip()
    if any(ord(character) < 33 or ord(character) > 126 for character in token):
        return result("INVALID_CREDENTIAL", "read credential contains invalid characters")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "codestra-stage6-authority-head-validator",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"https://api.github.com/repos/{repository}/git/ref/heads/main"
    opener = build_opener(NoRedirect())
    for attempt in range(ATTEMPTS):
        try:
            with opener.open(Request(url, headers=headers), timeout=TIMEOUT) as response:
                if response.geturl() != url:
                    return result("REDIRECT_REJECTED", "API endpoint changed; review repository authority")
                raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                return result("INVALID_RESPONSE", "GitHub ref response exceeds size limit")
            payload = json.loads(raw)
        except HTTPError as exc:
            code = exc.code
            response_headers = exc.headers or {}
            limited = code == 429 or (code == 403 and (
                response_headers.get("X-RateLimit-Remaining") == "0"
                or response_headers.get("Retry-After") is not None
            ))
            exc.close()
            if limited:
                # Do not retry before GitHub's reset/retry-after boundary.
                return result("RATE_LIMITED", "HTTP rate limit; retry after GitHub's reset window")
            if code in {500, 502, 503, 504} and attempt + 1 < ATTEMPTS:
                time.sleep(2 ** attempt)
                continue
            status = {
                401: "AUTHENTICATION_FAILED", 403: "ACCESS_DENIED",
                404: "NOT_FOUND_OR_INACCESSIBLE",
            }.get(code, "REDIRECT_REJECTED" if 300 <= code < 400 else "HTTP_ERROR")
            detail = f"cannot query authoritative main: HTTP {code}"
            if code in {401, 403, 404}:
                detail += "; verify repository/ref and trusted read-only credential access"
            return result(status, detail)
        except (URLError, TimeoutError, OSError):
            if attempt + 1 < ATTEMPTS:
                time.sleep(2 ** attempt)
                continue
            return result("NETWORK_ERROR", "GitHub ref request failed after bounded retries")
        except (ValueError, UnicodeError, RecursionError):
            return result("INVALID_RESPONSE", "GitHub ref response is not valid JSON")
        if not isinstance(payload, dict) or payload.get("ref") != "refs/heads/main":
            return result("INVALID_RESPONSE", "response must describe refs/heads/main")
        obj = payload.get("object")
        if not isinstance(obj, dict) or obj.get("type") != "commit":
            return result("INVALID_RESPONSE", "main must reference a commit object")
        observed = obj.get("sha")
        if not isinstance(observed, str) or not FULL_SHA.fullmatch(observed):
            return result("INVALID_RESPONSE", "authoritative commit SHA is invalid")
        if observed != expected:
            return result("DRIFT", "locked revision differs from authoritative main", observed)
        return result("MATCH", observed=observed)
    return result("NETWORK_ERROR", "GitHub ref request did not complete")


def authority_head(component: str, definition: dict) -> tuple[str, str, str]:
    """Retain the original tuple/exception API for existing callers."""
    result = inspect_head(component, definition)
    if result.status != "MATCH":
        raise RuntimeError(
            f"{component}: {result.status} locked={result.expected} "
            f"authoritative_main={result.observed or 'UNKNOWN'}; {result.detail}"
        )
    return component, result.repository, result.observed


def inspect_repositories(repositories: dict) -> list[Result]:
    results = []
    with ThreadPoolExecutor(max_workers=min(8, len(repositories))) as executor:
        futures = {
            executor.submit(inspect_head, component, definition): component
            for component, definition in repositories.items()
        }
        for future in as_completed(futures):
            component = futures[future]
            try:
                results.append(future.result())
            except Exception:
                # Preserve attribution and fail closed without leaking exception text.
                definition = repositories[component]
                results.append(Result(component, definition["repository"], definition["revision"],
                                      "INTERNAL_ERROR", detail="unexpected validator failure"))
    return sorted(results, key=lambda item: item.component)


def write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         delete=False) as output:
            temporary = Path(output.name)
            json.dump(report, output, indent=2, sort_keys=True)
            output.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=LOCK)
    parser.add_argument("--json-report", type=Path, help="write diagnostics even when validation fails")
    args = parser.parse_args(argv)
    if args.json_report and args.json_report.resolve() == args.lock.resolve():
        print("AUTHORITY_VALIDATION=FAIL report must not overwrite the source lock")
        return 2
    report = {"schema_version": 1, "validation": "FAIL", "lock_sha256": None,
              "required": 0, "matched": 0, "failed": 0, "results": []}
    try:
        raw = args.lock.read_bytes()
        report["lock_sha256"] = hashlib.sha256(raw).hexdigest()
        repositories = load_repositories(raw)
    except (OSError, LockError) as exc:
        report["error"] = str(exc) if isinstance(exc, LockError) else "cannot read source lock"
        print(f"AUTHORITY_INPUT=FAIL {report['error']}")
        code = 2
    else:
        results = inspect_repositories(repositories)
        matched = sum(item.status == "MATCH" for item in results)
        report.update(required=len(repositories), matched=matched,
                      failed=len(repositories) - matched, results=[asdict(item) for item in results])
        code = 0 if matched == len(repositories) else 1
        report["validation"] = "PASS" if code == 0 else "FAIL"
        for item in results:
            if item.status == "MATCH":
                print(f"AUTHORITY_HEAD component={item.component} repository={item.repository} sha={item.observed}")
            else:
                print(f"AUTHORITY_FAILURE component={item.component} status={item.status} "
                      f"locked={item.expected} authoritative_main={item.observed or 'UNKNOWN'}; {item.detail}")
        print(f"AUTHORITY_HEADS={matched}/{len(repositories)}")
    print(f"AUTHORITY_VALIDATION={report['validation']}")
    if args.json_report:
        try:
            write_report(args.json_report, report)
        except OSError:
            print("AUTHORITY_REPORT=FAIL cannot write diagnostic report")
            return 2
    return code


if __name__ == "__main__":
    raise SystemExit(main())
