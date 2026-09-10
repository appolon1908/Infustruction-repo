#!/usr/bin/env python3
"""Fetch clean, detached checkouts at the exact Stage 6 locked revisions."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "STAGE6-SOURCE-LOCK.yaml"
DEFAULT_CHECKOUT_ROOT = Path("/root/stage6-source-lock-checkouts")
SHA = re.compile(r"^[0-9a-f]{40}$")


def run(*args: str, cwd: Path | None = None) -> str:
    return subprocess.check_output(
        list(args), cwd=cwd, text=True, stderr=subprocess.STDOUT
    ).strip()


def git(*args: str, cwd: Path) -> str:
    return run("git", *args, cwd=cwd)


def prepare(component: str, repository: str, revision: str, checkout_root: Path) -> dict:
    destination = checkout_root / component
    result = {
        "component": component,
        "repository": repository,
        "locked_revision": revision,
        "checkout": str(destination),
        "fetch": "FAIL",
        "authority_branch": "main",
        "authority_head": None,
        "authority_head_match": False,
        "head_match": False,
        "clean_worktree": False,
        "status": "FAIL",
        "error": None,
    }
    try:
        if not SHA.fullmatch(revision):
            raise RuntimeError(f"invalid locked revision: {revision}")

        if destination.exists() and not (destination / ".git").is_dir():
            raise RuntimeError("checkout path exists but is not a Git worktree")

        if not destination.exists():
            destination.mkdir(parents=True)
            git("init", "--quiet", cwd=destination)
            git(
                "remote",
                "add",
                "origin",
                f"https://github.com/{repository}.git",
                cwd=destination,
            )
        else:
            origin = git("remote", "get-url", "origin", cwd=destination)
            expected_origin = f"https://github.com/{repository}.git"
            if origin != expected_origin:
                raise RuntimeError("existing locked checkout has an unexpected origin")
            dirty_before = git("status", "--porcelain", "--untracked-files=all", cwd=destination)
            if dirty_before:
                raise RuntimeError("existing locked checkout is dirty; refusing to replace it")

        git(
            "fetch", "--quiet", "--force", "--filter=blob:none", "--no-tags",
            "--depth=1", "origin", "main:refs/remotes/origin/main", cwd=destination,
        )
        result["fetch"] = "PASS"
        result["authority_head"] = git(
            "rev-parse", "refs/remotes/origin/main", cwd=destination
        )
        result["authority_head_match"] = result["authority_head"] == revision
        if not result["authority_head_match"]:
            raise RuntimeError(
                f"authoritative main HEAD {result['authority_head']} does not equal locked revision"
            )

        try:
            current = git("rev-parse", "HEAD", cwd=destination)
        except subprocess.CalledProcessError:
            current = ""
        if current != revision:
            if git("status", "--porcelain", "--untracked-files=all", cwd=destination):
                raise RuntimeError("worktree became dirty before locked checkout")
            git("checkout", "--quiet", "--detach", revision, cwd=destination)

        head = git("rev-parse", "HEAD", cwd=destination)
        dirty = git("status", "--porcelain", "--untracked-files=all", cwd=destination)
        result["checkout_head"] = head
        result["head_match"] = head == revision
        result["clean_worktree"] = dirty == ""
        if not result["head_match"]:
            raise RuntimeError(f"checkout HEAD {head} does not equal locked revision")
        if not result["clean_worktree"]:
            raise RuntimeError("locked checkout is dirty")
        result["status"] = "PASS"
    except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
        output = getattr(exc, "output", None)
        result["error"] = (output or str(exc)).strip()[-2000:]
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout-root", type=Path, default=DEFAULT_CHECKOUT_ROOT)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    lock = yaml.safe_load(LOCK.read_text())
    repositories = lock["repositories"]
    args.checkout_root.mkdir(parents=True, exist_ok=True)

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                prepare,
                component,
                definition["repository"],
                definition["revision"],
                args.checkout_root,
            ): component
            for component, definition in repositories.items()
        }
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda item: list(repositories).index(item["component"]))
    report = {
        "schema": "codestra.stage6.locked-checkouts.v1",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "authoritative_lock": str(LOCK),
        "results": results,
        "summary": {
            "components": len(results),
            "pass": sum(item["status"] == "PASS" for item in results),
            "fail": sum(item["status"] != "PASS" for item in results),
        },
    }
    report_path = args.checkout_root / "FETCH-RESULTS.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")

    for item in results:
        print(
            f"{item['component']} FETCH={item['fetch']} "
            f"AUTHORITY_HEAD_MATCH={'YES' if item['authority_head_match'] else 'NO'} "
            f"HEAD_MATCH={'YES' if item['head_match'] else 'NO'} "
            f"CLEAN={'YES' if item['clean_worktree'] else 'NO'} "
            f"STATUS={item['status']}"
        )
        if item["error"]:
            print(f"  ERROR={item['error']}")
    print(
        f"LOCKED_CHECKOUTS_PASS={report['summary']['pass']} "
        f"LOCKED_CHECKOUTS_FAIL={report['summary']['fail']}"
    )
    raise SystemExit(0 if report["summary"]["fail"] == 0 else 1)


if __name__ == "__main__":
    main()
