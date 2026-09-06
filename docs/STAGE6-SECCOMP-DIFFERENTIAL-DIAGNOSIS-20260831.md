# Stage 6 seccomp differential diagnosis

Status: read-only evidence; no remediation executed.

## Result

The Docker/containerd/runc version tuple is not sufficient to reproduce the
host-wide `docker exec` failure. A disposable Ubuntu 22.04 guest with a 5.15
kernel, the same libseccomp package, Docker 29.7.2, containerd 2.3.3, and runc
1.4.3 passed both a default-profile exec and an exec with the production-style
hardening controls (`no-new-privileges`, all capabilities dropped, read-only
root filesystem). The off-host gate therefore remains negative.

The strongest host-only difference is accumulated unreaped health-check
children:

| Property | Runtime host | Disposable guest |
| --- | ---: | ---: |
| Kernel | 5.15.0-187-generic | 5.15.0-190-generic |
| libseccomp2 | 2.5.3-2ubuntu3~22.04.1 | 2.5.3-2ubuntu3~22.04.1 |
| Docker | 29.7.2 | 29.7.2 |
| containerd | 2.3.3 | 2.3.3 |
| runc | 1.4.3 | 1.4.3 |
| LSMs | lockdown, capability, landlock, yama, AppArmor | same |
| Available seccomp actions | kill, trap, errno, user notification, trace, log, allow | same |
| `ssl_client` zombies | 32,048 | 0 |
| `bpf_jit` mappings observed at T1 | 32,587 | clean disposable baseline |
| `bpf_jit` mapped bytes observed at T1 | 661,848,064 | clean disposable baseline |
| configured `net.core.bpf_jit_limit` | 528,482,304 | clean disposable baseline |

The runtime values are point-in-time read-backs and do not authorize a runtime
change. Vmalloc totals are diagnostic correlation, not by themselves proof of
kernel accounting or causation.

## Ten-minute burn-rate measurement

The required 605-second read-only sample produced:

```text
BPF_MAPPINGS_T0=32584
BPF_MAPPINGS_T1=32587
BPF_JIT_BYTES_T0=662261760
BPF_JIT_BYTES_T1=661848064
MAPPINGS_PER_HOUR=17.851240
BYTES_PER_HOUR=-2461662
HOURS_TO_MODULES_LEN=UNBOUNDED_NO_POSITIVE_BYTE_BURN
```

Mapping count rose by three while mapped bytes decreased by 413,696. The sample
therefore does not support a positive byte burn or a finite exhaustion deadline.
The earlier approximately 1.19 GB observation matched both `bpf_jit` and
`bpf_prog` lines; it is not interchangeable with the mission's `bpf_jit`-only
measurement. The zombie leak remains a demonstrated source defect and must be
fixed, but authorization must not rely on the disproved one-day estimate.

## Ownership of the leaked children

The zombies have only two parents:

- 16,025 children of `codestra-n8n-internal-proxy` PID 1;
- 16,023 children of `codestra-odoo-internal-proxy` PID 1.

Both parents are Caddy processes started on 25 August. Their compose definitions
do not enable an init/reaper process. Every 30 seconds their Docker health check
runs BusyBox `wget` over TLS. Its `ssl_client` helper becomes an orphan adopted
by Caddy, and Caddy does not reap it. Every sampled zombie remains in seccomp
mode 2 with one attached filter.

This gives a coherent leading hypothesis: repeated health-check execs leaked
seccomp-filtered zombies until new exec-path filter installation began returning
`ENOTSUPP`. It explains why container creation originally succeeded, why the
failure appeared later, and why the clean guest cannot reproduce it from the
package tuple alone. It is not yet a mutation-tested causal proof.

The host kernel confirms the errno mechanism: `CONFIG_BPF_JIT_ALWAYS_ON=y` and
`net.core.bpf_jit_enable=1`. With no interpreter fallback, failure to JIT a new
filter is returned as `ENOTSUPP` (524). A separately authorized, non-persistent
increase of `net.core.bpf_jit_limit` can therefore serve as a reversible causal
canary. The exact proposal and rollback are recorded in
`operations/stage6-bpf-jit-limit-canary.yaml`; merging its source does not
authorize execution.

The canary ceiling is `1,400,000,000`, below the fixed x86-64 module mapping
region (`MODULES_LEN=1,593,835,520`). It is a short bridge measured in hours at
the observed allocation rate, not remediation and not additional address
space. Raising the sysctl above `MODULES_LEN` cannot make that address space
available.

## Reviewed remediation path

1. Fix the authoritative compose sources for both internal proxies by enabling
   an init/reaper (`init: true`) and bounding PIDs. Validate that the selected
   health-check client does not orphan helpers.
2. Complete the required isolated database restore verification before any
   runtime mutation.
3. Obtain exact-change approval to recreate only these two proxies, one at a
   time. Confirm they are not among the ten frozen workloads before approval.
4. After each change, verify proxy liveness externally, zombie count, BPF/JIT
   resource release, default-seccomp `docker exec`, and health recovery.
5. Roll back to the recorded proxy image/configuration if either proxy fails its
   external check. Do not weaken seccomp, privilege, capabilities,
   `no-new-privileges`, or the read-only filesystem.

A package downgrade and kernel change are not supported by this differential.
No container was executed into, stopped, restarted, recreated, or modified while
collecting this evidence.

```text
SECCOMP_REPRODUCED_OFFHOST=NO
DEFAULT_PROFILE_EXEC=PASS
HARDENED_PROFILE_EXEC=PASS
PACKAGE_TUPLE_CAUSALITY=NOT_SUPPORTED
ZOMBIE_FILTER_EXHAUSTION=LEADING_HYPOTHESIS_NOT_YET_MUTATION_PROVEN
RUNTIME_MUTATION=NO
PRODUCTION_CHANGED=NO
```
