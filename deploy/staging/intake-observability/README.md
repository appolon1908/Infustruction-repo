# Staging intake observability deployment

Execute runtime actions only from a standalone, root-owned protected checkout.
Do not invoke repository scripts as root from a checkout writable by a deployment
or login account. Prepare the accepted exact main revision without executing any
repository code:

~~~bash
install -d -o root -g root -m 0755 /opt/codestra-observability
install -d -o root -g root -m 0700 /opt/codestra-observability/infrastructure-authority
git -C /opt/codestra-observability/infrastructure-authority init
git -C /opt/codestra-observability/infrastructure-authority remote add origin https://github.com/appolon1908-hue/Infustruction-repo.git
git -C /opt/codestra-observability/infrastructure-authority fetch --no-tags origin refs/heads/main
git -C /opt/codestra-observability/infrastructure-authority checkout --detach <accepted-main-sha>
chown -R root:root /opt/codestra-observability/infrastructure-authority
chmod -R go-w /opt/codestra-observability/infrastructure-authority
~~~

Prepare the public, signed Middleware release evidence in its exact protected
path. The deployment verifies the GitHub artifact ZIP digest, signed manifest,
source SHA, image digest, schema head, release run, SBOM, vulnerability report,
image annotations, and the OCI SPDX predicate before pulling:

~~~bash
install -d -o root -g root -m 0700 /var/lib/codestra/releases/middleware/9a96ff1651a3-01a61e6c9761
/usr/bin/gh api repos/appolon1908-hue/Middleware-/actions/artifacts/9859370333/zip > /var/lib/codestra/releases/middleware/9a96ff1651a3-01a61e6c9761/signed-middleware-release-9a96ff1651a324b98f3a7efd60b7a342983ded4e-33662230894-2.zip
/usr/bin/unzip -q /var/lib/codestra/releases/middleware/9a96ff1651a3-01a61e6c9761/signed-middleware-release-9a96ff1651a324b98f3a7efd60b7a342983ded4e-33662230894-2.zip -d /var/lib/codestra/releases/middleware/9a96ff1651a3-01a61e6c9761
chown -R root:root /var/lib/codestra/releases/middleware/9a96ff1651a3-01a61e6c9761
chmod -R go-w /var/lib/codestra/releases/middleware/9a96ff1651a3-01a61e6c9761
~~~

Use an explicit state path rather than an implicit home-directory default. The
deployment entrypoint verifies the exact merged Infrastructure SHA and the
protected source closure before it pulls or starts a container. It clears
inherited Docker/Git configuration, invokes the root-owned system Compose
plugin directly, and disables global/system Git configuration:

~~~bash
/usr/bin/env -i \
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
INFRASTRUCTURE_SOURCE_SHA=<accepted-main-sha> \
CODESTRA_STAGING_ROOT=/var/lib/codestra/staging/intake-observability \
KEYCLOAK_PUBLIC_URL=https://auth-staging.codestra.co \
KEYCLOAK_REALM=codestra \
/bin/bash --noprofile --norc \
/opt/codestra-observability/infrastructure-authority/scripts/deploy_intake_observability_staging.sh deploy
~~~

This authority deploys only the isolated staging Middleware, PostgreSQL, and
Redis project. It also creates and validates the source-controlled
`codestra-observability` local bridge used only by the dedicated Prometheus
and Grafana runtimes. The bridge publishes no host port; its non-internal mode
allows Prometheus to exchange a read-only OAuth token with staging Keycloak.
The application project shares no network or volume with Klyrow or Postal.
Prometheus and Grafana remain separately owned and deployed.
