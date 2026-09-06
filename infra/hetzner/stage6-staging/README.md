# Isolated Stage 6 staging host

This directory is the only provisioning authority for
`codestra-stage6-staging-01`. It creates the isolated
`codestra-stage6-staging-net`, one application runtime host, and a separate
staging-only controlled egress gateway. It does not deploy applications or
production credentials.

## Protected inputs

The `stage6-infrastructure-provisioning` GitHub environment must be restricted
to `main`, prevent self-review, and require a trusted reviewer where the plan
supports it. It requires these names:

Secrets:

- `HETZNER_CLOUD_TOKEN` — project-scoped token permitted to manage only the
  reviewed Stage 6 network, runtime, gateway, and firewalls.
- `TF_STATE_ACCESS_KEY` and `TF_STATE_SECRET_KEY` — credentials for the isolated
  state bucket only.

Variables:

- `TF_STATE_BUCKET`, `TF_STATE_ENDPOINT`, `TF_STATE_REGION`.
- `STAGE6_TFVARS_JSON` — reviewed non-secret values matching `variables.tf`.

Dynamic GitHub, GHCR and package endpoints are not represented by guessed
public CIDRs. The runtime host can reach public HTTP(S) only through the gateway
private address. Squid applies an explicit FQDN/port allowlist, rejects arbitrary
destinations, and logs decisions without request credentials.

`known_internal_production_deny_cidrs` includes `37.27.128.39/32`,
`65.109.65.169/32`, and the Git-recorded `10.40.0.0/24` production VLAN.
Terraform rejects private-network overlap and gateway nftables denies these
authorities. External SaaS providers remain excluded by default rather than
being modeled as unstable CIDR lists.

The runtime uses the gateway as its private DNS and NTP boundary. Unbound
performs DNSSEC-validating recursion only on the gateway; workloads have no
direct public DNS path. Chrony on the gateway uses the Git-reviewed
`ntp.ubuntu.com` authority, and workloads have no direct public NTP path.
`approved_ssh_source_cidrs` remains a required owner-provided VPN, bastion, or
operator allowlist; global SSH is rejected.

An owner-reviewed plan from an earlier protected plan-only run is applied only
through `stage6-apply-reviewed-plan.yml`. Its first protected job verifies the
source run/SHA, GitHub artifact digest, internal checksums, exact eight-resource
policy, and remote-state lineage/serial. A separate protected apply job repeats
those checks and applies only the downloaded binary plan; it never regenerates
a plan or reads tfvars.

## Plan and apply

Pull requests run exact-head and merge-result formatting, validation, static
security checks, and a no-refresh plan using documentation-only TEST-NET
values. No push applies infrastructure.

After merge and protected-input review, manually dispatch `Stage 6 isolated
staging host` from the exact protected `main` SHA with confirmation
`APPLY_STAGE6_ISOLATED_HOST`. A protected job first generates a checksummed
plan against remote state and publishes it for review. A separate protected
apply job consumes only that saved plan; stale state fails closed. It creates
exactly the reviewed runtime and gateway plus their new network authority and
refuses delete actions.

## Baseline and seccomp acceptance

Cloud-init creates separate deploy/admin identities, disables root/password
SSH, keeps deployment users out of the Docker group, and installs Docker from
the signed Ubuntu archive. Runtime packages are held after installation until
a separately reviewed update. Applications remain absent.

Before application deployment, capture exact package versions and prove:

1. `docker info` reports the default seccomp profile and no TCP Docker API;
2. a representative container has `Privileged=false`, read-only rootfs and
   `no-new-privileges=true`;
3. `docker exec <container> true` succeeds;
4. Klyrow/Postal and all production provider routes are absent or denied.

## Rollback and destroy

`prevent_destroy` blocks accidental deletion. Rollback is a reviewed revert to
the previous protected commit followed by a protected plan/apply. Destruction
requires a separate PR removing `prevent_destroy`, a backup/state review, and a
manual protected apply. Never use `tofu destroy` from a workstation.

If bootstrap fails, do not attach production credentials or reuse production
volumes. Recreate only after a reviewed fix and preserved remote-state audit.
