# Server 37 Klyrow event-delivery remediation

- UTC change window: `2026-09-03T00:44:53Z` onward.
- Production backup: PASS at
  `/var/backups/codestra-operators/klyrow/20260903T004453Z`.
- Isolated restore: PASS, including database ACL and runtime configuration
  validation; no public ports or residual restore resources.
- Permanent source fix: Klyrow PR 78, exact head
  `6c9947636a6241cf22f5293b6ae80ca1926addb5`; 396 tests pass. It removes an
  incorrect dependency on the legacy middleware base URL when the dedicated
  mTLS callback is configured. Protected merge and immutable publication still
  require exact-head independent approval.
- Live compatibility bridge: PASS. The unchanged signed gateway image
  `sha256:1b0caed0283f03bf3e1f05e8411ca7e28f30ab42c4b854b570471a22671a740b`
  now receives the approved mTLS middleware authority as the legacy base guard
  for both gateway and delivery worker. Lifecycle events still use the
  dedicated callback URL.
- Controlled worker and gateway recreation: PASS. Image identity, non-root
  user, read-only root filesystem, capabilities, networks, and restart policy
  remain unchanged.
- Rollback rehearsal: PASS. Forward recovery after rehearsal: PASS. Root-only
  bundle: `/var/backups/codestra-operators/klyrow-event-bridge-20260903T004520Z`.
- Transport test: PASS through TLS 1.3 with verified server identity and the
  dedicated Klyrow client certificate; a trusted request without a client
  certificate is rejected during the TLS handshake.
- Synthetic non-customer delivery: FAIL at the receiver with HTTP 422
  `unsupported_klyrow_event`. No email was sent.
- Receiver root cause: Server A is still running middleware predating the
  durable Klyrow delivery-event inbox. The current protected platform tuple
  pins corrected middleware source
  `f199b6c40f4e467979e9a8b255a0e686321a182d` and digest
  `sha256:ec2cf4ca73ff072fbdd48bda108a60f103526cb3e97a721abdf38435b010908b`.
- Protected activation attempt: GitHub Actions run `33701213193`. Release
  signature/tuple verification passed, but Server A's root-owned restricted
  operator rejected the request because its installed tuple is older than the
  current protected tuple. Updating that operator requires authorized root
  administration on Server A (`65.109.65.169`), which is not exposed to Server
  37's bounded credential-consumer key.
- Customer messages sent: `0`.
- SSH configuration changes: `0`.

Classification: `WARNING` for the reversible Server 37 bridge; `FAIL` for the
end-to-end delivery gate until Server A's operator tuple is installed and the
corrected middleware rollout sequence completes.
