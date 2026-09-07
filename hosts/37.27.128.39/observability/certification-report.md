# Server B observability production certification

Status: **NOT_PRODUCTION_CERTIFIED**

This is a sanitized, fail-closed pre-change record for `37.27.128.39`. No
component was installed, recreated, restarted, or activated. SSH, firewall,
DNS, reverse-proxy, identity, and secret authorities were not changed.

The historical twelve probed DNS names resolved exclusively to the intended server. Eleven names
served an unrelated Klyrow certificate; only `bao.codestra.media` has a matching
certificate. Two critical Klyrow delivery alerts are firing. Only Prometheus,
Grafana, Node Exporter, and OpenBao have existing runtimes, none controlled by
this host authority. OpenBao is uninitialized and sealed. The host package Node
Exporter is healthy and loopback-only, but its broad default collector set is
not controlled by the reviewed host authority. The required API, release,
runtime, backup, restore, rollback, SBOM, provenance, and signature evidence is
not present on the protected product production branches.

The scope now includes all fourteen canonical components. Alertmanager and
PostgreSQL Exporter were missing from this record; their production/staging
heads and runtime/network/recovery evidence remain explicitly NOT_CAPTURED.
Canonical candidate references do not substitute for protected production
heads. No new DNS, service, or runtime probe was run for this source repair.

Activation remains prohibited until every JSON/YAML gate in this directory is
regenerated from reviewed protected release heads and validates PASS.
