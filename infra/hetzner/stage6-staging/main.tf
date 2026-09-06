locals {
  runtime_name = "codestra-stage6-staging-01"
  gateway_name = "codestra-stage6-egress-01"
  common_labels = {
    environment = "staging"
    production  = "false"
    klyrow      = "false"
    postal      = "false"
    managed-by  = "opentofu"
  }
  runtime_labels = merge(local.common_labels, { role = "stage6-runtime" })
  gateway_labels = merge(local.common_labels, { role = "stage6-egress-gateway" })
}

moved {
  from = hcloud_firewall.stage6
  to   = hcloud_firewall.runtime
}

resource "hcloud_network" "stage6" {
  name     = "codestra-stage6-staging-net"
  ip_range = var.network_cidr
  labels   = local.common_labels
  lifecycle {
    prevent_destroy = true
    precondition {
      condition = alltrue([for production in var.known_internal_production_deny_cidrs :
        !cidrcontains(var.network_cidr, cidrhost(production, 0)) && !cidrcontains(production, cidrhost(var.network_cidr, 0))
      ])
      error_message = "The Stage 6 network overlaps reviewed production authority."
    }
  }
}

resource "hcloud_network_subnet" "stage6" {
  network_id   = hcloud_network.stage6.id
  type         = "cloud"
  network_zone = "eu-central"
  ip_range     = var.staging_subnet_cidr
}

resource "hcloud_firewall" "runtime" {
  name   = "${local.runtime_name}-deny-default"
  labels = local.runtime_labels
  rule {
    direction   = "in"
    protocol    = "tcp"
    port        = "22"
    source_ips  = sort(tolist(var.approved_ssh_source_cidrs))
    description = "SSH from approved operator VPN or bastion only"
  }
  rule {
    direction       = "out"
    protocol        = "tcp"
    port            = "3128"
    destination_ips = ["${var.egress_gateway_private_ip}/32"]
    description     = "Public HTTP and HTTPS through controlled proxy"
  }
  rule {
    direction       = "out"
    protocol        = "tcp"
    port            = "53"
    destination_ips = ["${var.egress_gateway_private_ip}/32"]
    description     = "DNS through staging security boundary"
  }
  rule {
    direction       = "out"
    protocol        = "udp"
    port            = "53"
    destination_ips = ["${var.egress_gateway_private_ip}/32"]
    description     = "DNS through staging security boundary"
  }
  rule {
    direction       = "out"
    protocol        = "udp"
    port            = "123"
    destination_ips = ["${var.egress_gateway_private_ip}/32"]
    description     = "NTP through staging security boundary"
  }
  rule {
    direction       = "out"
    protocol        = "tcp"
    port            = "1-65535"
    destination_ips = [var.staging_subnet_cidr]
    description     = "Stage 6 private dependencies only"
  }
}

resource "hcloud_firewall" "egress" {
  name   = "${local.gateway_name}-boundary"
  labels = local.gateway_labels
  rule {
    direction   = "in"
    protocol    = "tcp"
    port        = "22"
    source_ips  = sort(tolist(var.approved_ssh_source_cidrs))
    description = "SSH from approved operator VPN or bastion only"
  }
  rule {
    direction   = "in"
    protocol    = "tcp"
    port        = "3128"
    source_ips  = ["${var.private_ip}/32"]
    description = "Proxy only from Stage 6 runtime"
  }
  rule {
    direction   = "in"
    protocol    = "tcp"
    port        = "53"
    source_ips  = ["${var.private_ip}/32"]
    description = "DNS only from Stage 6 runtime"
  }
  rule {
    direction   = "in"
    protocol    = "udp"
    port        = "53"
    source_ips  = ["${var.private_ip}/32"]
    description = "DNS only from Stage 6 runtime"
  }
  rule {
    direction   = "in"
    protocol    = "udp"
    port        = "123"
    source_ips  = ["${var.private_ip}/32"]
    description = "NTP only from Stage 6 runtime"
  }
  dynamic "rule" {
    for_each = var.approved_egress_ports
    content {
      direction       = "out"
      protocol        = "tcp"
      port            = tostring(rule.value)
      destination_ips = ["0.0.0.0/0"]
      description     = "Gateway-only public egress; Squid enforces FQDN policy"
    }
  }
  rule {
    direction       = "out"
    protocol        = "tcp"
    port            = "53"
    destination_ips = ["0.0.0.0/0"]
    description     = "Gateway-only DNS recursion"
  }
  rule {
    direction       = "out"
    protocol        = "udp"
    port            = "53"
    destination_ips = ["0.0.0.0/0"]
    description     = "Gateway-only DNS recursion"
  }
  rule {
    direction       = "out"
    protocol        = "udp"
    port            = "123"
    destination_ips = ["0.0.0.0/0"]
    description     = "Gateway-only NTP to Git-reviewed authority"
  }
}

resource "hcloud_server" "egress" {
  name               = local.gateway_name
  server_type        = var.egress_gateway_server_type
  image              = var.image
  location           = var.location
  ssh_keys           = sort(tolist(var.approved_ssh_key_ids))
  labels             = local.gateway_labels
  backups            = true
  keep_disk          = true
  delete_protection  = true
  rebuild_protection = true
  user_data = templatefile("${path.module}/egress-cloud-init.yaml.tftpl", {
    approved_fqdns        = sort(tolist(var.approved_egress_fqdns))
    gateway_private_ip    = var.egress_gateway_private_ip
    runtime_private_ip    = var.private_ip
    staging_subnet_cidr   = var.staging_subnet_cidr
    approved_ntp_fqdns    = sort(tolist(var.approved_ntp_fqdns))
    production_deny_cidrs = sort(tolist(var.known_internal_production_deny_cidrs))
  })
  firewall_ids = [hcloud_firewall.egress.id]
  public_net {
    ipv4_enabled = true
    ipv6_enabled = false
  }
  lifecycle { prevent_destroy = true }
}

resource "hcloud_server_network" "egress" {
  server_id  = hcloud_server.egress.id
  network_id = hcloud_network.stage6.id
  ip         = var.egress_gateway_private_ip
  depends_on = [hcloud_network_subnet.stage6]
}

resource "hcloud_server" "stage6" {
  name               = local.runtime_name
  server_type        = var.server_type
  image              = var.image
  location           = var.location
  ssh_keys           = sort(tolist(var.approved_ssh_key_ids))
  labels             = local.runtime_labels
  backups            = true
  keep_disk          = true
  delete_protection  = true
  rebuild_protection = true
  user_data = templatefile("${path.module}/cloud-init.yaml.tftpl", {
    egress_gateway_private_ip            = var.egress_gateway_private_ip
    staging_readonly_operator_public_key = trimspace(var.staging_readonly_operator_public_key)
  })
  firewall_ids = [hcloud_firewall.runtime.id]
  depends_on   = [hcloud_server_network.egress]
  public_net {
    ipv4_enabled = true
    ipv6_enabled = false
  }
  lifecycle { prevent_destroy = true }
}

resource "hcloud_server_network" "stage6" {
  server_id  = hcloud_server.stage6.id
  network_id = hcloud_network.stage6.id
  ip         = var.private_ip
  depends_on = [hcloud_network_subnet.stage6, hcloud_server_network.egress]
}
