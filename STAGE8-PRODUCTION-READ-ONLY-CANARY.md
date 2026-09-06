# Stage 8 Production Read-only Canary

Captured: 2026-08-31 (Europe/Berlin)

```text
PRODUCTION_READ_ONLY_CANARY=FAIL
PRODUCTION_BUSINESS_WRITES=NOT_PROVEN_DISABLED
```

The canary was not deployed or executed because `STAGING_CERTIFIED=NO`. This is
the required fail-closed result; production was not used to compensate for an
uncertified staging release.

The canary also fails its entry invariant because effective
`LIVE_EMAIL_DELIVERY=true` was read from three running Klyrow production-email
containers and public SMTP port 25 remains active. No health, readiness,
version, capability, issuer/JWKS, auth, safe-read API, Kong, DB, Redis, OpenBao,
Prometheus, Loki, Tempo, Grafana, Blackbox, or rollback-readiness canary claim is
made.

```text
CANARY_DEPLOYED=NO
PRODUCTION_MUTATIONS_BY_THIS_RUN=0
UNEXPECTED_WRITE_TEST=NOT_EXECUTED
ROLLBACK_REQUIRED_BY_THIS_RUN=NO
```

PASS is impossible until staging is certified and every production business
write control is explicitly read back in the disabled state.
