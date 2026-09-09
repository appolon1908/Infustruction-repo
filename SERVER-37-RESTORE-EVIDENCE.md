# Server 37 isolated restore evidence

Observed through `2026-09-02T23:57:15Z` on `37.27.128.39`.

The root-only encrypted archives below passed checksum validation and restored
into temporary isolated targets with no public ports and no residual resources:

- Klyrow `20260902T235702Z`: application PostgreSQL, Mautic MariaDB, Postal
  MariaDB, configuration, release evidence, boot controls, and root-owned
  runtime configuration.
- Telnexa `20260902T235528Z`: core PostgreSQL, billing PostgreSQL, Keycloak
  PostgreSQL, Redis, RabbitMQ definitions, Jasmin state, and configuration.
- Kyqra `20260902T235705Z`: PostgreSQL, Redis, and configuration.

All restore commands returned `RESTORE_TEST=PASS`. The backup operators now
select only timestamped directories containing `backup.tar.gpg`; unrelated
rollback/evidence directories can no longer shadow the newest archive. This
evidence does not claim off-host coverage; that remains a separate failing
gate.

Source review correction: the checked-in operator previously imported only PostgreSQL;
MariaDB dumps received compression checks. The historical prose above is not sufficient
proof of a complete restore. The corrected operator imports and queries both MariaDB
dumps in isolated ephemeral containers, but no new runtime rehearsal was performed.
`ISOLATED_RESTORE=FAIL` until a complete corrected-operator receipt is recorded.
