# Stage 6 Scoped Runtime Read-back

Authority: issue #16 approved scope; source-lock merge `ef78ace25c6c322cc949166c26a6c8ad75cc35f0`.

The read-only inspection targeted exactly the 22 locked staging workloads on
`65.109.65.169`. It read container identity, immutable image ID, running/health
state, and only the eight approved safety-variable names and values. It did not
dump environments or secrets and performed no runtime mutation.

```text
SCOPED_WORKLOADS=22
PRESENT=22
DIGEST_MATCH=22
RUNNING=22
SAFETY_APPLICABLE=17
SAFETY_COMPLETE=0
SAFETY_UNSAFE_VALUES=0
UNHEALTHY=6
SCOPED_RUNTIME_READBACK=FAIL
RUNTIME_MUTATION=NO
```

Seven required safety keys are absent from all 17 applicable workloads.
`EXTERNAL_DELIVERY_ENABLED` is absent from 12 of 17. No inspected safety value
was explicitly enabled, but absence is fail-closed and cannot prove the Stage 6
path disabled.

The six non-healthy checks are the Middleware callback/API and all four n8n
runtime processes. All 22 containers remain running and digest-matched.

Ten applicable workloads are frozen by the authoritative source lock. They
must not be recreated merely to add environment variables. A separately
reviewed enforcement design is required before the safety gap can be closed.

Klyrow/Postal remains `OUT_OF_SCOPE_ACTIVE_PRODUCTION_DO_NOT_TOUCH`. Production,
staging apply, external writes, migrations, restarts, and workflow dispatch
remain unauthorized.
