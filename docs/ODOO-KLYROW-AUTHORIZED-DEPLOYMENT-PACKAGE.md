# Odoo → Klyrow authorized deployment package

Status: source preparation only; runtime mutation is not authorized.

## Bound candidate

- Repository: `appolon1908-hue/Odoo`
- Source: `a7a9364925c7182098cbda234f3fddc13c594c71`
- Source bundle SHA-256: `5584e92342cd70371eed6ad3bdc8bb24325405f43b3e3f446b9e4905d5de7882`
- The published source manifest remains non-deploying and denies external effects.

## Discovered execution topology

The owner selected Server A (`65.109.65.169`, observed hostname
`middleware`) for both staging and production on 2026-09-09. The target-map
template now records that assignment for `staging-readonly` and
`production-readonly-canary`. The existing `codestra-deploy` account is the
requested operator identity; this assignment does not register a runner or
install a sudo policy.

The reusable workflow selects a self-hosted runner labelled `codestra-staging`
for staging and `codestra-production-canary` for production read-only canary.
The protected GitHub environments have been created with independent review,
protected-branch restriction, self-review disabled and administrator bypass
disabled. Matching infrastructure runners, protected deployment inputs, an
installed controller/adapter and complete recovery evidence remain outstanding.

The controller's target-map validator accepts explicit environment-to-host
bindings; it does not require distinct physical hostnames. The adapter resolves
an environment-scoped protected configuration named
`<validated-host>.<environment>.json`; staging and production therefore cannot
silently share a compose directory, service, database, release pointer, or
health endpoint through one host-scoped file. Each configuration must bind its
own environment and isolated resources. The separate
`config/stage6-staging-host-provisioning-request.v1.json` still forbids reusing
the production host for its isolated-host provisioning operation. This target
assignment does not change that request or claim its provisioning checks passed.
Before a deployment on Server A, prove separate staging containers, writable
data/filestore paths, secrets, endpoints and recovery resources. Never point a
staging replacement or restore at a production database, volume or service.

Host identity must be checked before issuing the authorization: Server A reports
hostname `middleware` but `socket.getfqdn()` currently returns
`Ubuntu-jammy-latest-amd64-base.zst`. The controller checks the execution FQDN;
do not silently substitute the hostname, use the FQDN as unique host proof, or
copy that identity from another server. Bind the actual assigned runner and
verified Server A identity in the protected bootstrap process. Installation
still requires the reviewed package and exact bootstrap/rollback record.

## Prepared controls

`operators/codestra-deploy` validates a root-owned authorization record before
dispatch, binds repository/source/artifact/action/environment/controller/runner
and target identities, enforces a time window and approval expiry, requires
database, filestore, configuration, isolated-restore, and rollback-rehearsal
evidence, requires an immutable rollback target, and serializes execution.

The controller delegates only to the root-owned
`/usr/local/libexec/codestra-deploy-odoo`. Its source implementation consumes
only the preserved digest-bound Odoo release URL, rejects bounded-download or
bounded-expansion violations, and verifies all five recovery records against
the candidate, rollback target, host, and recovery-set identity. Before any
deployment mutation it validates the effective digest-qualified image,
no-send environment, read-only addon mount, internal-only networks, and durable
evidence destination. After a possibly database-changing upgrade begins, a
failure enters `NEEDS_RECOVERY` and never restarts old code against a database
that has not been restored. Certification checks every approved health endpoint
with bounded, non-redirecting requests and compares the importer visible inside
Odoo with the verified artifact bytes. Production promotion remains rejected
until a real traffic canary exists; staging's service replacement is not used
as a production canary. Its released package digest and Sigstore bundle remain pending until
this source is protected and the release environment is approved. Bootstrap is
a separately reviewed action. The workflow invokes the controller through
non-interactive sudo; no ordinary pull-request job invokes it.

## Owner-supplied authorization fields

Copy `release/templates/odoo-runtime-deployment-authorization.v1.json` into the
protected authorization process and supply, without placeholders:

- immutable artifact reference (the preserved Odoo release URL is populated);
- exact action and environment;
- released controller SHA-256;
- execution-runner FQDN and service account;
- exact sanitized evidence-output path;
- approved execution-window start and end;
- database backup evidence digest;
- filestore backup evidence digest;
- configuration backup evidence digest;
- isolated restoration evidence digest covering all three;
- rollback-rehearsal evidence digest;
- exact recovery-set identity shared by every recovery record;
- previous source SHA and artifact digest;
- approval identity, time, expiry, and signed evidence digest;
- released Odoo adapter artifact digest and installation target.

Unknown values remain `PENDING`; such a record is intentionally rejected.

## Required caller integration

The preserved Odoo candidate pins the reusable workflow at
`1b4a90810eb03db3eae2b676b2d418daa434ec16`; merging this infrastructure
repair does not alter that candidate. After this PR is protected and released,
the owner must choose one of two separately reviewed integrations: have an
authorized orchestrator consume the unchanged Odoo artifact, or update Odoo's
workflow pin and produce a new source candidate with a new source SHA and
artifact digest. The old candidate identity must not be reported for the latter.

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
