# Stage 6 isolated staging host provisioning execution gate

The isolated staging host must be created and verified by the repository-owned `stage6-provision-staging-host.yml` workflow. A production or shared application host is not an acceptable substitute.

## Required protected inputs

- exact infrastructure source SHA;
- approved Hetzner project and network identifiers supplied as environment variables or encrypted secrets;
- one dedicated staging host identity and private address;
- expected operating-system image, size, region, VLAN/vSwitch, firewall profile, storage, and labels;
- protected SSH public key reference for provisioning and separate read-only operator credential for certification;
- known-host fingerprint captured after creation;
- immutable bootstrap artifacts and checksums;
- destroy/rollback authority and change record.

## Required result

```text
HOST_STATUS=CREATED_AND_VERIFIED
PUBLIC_APPLICATION_TRAFFIC=0
PRODUCTION_NETWORK_MEMBERSHIP=NO
PRIVATE_STAGING_NETWORK=PASS
SSH_HOST_KEY_VERIFIED=PASS
BASELINE_HARDENING=PASS
DOCKER_HEALTH=PASS
FAILED_SYSTEMD_UNITS=0
PRODUCTION_SECRETS_INSTALLED=NO
BUSINESS_WRITES_ENABLED=NO
```

## Fail-closed rules

The workflow must stop before any provider mutation when required environment values, protected approval, billing/quota, exact source identity, network authority, SSH key reference, or destroy/rollback metadata is missing. It must never silently reuse `37.27.128.39`, `65.109.65.169`, the VICIdial host, or any existing production node as the isolated staging host.

No private key, provider token, password, server credential, or secret value may appear in repository evidence or workflow summaries.

## Handoff to production-platform

After successful provisioning, publish only sanitized evidence:

- staging host ID and canonical non-secret name;
- private address or protected environment variable reference;
- public address only if one is explicitly approved for operator access;
- SSH host-key fingerprints;
- exact infrastructure source SHA;
- bootstrap artifact checksums;
- network/firewall profile IDs;
- creation timestamp;
- verification results;
- destroy/rollback procedure.

The production-platform `staging-readonly` environment may then receive its host, user, port, known-hosts, and endpoint-manifest values through approved account-side configuration. Provisioning does not authorize application deployment or production canary traffic.
