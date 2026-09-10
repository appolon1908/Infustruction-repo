#!/usr/bin/env python3
"""Bind candidate source to an independent exact-commit review; never execute it."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

REPOSITORY = "appolon1908-hue/Infustruction-repo"
REPOSITORY_ID = 1350724865
REVIEWER_ID = 77101516
SHA = re.compile(r"[0-9a-f]{40}\Z")


class ReviewError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReviewError(message)


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(
        ["git", "-C", str(root), *args], stderr=subprocess.DEVNULL, timeout=30,
    )


def source_fingerprint(root: Path, source_sha: str) -> str:
    require(isinstance(source_sha, str) and bool(SHA.fullmatch(source_sha)), "invalid source SHA")
    require(git(root, "rev-parse", "HEAD").decode().strip() == source_sha, "checkout SHA mismatch")
    # Bind every tracked entry, including mode, path and Git object identity.
    # No assignments, closure values, workflows, tests or evidence are omitted.
    tree = git(root, "ls-tree", "-r", "-z", source_sha)
    require(bool(tree), "empty source tree")
    return hashlib.sha256(b"codestra.reviewed-source.v1\0" + tree).hexdigest()


def validate_subject(pr: dict, number: int, base_sha: str) -> str:
    require(isinstance(pr, dict), "invalid PR metadata")
    require(type(number) is int and number > 0 and pr.get("number") == number, "PR identity mismatch")
    require(pr.get("state") == "open" and pr.get("draft") is False, "PR must be open and ready")
    base = pr.get("base", {})
    require(base.get("ref") == "main", "protected base must be main")
    require(base.get("sha") == base_sha and bool(SHA.fullmatch(base_sha)), "protected base changed")
    repository = base.get("repo", {})
    require(repository.get("id") == REPOSITORY_ID and repository.get("full_name") == REPOSITORY,
            "repository identity mismatch")
    head_sha = pr.get("head", {}).get("sha")
    require(isinstance(head_sha, str) and bool(SHA.fullmatch(head_sha)), "invalid candidate SHA")
    require(type(pr.get("user", {}).get("id")) is int, "PR author identity missing")
    return head_sha


def validate_review(pr: dict, reviews: list, source_sha: str) -> int:
    require(pr["user"]["id"] != REVIEWER_ID, "reviewer cannot approve their own PR")
    require(isinstance(reviews, list), "invalid review collection")
    decisions = []
    seen = set()
    for review in reviews:
        require(isinstance(review, dict), "invalid review record")
        if review.get("user", {}).get("id") != REVIEWER_ID:
            continue
        state = review.get("state")
        if state in {"COMMENTED", "PENDING"}:
            continue
        require(state in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}, "unknown review state")
        identity = review.get("id")
        require(type(identity) is int and identity > 0 and identity not in seen, "invalid review identity")
        seen.add(identity)
        decisions.append(review)
    require(bool(decisions), "independent approval of this exact commit is required")
    latest = max(decisions, key=lambda review: review["id"])
    require(latest["state"] == "APPROVED", "independent approval is withdrawn or changes requested")
    require(latest.get("commit_id") == source_sha, "independent approval is stale")
    require(latest.get("author_association") in {"COLLABORATOR", "MEMBER", "OWNER"},
            "reviewer must be a repository collaborator")
    return latest["id"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-root", type=Path, required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--pr", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--candidate-root", type=Path)
    parser.add_argument("--head-sha")
    parser.add_argument("--reviews", type=Path)
    parser.add_argument("--final-pr", type=Path)
    args = parser.parse_args()
    base_root = args.base_root.resolve(strict=True)
    # The entry point itself must come from the protected checkout.
    require(Path(__file__).resolve() == base_root / "scripts/validate_release_policy_review.py",
            "validator must execute from the protected checkout")
    require(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY, "workflow repository mismatch")
    require(os.environ.get("GITHUB_SHA") == args.base_sha, "workflow source is not the protected base")
    base_fingerprint = source_fingerprint(base_root, args.base_sha)
    pr = json.loads(args.pr.read_text())
    head_sha = validate_subject(pr, args.pr_number, args.base_sha)
    if args.prepare:
        with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
            output.write(f"head_sha={head_sha}\n")
        return
    require(args.head_sha == head_sha, "candidate changed after preparation")
    require(args.candidate_root is not None and args.reviews is not None and args.final_pr is not None,
            "candidate and review evidence are required")
    candidate_fingerprint = source_fingerprint(args.candidate_root, head_sha)
    pages = json.loads(args.reviews.read_text())
    require(isinstance(pages, list) and all(isinstance(page, list) for page in pages),
            "review pagination is invalid")
    review_id = validate_review(pr, [review for page in pages for review in page], head_sha)
    final_pr = json.loads(args.final_pr.read_text())
    require(validate_subject(final_pr, args.pr_number, args.base_sha) == head_sha,
            "PR changed while reviews were collected")
    require(final_pr["user"]["id"] == pr["user"]["id"], "PR author changed")
    print(json.dumps({
        "status": "PASS", "repository": REPOSITORY, "pull_request": args.pr_number,
        "base_sha": args.base_sha, "head_sha": head_sha, "review_id": review_id,
        "reviewer_id": REVIEWER_ID, "base_source_sha256": base_fingerprint,
        "candidate_source_sha256": candidate_fingerprint, "candidate_executed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (ReviewError, OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"RELEASE_POLICY_REVIEW=FAIL: {error}") from error
