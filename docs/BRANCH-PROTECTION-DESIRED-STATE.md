# Observability/Security Branch Protection Desired State

## Observed gap

The repository inventory on 2026-08-29 confirmed that all 14 principal repositories contain `main`, `development`, `test`, `staging`, and `production`, but GitHub reported each persistent branch as unprotected.

This document defines desired state only. It does not claim that a GitHub ruleset or classic branch-protection rule has been applied.

## Universal controls

Every persistent branch must:

- reject deletion and non-fast-forward updates;
- reject direct pushes except through an independently reviewed break-glass procedure;
- require a pull request;
- require all review conversations to be resolved;
- dismiss stale approval after a new commit;
- require approval of the latest reviewable push by someone other than its author;
- require exact-head source validation and merge-result validation;
- require CODEOWNERS review for configuration, deployment, workflow, security, release and rollback files;
- require linear or controlled merge history according to repository policy;
- prohibit force pushes;
- prohibit bypass by automation except a separately reviewed, least-privilege release identity;
- treat a merge as source promotion only, never deployment authorization.

## Branch-specific policy

### `development`

Purpose: normal integration target.

Required:

- one independent approving review;
- exact-source CI;
- merge-result CI;
- secret scan;
- configuration/source validation;
- resolved threads.

### `test`

Purpose: automated and destructive-test candidate.

Required:

- all `development` controls;
- integration-test evidence;
- failure-path tests;
- synthetic-secret-only test fixtures;
- no live provider or business mutation.

### `staging`

Purpose: staging release-candidate source.

Required:

- all `test` controls;
- immutable source/image identity candidate;
- SBOM/provenance candidate;
- configuration checksums;
- rollback evidence;
- independently approved promotion PR.

### `production`

Purpose: production release-candidate source. This branch is not a deployment trigger.

Required:

- all `staging` controls;
- two-person approval for identity, edge, secrets, firewall, stateful storage or release-manifest changes;
- accepted cross-repository compatibility matrix;
- accepted security evidence;
- accepted upgrade/rollback/restore evidence;
- no unresolved release blocker;
- deployment remains disabled unless a later, separate change-management process authorizes the exact release manifest.

### `main`

Purpose: accepted source authority and release-tag origin.

Required:

- all `production` controls;
- pull request only from the accepted `production` candidate or a separately approved emergency rollback/hotfix path;
- exact release-manifest SHA binding;
- immutable version and image-digest evidence;
- signed or annotated release tag after merge;
- no workflow may automatically deploy solely because `main` changed.

## Required status-check classes

Repository-specific check names differ, but each repository must cover these semantic classes:

```text
validate-source
validate-merge-result
configuration-validate
unit-or-policy-tests
integration-or-contract-tests
secret-scan
supply-chain-or-image-policy
release-evidence-validate
```

Stateful components additionally require:

```text
backup-restore-policy
upgrade-rollback-policy
storage-retention-policy
```

Security/identity/edge components additionally require:

```text
authentication-authorization-policy
unsafe-exposure-denial
secret-redaction
protected-plan-review-apply-policy
```

## Ruleset application gate

Branch protection may be applied only after:

1. required check names are stable on pull requests;
2. the repository does not require a self-approval that the owner cannot satisfy;
3. CODEOWNERS resolve to active, authorized reviewers;
4. emergency recovery is documented;
5. the ruleset desired state is stored in the principal repository;
6. a dry-run or audit proves the rules will not deadlock source promotion;
7. the change does not dispatch a deployment.

## Temporary status

```text
PERSISTENT_BRANCHES_PRESENT=YES
PERSISTENT_BRANCHES_PROTECTED=NO
PROTECTION_DESIRED_STATE_DEFINED=YES
PROTECTION_APPLY_AUTHORIZED=NO
DEPLOYMENT_ENABLED=NO
```
