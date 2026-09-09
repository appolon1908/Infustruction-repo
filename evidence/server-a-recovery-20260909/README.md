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

## Permanent proxy fix

[Middleware PR #202](https://github.com/appolon1908-hue/Middleware-/pull/202) merged at 18:24:49Z as `56005c75d42ef04fc5083443f1aa54c7f4b1ec9f`. It adds `init: true` and `pids_limit: 256` to the two private Caddy proxies.

The earlier targeted restarts recovered service health. The permanent settings remain **NOT INSTALLED**: SentinelX reports no writable paths, and both live proxies still report no init process or PID limit. No alternative file-writing mechanism was used to evade the rejected edit.

## Host administrator access step

The owner has approved these two file edits. The remaining requirement is technical access, not another chat approval.

From an authorized Server A terminal, open the existing agent configuration:

```sh
sudoedit /etc/sentinelx/config.yaml
```

Append these two entries to the existing `file_ops.paths` list, preserving every existing entry and the rest of the configuration:

```yaml
    - path: /opt/codestra/middleware/deploy/internal-odoo/compose.internal-odoo.yaml
      access: rw
    - path: /opt/codestra/middleware/deploy/internal-n8n-private/compose.internal-n8n.yaml
      access: rw
```

Reload the active agent configuration by restarting its verified unit:

```sh
sudo systemctl restart sentinelx-cloud-core
sudo systemctl is-active sentinelx-cloud-core
```

After reconnection, confirm that SentinelX advertises exactly those additional writable files. The assistant must not modify its own access policy through another execution path.

The subsequent approved deployment must use the infrastructure authority, preserve local Compose changes and the exact live image digest `sha256:269c6bd9b2713a27f8dc34a19a904bb0ba9d8f0f1564913576becd24779674d5`, validate the effective two-setting diff, and recreate only one proxy service at a time with no image build/pull or dependency recreation. Verify init, PID limit, security settings, networks, TLS health and process reaping before proceeding to the other proxy.

[Infrastructure PR #112](https://github.com/appolon1908-hue/Infustruction-repo/pull/112) separately records the owner's same-Server-A staging assignment and awaits independent review. Existing release, runner identity, staging isolation and production certification gates remain applicable.
