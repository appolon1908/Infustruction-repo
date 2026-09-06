# Stage 6 isolated staging host sizing

Status: reviewed proposal; no cloud resource created.

## Evidence

On 2026-08-31, a no-stream read of the 22 currently running Stage 6 containers
showed approximately 2.35 GiB combined resident memory. Sampled aggregate CPU
was approximately 11%, dominated by PostgreSQL and Odoo. The scope contains
three PostgreSQL instances, two Redis instances, six n8n processes, three Odoo
processes, Middleware workers, and the desktop staging service.

Steady-state use is not a safe sizing ceiling. Stage 6 also requires concurrent
image extraction, one-shot migrations, database backup/restore verification,
Prometheus and host/container agents, controlled-failure recovery, and enough
memory to avoid swapping during Odoo/n8n startup.

## Selection

`CX43`: 8 shared x86 vCPUs, 16 GB RAM, 160 GB local disk.

- Memory: about 4x the observed workload footprint after reserving 2 GiB for
  the OS/runtime and about 4 GiB for migration and monitoring bursts.
- CPU: eight vCPUs allow parallel database, Odoo and n8n startup while remaining
  a cost-optimized non-production plan.
- Disk: 160 GB provides room for pinned images, three staging databases,
  sanitized fixtures, migration backups and monitoring buffers. Disk alerts
  must fire before 70% use.
- Architecture: x86 avoids introducing an unreviewed multi-architecture image
  requirement.

This is the smallest defensible plan. Downsizing requires measured peak
migration/E2E evidence; resizing upward requires a reviewed OpenTofu change.

Hetzner bills servers hourly up to a monthly cap. Current price must be read
from the approved project immediately before apply because location, IPv4 and
pricing can change. Hetzner's 2026 price schedule lists CX43 in Germany/Finland
at EUR 15.99/month excluding IPv4 and VAT from 2026-06-15; IPv4, backups and
taxes are additional. Source:
<https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/>.
