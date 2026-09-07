# SentinelX Server B installation runbook

## Authority and current decision

This runbook covers only the SentinelX Linux agent on the VICIdial/Asterisk
host at `65.21.67.207`. It does not authorize telephony activation, Ralph
account creation, business writes, firewall changes, SSH changes, or changes
to the `codestra-admin` sudo policy.

`INSTALLATION_AUTHORIZED=false`

The 2026-09-05 review is historical, **fail-closed** evidence:

- `FINAL_STATUS=BLOCKED_ROOT_ACCESS` records the access observed on that date,
  not a fresh assertion about present root access;
- the reviewed SentinelX schema has no supported switch that disables
  `script_run` or inline/chunked uploads, so the accompanying policy remains a
  blocked review template, not an approved production policy;
- no SentinelX installation, enrollment, service creation, or telephony
  configuration change was performed by that review or this source repair.

See `evidence-20260905.yaml` for the unchanged sanitized historical values.
Restored root access alone does not clear the policy and supply-chain gates.

## Reviewed sources

The historical review used the owner-specified public sources:

- `https://get.sentinelx.app/install.sh`
- `https://github.com/pensados/sentinelx-cloud-installer`
- `https://github.com/pensados/sentinelx-cloud-core`

The endpoint installer downloaded on both the target and review host had
SHA-256 `56f5da769567a471ccf798fa11105f747738f26ee48d0d106922922e56d3acb9`
and passed `bash -n`. It is the exact `install.sh` blob at installer commit
`ee8628482a83959b9e1a7b99d1082f32b49e4196` (2026-08-14). The installer
`main` observed during that review was `e637b12c35e40a81fef3171394fe863235575dfb`;
its `install.sh` differs from the endpoint copy because a duplicated fallback
configuration was later removed.

The historical installer does not pin everything it executes. It
shallow-clones core `main` and downloads `enroll.py` from installer `main`.
At review time those commits were:

- core: `d6b33822b61e7fccf39547d5cce8add8bc7021f9`, package version `0.11.14`;
- installer: `e637b12c35e40a81fef3171394fe863235575dfb`.

The installer checksum authenticates neither its publisher nor subsequently
fetched bytes. **Do not execute the historical installer**, even after root
access or policy compatibility is repaired. The execution instructions from
the earlier revision are withdrawn because they permit unreviewed mutable
code to run with installation privileges.

## Installer behavior reviewed (not an approved procedure)

The historical Linux installer:

1. requires root, Linux on `x86_64`/`aarch64`/`arm64`, `curl`, `git`, a
   working systemd, and Python >=3.11 with both `pip` and `venv`;
2. creates or reuses `/etc/sentinelx/host_id`;
3. creates the non-login `sentinelx` system user if missing;
4. normally offers `sentinelx ALL=(ALL) NOPASSWD: ALL`, but skips creation
   when `SENTINELX_SKIP_SUDO=1`; an existing rule is not removed;
5. removes and re-clones `/opt/sentinelx-cloud-core`, creates a virtualenv,
   upgrades pip inside it, and installs the core editable;
6. downloads the unpinned enrollment helper to
   `/etc/sentinelx/sentinelx-enroll.py`;
7. preserves an existing `/etc/sentinelx/identity.json`, otherwise prompts
   for owner enrollment and writes the JWT-bearing identity there;
8. preserves an existing `/etc/sentinelx/config.yaml`, otherwise installs the
   broad example configuration;
9. creates and chowns `/var/lib/sentinelx` and `/var/log/sentinelx` to the
   agent user;
10. overwrites `/etc/systemd/system/sentinelx-cloud-core.service`, reloads
    systemd, and enables and starts it as `User=sentinelx`.

No distribution upgrade was needed at the time of review. Python 3.11.15,
pip, venv, git, curl, and systemd were present. `/usr/bin/python3` was
Python 3.6.15; a future approved install must not change the system default.

## Policy compatibility hold

Static review and a bounded test against core commit
`d6b33822b61e7fccf39547d5cce8add8bc7021f9` established:

- `allowed_commands: []` rejects the `exec` operation;
- an `r`-only `file_ops.paths` list allows the selected health files and
  rejects `/etc/passwd` and non-`rw` writes;
- an empty `services` map rejects Asterisk service control;
- `security.trusted_fetch_hosts: []` blocks URL fetching only;
- `script_run` stays registered and executes arbitrary Bash/Python without
  consulting `allowed_commands`;
- inline and chunked uploads stay registered and can write under
  `upload_base` without consulting `trusted_fetch_hosts`;
- command entries are prefix-matched and executed through `bash -lc`, so an
  allowed prefix can be followed by a shell compound operator.

The blocked template sets `upload_base: /dev/null` as a defense-in-depth
backstop. The reviewed handlers then fail before creating a script or upload,
but with a generic `FileExistsError`; this is not a documented policy switch
and is not sufficient for approval. A reviewed core version must provide
explicit, host-enforced operation denial (or an equivalent separately reviewed
sandbox), with negative tests proving:

- `script_run` is rejected before a script file or process is created;
- inline, chunked, edit-staging, and cross-host uploads are rejected before
  bytes are written;
- shell compounds cannot extend an allowed command prefix;
- no sudo edit can bypass the no-write policy;
- only the exact `r` paths in the policy can be read.

## Immutable offline bundle gate

A successor installation procedure requires a separate reviewed commit and
an independently approved, authenticated bundle manifest. No such approved
bundle or replacement installation command is supplied by this PR.

The manifest must bind the exact installer, core and enrollment-helper Git
commits, SHA-256 of every installed file and wheel, all transitive Python and
build dependencies, the target Python/OS/architecture, restricted policy,
service unit, and pre-install/rollback procedure. A checksum created beside
untrusted bytes is not publisher authentication; verify the approved manifest
signature against the separately provisioned release trust anchor first.

Stage all artifacts on a separate review/build host from immutable commits.
Build wheels there, verify provenance, and record the complete dependency
lock. Transfer the reviewed bundle into a root-owned directory not writable
by the agent or an unprivileged contributor. Reject unexpected files,
symlinks, path traversal, missing entries, and every hash mismatch before
execution. Recheck the authenticated manifest and all hashes immediately
before installation from that same protected directory.

The successor installer must consume only these local verified artifacts:
no branch clone, mutable URL, editable install, network package resolution,
unpinned pip upgrade, or on-target dependency build. Its wheel installation
must use `--no-index`, a reviewed local `--find-links` directory,
`--require-hashes`, and a complete pinned requirements set; use `--no-deps`
after every transitive dependency is explicitly locked. Build tooling must
also be provisioned from the reviewed bundle, not downloaded implicitly.

Do not enable or start the service while validating/installing the bundle.
Enrollment's separately authorized network exchange is not permission to
fetch executable code. Install the reviewed restricted policy before any
agent connection, verify ownership and operation denials in isolation, and
require separate owner authorization for enrollment and service start.

## Existing-installation gate

An authorized root operator must complete this read-only inspection before
any future installation. Do not infer absence from unprivileged checks.

```bash
set -eu
id
hostname -f || hostname
find /etc/sentinelx /opt/sentinelx-cloud-core /var/lib/sentinelx \
  -maxdepth 2 -printf '%M %u:%g %p\n' 2>/dev/null || true
systemctl cat sentinelx-cloud-core.service 2>/dev/null || true
systemctl show sentinelx-cloud-core.service \
  -p LoadState -p ActiveState -p UnitFileState -p User -p FragmentPath \
  --no-pager 2>/dev/null || true
getent passwd sentinelx || true
test ! -e /etc/sudoers.d/sentinelx || {
  stat -c '%A %U:%G %n' /etc/sudoers.d/sentinelx
  visudo -c -f /etc/sudoers.d/sentinelx
}
```

If any SentinelX state exists, stop and preserve its `host_id`, identity,
policy, unit/drop-ins, ownership, and dashboard association. Never print or
copy the contents of `identity.json` into evidence. Audit and remove a
pre-existing broad sudo rule only under a separately reviewed root change;
`SENTINELX_SKIP_SUDO=1` does not remove it.

## Verification after a separately approved installation

Systemd health is not proof of enrollment. These commands are read-only
verification, not permission to install or start anything. Run them from the
authorized root session after an approved installation; a missing user or
probe prerequisite is an error, not evidence of restricted privilege.

```bash
set -eu
test "$(id -u)" -eq 0
command -v runuser >/dev/null
command -v sudo >/dev/null
getent passwd sentinelx >/dev/null
test "$(runuser -u sentinelx -- id -un)" = sentinelx
systemctl is-active sentinelx-cloud-core.service
systemctl is-enabled sentinelx-cloud-core.service
systemctl show sentinelx-cloud-core.service -p User -p Group --no-pager
if runuser -u sentinelx -- sudo -n -u root -- /usr/bin/true; then
  echo 'UNRESTRICTED_ROOT_PROBE=FAIL' >&2
  exit 1
fi
echo 'ROOT_TRUE_PROBE=DENIED'
sudo -n -l -U sentinelx
```

The nested sudo invocation originates from the `sentinelx` account, not root.
Denial of this one command alone does not prove that all privilege-escalation
paths are absent. Review the complete effective sudo policy (including group
and included rules) and confirm the agent has no unauthorized root commands.
Do not treat a probe execution error as a successful negative policy test.

Then use authenticated SentinelX/dashboard evidence to confirm the requested
label, host ID, intended hub, and owner account. The owner completes enrollment
only through the separately reviewed helper's official URL and terminal.
Never put the token in chat, shell arguments, logs, Git, or this repository.
If enrollment is incomplete, report `BLOCKED_OWNER_ENROLLMENT`; do not enable
the agent connection. Prove all allowed health reads and denied operations
against the exact reviewed installed tuple before declaring policy success.

Do not restart, reload, start, or stop Asterisk, MariaDB, VICIdial, either
Codestra adapter, or the provisioning service. Do not open inbound ports or
place calls. Re-run the restricted VICIdial operator `status` action and
confirm its active states and write gates are unchanged.

## Rollback boundary

No rollback applies to the historical review because nothing was installed.
For a future approved install, capture the pre-install state first and define
a reviewed rollback that disables the SentinelX unit, revokes the host in the
owner dashboard, and removes only newly created SentinelX files/users/rules.
Never delete a pre-existing identity or policy.
