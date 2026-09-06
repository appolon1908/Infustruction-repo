# Staging read-only and production-canary controller freeze

This marker freezes pull request `#69` after permanent source convergence and removal of every temporary repository-writing finalizer.

- Frozen parent head: `006385ecd4fd5e9f9fd705fc50b7b4ff5bf944b2`
- Controller source: `operations/staging-readonly/release_control_v2.py`
- Staging workflow: `.github/workflows/staging-readonly-certification.yml`
- Full guarded chain: `.github/workflows/full-readonly-release-chain.yml`
- Required Kong smoke routes: `29`
- Maximum production read-only canary: `1%`
- Allowed canary methods: `GET`, `HEAD`
- Image builds or retags during deployment: forbidden
- Live-effect capabilities: disabled
- Runtime contacted by this source change: no
- Production traffic changed by this source change: no

The commit containing this marker is the frozen pull-request source head. Any subsequent source change invalidates this freeze and requires a new exact-head validation and independent review. A protected merge establishes controller authority only; it does not prove that a staging host exists, configure secrets, deploy a candidate, certify rollback, or authorize production traffic.
