# Server 37 Telnexa admin deny evidence

Observed on `2026-09-02T23:51:46Z` at `37.27.128.39`.

`admin.telnexa.co` remains intentionally disabled. The missing authoritative
DNS record was restored to the server, a dedicated Let's Encrypt certificate
was issued, and the existing denial boundary was extended to TLS. External
HTTP/1.1 and HTTP/2 requests both return `403`; HTTPS also returns HSTS,
`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`,
`Permissions-Policy`, and `X-Request-ID`.

No admin application or upstream was enabled. The hostname was added to the
enabled public TLS-expiry monitor, whose immediate run passed. The root-only
rollback bundle is
`/var/backups/codestra-operators/telnexa/admin-dns-https-20260902T235016Z`.
