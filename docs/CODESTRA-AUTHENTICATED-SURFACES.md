# Codestra authenticated surfaces

The Odoo login is the visual reference for human access: black background and
panels, white text, muted gray helper copy, and a gold primary action. Keycloak
owns the shared browser credential and MFA flow; downstream applications use
Authorization Code with PKCE S256 and preserve their native session/CSRF/logout
behavior.

The machine-only monitoring repositories do not get login forms. Prometheus,
Alertmanager, Loki, Tempo, Telemetry, Alloy, Node Exporter, cAdvisor, Redis
Exporter, Postgres Exporter and Blackbox Exporter remain private scrape/API
services. Grafana and Superset redirect human users to the shared Keycloak
surface. OpenBao is private and uses an operator gateway with role checks.

The machine-readable onboarding contract is [`config/observability/authenticated-surfaces.v1.json`](../config/observability/authenticated-surfaces.v1.json).
