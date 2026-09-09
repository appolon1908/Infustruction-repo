# Odoo → Klyrow deployment topology discovery

Discovery date: 2026-09-07. Read-only observations only.

## Verified facts

- Odoo protected candidate: `a7a9364925c7182098cbda234f3fddc13c594c71`.
- Odoo source bundle: `sha256:5584e92342cd70371eed6ad3bdc8bb24325405f43b3e3f446b9e4905d5de7882`.
- Infrastructure protected source before this work:
  `f98f4c9d3812ccec82c4621f91193f5b4fbf36ae`.
- Reusable workflow staging label: `codestra-staging`.
- Reusable workflow production label: `codestra-production-canary`.
- GitHub repository runner inventory returned no matching registered runners.
- Server A SSH alias `codestra-app` connected as `codestra-admin`; hostname
  readback was `middleware`.
- Server A exposes only the Keycloak repository Actions runner service. It is
  not assigned to the Odoo deployment workflow.
- Server A has neither `/usr/local/bin/codestra-deploy` nor an effective sudo
  rule for that command.
- Klyrow SSH alias `klyrow-server` connected as `klyrow-deploy`.
- `klyrow-deploy` lacks the no-argument exporter sudo permission.
- No controller, runner, policy, or service was changed during discovery.

## Proposed assignments—not discovered facts

None. Staging runner FQDN, staging target hostname, production runner FQDN,
runner service account, and bootstrap host remain pending owner assignment.
