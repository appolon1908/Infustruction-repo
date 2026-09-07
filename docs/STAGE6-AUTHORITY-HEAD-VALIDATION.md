# Stage 6 authority-head validation

This read-only gate compares every locked repository revision with that repository's
live `refs/heads/main`. A successful comparison is **not** artifact attestation,
runtime read-back, deployment approval, or production authorization. The validator
never rewrites the lock, image digests, rollback pins, or activation gates.

## Run

```sh
python scripts/validate_stage6_authority_heads.py
python scripts/validate_stage6_authority_heads.py \
  --lock STAGE6-SOURCE-LOCK.yaml \
  --json-report /tmp/stage6-authority-heads.json
```

Exit status is `0` only when every repository matches, `1` for drift or unavailable
verification, and `2` for invalid input or a report I/O failure. The optional JSON
report records the SHA-256 of the exact input lock, expected/observed revisions,
per-component results, and match/failure counts. It is diagnostic evidence, not a
replacement source lock. Results are sorted and reports are written atomically.
The report path cannot overwrite the input lock.

CI retains the strict nonzero authority check and copies its diagnostic report to
the job summary even after a failure. It does not use `continue-on-error` or treat
private repositories, transient errors, or drift as successful validation. A later
artifact-verification step skipped because the authority gate failed is not PASS.

## Interpret failures

| Status | Required action |
| --- | --- |
| `DRIFT` | Reconcile the observed main revision with reviewed source, artifact/config evidence, resolved lock and checksums. Do not just replace a SHA while retaining evidence for another build. |
| `NOT_FOUND_OR_INACCESSIBLE` | Check the exact repository/ref and credential permissions. GitHub's 404 does not distinguish a missing resource from a private resource the caller cannot access. |
| `AUTHENTICATION_FAILED` / `ACCESS_DENIED` | Verify the trusted read-only credential's validity and repository access. |
| `RATE_LIMITED` | Respect GitHub's reset/retry-after window before rerunning. The validator does not immediately retry a rate-limit response. |
| `NETWORK_ERROR` / `HTTP_ERROR` | Inspect connectivity/service health. Transient network errors and HTTP 500/502/503/504 receive at most three attempts with bounded backoff. |
| `INVALID_RESPONSE` / `REDIRECT_REJECTED` | Investigate the API or repository authority; do not accept a malformed ref, non-commit object, invalid SHA, or redirect. |

Malformed/empty locks, duplicate YAML keys, invalid component/repository names and
non-full revisions fail before requests are sent. Raw API bodies, parser source
lines and exception text are not copied into diagnostics. Requests target only
the canonical GitHub API ref endpoint; redirects are disabled.

## Private repositories and credential boundaries

The only optional credential variable is `STAGE6_SOURCE_READ_TOKEN`. There is no
implicit `GITHUB_TOKEN` fallback. A credential must already have read access to
every private repository in the lock. The code does not create credentials or
grant repository permissions.

**Never inject a cross-repository token into a PR-controlled job.** Keep the PR
workflow secret-free. Authenticated verification must execute reviewed code in a
separately trusted runner/workflow boundary, with least-privilege repository read
access supplied by its operator. A script cannot establish that trust merely by
checking an environment flag. Do not switch to `pull_request_target` and execute
PR code to work around missing credentials. This change does not provision that
external credential boundary or declare the existing stale lock reconciled.

## Offline regression tests

```sh
python -m unittest discover -s tests -p test_stage6_authority_heads.py -v
python -O -m unittest discover -s tests -p test_stage6_authority_heads.py -v
```

Both source-head and merge-head regression jobs run these tests. Network calls
are mocked; no credentials or runtime access are required. The original
`authority_head(component, definition)` tuple/exception interface is retained.

API behavior references: GitHub REST API troubleshooting and Actions security
reference, https://docs.github.com/en/rest/using-the-rest-api/troubleshooting-the-rest-api
and https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target.
