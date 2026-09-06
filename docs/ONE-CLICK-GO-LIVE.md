# One-click isolated staging and read-only production canary

## Operator button

After merge into protected `main`, open:

`https://github.com/appolon1908-hue/Infustruction-repo/actions/workflows/one-click-go-live.yml`

Choose **Run workflow**, retain `GO_LIVE_READONLY`, and keep `canary_percent` greater than zero and no more than `1`.

## Purpose

This workflow is a small operator wrapper around the existing permanent authority:

`.github/workflows/full-readonly-release-chain.yml`

It does not duplicate deployment logic and does not accept an arbitrary workflow name, branch, host, image, command, or environment. It dispatches the exact protected-main child workflow and waits for the exact run to finish.

The child authority performs, in order:

1. policy validation;
2. exact-digest staging deployment on the isolated staging runner;
3. staging certification and recovery-point evidence;
4. rollback rehearsal to the previous exact release and restoration of the candidate;
5. a production GET/HEAD-only canary no greater than 1%;
6. sanitized evidence publication.

## Required protected resources

The existing child workflow requires:

- protected environment `staging-readonly`;
- protected environment `production-readonly-canary`;
- self-hosted runner labels `codestra-staging` and `codestra-production-canary`;
- exact candidate and endpoint manifests;
- read-only bearer and metrics credentials;
- GHCR read-only credentials;
- Restic backup repository and password-file bindings.

Any missing value, digest mismatch, failed staging check, failed rollback, write attempt, or canary percentage over 1 causes a hard failure.

## Platform orchestration

`appolon1908-hue/codestra-production-platform` supplies an optional correlation identifier when it launches this workflow. Operators may also run this infrastructure button directly.

## Safety boundary

The wrapper never calls SSH, Docker Compose, OpenTofu apply, or a production web-traffic activation command itself. It only invokes the reviewed child release authority. Live writes, messages, calls, payments, withdrawals, and external-provider execution remain disabled.
