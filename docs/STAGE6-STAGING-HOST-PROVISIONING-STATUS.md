# Stage 6 staging host provisioning status

```text
STATUS=NOT_RUN_HOST_NOT_CREATED
ISOLATED_STAGING_HOST=REQUIRED
PRODUCTION_HOST_REUSE=FORBIDDEN
PRODUCTION_SECRETS_INSTALLED=NO
APPLICATION_DEPLOYMENT_AUTHORIZED=NO
```

The repository-owned workflow `.github/workflows/stage6-provision-staging-host.yml` remains the only provisioning authority. This status may be changed to `CREATED_AND_VERIFIED` only by sanitized evidence from an exact protected workflow run proving host identity, network isolation, SSH host-key verification, baseline hardening, Docker health, zero failed systemd units, and a tested destroy/rollback procedure.
