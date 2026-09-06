# Codestra Observability Staging Evidence Contract

## General evidence rules

Every evidence record must identify the repository, exact ref, exact 40-character source SHA, workflow or operator procedure, UTC timestamp, environment, evidence owner, and SHA-256 checksum. Evidence must be reproducible, redacted, and bound to the unchanged release candidate.

Git may contain checksums, digests, public certificates, schemas, and redacted summaries. Git must not contain passwords, API keys, tokens, private keys, database URLs, broker or exchange credentials, client secrets, unseal material, or root tokens.

## Source evidence

For every authority record:

- repository and canonical hostname;
- accepted source stage and ref;
- exact source SHA;
- exact-head workflow names, run IDs, and conclusions;
- merge-result workflow names, run IDs, and conclusions;
- pull request number and merge SHA;
- unresolved review-thread count;
- confirmation that runtime activation remains false.

## Supply-chain evidence

Each component requires:

- an **immutable OCI digest** and complete immutable image reference;
- an **SBOM digest** for SPDX or CycloneDX output;
- a **provenance digest** tied to source, builder, dependencies, and build parameters;
- **signature verification** evidence identifying the signer and trust policy;
- a SHA-256 configuration checksum;
- vulnerability scan output with severity policy and explicit disposition;
- license and dependency policy results;
- proof that no mutable tag or unpinned base image remains.

Digest values use `sha256:<64-lowercase-hex>`.

## Server and network evidence

Read-only inventory must include:

- operating system, kernel, capacity, runtime, storage driver, and time synchronization;
- current listeners, Docker networks, forwarding policy, and firewall state;
- current Caddy validation and configuration checksum;
- current service inventory and approved shared-host exceptions;
- available backup capacity and rollback paths;
- DNS and TLS observations.

The inventory package must prove that it did not collect secret values.

## Backup and recovery evidence

Required evidence includes:

- pre-change backup identifiers and checksums;
- stateful object counts and sizes;
- **isolated restore validation** results;
- restore duration and integrity checks;
- documented recovery point and recovery time;
- component rollback commands and prerequisites;
- full-stack **rollback rehearsal** results;
- post-rollback health and data-integrity checks.

## Identity and edge evidence

Keycloak evidence requires an exact desired-state plan, before and desired hashes, repository SHA, **unchanged-plan hash**, independent reviewer identity, review timestamp, and proof that apply was not dispatched.

Caddy evidence requires a rendered configuration, validation result, before/after diff, route and header inventory, rollback file, and proof that reload was not performed.

Firewall evidence requires a rendered rule set, before/after diff, SSH lockout analysis, Docker forwarding analysis, rollback rules, and proof that no rules were applied.

OpenBao evidence requires configuration review, storage/seal decision records, recovery and custody design, policy tests, and proof that initialization and unseal were not performed.

## Disposable-lab evidence

The laboratory record must include:

- exact image and configuration digests;
- test topology and isolated networks;
- startup, readiness, liveness, and shutdown results;
- mTLS and authorization negative tests;
- business-isolation negative tests;
- redaction fixtures and results;
- upgrade, backup, restore, and rollback results;
- resource observations;
- confirmation that no external delivery, business write, provider write, financial action, or trading action occurred.

## Approval evidence

Staging approval must reference the unchanged manifest digest, all component digests, every open blocker, the deployment and rollback procedures, the change window, the responsible operator, and the independent approver. Any source, image, configuration, plan, or evidence change invalidates the approval.
