import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / "config/observability/authenticated-surfaces.v1.json").read_text())
assert data["schema"] == "codestra.authenticated-surfaces.v1"
assert data["design_reference"]["palette"]["accent"] == "#f4c223"
assert data["design_reference"]["interaction"].endswith("password collection")
services = {item["service"]: item for item in data["surfaces"]}
for service in ("openbao", "n8n", "social", "keycloak", "grafana", "superset", "prometheus-and-exporters", "alertmanager", "loki", "tempo", "telemetry", "alloy", "node-exporter", "cadvisor", "redis-exporter", "postgres-exporter", "blackbox-exporter"):
    assert service in services
assert services["prometheus-and-exporters"]["human_entry"] == "none-private-operations"
print("CODESTRA_AUTHENTICATED_SURFACES=PASS")
