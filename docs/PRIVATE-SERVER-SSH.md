# Private server SSH communication

The shared infrastructure repository owns `scripts/manage_private_ssh_links.py`.
Use it only through an already authorized administrative connection to each
explicitly approved host. It creates the dedicated `codestra-link` account for
shell commands and file exchange within that account's permissions. Application
writes and deployment privileges remain with their existing governed operators.

Each server generates its own Ed25519 identity locally. Only its public key and
the public SSH host key are exchanged. Obtain host keys through the authenticated
management connection, then pin them; do not trust an unauthenticated key scan.
Private keys, complete live manifests, and operations evidence stay on the hosts.

## Installation

1. Validate the exact source with
   `python3 -m unittest discover -s tests -p test_private_ssh_links.py -v`.
2. On each approved server, as root, run:
   `python3 scripts/manage_private_ssh_links.py identity --node NODE --private-ip PRIVATE_IP`.
   The IP must already be assigned locally. Preserve the returned public identity.
3. Build a separate root-owned, mode 0600 manifest for each server. Include only
   its approved peers, using their management-verified public identities:

```json
{
  "schema": 1,
  "node": "core",
  "private_ip": "10.20.0.1",
  "peers": [
    {
      "node": "web",
      "private_ip": "10.20.0.2",
      "public_key": "ssh-ed25519 <peer identity public key>",
      "host_key": "ssh-ed25519 <verified peer SSH host public key>"
    }
  ]
}
```

4. Run `python3 scripts/manage_private_ssh_links.py authorize --manifest /root/private-ssh-links.json`.
5. Verify every intended direction:
   `runuser -u codestra-link -- ssh codestra-web 'id -un'`.
   Expect `codestra-link`. File transfers can use `/var/lib/codestra-link/data/`.

The account has a locked password, a dedicated primary group, and no additional
groups. Its home and SSH authorization/configuration files are root-owned. The
private key is mode 0600 and readable only by its originating account and root.
Authorized keys use `restrict,from="EXACT_PRIVATE_IP"`, which disables forwarding,
PTY, X11, agent forwarding and user rc. Clients bind their declared private source
address, require the pinned host key, and disable password fallback.

No SSH daemon reload, root-login change, firewall modification, container restart,
or application credential change is needed. This does not enroll hosts into an
isolated staging network or replace a forced-command deployment identity.
A restricted existing SSH operator is not an account-installation path.

## Repeat runs, revocation and recovery

An exact repeat preserves keys and returns `UNCHANGED`. Different peers, changed
keys, or drifted managed files require a separately reviewed rotation. Interrupted
initial authorization may leave partial files; inspect those files against the
private manifest through the management connection before recovery.

To revoke access immediately, root can move
`/var/lib/codestra-link/.ssh/authorized_keys` into the mode 0700
`/etc/codestra/ssh/server-links/` directory. This blocks new logins; established
sessions must be ended separately if immediate revocation is required. Do not
delete the account, its transfer data, or its private key as an automatic rollback.
Restore only the reviewed authorization file, with root ownership and mode 0644.

The applied manifest is recorded locally at
`/etc/codestra/ssh/server-links/applied.json` with mode 0600.
