# Server 37 Mautic integration evidence

Observed at `2026-09-02T23:10:45Z` on `37.27.128.39`.

The dedicated Klyrow OAuth2 client-credentials identity passed private-network
token issuance and `GET /api/users/self`. Controlled test records then passed
contact create/read/update, segment membership add/remove, campaign membership,
and cleanup. The dedicated client secret was rotated after certification and
token issuance plus `users/self` were revalidated without printing credentials
or tokens.

The Klyrow scheduler consumes the client ID and secret through root-owned
read-only files. Nginx continues to return 404 for public `/mautic/api/*` and
`/mautic/oauth/*` routes; the browser UI remains separately authenticated.
