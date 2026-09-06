# PR 1 observability documentation reconciliation — 2026-09-06

This is source-only merge evidence, not a deployment instruction or fresh
DNS, host, health, or runtime certification.

Reviewed inputs:
- PR 1: `4bad72bfc3aa4eca04b57be60b4cc34b7e706ac9`
- accepted main: `de8e6b6d42d4e166736444d3730faf3a97a77510`

All six documents proposed by PR 1 are already represented on accepted main.
Three add/add conflicts arose from older PostgreSQL Exporter authority and
wiring language. The resolution preserves main's canonical
`Codestra-Postgres-Exporter` mapping, its still-disabled deployment contract,
and the accepted collector/Prometheus wiring rather than restoring the
obsolete assertion that the repository does not exist.

Before adding this record, the resolved tree was byte-identical to accepted
main. Both original branch histories remain ancestors; there is no reset or
force push. Existing source validators, secret scans, deployment holds,
private-network constraints, and historical evidence remain unchanged.

Merging this documentation does not deploy observability, alter DNS/firewall
rules, activate Alertmanager delivery, initialize OpenBao, or change production.
