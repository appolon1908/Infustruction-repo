# Stage 6 seccomp maintenance runbook

Status: withdrawn without execution. Package-level causality must be tested
through the separately reviewed container-runtime rollback experiment before
any kernel or reboot proposal can be reconsidered.

The selected remediation is a single controlled boot from Ubuntu kernel
`5.15.0-187-generic` to the already installed `5.15.0-190-generic`. It does not
change Docker, runc, libseccomp, container configuration, images, networks, or
security options.

This host currently runs 101 containers. All ten Stage 6 frozen workloads are
present with `unless-stopped` restart policy. A host reboot therefore restarts
them even though it does not recreate or redeploy them. Merging the source PR
does not authorize that disruption. Execution requires an owner-approved exact
plan fingerprint, a declared maintenance window, and working provider-console
access.

## Before the window

1. Capture sanitized `docker inspect` identity, image digest, start time,
   restart count, health, networks, and restart policy for all 22 locked and ten
   frozen workloads.
2. Verify both target and rollback kernel image/initrd pairs exist.
3. Record Docker, runc, containerd, libseccomp, kernel, bootloader, filesystem,
   and database-backup state.
4. Verify console access can select both kernel entries.
5. Record the running container set and flag every `no` restart policy for
   manual recovery. Do not change a restart policy in this change.
6. Confirm external business writes remain disabled for the scoped Stage 6
   path. Klyrow/Postal remains out of scope and untouched.

## Change

Select `Ubuntu, with Linux 5.15.0-190-generic` as the next boot only, then
perform one host reboot inside the approved window. Do not run package upgrades,
Docker restarts, Compose operations, migrations, or reconciliation in the same
change.

## Acceptance

After the host returns, verify the gates declared in
`operations/stage6-host-seccomp-maintenance.yaml`. The decisive canaries are:

```text
docker exec codestra-n8n-staging-n8n-1 true
docker exec codestra-identity-staging-keycloak-staging-1 true
```

Both must succeed with the default seccomp profile. `seccomp=unconfined`,
privileged mode, capability changes, writable-root changes, and any other
security relaxation are prohibited.

## Rollback

If the host, Docker, locked workloads, or exec canaries fail, use the provider
console to select `Ubuntu, with Linux 5.15.0-187-generic` and reboot once. Do not
attempt application repair, image replacement, migration, or workload
recreation inside the kernel rollback window.

## Following changes

Only after this change passes may separate reviewed changes verify/remediate
Prometheus health and restart-count alerting, re-run Stage 6 preflight, and
begin controlled staging reconciliation. Production remains unauthorized.
