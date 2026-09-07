# Source bundle release assets

The source-bundle publication path uploads only regular files directly under
`evidence/`. Runtime evidence is retained in its directory for the workflow's
artifact collection; a directory is not a GitHub release asset. The upload list
also excludes symlinks, preserves spaces in filenames, and fails if no regular
assets exist. Both new releases and replacement uploads use the same list.

This corrects the directory upload failure observed in Klyrow run
[34050892586](https://github.com/appolon1908-hue/klyrow.com/actions/runs/34050892586),
job 101534218305. Signing, source identity, provenance, and existing artifact
gates are unchanged. No release is published by the regression tests.

`tests/test_deploy_readiness_release_assets.py` executes the actual workflow
release block against a fake GitHub CLI for both create and upload paths.
Consumer repositories must update their workflow pin only after this change is
reviewed and merged into protected source. A successful source release is not
runtime activation or deployment approval.
