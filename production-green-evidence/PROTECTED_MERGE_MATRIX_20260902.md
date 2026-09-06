# Protected merge matrix — 2026-09-02

Captured at `2026-09-02T23:24:00Z` from GitHub. All eight heads are current
with their protected base (`behind=0`). Repository auto-merge is disabled for
all eight repositories, so no auto-merge request can be queued. No commit in
the PR set has a GitHub signature object; current rules do not report signature
failure as a merge-state blocker.

| Repository | PR | Exact head | Base SHA | Merge state | Checks | Review | Threads | Blocker |
|---|---:|---|---|---|---|---|---:|---|
| `Codestra-SRL/codestra-middleware` | 282 | `a397f6084703472ae2fbfb1995cc5508bddabe39` | `61e5948f9c800f4dd587cce75a332b617f418a0c` | MERGED `c8c8d6fad442e7a65eeac353a0f0853797ea84a8` | no protected contexts reported | gates satisfied | 0 | NONE |
| `appolon1908-hue/Odoo` | 58 | `b77dd59fa1b3c054a2fd9c61049f534b7cbe59d7` | `2015c682c0b6e37b306d8a2b75ee025578637b2e` | BLOCKED | all 5 required contexts pass | `kazan555` requested; no exact-head approval | 0 | CODEOWNER_APPROVAL_PENDING |
| `appolon1908-hue/Codestra-AI` | 5 | `9d141379a9f355c8dbbee56214be4129e9c9f66b` | `94d990e269b3a8cdc8176088be65dd02fdac37ea` | MERGED `1832d19eb779146beaf7aa9ead17aac4f502beb7` | 2 pass | findings fixed | 0 | NONE |
| `appolon1908-hue/Codestra-Communication-CC` | 5 | `ec56638cbf543f02ad960c3647e74481d5a5bbb1` | `0ee0dcbd3d4a9405ffc7d14019bf4a1105f91113` | MERGED `cceb1fd7462f765e6ac36db154086d56a88ba712` | 2 pass | gates satisfied | 0 | NONE |
| `appolon1908-hue/Codestra-Marketing-` | 5 | `4a7c0277d831e658ed3ed77ef9bf331171c0b819` | `460ff98f64ef9f0724fe4d2afc51a1a6c5b053dd` | MERGED `3f78cbdeccbdd69f1dfa7f4d31232b43e798047a` | 2 pass | gates satisfied | 0 | NONE |
| `appolon1908-hue/Codesrea-Social-` | 5 | `9479a3bc59bd8f809e052c191fe138f72da4531c` | `7bc0dd9ee8a13abbd1463ca106629ad63d957145` | MERGED `1323a7335e1724a00406aeadd1fec4c8e8af5f1a` | 2 pass | findings fixed | 0 | NONE |
| `appolon1908-hue/klyrow.com` | 66 | `ac6d9dea634f88d6321735d63b18f5632861d9b7` | `f67b1529acea52ea37976f9e6defbe5a5430d6b4` | BLOCKED | frontend/test/secrets pass; image running | prior approval stale after required base reconciliation; `kazan555` re-requested | 0 | CHECKS_PENDING |
| `appolon1908-hue/Infustruction-repo` | 60 | `de0f3c3c5f67f7de537db33a83452ad9ef039564` | `cae843886a6ece21025b730de458dd14a47a9f51` | BLOCKED | 2 pass | `kazan555` requested; no exact-head approval | 0 | CODEOWNER_APPROVAL_PENDING |

The Odoo head changed after the starting evidence SHA through two externally
authored commits that address the valid deployed-gate review finding. This
matrix records the live GitHub head and does not overwrite or rewrite it.

Klyrow `main` advanced after the exact-head approval, and GitHub changed the PR
to `CONFLICTING`. The feature branch was reconciled with current protected main
without rewriting history. Only the two conflicting Dockerfiles required manual
resolution; targeted reproducibility/readiness tests passed 30/30. The resulting
head is `ac6d9dea634f88d6321735d63b18f5632861d9b7`; the prior approval is correctly
treated as stale, exact-head CI run `33694564916` is active, and fresh review was
requested.

## Protected-merge build evidence

The Middleware protected merge triggered run
[`33657039930`](https://github.com/Codestra-SRL/codestra-middleware/actions/runs/33657039930)
for exact SHA `c8c8d6fad442e7a65eeac353a0f0853797ea84a8`. GitHub reports
`conclusion=startup_failure`; its workflow record is deleted with path
`BuildFailed`, and the check suite contains zero jobs. An unchanged retry was
attempted and GitHub returned `This workflow run cannot be retried`. No workflow
or branch-protection setting was changed. Immutable Middleware image, SBOM and
provenance publication therefore remain blocked by an external Actions startup
failure, not by a source-test failure.

`PRODUCTION_BUSINESS_WRITES_ENABLED=NO`

`PRODUCTION_EXTERNAL_EFFECTS_ENABLED=NONE`
