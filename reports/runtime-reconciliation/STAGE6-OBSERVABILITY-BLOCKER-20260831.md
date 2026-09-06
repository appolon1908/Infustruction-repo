# Stage 6 Observability Blocker

Status: independently blocking; no remediation applied.

Six container healthchecks have accumulated thousands of consecutive failures
because host exec cannot initialize seccomp. No alert reached the release gate
for weeks.

Current read-only process inventory on `65.109.65.169`:

```text
Prometheus: running as codestra-monitoring-prometheus-1
Grafana: absent
Loki: absent
Tempo: absent
Alloy: absent
Superset: absent
```

Prometheus presence does not prove scrape success, alert rules, alert routing,
notification delivery, dashboards, logs, or traces. Those require separate
read-backs after host exec is repaired.

Remediation path:

1. repair host exec through the separately reviewed seccomp change;
2. inventory exact observability repositories, digests, configuration and
   rollback identities;
3. deploy only through its own staging change and approval;
4. prove scrape targets, alert evaluation/routing, logs, traces, dashboards and
   a synthetic failed-health alert;
5. keep production and external business writes disabled throughout.

This blocker is independent of the seccomp root cause: repairing healthchecks
does not establish monitoring, and installing monitoring does not repair host
exec.
