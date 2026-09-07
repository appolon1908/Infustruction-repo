# Server B observability authority

This directory is the host-specific evidence package for the fourteen-component
canonical observability mission on `37.27.128.39`. Generate and validate its sanitized
evidence with:

```bash
python3 hosts/37.27.128.39/observability/generate_evidence.py
python3 hosts/37.27.128.39/observability/validate.py
```

The canonical component set is `config/observability/repository-registry.v1.json`.
This package must include Alertmanager and PostgreSQL Exporter alongside the
original twelve products. Their missing protected-head and runtime observations
are `NOT_CAPTURED`, not invented source SHAs or absence claims. The existing
September 2 observations remain historical; regeneration does not run probes.

The current record is deliberately fail-closed. It commits no credential,
private key, recovery material, environment file, runtime state, or customer
data. No deployment may consume this authority until `activation_allowed` is
true in a reviewed protected release and all referenced source/image locks are
exact and immutable.

The blocked, proposed future release layout is recorded in `release-layout.json`.
Direct edits beneath `/opt/codestra/current`, live Compose/configuration paths,
or application source directories are forbidden.

CI compares tracked changes and untracked generated files, then checks both
normal and optimized Python. Every required generated file must already be
tracked; regeneration cannot hide a deleted artifact. `release-layout.json`
is parsed directly, and its `activation_allowed` field must be the boolean
`false`, consistent with the failed gates. A future activation requires a
separate reviewed implementation and evidence change, not editing one field.
