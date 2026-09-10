# Independent release-policy review

Required-check source hashes cannot approve themselves. The independent
`release-policy-review` workflow runs the validator from the protected `main`
commit, reads the candidate as Git data, and requires reviewer ID `77101516`
(`kazan555`) to approve the exact candidate commit. A changed closure literal,
validator, workflow, test input or other tracked file changes the bound source
fingerprint. Nothing is normalized out of this independent binding.

The workflow has read-only repository and pull-request permissions, uses hosted
runners and immutable checkout actions, and never imports or executes candidate
code. Candidate CI remains a separate check. Missing, stale, dismissed,
self-authored, substituted or non-collaborator approvals fail. Repository, PR,
base and head identities are checked before and after collecting reviews.

## Initial activation

This workflow cannot provide protected-base evidence for the PR that first adds
it: GitHub executes `pull_request_target` workflows from protected base source.
The initial change therefore requires the existing independent code-owner and
last-push approval gates on its exact commit. After that reviewed merge, add
`release-policy-review` from the GitHub Actions app (15368) to the existing
required checks, preserving every current protection. Run it against the next
PR and verify its base SHA, candidate SHA and independent review ID before
claiming the new gate is active. Unit-test success alone is not activation proof.

## Rechecking after approval

Rerun the protected-base workflow after a fresh review, or dispatch
`Independent release policy review` from `main` with the PR number. Updates to
either the PR head or protected base require a fresh matching run; changed PR
heads also require fresh independent approval. Never substitute the PR's own
validator, disable a required check, or treat a candidate-generated report as
independent evidence.

The additional branch check is PR-specific. Release-intent consumers must retain
their own exact workflow/run/job identity checks; a shared Actions app ID and
matching job name alone are insufficient evidence of workflow identity.

Reference: [GitHub pull_request_target semantics](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request_target).
