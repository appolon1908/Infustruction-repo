# Recovery verification — 2026-09-09

| Check | Result |
| --- | --- |
| n8n local encrypted recovery capture | PASS |
| n8n checksums and expected signing key | PASS |
| n8n service recovery and temporary plaintext cleanup | PASS |
| Fresh Kong local encrypted backup and checksum verification | PASS |
| Replacement backup credentials installed with restricted file permissions | PASS |
| Encrypted offsite repository read access with replacement credentials | PASS |
| Existing Kong archive readback and ciphertext checksum comparison | PASS |
| New Kong offsite upload after credential replacement | NOT RUN: automatic approval review blocked starting the backup job |
| Protected control-plane source, schema, and worker validation | PASS |
| Full production certification | INCOMPLETE |

At the 2026-09-09 21:17 UTC verification, the existing offsite Kong archive was read successfully and its ciphertext checksum matched the local copy. That archive was captured on September 7; it is not a newly uploaded September 9 backup.

The earlier upload failure did not advance the backup job's last-success marker. Replacement credentials now permit reading the repository, but a new upload remains unverified. Existing archive readback does not establish an independent-machine restore, decryption rehearsal, or full production readiness.

A fresh protected control-plane validation passed at 2026-09-09 21:31 UTC. This validates the installed control-plane source, required mailbox tables, worker health, and disabled external-delivery state. It does not activate a release or clear the database recovery and traffic-opening gates.
