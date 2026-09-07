# Signed provenance integrity — issue #99

The prior reusable publisher generated a SLSA v1 document but used Cosign's
`slsaprovenance` alias, which selects v0.2. In pinned Cosign v3.1.2, unknown v1
fields are discarded on that path. A valid signature on an empty predicate does
not attest the source, builder, or run. The unsigned sidecar cannot replace it.

The publisher now uses the explicit `https://slsa.dev/provenance/v1` URI for
both attestation and verification. Cosign v3.1.2 preserves the entire JSON
predicate for that URI, including empty optional maps/lists. Its enclosing
in-toto statement remains v0.1; that is distinct from the SLSA predicate version.

After the existing cryptographic identity/issuer checks succeed, an embedded
semantic gate binds the exact image repository/digest, complete generated
predicate, source repository/SHA, resolved source dependency, workload class,
artifact strategy, builder URL and run ID/attempt. It rejects empty, malformed,
wrong-type, duplicate-key and mismatched evidence before any OCI deploy-ready
output or manifest. JSON object, array and JSONL verified outputs are supported.
The helper is embedded because reusable workflows check out their caller, not
this repository. No consumer-local helper is assumed.

## Validation

`python -m pytest -q tests/test_reusable_provenance.py` exercises the actual
embedded generator and validator. The local semantic cases do not verify
cryptographic signatures. The serialization case requires
`CODESTRA_COSIGN_OUTPUT` and is mandatory in `test-provenance-integrity.yml`.
That read-only workflow tests both the exact source head and current merge
result. It checks out Cosign v3.1.2 at
`193d2153431f8bb0d945a4c1ee721872f73add67`, uses its real `GenerateStatement`
implementation and committed Go dependency sums, and proves both the repaired
round-trip and the former lossy alias. It creates no key and signs/publishes
nothing. Existing source, secret, vulnerability and release gates remain.

Upstream implementation: `sigstore/cosign`, `pkg/cosign/attestation/attestation.go`
at the source commit above (`GenerateStatement`, `generateCustomPredicate`,
`generateSLSAProvenanceStatementSLSA02`). Existing release binary version and
checksum remain unchanged.

## Rollout and rollback

This source change does not repair old signed artifacts, authorize deployment,
or certify any runtime. Keep issue #99 open until independent review, required
CI, protected merge, exact consumer-pin updates and new protected publisher
artifacts establish valid signed provenance. Start with the incident's
VICIdial consumer; inventory other pinned callers before changing them.
Do not point consumers at an unreviewed feature SHA or rerun a deployment to
bypass this order. Retain all old incident evidence unchanged. Roll back only
through a reviewed source revert, keeping release acceptance blocked for any
artifact with missing or mismatched provenance. No identity regex, signing
trust, environment approval, image digest, source lock, secret, runtime or
external-delivery switch is changed here.
