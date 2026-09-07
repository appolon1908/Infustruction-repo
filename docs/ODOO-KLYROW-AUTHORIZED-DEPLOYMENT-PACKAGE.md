# Odoo → Klyrow authorized deployment package

Status: source preparation only; runtime mutation is not authorized.

## Bound candidate

- Repository: `appolon1908-hue/Odoo`
- Source: `a7a9364925c7182098cbda234f3fddc13c594c71`
- Source bundle SHA-256: `5584e92342cd70371eed6ad3bdc8bb24325405f43b3e3f446b9e4905d5de7882`
- The published source manifest remains non-deploying and denies external effects.

## Discovered execution topology

The reusable workflow selects a self-hosted runner labelled `codestra-staging`
for staging and `codestra-production-canary` for production read-only canary.
No matching runner is currently registered with the Odoo repository. Server A
has only a Keycloak repository runner. Neither Server A nor the provider host
has `/usr/local/bin/codestra-deploy`. The execution-runner FQDN, runner service
identity, staging target, and Odoo adapter release are therefore pending owner
assignment. The production Odoo target is the host reporting hostname
`middleware`; installing the controller there merely to satisfy the workflow
check is prohibited.

## Prepared controls

`operators/codestra-deploy` validates a root-owned authorization record before
dispatch, binds repository/source/artifact/action/environment/controller/runner
and target identities, enforces a time window and approval expiry, requires
database, filestore, configuration, isolated-restore, and rollback-rehearsal
evidence, requires an immutable rollback target, and serializes execution.

The controller delegates only to the root-owned
`/usr/local/libexec/codestra-deploy-odoo`. That adapter has not yet been selected
or released and the controller must fail closed while it is absent. Bootstrap
is a separately reviewed action. The workflow invokes the controller through
non-interactive sudo; no ordinary pull-request job invokes it.

## Owner-supplied authorization fields

Copy `release/templates/odoo-runtime-deployment-authorization.v1.json` into the
protected authorization process and supply, without placeholders:

- immutable artifact reference;
- exact action and environment;
- released controller SHA-256;
- execution-runner FQDN and service account;
- approved execution-window start and end;
- database backup evidence digest;
- filestore backup evidence digest;
- configuration backup evidence digest;
- isolated restoration evidence digest covering all three;
- rollback-rehearsal evidence digest;
- previous source SHA and artifact digest;
- approval identity, time, expiry, and signed evidence digest;
- reviewed Odoo adapter source, artifact digest, and installation target.

Unknown values remain `PENDING`; such a record is intentionally rejected.

## Separate approval scopes

1. Controller and Odoo-adapter bootstrap on the assigned runner.
2. Exact Odoo candidate staging, recovery rehearsal, and deployment.
3. Provider sudo restoration using only
   `klyrow-deploy ALL=(root) NOPASSWD: /usr/local/sbin/export-odoo-postal-credential ""`.
4. Protected credential import while both Odoo mail servers remain archived and
   `codestra.mail.live_delivery_enabled=false`.
5. SMTP verification limited to CONNECT, EHLO, STARTTLS, EHLO, AUTH, NOOP, QUIT.

MAIL FROM, RCPT TO, DATA, message submission, queue activation, failed-message
retries, provider-hold release, and broader application activation are excluded.

After deployment, acceptance must hash the importer from the running
container's actual `/mnt/extra-addons` mount and compare the mount source with
the authorized release. GitHub merge or release existence is not installation
evidence.
