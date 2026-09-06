# Infrastructure repository-name migration record

```text
REPOSITORY_ID=1350724865
CURRENT_FULL_NAME=appolon1908-hue/Infustruction-repo
TARGET_FULL_NAME=appolon1908-hue/Codestra-Infrastructure
STATUS=PREPARED_NOT_RENAMED
RUNTIME_CRITICAL=YES
CURRENT_RUNTIME_STATE=REQUIRES_PRE_CUTOVER_DISCOVERY
```

The approved target corrects the legacy spelling and preserves this repository's role as the Codestra infrastructure, topology, GitOps, backup and recovery, observability-composition, and release-governance authority.

## Protected-check availability

The `source-authority-matrix` workflow runs for every pull request because its
`validate-source` and `validate-merge-result` jobs are required `main` branch
protection contexts. Do not add a pull-request path filter to that workflow: a
filtered event leaves both required checks pending for out-of-filter changes.

Rollback is the protected revert of the workflow and its regression test only
after branch protection has been migrated to replacement checks that run for
every pull request. Never remove the checks first or leave the branch without an
exact-head source and merge-result gate.

## Operational rule

The current full name remains authoritative for checkouts, workflows, source locks, deployment manifests, server remotes, GitHub Apps, webhooks, packages, and links until an authorized rename is completed and repository ID `1350724865` is read back at the target name.

The local machine-readable authority is [`config/repository-name-aliases.v1.json`](config/repository-name-aliases.v1.json). Validate it with:

```bash
python3 scripts/validate_repository_name_aliases.py
```

## Required pre-cutover evidence

Inventory and preserve without secret values:

- default-branch and release SHAs, visibility, history, issues, pull requests, tags, and releases;
- rulesets, branch protection, required checks, CODEOWNERS, and Environments;
- Actions and reusable workflows plus the exact merge, release-dispatch, workflow-dispatch, and deployment-dispatch state being frozen;
- every active source lock, BOM, image lock, rollback manifest, deployment reference, infrastructure module source, and submodule;
- deploy-key fingerprints, GitHub Apps, webhooks, and Pages state;
- GHCR and package identities, SBOMs, provenance, attestations, and image labels;
- every developer, CI, and server checkout and current Git remote;
- every downstream repository, workflow, automation, release process, and deployment consumer using the current slug.

Discover runtime state immediately before cutover:

- when reviewed staging or production workloads consume this repository, record their exact current and rollback image digests and source SHAs;
- when no deployed consumer exists for a mapping, record `CURRENT_RUNTIME_STATE=NOT_DEPLOYED`, `DEPLOYED_IMAGE_DIGEST=N/A`, and `RUNTIME_DIGEST_UNCHANGED=N/A`;
- do not fabricate runtime evidence.

Dated release, incident, certification, and source-lock evidence remains unchanged. New current-state manifests supersede it; history is not rewritten.

## Rename sequence

1. Merge stable-ID alias awareness into all active consumers.
2. Freeze infrastructure merges, releases, workflow dispatches, and deployment dispatches; record the prior state.
3. Prove all existing production and staging deployments use exact SHAs and immutable digests, or explicitly record `N/A` where no deployment exists.
4. Rename only this GitHub repository through an authorized owner or administrator action.
5. Before updating any consumer, require the same repository ID, visibility, default branch and protected SHA, history, issues, pull requests, tags, releases, rulesets, CODEOWNERS, required checks, Actions, reusable workflows, Environments, packages, GHCR identities, attestations, deploy keys, GitHub Apps, webhooks, and Pages state.
6. Stop and roll back if any inventoried integration is missing, weakened, or unresolved.
7. Update only mutable active source locks, workflow references, module sources, package metadata, badges, server remotes, and current documentation. Preserve dated evidence.
8. Run every infrastructure validator, source-lock check, package and workflow-resolution check, server-remote check, and deployment preflight without applying runtime changes.
9. When deployments exist, prove running images, networks, databases, secrets, and traffic are unchanged. Otherwise retain the explicit `N/A` runtime result.
10. Rehearse rollback to the prior slug.
11. After success or validated rollback, restore the exact recorded merge, release-dispatch, workflow-dispatch, and deployment-dispatch state. Do not leave the infrastructure authority frozen.

## Rollback

Rollback restores the prior slug when safe, restores mutable references and remotes from the checksum-bound pre-change packet, repeats the complete repository, workflow, package, deploy-key, GitHub App, webhook, source-lock, downstream-consumer, server, and runtime readback, verifies no configuration or production effect occurred, and then restores the recorded freeze state. A successful rollback must not leave normal infrastructure operations disabled.

Required metadata-only result:

```text
POST_RENAME_INTEGRATION_READBACK=PASS
ACTIONS_REQUIRED_CHECKS=PASS
PACKAGES_GHCR_ATTESTATIONS=PASS|N/A
DEPLOY_KEYS_APPS_WEBHOOKS=PASS|N/A
SOURCE_LOCKS_AND_BOMS=PASS
DOWNSTREAM_CONSUMERS=PASS
SERVER_REMOTES_UPDATED=<n>/<total>
CURRENT_RUNTIME_STATE=DEPLOYED|NOT_DEPLOYED
DEPLOYED_IMAGE_DIGEST=<immutable-digest>|N/A
RUNTIME_DIGEST_UNCHANGED=PASS|N/A
MERGES_UNFROZEN=PASS
RELEASE_DISPATCH_UNFROZEN=PASS|N/A
WORKFLOW_DISPATCH_UNFROZEN=PASS|N/A
DEPLOYMENT_DISPATCH_RESTORED=PASS|N/A
ROLLBACK_UNFREEZE=PASS|N/A
WORKLOADS_RESTARTED=0
IMAGES_REBUILT=0
CONFIG_APPLIES=0
DATABASE_MIGRATIONS=0
SECRETS_ROTATED=0
DNS_CHANGES=0
PRODUCTION_TRAFFIC_CHANGED=NO
```

The account-wide runbook is maintained in `appolon1908-hue/documentaions` until the documentation repository completes its own controlled rename.
