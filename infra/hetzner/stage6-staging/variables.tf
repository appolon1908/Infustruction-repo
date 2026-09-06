variable "location" {
  description = "Owner-approved EU Hetzner location for the isolated Stage 6 network."
  type        = string
  default     = "hel1"
  validation {
    condition     = contains(["fsn1", "nbg1", "hel1"], var.location)
    error_message = "Stage 6 must use an approved EU Hetzner location."
  }
}

variable "server_type" {
  description = "Reviewed minimum runtime size for 22 workloads and monitoring agents."
  type        = string
  default     = "cx43"
  validation {
    condition     = var.server_type == "cx43"
    error_message = "Changing the reviewed CX43 size requires a new sizing review."
  }
}

variable "egress_gateway_server_type" {
  description = "Small dedicated proxy host; it carries no application or production workload."
  type        = string
  default     = "cx23"
  validation {
    condition     = var.egress_gateway_server_type == "cx23"
    error_message = "Changing the reviewed egress-gateway size requires review."
  }
}

variable "image" {
  description = "Approved Ubuntu image or immutable snapshot identifier."
  type        = string
  default     = "ubuntu-24.04"
  validation {
    condition     = var.image == "ubuntu-24.04" || can(regex("^[0-9]+$", var.image))
    error_message = "Use Ubuntu 24.04 or a reviewed numeric snapshot identifier."
  }
}

variable "network_cidr" {
  type        = string
  description = "Owner-approved isolated Stage 6 network range."
  default     = "10.250.0.0/16"
  validation {
    condition     = var.network_cidr == "10.250.0.0/16"
    error_message = "Changing the reviewed network requires overlap review."
  }
}

variable "staging_subnet_cidr" {
  type        = string
  description = "Owner-approved Stage 6 runtime subnet."
  default     = "10.250.6.0/24"
  validation {
    condition     = var.staging_subnet_cidr == "10.250.6.0/24"
    error_message = "Changing the reviewed subnet requires overlap review."
  }
}

variable "private_ip" {
  type        = string
  description = "Deterministic runtime address inside the new Stage 6 subnet."
  default     = "10.250.6.10"
  validation {
    condition     = var.private_ip == "10.250.6.10"
    error_message = "Changing the reviewed runtime address requires review."
  }
}

variable "egress_gateway_private_ip" {
  type        = string
  description = "Deterministic address of the staging-only controlled egress gateway."
  default     = "10.250.6.2"
  validation {
    condition     = var.egress_gateway_private_ip == "10.250.6.2"
    error_message = "Changing the reviewed gateway address requires review."
  }
}

variable "approved_ssh_key_ids" {
  description = "Dedicated Hetzner Stage 6 administrative key IDs."
  type        = set(number)
  default     = [118172836]
  validation {
    condition     = var.approved_ssh_key_ids == toset([118172836])
    error_message = "Only the owner-approved codestra-stage6-admin key is permitted."
  }
}

variable "staging_readonly_operator_public_key" {
  description = "Distinct Ed25519 public key for the forced-command staging-readonly automation identity."
  type        = string
  sensitive   = true
  validation {
    condition = (
      !strcontains(trimspace(var.staging_readonly_operator_public_key), "\n") &&
      can(regex("^ssh-ed25519 [A-Za-z0-9+/]{40,}={0,2}( [A-Za-z0-9_.@-]{1,64})?$", trimspace(var.staging_readonly_operator_public_key)))
    )
    error_message = "Provide exactly one reviewed Ed25519 public key for the restricted staging-readonly identity."
  }
}

variable "approved_ssh_source_cidrs" {
  description = "Narrow owner-approved operator, VPN, or bastion CIDRs."
  type        = set(string)
  validation {
    condition = length(var.approved_ssh_source_cidrs) > 0 && alltrue([
      for cidr in var.approved_ssh_source_cidrs : can(cidrhost(cidr, 0)) && !contains(["0.0.0.0/0", "::/0"], cidr)
    ])
    error_message = "SSH requires explicit non-global operator, VPN, or bastion CIDRs."
  }
}

variable "approved_egress_fqdns" {
  description = "Reviewed FQDN suffix allowlist enforced by the staging proxy."
  type        = set(string)
  validation {
    condition = alltrue([
      for required in ["archive.ubuntu.com", "security.ubuntu.com"] : contains(var.approved_egress_fqdns, required)
      ]) && alltrue([
      for name in var.approved_egress_fqdns : contains([
        "api.github.com",
        "archive.ubuntu.com",
        "azure.archive.ubuntu.com",
        "github.com",
        "ghcr.io",
        "objects.githubusercontent.com",
        "pkg-containers.githubusercontent.com",
        "release-assets.githubusercontent.com",
        "security.ubuntu.com",
      ], name)
    ])
    error_message = "Egress destinations must come from the Git-reviewed catalog and include both required Ubuntu mirrors."
  }
}

variable "approved_egress_ports" {
  description = "Reviewed proxy destination ports."
  type        = set(number)
  default     = [80, 443]
  validation {
    condition     = var.approved_egress_ports == toset([80, 443])
    error_message = "The initial gateway authority permits only HTTP and HTTPS."
  }
}

variable "approved_ntp_fqdns" {
  description = "Git-reviewed time authorities used only by the staging gateway."
  type        = set(string)
  default     = ["ntp.ubuntu.com"]
  validation {
    condition     = var.approved_ntp_fqdns == toset(["ntp.ubuntu.com"])
    error_message = "Changing the reviewed Stage 6 time authority requires review."
  }
}

variable "known_internal_production_deny_cidrs" {
  description = "Git-reviewed internal production hosts and networks denied from Stage 6."
  type        = set(string)
  default     = ["37.27.128.39/32", "65.109.65.169/32", "10.40.0.0/24"]
  validation {
    condition = alltrue([
      for required in ["37.27.128.39/32", "65.109.65.169/32", "10.40.0.0/24"] : contains(var.known_internal_production_deny_cidrs, required)
    ])
    error_message = "The reviewed Klyrow/Postal, shared-host and production VLAN inventory is mandatory."
  }
}
