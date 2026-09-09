# Server A recovery evidence — 2026-09-09

The owner-approved protected backup, backup validation and isolated restore all passed on Server A (`middleware`, `65.109.65.169`). At 18:32:20Z, Middleware, Kong, Caddy, Redis, n8n, Odoo and both private proxies were running, healthy and unpaused.

The machine-readable observations and hashes are in [recovery.json](recovery.json). Original root-controlled evidence remains on Server A; no database contents, private keys or credentials are included here.

## Results

| Operation | Result |
| --- | --- |
| Protected backup | PASS; snapshot `20260909T182238Z` |
| Application writer pause | 11.698 seconds; recovery gate PASS |
| Encrypted archive and evidence checksums | PASS |
| Isolated restore | PASS; four databases |
| Odoo filestore validation | PASS; 37 objects read through the ORM |
| Middleware migration/readiness | PASS for `0056_klyrow_delivery_events` and the installed protected candidate |
| Measured rehearsal recovery time | 157.503 seconds |
| Production role privileges | Unchanged, verified by rehearsal |
| Disposable containers, volume, network and plaintext work directory | Absent in subsequent read-back |
| Runtime safety checks | Zero active calls/channels; required delivery flags false |

The installed operator SHA-256 was `9ddaeb6df45514688f66db7ea9f8e86f93e6876b7eb90e6460f9ce251bad26a0`, and its installed-file manifest verified before each operation. The operator validated the existing owner maintenance waiver; this work did not change that waiver, the release tuple or operator policy.

These results prove local recovery for protected platform commit `8e365724d1216581471835ee05d5fdc7b13ee501` and Middleware candidate digest `sha256:bca7a220b9ce50411ae67e2115507329656c4ee351333d14568af3695e3c347a`. They do not certify the newer appolon integration release, offsite restoration on an independent machine, or the full portfolio. No fresh offsite upload or independent recovery-key proof was performed in this operation.

## Permanent proxy fix — installed

[Middleware PR #202](https://github.com/appolon1908-hue/Middleware-/pull/202) merged at 18:24:49Z as `56005c75d42ef04fc5083443f1aa54c7f4b1ec9f`. Its `init: true` and `pids_limit: 256` settings are now **INSTALLED AND VERIFIED** on both private proxies.

SentinelX began advertising write access to the two exact Compose files before installation. Structured edits passed YAML validation and created timestamped backups. The assistant did not change its own access policy or grant server-wide write access.

The effective Compose configuration was compared with the pre-installation configuration and differed only by the approved init and PID-limit fields. Odoo was recreated first and verified healthy, followed by n8n. Both retained the exact live image digest `sha256:269c6bd9b2713a27f8dc34a19a904bb0ba9d8f0f1564913576becd24779674d5`. No builds, pulls, dependency recreations, daemon restart or host reboot were performed.

At 18:54:07Z, each proxy reported `docker-init` as PID 1, PID limit 256, five successful retained TLS health checks and zero descendant zombies. The host-wide `ssl_client` zombie count was zero. All six requested core services were healthy and unpaused.

The n8n recreation changed the order of the bind-mount list. The first verification stopped at that difference; subsequent read-back proved exact equality of the mount values with no duplicates. The image, mounts, capabilities, read-only filesystem, no-new-privileges setting, private networks and aliases were preserved.

Exact before/after container IDs, file hashes, backups, guarded apply details and final health observations are in [proxy-installation.json](proxy-installation.json). Earlier observations in [recovery.json](recovery.json) retain their original timestamps; the new `after_permanent_installation` observation records the installed state.

[Infrastructure PR #112](https://github.com/appolon1908-hue/Infustruction-repo/pull/112) separately addresses the owner's same-Server-A staging assignment. Existing release, runner identity, staging isolation, offsite recovery and full production certification gates remain applicable.
