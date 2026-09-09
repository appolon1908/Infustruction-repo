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
| New Kong offsite upload after credential replacement | PASS |
| Approved Kong snapshot retention job | PASS |
| New Kong archive readback and ciphertext checksum comparison | PASS |
| Protected control-plane source, schema, and worker validation | PASS |
| Kong protected-main candidate artifact verification | PASS |
| Kong Appolon preflight repair source checks | PASS |
| Kong isolated restore rehearsal | BLOCKED — required image access rejected |
| Authenticated Kong staging runtime certification | NOT RUN |
| Appolon Kong runtime integration gate | FAIL |
| Full production certification | INCOMPLETE |

The approved Kong backup job completed successfully at 2026-09-09 21:47 UTC, including encrypted upload, the existing 14-daily/8-weekly/12-monthly snapshot-retention policy, and its offsite verification step. The job advanced its last-success marker to the new September 9 capture.

At 21:49 UTC, the exact new offsite archive was read back and its ciphertext checksum matched the local capture. This proves encrypted upload and readback; an independent-machine restore and full production certification remain incomplete.

Kong's source repository is [appolon1908-hue/Kong](https://github.com/appolon1908-hue/Kong). Its runtime integration check against the Appolon Middleware instance failed. Source ownership, container health, and backup success do not by themselves establish a certified production integration.

A fresh protected control-plane validation passed at 2026-09-09 21:31 UTC. This validates the installed control-plane source, required mailbox tables, worker health, and disabled external-delivery state. It does not activate a release or clear the database recovery and traffic-opening gates.

Kong's protected-main candidate artifact was independently retrieved and validated with the repository's canonical verifier at 22:22 UTC. The Appolon preflight repair is tracked in [Kong PR #97](https://github.com/appolon1908-hue/Kong/pull/97); its focused tests, migration manifests, and reported GitHub checks pass. This is source and artifact evidence only. A fresh read-only runtime preflight still fails.

The isolated Kong restore rehearsal could not start because the registry rejected access to its required pinned PostgreSQL image. No restored database or restore PASS is claimed. Staging has no registered runtime runner or completed authenticated runtime-certification run. The coordinated Admin/operator migration and protected review remain outstanding before gateway activation.
