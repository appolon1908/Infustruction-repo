# PR 101 main/development reconciliation — 2026-09-06

This record concerns Git source history only. It is not staging or production
promotion, provisioning, installation, or runtime certification.

Reviewed inputs:
- original PR 101 main snapshot: `a67b051fb0ca8647e5dc603d41884d0ba920bf6e`
- accepted main after PR 30: `de8e6b6d42d4e166736444d3730faf3a97a77510`
- development: `3d9d827980ebac51fc0bf0848a1011a1275e8ae2`

The candidate first incorporates accepted main and then merges development.
All development-only history is retained as ancestry. Four add/add conflicts
in the staging-host request, its validator, its tests, and its workflow were
resolved to main's later reviewed versions. Those versions preserve observed
provisioning evidence, bind its checksum, distinguish provisioned-but-unverified
from certified state, retain blocked-state handling, and prohibit workload
deployment and production certification. They do not invent a new host or
claim current host verification.

After this reconciliation and before adding this record, the combined tracked
tree was byte-identical to accepted main. Development's separate commit history
therefore does not justify resurrecting the older blocked-only request model
or dropping main's inventory/provenance regressions. No development-only
content outside those reviewed conflict resolutions was discarded.

The source is updated through an ordinary reviewed PR into development, not a
ref reset or force push. Main remains the accepted source authority. PR 62
must be rechecked against the resulting development head; this record does not
authorize its merge automatically. Issue 99, consumer workflow pins, successor
artifact verification, and every deployment gate remain separate.
