#!/usr/bin/env python3
"""Validate Codestra observability topology, communication, and firewall intent."""

from __future__ import annotations

import ipaddress
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "observability"
TOPOLOGY = CONFIG / "topology.v1.json"
COMMUNICATION = CONFIG / "communication-map.v1.json"
FIREWALL = CONFIG / "firewall.v1.json"

EXPECTED_HOSTS: dict[str, str | None] = {
    "grafana": "graf.codestra.media",
    "prometheus": "prom.codestra.media",
    "alertmanager": "aler.codestra.media",
    "loki": "loki.codestra.media",
    "tempo": "temp.codestra.media",
    "otel-collector": "otel.codestra.media",
    "superset": "supe.codestra.media",
    "node-exporter": "node.codestra.media",
    "cadvisor": "cadv.codestra.media",
    "postgres-exporter": None,
    "redis-exporter": "rdex.codestra.media",
    "blackbox-exporter": "blac.codestra.media",
    "alloy": "allo.codestra.media",
    "openbao": "bao.codestra.media",
}
EXPECTED_PRIVATE_SERVICE_IDENTITIES = {
    "postgres-exporter": "postgres-exporter:9187",
}
EXPECTED_REPOSITORIES = {
    "grafana": "appolon1908-hue/Codestra-Grafana-",
    "prometheus": "appolon1908-hue/Codestra-Prometheus",
    "alertmanager": "appolon1908-hue/Codestra-Alertmanager",
    "loki": "appolon1908-hue/Codestra-Loki",
    "tempo": "appolon1908-hue/Codestra-Tempo",
    "otel-collector": "appolon1908-hue/Codestra-Telemetry",
    "superset": "appolon1908-hue/Superset",
    "node-exporter": "appolon1908-hue/Codestra-Node-Exporter",
    "cadvisor": "appolon1908-hue/Codestra-cAdvisor",
    "postgres-exporter": "appolon1908-hue/Codestra-Postgres-Exporter",
    "redis-exporter": "appolon1908-hue/Codestra-Redis-Exporter",
    "blackbox-exporter": "appolon1908-hue/Codestra-Blackbox-Exporter",
    "alloy": "appolon1908-hue/Codestra-Alloy",
    "openbao": "appolon1908-hue/Codestra-OpenBao",
}
BROWSER_HOSTS = {
    "graf.codestra.media",
    "supe.codestra.media",
    "bao.codestra.media",
}
PRIVATE_HOSTS = {
    hostname
    for hostname in EXPECTED_HOSTS.values()
    if hostname is not None and hostname not in BROWSER_HOSTS
}
EXPECTED_FLOWS = {
    ("caddy", "grafana", 3000),
    ("caddy", "superset", 8088),
    ("caddy", "openbao", 8200),
    ("grafana", "prometheus", 9090),
    ("grafana", "loki", 3100),
    ("grafana", "tempo", 3200),
    ("prometheus", "alertmanager", 9093),
    ("prometheus", "node-exporter", 9100),
    ("prometheus", "cadvisor", 8080),
    ("prometheus", "postgres-exporter", 9187),
    ("prometheus", "redis-exporter", 9121),
    ("prometheus", "blackbox-exporter", 9115),
    ("alloy", "loki", 3100),
    ("alloy", "tempo", 4317),
    ("alloy", "otel-collector", 4317),
    ("otel-collector", "tempo", 4317),
    ("otel-collector", "prometheus", 9090),
    ("otel-collector", "loki", 3100),
    ("superset", "curated-analytics-read-model", 5432),
    ("authorized-application", "openbao", 8200),
}
EXPECTED_PRIVATE_PORTS = {
    "grafana": {3000},
    "superset": {8088},
    "openbao": {8200},
    "prometheus": {9090},
    "alertmanager": {9093},
    "loki": {3100},
    "tempo": {3200, 4317, 4318},
    "otel-collector": {4317, 4318, 8888, 8889},
    "node-exporter": {9100},
    "cadvisor": {8080},
    "postgres-exporter": {9187},
    "redis-exporter": {9121},
    "blackbox-exporter": {9115},
    "alloy": {12345},
}
FORBIDDEN_PUBLIC_PORTS = set().union(*EXPECTED_PRIVATE_PORTS.values())


def fail(message: str) -> None:
    print(f"OBSERVABILITY_TOPOLOGY_VALIDATION_ERROR={message}", file=sys.stderr)
    raise SystemExit(1)


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot load {path.relative_to(ROOT)}: {exc}")
    if not isinstance(value, dict):
        fail(f"{path.relative_to(ROOT)} must contain a JSON object")
    return value


def validate_topology(topology: dict) -> None:
    if topology.get("version") != 1:
        fail("topology version must be 1")
    if topology.get("dnsTarget") != "37.27.128.39":
        fail("DNS target mismatch")
    ipaddress.ip_address(topology["dnsTarget"])
    if topology.get("listenerAuthority") != "principal-service-repository-deployment-definition":
        fail("listener authority must remain with each principal service repository")
    if topology.get("listenerValuesAreReferences") is not True:
        fail("unconfirmed listeners must remain labelled as references")
    if topology.get("liveInstallationAuthorized") is not False:
        fail("topology source must not authorize installation")

    components = topology.get("components")
    if not isinstance(components, list) or len(components) != 14:
        fail("exactly 14 components are required")
    by_id = {component.get("id"): component for component in components if isinstance(component, dict)}
    if set(by_id) != set(EXPECTED_HOSTS) or len(by_id) != len(components):
        fail("component IDs are incomplete or duplicated")

    for component_id, hostname in EXPECTED_HOSTS.items():
        component = by_id[component_id]
        if component.get("hostname") != hostname:
            fail(f"{component_id}: canonical hostname mismatch")
        expected_private_identity = EXPECTED_PRIVATE_SERVICE_IDENTITIES.get(component_id)
        if expected_private_identity is None:
            if "privateServiceIdentity" in component:
                fail(f"{component_id}: unexpected private service identity")
            if not isinstance(hostname, str) or not hostname.endswith(".codestra.media"):
                fail(f"{component_id}: canonical hostname is invalid")
        elif component.get("privateServiceIdentity") != expected_private_identity:
            fail(f"{component_id}: private service identity mismatch")
        if component.get("repository") != EXPECTED_REPOSITORIES[component_id]:
            fail(f"{component_id}: repository authority mismatch")
        confirmation = component.get("portConfirmation")
        if not isinstance(confirmation, str) or not confirmation.startswith("pending-principal-repository"):
            fail(f"{component_id}: reference port is not marked pending")

        listeners: list[str] = []
        if isinstance(component.get("nativeListener"), str):
            listeners.append(component["nativeListener"])
        listeners.extend(component.get("nativeListeners") or [])
        listeners.extend(component.get("ingestListeners") or [])
        if not listeners:
            fail(f"{component_id}: reference listener missing")
        if any(
            "0.0.0.0" in listener
            or "[::]" in listener
            or listener.startswith("::")
            or listener.startswith("*:")
            for listener in listeners
        ):
            fail(f"{component_id}: public wildcard listener forbidden")

    required_connections = {
        "grafana": {"prometheus", "loki", "tempo"},
        "prometheus": {"alertmanager", "node-exporter", "cadvisor", "postgres-exporter", "redis-exporter", "blackbox-exporter"},
        "alloy": {"loki", "tempo", "otel-collector"},
        "otel-collector": {"tempo", "prometheus", "loki"},
        "superset": {"curated-analytics-read-models"},
    }
    for source, destinations in required_connections.items():
        if set(by_id[source].get("connectsTo") or []) != destinations:
            fail(f"{source}: approved downstream set mismatch")

    rules = topology.get("rules") or {}
    if rules.get("publicNativePorts") is not False:
        fail("native service ports must not be public")
    if rules.get("caddyOnlyPublicListeners") != [80, 443]:
        fail("Caddy must be the only public observability web listener")
    if rules.get("productionActivationAuthorized") is not False:
        fail("topology source must not authorize production activation")


def validate_communication(data: dict) -> None:
    if data.get("schemaVersion") != 1 or data.get("defaultEastWestPolicy") != "deny":
        fail("east-west communication must be version 1 and default deny")
    if data.get("referencePortsPendingPrincipalConfirmation") is not True:
        fail("communication ports must remain pending principal confirmation")
    if data.get("liveInstallationAuthorized") is not False:
        fail("communication map must not authorize installation")
    flows = data.get("flows")
    if not isinstance(flows, list):
        fail("communication flows must be a list")
    actual = {
        (flow.get("source"), flow.get("destination"), flow.get("referencePort"))
        for flow in flows
        if isinstance(flow, dict)
    }
    if actual != EXPECTED_FLOWS or len(actual) != len(flows):
        fail("communication flow allowlist mismatch or duplicate")


def validate_firewall(firewall: dict, communication: dict) -> None:
    if firewall.get("version") != 1:
        fail("firewall version must be 1")
    if firewall.get("scope") != "observability-additions-on-shared-provider-host":
        fail("firewall scope must remain additive on the shared host")
    if firewall.get("policy") != "default-deny-inbound" or firewall.get("defaultRoutedPolicy") != "deny":
        fail("host and routed ingress must be default deny")
    if firewall.get("establishedRelatedAllowed") is not True:
        fail("established/related return traffic policy missing")
    if firewall.get("liveInstallationAuthorized") is not False:
        fail("firewall source must not authorize installation")

    public = firewall.get("publicIngress")
    if not isinstance(public, list) or {entry.get("port") for entry in public} != {22, 80, 443}:
        fail("observability additions may expose only restricted SSH and Caddy web ports")
    ssh = next((entry for entry in public if entry.get("port") == 22), {})
    if ssh.get("sourcePolicy") != "approved-admin-cidrs-only":
        fail("SSH source policy must be restricted")
    if any(entry.get("sourcePolicy") != "internet" for entry in public if entry.get("port") in {80, 443}):
        fail("Caddy public ingress source policy mismatch")
    if {entry.get("port") for entry in public} & FORBIDDEN_PUBLIC_PORTS:
        fail("public/native port overlap")

    if set(firewall.get("browserFacingThroughCaddy") or []) != BROWSER_HOSTS:
        fail("browser-facing host set mismatch")
    if set(firewall.get("publicDnsButNoPublicProxy") or []) != PRIVATE_HOSTS:
        fail("private-only host set mismatch")
    private_entries = firewall.get("loopbackOrPrivateOnly")
    if not isinstance(private_entries, list) or len(private_entries) != 14:
        fail("firewall must classify all 14 private listeners")
    private_by_component = {entry.get("component"): entry for entry in private_entries}
    if set(private_by_component) != set(EXPECTED_PRIVATE_PORTS):
        fail("firewall component coverage mismatch")
    for component_id, expected_ports in EXPECTED_PRIVATE_PORTS.items():
        if set(private_by_component[component_id].get("ports") or []) != expected_ports:
            fail(f"{component_id}: private port reference mismatch")

    for flow in communication.get("flows") or []:
        destination = flow.get("destination")
        if destination not in private_by_component:
            continue
        source = flow.get("source")
        allowed_sources = set(private_by_component[destination].get("allowedSources") or [])
        if source not in allowed_sources:
            fail(f"{source} -> {destination}: approved flow is absent from firewall allowlist")

    if set(firewall.get("forbiddenPublicNativePorts") or []) != FORBIDDEN_PUBLIC_PORTS:
        fail("forbidden public native port set mismatch")
    listener_policy = firewall.get("nativeListenerPolicy") or {}
    if set(listener_policy.get("allowedBindScopes") or []) != {"loopback", "private-vlan", "private-docker-network"}:
        fail("private bind-scope policy mismatch")
    if set(listener_policy.get("forbiddenBindAddresses") or []) != {"0.0.0.0", "::"}:
        fail("public wildcard bind guard missing")
    if listener_policy.get("dockerPublishedPortRequiresDockerUserPolicy") is not True:
        fail("Docker forwarding requires DOCKER-USER/nftables enforcement")
    if listener_policy.get("publicNativeServicePort") is not False:
        fail("native service ports must remain private")

    shared = firewall.get("sharedHostSafety") or {}
    for key in (
        "preserveUnrelatedApprovedServices",
        "smtpPort25IsOutsideThisObservabilityPolicy",
        "doNotFlushExistingFirewall",
        "doNotReplaceHostPolicyWithoutFullInventory",
    ):
        if shared.get(key) is not True:
            fail(f"shared-host safety gate missing: {key}")

    activation = firewall.get("activation") or {}
    if not activation or any(value is not False for value in activation.values()):
        fail("all firewall activation gates must remain false")


def main() -> None:
    validate_topology(load(TOPOLOGY))
    communication = load(COMMUNICATION)
    validate_communication(communication)
    validate_firewall(load(FIREWALL), communication)
    print("OBSERVABILITY_SERVICE_COUNT=14")
    print("PUBLIC_DNS_HOST_COUNT=13")
    print("POSTGRES_EXPORTER_PRIVATE_IDENTITY=postgres-exporter:9187")
    print("BROWSER_EDGE_HOSTS=graf.codestra.media,supe.codestra.media,bao.codestra.media")
    print("PRIVATE_CADDY_POLICY=DENY_ONLY")
    print("EAST_WEST_DEFAULT=DENY")
    print("PUBLIC_NATIVE_PORTS=DENIED")
    print("DOCKER_FORWARDING_POLICY=REQUIRED")
    print("SHARED_HOST_SMTP_POLICY=PRESERVED_OUT_OF_SCOPE")
    print("POSTGRES_EXPORTER_DEPLOYMENT_AUTHORITY=PENDING")
    print("PRINCIPAL_REPOSITORY_PORT_CONFIRMATION=PENDING")
    print("LIVE_INSTALLATION_AUTHORIZED=NO")
    print("OBSERVABILITY_TOPOLOGY_VALID=1")


if __name__ == "__main__":
    main()
