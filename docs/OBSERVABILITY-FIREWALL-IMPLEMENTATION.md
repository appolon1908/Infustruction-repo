# Observability firewall implementation gate

The machine-readable authority is under `config/observability/`. It permits
public ingress only to Caddy on TCP 80/443 and restricted administrative SSH
on TCP 22. It never permits a native observability listener on a public bind.

This is an additive observability policy for the shared provider host. It must
not flush or replace the existing firewall, and it must preserve separately
approved services such as SMTP on TCP 25. A full host-policy migration requires
its own inventory and change approval.

## Native listener rule

Ports 3000, 8088, 9090, 9093, 3100, 3200, 4317, 4318, 8888, 8889, 9100,
8080, 9187, 9121, 9115, 12345 and 8200 must bind only to loopback, the reviewed private
VLAN, or a private Docker network. Publishing a container port requires both
an explicit host bind and a `DOCKER-USER`/nftables policy; UFW alone is not
accepted as proof because Docker forwarding may bypass ordinary UFW paths.

## Source audit result

As of 2026-08-29, the dedicated service repositories declare deployment
disabled and do not contain an accepted Codestra listener/deployment
definition. Their familiar native ports therefore remain reference values,
not confirmed deployment authority. The PostgreSQL Exporter repository now
exists and declares no host-published port, but deployment and immutable-image
activation remain disabled. These are hard installation blockers, not
permission to use upstream defaults silently.

The observed provider-host baseline is safer than the target exposure: the
existing Grafana publishes container port 3000 only as host loopback port
18003, Prometheus has no host-published port, and no Superset or OpenBao runtime
is present. Source review must preserve that fail-closed state.

## Apply prerequisites

1. Each principal service repository adds an immutable deployment definition,
   health/readiness checks, exact listener bindings and rollback steps.
2. PostgreSQL Exporter receives an accepted immutable deployment definition
   and private-listener evidence, or is removed from the approved stack.
3. Exact private VLAN/container subnets and service identities replace the
   symbolic source groups in the policy.
4. Caddy, Keycloak and infrastructure candidates pass independent review.
5. A pre-change snapshot records UFW, nftables, Docker bindings and all public
   listeners.
6. Rendered rules are tested in staging, including Docker forwarding behavior.
7. Rollback is armed before any firewall or Caddy reload.

No file in this branch authorizes a live firewall mutation or server install.
