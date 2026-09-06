#!/usr/bin/env python3
import pathlib
import re
import yaml

matrix = yaml.safe_load(pathlib.Path("PRODUCTION-SAFETY-CAPABILITY-MATRIX.yaml").read_text())
bindings = yaml.safe_load(pathlib.Path("PRODUCTION-CAPABILITY-EVIDENCE-BINDINGS.yaml").read_text())
inventory = {line for line in pathlib.Path("PRODUCTION-WORKLOAD-INVENTORY-20260901.txt").read_text().splitlines() if line}
services = matrix["services"]
keys = {"advertising_write", "external_delivery", "social_publish", "external_model_call", "sms_delivery", "email_delivery", "pstn_dialing", "n8n_provider_write"}
assert len(inventory) == 64
assert set(services) == inventory
assert set(bindings["services"]) == inventory
assert bindings["production_changed"] is False
assert matrix["coverage"] == "64/64"
unknown = 0
for name, item in services.items():
    assert set(item["capabilities"]) == keys, name
    for value in item["capabilities"].values():
        assert value in (True, False, "UNKNOWN"), (name, value)
        unknown += value == "UNKNOWN"
    binding = bindings["services"][name]
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", binding["runtime_image_id"]), name
    assert binding["oci_revision"] == "UNKNOWN" or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", binding["oci_revision"]), name
    assert binding["deployment_configs"], name
    for config in binding["deployment_configs"]:
        assert config["path"].startswith("/"), (name, config)
        assert config["sha256"] == "UNAVAILABLE" or re.fullmatch(r"[0-9a-f]{64}", config["sha256"]), (name, config)
assert unknown == 0, unknown
assert matrix["capability_unknown_fields"] == 0
assert matrix["production_write_safety"] == "PASS"
safe = matrix["effective_runtime_state"]
expected_safe_keys = {
    "LIVE_ADVERTISING_ENABLED",
    "EXTERNAL_DELIVERY_ENABLED",
    "SOCIAL_PUBLISHING_ENABLED",
    "EXTERNAL_MODEL_CALLS_ENABLED",
    "LIVE_SMS_DELIVERY",
    "LIVE_EMAIL_DELIVERY",
    "LIVE_PSTN_DIALING",
    "N8N_EXTERNAL_PROVIDER_WRITES",
    "PRODUCTION_DIALING",
}
assert set(safe) == expected_safe_keys, (set(safe), expected_safe_keys)
assert all(value is False for key, value in safe.items() if key != "PRODUCTION_DIALING")
assert safe["PRODUCTION_DIALING"] == "DISABLED"
print("CAPABILITY_MATRIX_COVERAGE=64/64")
print("CAPABILITY_UNKNOWN_FIELDS=0")
print("PRODUCTION_WRITE_SAFETY=PASS")
