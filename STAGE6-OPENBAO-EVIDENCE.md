# Stage 6 OpenBao Evidence

Captured: 2026-08-31 (Europe/Berlin)

`OPENBAO_BINDING=FAIL`

No running OpenBao container or shared OpenBao service was discovered on the
documented observability/security host `37.27.128.39`. Core-server access was
insufficient to inspect another candidate safely. No OpenBao path, policy,
token, mount, lease, or secret value was read or changed.

The required health check, staging/production namespace separation,
least-privilege policy read-back, and cross-namespace negative tests were not
executable. A credential-shaped environment value surfaced during local
preflight inspection and was not copied into Git; the affected Klyrow worker
RabbitMQ credential must be rotated through the approved secret authority before
any promotion resumes.

```text
OPENBAO_HEALTH=NOT_VERIFIED
STAGING_NAMESPACE_SEPARATION=NOT_VERIFIED
NEGATIVE_POLICY_TESTS=NOT_EXECUTED
SECRET_VALUES_COMMITTED=NO
CREDENTIAL_ROTATION_REQUIRED=YES
```
