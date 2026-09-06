# Stage 6 Host-wide Seccomp Evidence and Remediation Proposal

Status: read-only evidence and proposal; not applied.

## Reproduction

Both an in-scope workload and a container outside the 22-workload set fail on
the minimal command `true` before command execution:

```text
codestra-n8n-staging-n8n-1: OCI runtime exec failed; unable to init seccomp; errno 524
codestra-identity-staging-keycloak-staging-1: OCI runtime exec failed; unable to init seccomp; errno 524
```

This confirms a host-wide Docker/runc/libseccomp/kernel interaction rather than
an application health failure.

```text
libseccomp2=2.5.3-2ubuntu3~22.04.1
runc=1.4.3 (libseccomp 2.5.3)
docker-ce=29.7.2
kernel_running=5.15.0-187-generic
kernel_installed_not_running=5.15.0-190-generic
```

## Ranked remediation proposal

1. Test and install a vendor-supported, signed libseccomp2 update newer than
   2.5.3 in an isolated matching canary. The configured Jammy repositories do
   not currently offer one, so no package source may be added without review.
   Preserve the current package and apt source metadata for downgrade.
2. In an approved maintenance window, boot the already-installed Ubuntu kernel
   5.15.0-190 and run minimal exec/health canaries before accepting it. Rollback
   selects 5.15.0-187 in the bootloader and reboots under the same window.
3. Only if the first two paths fail, canary a Docker/runc/containerd version
   proven compatible with kernel 5.15 and the enforced seccomp profile. Pin the
   exact passing packages. Preserve and verify the current 29.7.2/containerd
   packages for rollback before changing anything.

Every option requires backup, console access, a maintenance window, explicit
approval, and post-change checks on both scoped and non-scoped canaries.
`seccomp=unconfined`, privileged mode, capability relaxation,
`no-new-privileges` removal, writable-root changes, and security-profile
weakening are prohibited.
