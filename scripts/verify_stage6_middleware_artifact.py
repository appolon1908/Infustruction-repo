#!/usr/bin/env python3
"""Independently verify the exact Stage 6 Middleware release artifacts with Cosign."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = (
    "ghcr.io/appolon1908-hue/codestra-middleware@"
    "sha256:d899b182a414eef7c59e66c7fecb38b1161851b66c43d95e19e890a53f8caf58"
)
DIGEST = "sha256:d899b182a414eef7c59e66c7fecb38b1161851b66c43d95e19e890a53f8caf58"
SOURCE_SHA = "ab6e28769815f2bc60ca5bb52a4f3aa5818f89a5"
REPOSITORY = "appolon1908-hue/Middleware-"
IDENTITY = (
    "https://github.com/appolon1908-hue/Middleware-/"
    ".github/workflows/release.yml@refs/heads/main"
)
ISSUER = "https://token.actions.githubusercontent.com"
EXPECTED_COSIGN_VERSION = "v3.0.6"
MANIFEST = (
    ROOT
    / "reports/runtime-reconciliation/middleware-release-ab6e287/release-manifest.v1.json"
)
BUNDLE = MANIFEST.with_name("release-manifest.v1.sigstore.json")


def cosign(*arguments: str) -> str:
    completed = subprocess.run(
        ["cosign", *arguments],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=120,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"cosign {' '.join(arguments[:2])} failed: {detail[-2000:]}")
    return completed.stdout


def verify() -> dict:
    cosign_version = json.loads(cosign("version", "--json"))
    if cosign_version.get("gitVersion") != EXPECTED_COSIGN_VERSION:
        raise RuntimeError(
            f"Cosign version mismatch: {cosign_version.get('gitVersion')!r}"
        )
    image_output = cosign(
        "verify",
        "--certificate-identity",
        IDENTITY,
        "--certificate-oidc-issuer",
        ISSUER,
        "--output",
        "json",
        REFERENCE,
    )
    signatures = json.loads(image_output)
    if not isinstance(signatures, list) or not signatures:
        raise RuntimeError("Cosign returned no verified image signatures")
    annotated_source_match = False
    for signature in signatures:
        critical = signature.get("critical") or {}
        observed_digest = (critical.get("image") or {}).get("docker-manifest-digest")
        source_sha = (signature.get("optional") or {}).get("codestra.source_sha")
        if observed_digest != DIGEST:
            raise RuntimeError(f"verified image digest mismatch: {observed_digest!r}")
        if source_sha == SOURCE_SHA:
            annotated_source_match = True
        elif source_sha is not None:
            raise RuntimeError(f"verified source annotation mismatch: {source_sha!r}")
    if not annotated_source_match:
        raise RuntimeError("no verified image signature carries the locked source annotation")

    attestation_output = cosign(
        "verify-attestation",
        "--type",
        "spdxjson",
        "--certificate-identity",
        IDENTITY,
        "--certificate-oidc-issuer",
        ISSUER,
        REFERENCE,
    )
    attestations = [
        json.loads(line) for line in attestation_output.splitlines() if line.strip()
    ]
    if not attestations:
        raise RuntimeError("Cosign returned no verified SPDX attestations")
    attestation_digest_match = False
    for envelope in attestations:
        payload = json.loads(base64.b64decode(envelope["payload"]))
        if payload.get("predicateType") != "https://spdx.dev/Document":
            continue
        for subject in payload.get("subject") or []:
            if (subject.get("digest") or {}).get("sha256") == DIGEST.removeprefix(
                "sha256:"
            ):
                attestation_digest_match = True
    if not attestation_digest_match:
        raise RuntimeError("verified SPDX attestation does not bind the locked digest")

    cosign(
        "verify-blob",
        "--bundle",
        str(BUNDLE),
        "--certificate-identity",
        IDENTITY,
        "--certificate-oidc-issuer",
        ISSUER,
        str(MANIFEST),
    )

    manifest = json.loads(MANIFEST.read_text())
    checks = {
        "image_signature_verified": True,
        "spdx_attestation_verified": True,
        "release_manifest_bundle_verified": True,
        "cosign_version_match": True,
        "image_digest_match": (manifest.get("image") or {}).get("digest") == DIGEST,
        "image_reference_match": (manifest.get("image") or {}).get("reference")
        == REFERENCE,
        "source_sha_match": (manifest.get("source") or {}).get("git_sha") == SOURCE_SHA,
        "source_ref_match": (manifest.get("source") or {}).get("ref")
        == "refs/heads/main",
        "repository_match": manifest.get("repository") == REPOSITORY,
        "workflow_identity_match": (manifest.get("build") or {}).get(
            "workflow_identity"
        )
        == IDENTITY,
        "certificate_identity_match": (manifest.get("verification") or {}).get(
            "certificate_identity"
        )
        == IDENTITY,
        "oidc_issuer_match": (manifest.get("verification") or {}).get("oidc_issuer")
        == ISSUER,
    }
    failed = sorted(name for name, passed in checks.items() if passed is not True)
    if failed:
        raise RuntimeError(f"release manifest field checks failed: {', '.join(failed)}")
    return {
        "status": "PASS",
        "reference": REFERENCE,
        "digest": DIGEST,
        "source_sha": SOURCE_SHA,
        "certificate_identity": IDENTITY,
        "oidc_issuer": ISSUER,
        "cosign_version": cosign_version,
        "verified_image_signatures": len(signatures),
        "verified_spdx_attestations": len(attestations),
        "release_manifest_sha256": "sha256:"
        + hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        "release_manifest_bundle_sha256": "sha256:"
        + hashlib.sha256(BUNDLE.read_bytes()).hexdigest(),
        "checks": checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    arguments = parser.parse_args()
    result = verify()
    if arguments.json:
        print(json.dumps(result, sort_keys=True))
        return
    for name in sorted(result["checks"]):
        print(f"MIDDLEWARE_ARTIFACT_{name.upper()}=PASS")
    print("MIDDLEWARE_ARTIFACT_PROVENANCE=PASS")


if __name__ == "__main__":
    main()
