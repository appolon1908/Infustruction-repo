# private-integration-gateway-1 Read-only Investigation

Captured: 2026-08-30 (America/Santo_Domingo)

No restart, replacement, filesystem write, database query, or secret-value read
was performed.

| Field | Observation |
|---|---|
| Owner | `UNVERIFIED`; host files are root-owned and are not in a Git checkout |
| Purpose | Provider integration gateway forwarding Kyqra/Telnexa events toward the Codestra integration control plane |
| Image | local `private-integration-gateway` |
| Immutable local digest | `sha256:a9a1562f6d7b3557f480c2ffb513bd8bb472a2e0f0f01e0f9aa8bcc6e7fab8a0` |
| Image provenance | `UNVERIFIED`; Compose labels exist but OCI source/revision labels do not |
| Compose authority | `/opt/middleware/integration-gateway/compose.yaml`; non-Git host directory |
| Compose project/service | `private-integration` / `gateway` |
| Source checksum | `/app/gateway.py`: `sha256:82f9ca6ef58d399195a8223dd77754d33bce7cf9b1269182c779d10188e8dbda` |
| Network | shared external `codestra_edge`; container address observed as `172.19.0.11/16` |
| Published port | `10.40.0.1:8095 -> 8080/tcp`; not bound to a public wildcard address |
| Writable state | named volume `private-integration_gateway_data` mounted at `/data`; contains `integration.db` |
| Secret authority | `/etc/codestra/secrets/kyqra-telnexa/middleware.env`; values were not read or recorded |
| Upstreams | configured Kyqra and Telnexa private endpoints on `10.40.0.2` |
| Downstream | `codestra-integration-control-plane-api-1:8096/api/v1/events` |
| Architecture disposition | Functionally belongs to provider-to-Middleware/control-plane integration, not Kong route authority; ownership and reviewed source remain unproven |
| Action | Keep `UNKNOWN`, freeze, do not restart or replace |

The shared `codestra_edge` network also contains Kong, Middleware, provider,
identity, Odoo, n8n, and legacy services. Network membership alone is not proof
of ownership. The gateway must remain excluded from automatic reconciliation
until its repository and responsible owner are documented and reviewed.
