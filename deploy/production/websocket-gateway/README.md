# Canonical WebSocket gateway cutover

This replaces only the `gateway` service in the existing
`codestra-websocket-gateway` project. It preserves the three live external
networks and pins the signed `appolon1908-hue/Websocket-` image by digest.

The host must provide
`/etc/codestra/secrets/websocket-gateway/middleware_service_token`, and the
middleware at `MIDDLEWARE_URL` must implement
`POST /internal/v1/realtime/tickets/consume`. Run `cutover.sh` as root only
after those prerequisites and the Caddy/Kong route readbacks pass.

Any failed compose wait or `/healthz`, `/readyz`, or `/version` assertion
automatically restores the recorded legacy compose. A rollback is considered
successful only when the restored container image ID equals the recorded
legacy digest.
