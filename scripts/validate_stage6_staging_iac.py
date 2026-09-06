#!/usr/bin/env python3
"""Fail-closed static policy for the isolated Stage 6 host authority."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IAC = ROOT / "infra" / "hetzner" / "stage6-staging"


def require(condition: bool, label: str) -> None:
    if not condition:
        raise SystemExit(f"STAGE6_STAGING_IAC_ERROR={label}")


required = {
    "versions.tf",
    "backend.tf",
    "variables.tf",
    "main.tf",
    "outputs.tf",
    "cloud-init.yaml.tftpl",
    "egress-cloud-init.yaml.tftpl",
    "ci.auto.tfvars",
    ".gitignore",
    "README.md",
}
require(required <= {path.name for path in IAC.iterdir()}, "required_files")

text = "\n".join(
    path.read_text(encoding="utf-8")
    for path in IAC.iterdir()
    if path.is_file()
)
main = (IAC / "main.tf").read_text(encoding="utf-8")
cloud_init = (IAC / "cloud-init.yaml.tftpl").read_text(encoding="utf-8")
egress_init = (IAC / "egress-cloud-init.yaml.tftpl").read_text(encoding="utf-8")
workflow = (ROOT / ".github/workflows/stage6-provision-staging-host.yml").read_text(
    encoding="utf-8"
)

for marker in (
    'runtime_name = "codestra-stage6-staging-01"',
    'gateway_name = "codestra-stage6-egress-01"',
    'name     = "codestra-stage6-staging-net"',
    'environment = "staging"',
    'role = "stage6-runtime"',
    'role = "stage6-egress-gateway"',
    'production  = "false"',
    'klyrow      = "false"',
    'postal      = "false"',
    "prevent_destroy = true",
    'backend "s3"',
):
    require(marker in text, f"missing_{re.sub(r'[^a-z0-9]+', '_', marker.lower()).strip('_')}")

require(re.search(r'port\s*=\s*"22"', main) is not None, "ssh_rule")
require("approved_ssh_source_cidrs" in main, "ssh_source_allowlist")
require("known_internal_production_deny_cidrs" in main, "production_deny_inventory")
require("cidrcontains" in main, "cidr_overlap_rejection")
for port, label in (("5432", "postgresql"), ("6379", "redis"), ("2375", "docker"), ("2376", "docker_tls")):
    require(re.search(rf'port\s*=\s*"{port}"', main) is None, f"public_{label}_forbidden")
require('source_ips = ["0.0.0.0/0"]' not in main, "global_ingress_cidr")
require('destination_ips = ["0.0.0.0/0"]' in main, "gateway_public_egress")
require("approved_egress_fqdns" in main, "fqdn_egress_policy")
require('"pkg-containers.githubusercontent.com"' in (IAC / "variables.tf").read_text(encoding="utf-8"), "reviewed_fqdn_catalog")
require(re.search(r'port\s*=\s*"3128"', main) is not None, "proxy_only_runtime_egress")
require("hcloud_network" in main and "hcloud_network_subnet" in main, "network_created_by_authority")
require("from = hcloud_firewall.stage6" in main and "to   = hcloud_firewall.runtime" in main, "firewall_state_migration")
require("private_network_id" not in (IAC / "variables.tf").read_text(encoding="utf-8"), "preexisting_network_input_removed")
require("seccomp=unconfined" not in text, "seccomp_unconfined")
require("privileged: true" not in text, "privileged_container")
require("LIVE_" not in cloud_init, "runtime_flags_in_bootstrap")
require("PRODUCTION_" not in cloud_init, "production_flags_in_bootstrap")
require("codestra-stage6-deploy" in cloud_init, "deployment_identity")
require("codestra-stage6-admin" in cloud_init, "operator_identity")
require("groups: []" in cloud_init, "deploy_user_no_docker_group")
require("PermitRootLogin no" in cloud_init, "root_ssh_disabled")
require("PasswordAuthentication no" in cloud_init, "password_ssh_disabled")
require("/run/docker.sock" in cloud_init, "local_docker_socket")
require("tcp://" not in cloud_init, "network_docker_socket")
require("/dev/tcp/${egress_gateway_private_ip}/3128" in cloud_init, "gateway_readiness_wait")
require("archive.ubuntu.com/ubuntu" in cloud_init and "security.ubuntu.com/ubuntu" in cloud_init, "pinned_bootstrap_mirrors")
require("http_access deny all" in egress_init, "proxy_default_deny")
require("approved_domains" in egress_init, "proxy_fqdn_allowlist")
require("deny reviewed production authority" in egress_init, "gateway_production_deny")
require("[iptables, -I, OUTPUT" in egress_init, "pre_package_production_deny")
require("access_log" in egress_init, "proxy_decision_logging")
require("Proxy-Authorization deny all" in egress_init, "proxy_auth_header_not_logged")

require("pull_request:" in workflow, "pull_request_validation")
require("workflow_dispatch:" in workflow, "manual_apply")
require("environment: stage6-infrastructure-provisioning" in workflow, "protected_environment")
require("github.ref == 'refs/heads/main'" in workflow, "main_only_apply")
require("HETZNER_CLOUD_TOKEN" in workflow, "token_secret_name")
require("PLAN_STAGE6_ISOLATED_HOST" in workflow, "plan_only_confirmation")
require(
    "inputs.confirmation == 'PLAN_STAGE6_ISOLATED_HOST' || inputs.confirmation == 'APPLY_STAGE6_ISOLATED_HOST'"
    in workflow,
    "plan_accepts_plan_or_apply_confirmation",
)
require(
    workflow.count("inputs.confirmation == 'APPLY_STAGE6_ISOLATED_HOST'") >= 2,
    "apply_requires_explicit_apply_confirmation",
)
require(re.search(r"tofu(?:\s+-chdir=\S+)?\s+apply", workflow) is not None, "apply_step")
require("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02" in workflow, "plan_artifact_upload")
require("actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093" in workflow, "plan_artifact_download")
require("sha256sum -c stage6-plan.SHA256SUMS" in workflow, "plan_checksum_verification")
require("needs: plan-remote" in workflow, "plan_before_apply")
require("push:" not in workflow, "automatic_push_apply_forbidden")


def workflow_step(name: str) -> str:
    """Return one named workflow step without parsing protected values."""
    match = re.search(
        rf"(?ms)^      - name: {re.escape(name)}\n(?P<body>.*?)(?=^      - name: |^  [a-zA-Z0-9_-]+:|\Z)",
        workflow,
    )
    require(match is not None, f"missing_workflow_step_{name.lower().replace(' ', '_')}")
    return match.group("body")


def require_state_credentials(step: str, label: str) -> None:
    require(
        "AWS_ACCESS_KEY_ID: ${{ secrets.TF_STATE_ACCESS_KEY }}" in step,
        f"{label}_state_access_key",
    )
    require(
        "AWS_SECRET_ACCESS_KEY: ${{ secrets.TF_STATE_SECRET_KEY }}" in step,
        f"{label}_state_secret_key",
    )


require_state_credentials(
    workflow_step("Initialize protected remote state"), "plan_init"
)
require_state_credentials(
    workflow_step("Generate exact remote-state plan for review"), "remote_plan"
)
require_state_credentials(
    workflow_step("Verify artifact and initialize protected remote state"), "apply_init"
)
apply_step = workflow_step("Apply only the exact saved plan")
require_state_credentials(apply_step, "saved_plan_apply")
require(
    "apply -input=false /tmp/stage6-reviewed-plan/stage6.tfplan" in apply_step,
    "apply_saved_plan_only",
)
require("tofu -chdir=\"$IAC_DIR\" plan" not in apply_step, "apply_replan_forbidden")

secret_patterns = (
    re.compile(r"(?i)(password|token|private[_-]?key)\s*[=:]\s*['\"]?[^\s$<{][^\s]*"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)
for pattern in secret_patterns:
    require(pattern.search(text) is None, "embedded_secret_material")

print("STAGE6_STAGING_IAC=PASS")
print("HOST_COUNT=2")
print("APPLICATION_HOST_COUNT=1")
print("EGRESS_GATEWAY_COUNT=1")
print("PRODUCTION_WORKLOADS=0")
print("PUBLIC_DATABASE_PORTS=0")
print("PUBLIC_DOCKER_PORTS=0")
print("AUTOMATIC_APPLY=NO")
