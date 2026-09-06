# Stage 6 staging network isolation evidence

Status: `NOT_RUN_HOST_NOT_CREATED`

The design is deny-by-default. It allows SSH only from reviewed operator/VPN
CIDRs, staging-private dependencies on reviewed CIDRs, approved DNS/NTP, and
explicit package/GitHub/GHCR bootstrap CIDRs. There are no public PostgreSQL,
Redis, Docker API, or internal application ports.

Apply also requires a reviewed, nonempty `forbidden_production_cidrs` inventory
for Klyrow, Postal and live providers. A lifecycle precondition rejects every
allow/deny CIDR overlap before resource creation.

The protected apply values must prove the selected private network contains no
Klyrow, Postal, or unrelated production node and has no production route.
Effective runtime negative probes must subsequently establish:

- `STAGING_TO_KLYROW_EMAIL_WRITE=DENIED`
- `STAGING_TO_KLYROW_SMTP_SUBMISSION=DENIED`
- `STAGING_TO_KLYROW_PROVIDER_WRITE=DENIED`
- `STAGING_TO_KLYROW_GATEWAY_WRITE=DENIED`

No real email or provider write may be used as a probe.
