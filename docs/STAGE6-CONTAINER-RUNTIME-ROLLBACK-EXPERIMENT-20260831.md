# Stage 6 container-runtime rollback experiment

Status: proposal only; not executed.

The host journal covers five days before the 25 August Docker/containerd
upgrade. It contains no retained seccomp errno 524 before 30 August, but all 101
currently running containers started after the upgrade, so no current container
provides a pre-upgrade exec control. Container creation succeeds while every
tested `docker exec` path fails during seccomp setup. This makes the bundled
runc change from 1.3.6 to 1.4.3 a testable hypothesis, not an established cause.

The experiment restores the exact six-package tuple installed before 25 August,
observes two minimal exec canaries, and immediately restores the current tuple
if either canary fails. APT simulation resolves both tuples without package
installation or removal.

This avoids a host reboot and requires no provider console. It is not
disruption-free: package maintainer scripts restart containerd/Docker, and all
101 running containers may be interrupted. The ten frozen workloads may restart
but must never be recreated or redeployed. Source approval alone does not
authorize execution.

No seccomp, privilege, capability, `no-new-privileges`, or read-only-root
control may be weakened. No migration, staging reconciliation, or production
deployment is part of the experiment.
