#!/usr/bin/env python3
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compose = (root / "deploy/production/websocket-gateway/compose.yaml").read_text()
script = (root / "deploy/production/websocket-gateway/cutover.sh").read_text()

digest = "sha256:dd3039f69532ccd918cf2e44f58871199943fffa492423b3e6235517a8e8976e"
rollback = "sha256:1c8f28d3627955c0d07f8a3f2e4187edb0770f3a9fc7cbc7dc9d819fcd255ffd"
required = ("MIDDLEWARE_URL", "MIDDLEWARE_SERVICE_TOKEN", "ALLOWED_ORIGINS")

assert f"ghcr.io/appolon1908-hue/websocket-gateway@{digest}" in compose
assert "codestra-srl" not in compose.lower()
assert all(name in compose for name in required)
assert all(path in script for path in ("/healthz", "/readyz", "/version"))
assert digest in script and rollback in script
assert "trap rollback EXIT HUP INT TERM" in script
assert "live rollback digest drifted" in script
assert "docker compose" in script and "healthz did not become reachable in 60 seconds" in script
print("websocket primary cutover validation: PASS")
