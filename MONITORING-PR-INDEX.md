# Integrated monitoring commit and verification index

Snapshot: 2026-09-10T16:17:24.267Z

**63 repositories have committed design/onboarding records and open pull requests.** The shared design includes 17 monitoring components, with Backstage, Sentry and Wazuh added. Repository records are source/onboarding contracts; runtime coverage remains unverified.

**36 API operations are implemented and verified:** [Middleware PR 226](https://github.com/appolon1908-hue/Middleware-/pull/226), commit `cedaa23b89f84f365ae6789413411c3f01516952`; [PostgreSQL CI](https://github.com/appolon1908-hue/Middleware-/actions/runs/34500827916) passes **23 tests**, including all 36 exact method/path pairs, transactional replay/concurrency, original-JWT authorization, campaign isolation, three application entrypoints, backend failures, empty migration downgrade/reupgrade and nonempty evidence preservation. External backends use test transports in this suite; live backend connectivity is not certified.

The new commits in [Backstage](https://github.com/appolon1908-hue/Backstage/pull/1), [Sentry](https://github.com/appolon1908-hue/Sentry/pull/1) and [Wazuh](https://github.com/appolon1908-hue/Wazuh/pull/1) have successful validate CI. Backstage's catalog includes 63 source Resources plus the ownership group, monitoring System and API definition.

## CI snapshot

45 repositories have passing observed workflows, 6 need attention, 2 still have running jobs, and 10 have no triggered workflow at their recorded commit. A passing source workflow is distinct from an independent review, protected merge gate or deployed runtime. See [machine-readable evidence](monitoring-pr-status.json) for each workflow URL, conclusion and tested commit.

[Migration/release review packet](MONITORING-MIGRATION-REVIEW.md) explains the protected Middleware schema-authority requirement and unchanged trust-workflow mismatch. No approval policy, trust hash allowlist or protected release tuple has been bypassed or rewritten to make CI green. Nothing has been merged or deployed by this work.

## Repository changes

| Repository | Pull request | Recorded commit | CI snapshot |
| --- | --- | --- | --- |
| Middleware- | [PR 226](https://github.com/appolon1908-hue/Middleware-/pull/226) | [cedaa23b89f8](https://github.com/appolon1908-hue/Middleware-/commit/cedaa23b89f84f365ae6789413411c3f01516952) | needs-attention |
| Infustruction-repo | [PR 122](https://github.com/appolon1908-hue/Infustruction-repo/pull/122) | [66ce3cb997d0](https://github.com/appolon1908-hue/Infustruction-repo/commit/66ce3cb997d0d13d0e212db64b1e05d9e94c11ca) | passed |
| Backstage | [PR 1](https://github.com/appolon1908-hue/Backstage/pull/1) | [1bcb8647a6e9](https://github.com/appolon1908-hue/Backstage/commit/1bcb8647a6e9bc275045d432a53e87a4a4b034a6) | passed |
| Sentry | [PR 1](https://github.com/appolon1908-hue/Sentry/pull/1) | [83eeabf4e1ba](https://github.com/appolon1908-hue/Sentry/commit/83eeabf4e1ba1e5e2ee4d9d5510f8437d39567b3) | passed |
| Wazuh | [PR 1](https://github.com/appolon1908-hue/Wazuh/pull/1) | [af13c8307e77](https://github.com/appolon1908-hue/Wazuh/commit/af13c8307e777eae3164b55a2278972f5e3d7e79) | passed |
| Frontend-Resturant- | [PR 13](https://github.com/appolon1908-hue/Frontend-Resturant-/pull/13) | [7282fc2e0f86](https://github.com/appolon1908-hue/Frontend-Resturant-/commit/7282fc2e0f86591d87329ae15d1c93e0a9bf095a) | passed |
| codestra-production-platform | [PR 340](https://github.com/appolon1908-hue/codestra-production-platform/pull/340) | [0a9f15828862](https://github.com/appolon1908-hue/codestra-production-platform/commit/0a9f15828862bc1aaf25b80d4e95508b32af8e5d) | needs-attention |
| Codestraxxxx | [PR 2](https://github.com/appolon1908-hue/Codestraxxxx/pull/2) | [ab5d7bd61556](https://github.com/appolon1908-hue/Codestraxxxx/commit/ab5d7bd615560c9db6ec42932b3d78de3011f70a) | passed |
| codestra | [PR 28](https://github.com/appolon1908-hue/codestra/pull/28) | [8d5bcd6d3a8c](https://github.com/appolon1908-hue/codestra/commit/8d5bcd6d3a8cc6729d2eda9fe683b6c7e4ecc69d) | needs-attention |
| beyvra-backend | [PR 107](https://github.com/appolon1908-hue/beyvra-backend/pull/107) | [e640ab06f08b](https://github.com/appolon1908-hue/beyvra-backend/commit/e640ab06f08b82eb75a16450def7f00291a76ba9) | passed |
| codestra-backend | [PR 4](https://github.com/appolon1908-hue/codestra-backend/pull/4) | [0f1f6d9992c0](https://github.com/appolon1908-hue/codestra-backend/commit/0f1f6d9992c081a290f7a95ede89c47c310fdddc) | passed |
| backend2 | [PR 10](https://github.com/appolon1908-hue/backend2/pull/10) | [ea5f316e16b6](https://github.com/appolon1908-hue/backend2/commit/ea5f316e16b69b002e98e8ec29cfb52fa6117029) | needs-attention |
| beyvra-frontend | [PR 42](https://github.com/appolon1908-hue/beyvra-frontend/pull/42) | [fad35760130e](https://github.com/appolon1908-hue/beyvra-frontend/commit/fad35760130e7ac70d33151f47d97151e4268b13) | passed |
| scrapper | [PR 33](https://github.com/appolon1908-hue/scrapper/pull/33) | [df35f5e4499a](https://github.com/appolon1908-hue/scrapper/commit/df35f5e4499a33d680196348586feb420f6ef3b5) | passed |
| Breero.com | [PR 125](https://github.com/appolon1908-hue/Breero.com/pull/125) | [8e89a865583b](https://github.com/appolon1908-hue/Breero.com/commit/8e89a865583bb2abf46f9ba44d3a5df92626f849) | passed |
| booked4seasons | [PR 11](https://github.com/appolon1908-hue/booked4seasons/pull/11) | [b30c0fe9e53d](https://github.com/appolon1908-hue/booked4seasons/commit/b30c0fe9e53d494aac5011e283fdf59c2a7b48fd) | passed |
| kyqra | [PR 7](https://github.com/appolon1908-hue/kyqra/pull/7) | [945d873e2c62](https://github.com/appolon1908-hue/kyqra/commit/945d873e2c62241d352c0aab3eec5b69f71138e7) | passed |
| telnexa | [PR 33](https://github.com/appolon1908-hue/telnexa/pull/33) | [4cf4279c8b02](https://github.com/appolon1908-hue/telnexa/commit/4cf4279c8b02cd0f5344b7ba4c68ccea90fc7333) | passed |
| kyqra-crawler | [PR 50](https://github.com/appolon1908-hue/kyqra-crawler/pull/50) | [d754fee59748](https://github.com/appolon1908-hue/kyqra-crawler/commit/d754fee59748ef4d5a3ebf8d553070cafd87e402) | passed |
| klyrow.com | [PR 111](https://github.com/appolon1908-hue/klyrow.com/pull/111) | [8e108c6950fc](https://github.com/appolon1908-hue/klyrow.com/commit/8e108c6950fc6074dd8ed87806ed8f76724e3834) | running |
| codestra-provisioning-service | [PR 30](https://github.com/appolon1908-hue/codestra-provisioning-service/pull/30) | [0ee42ae32af0](https://github.com/appolon1908-hue/codestra-provisioning-service/commit/0ee42ae32af068f0097b2c3b4bc38710d5757065) | passed |
| Moneybee-frontend- | [PR 35](https://github.com/appolon1908-hue/Moneybee-frontend-/pull/35) | [0e5b35f3904c](https://github.com/appolon1908-hue/Moneybee-frontend-/commit/0e5b35f3904c06462bad08dfa440de0a56c59f5d) | passed |
| Moneybee-Backend | [PR 77](https://github.com/appolon1908-hue/Moneybee-Backend/pull/77) | [526c692bd807](https://github.com/appolon1908-hue/Moneybee-Backend/commit/526c692bd8076ca552912ac8cf5e222599152698) | passed |
| transportaion-Frontend | [PR 10](https://github.com/appolon1908-hue/transportaion-Frontend/pull/10) | [5cebc6027bee](https://github.com/appolon1908-hue/transportaion-Frontend/commit/5cebc6027bee15e6973fed4a9eb0f7c5bdbd86d2) | passed |
| transportation-backend- | [PR 18](https://github.com/appolon1908-hue/transportation-backend-/pull/18) | [4ad5f2878c67](https://github.com/appolon1908-hue/transportation-backend-/commit/4ad5f2878c67e2f030a9ad6bde1f397eb13f3e54) | passed |
| LARIM-A-Fornt-end | [PR 8](https://github.com/appolon1908-hue/LARIM-A-Fornt-end/pull/8) | [74467bbc8553](https://github.com/appolon1908-hue/LARIM-A-Fornt-end/commit/74467bbc85534c1a58e744c301360ecd13919746) | passed |
| LARIM-A-Backend | [PR 7](https://github.com/appolon1908-hue/LARIM-A-Backend/pull/7) | [34f59432cc12](https://github.com/appolon1908-hue/LARIM-A-Backend/commit/34f59432cc122eaccb0b6629caba7581278aa449) | needs-attention |
| Telnexa-web | [PR 14](https://github.com/appolon1908-hue/Telnexa-web/pull/14) | [db5b17109fea](https://github.com/appolon1908-hue/Telnexa-web/commit/db5b17109fea496824cd755413511366da5a94c0) | passed |
| klyrow-Website- | [PR 30](https://github.com/appolon1908-hue/klyrow-Website-/pull/30) | [149e1889b6be](https://github.com/appolon1908-hue/klyrow-Website-/commit/149e1889b6be710b4552bfbf06cafc196264b02c) | passed |
| Odoo | [PR 98](https://github.com/appolon1908-hue/Odoo/pull/98) | [6cdee8611cc8](https://github.com/appolon1908-hue/Odoo/commit/6cdee8611cc89d72341a8ca69616f6ae07d2066f) | passed |
| Keycloak | [PR 110](https://github.com/appolon1908-hue/Keycloak/pull/110) | [8222aa0084ac](https://github.com/appolon1908-hue/Keycloak/commit/8222aa0084ac141dd1a05ef23460088933694b12) | needs-attention |
| N8N | [PR 61](https://github.com/appolon1908-hue/N8N/pull/61) | [8f2d4225fd98](https://github.com/appolon1908-hue/N8N/commit/8f2d4225fd989584edc6bd5142877f8ff15b9971) | passed |
| Vicidialer-Codestra | [PR 47](https://github.com/appolon1908-hue/Vicidialer-Codestra/pull/47) | [30ebbddf46b1](https://github.com/appolon1908-hue/Vicidialer-Codestra/commit/30ebbddf46b1853e0b53db59372b9afd56473ddc) | passed |
| Kong | [PR 100](https://github.com/appolon1908-hue/Kong/pull/100) | [5e96bbe687e3](https://github.com/appolon1908-hue/Kong/commit/5e96bbe687e336f6c5c8afcc6d48bef568dc9ba3) | passed |
| social.codestra.co | [PR 49](https://github.com/appolon1908-hue/social.codestra.co/pull/49) | [151febfaaa82](https://github.com/appolon1908-hue/social.codestra.co/commit/151febfaaa8256f51268d2c4878897d5c8d35b1f) | running |
| SDK-repository | [PR 140](https://github.com/appolon1908-hue/SDK-repository/pull/140) | [2e25e9303d23](https://github.com/appolon1908-hue/SDK-repository/commit/2e25e9303d237161709056d888c96c652a43872a) | passed |
| Caddy | [PR 169](https://github.com/appolon1908-hue/Caddy/pull/169) | [a211989ab05c](https://github.com/appolon1908-hue/Caddy/commit/a211989ab05c8cf2033635476083f786226fa8a6) | passed |
| documentaions | [PR 13](https://github.com/appolon1908-hue/documentaions/pull/13) | [e93ed65f086a](https://github.com/appolon1908-hue/documentaions/commit/e93ed65f086a3827d948b43d7c061c7f7d979486) | passed |
| communication-platform- | [PR 9](https://github.com/appolon1908-hue/communication-platform-/pull/9) | [74396318ff97](https://github.com/appolon1908-hue/communication-platform-/commit/74396318ff970ddf066a0fe621d2f56213901614) | not-triggered |
| Codestra-Grafana- | [PR 28](https://github.com/appolon1908-hue/Codestra-Grafana-/pull/28) | [7c5d4bfbdc93](https://github.com/appolon1908-hue/Codestra-Grafana-/commit/7c5d4bfbdc93ea3193ba6ef9ed40191da04cb0eb) | not-triggered |
| Codestra-Prometheus | [PR 66](https://github.com/appolon1908-hue/Codestra-Prometheus/pull/66) | [58b705cda683](https://github.com/appolon1908-hue/Codestra-Prometheus/commit/58b705cda683a2be122f7d7b23256fae375bbf3e) | passed |
| Codestra-Alertmanager | [PR 25](https://github.com/appolon1908-hue/Codestra-Alertmanager/pull/25) | [6482c34bad18](https://github.com/appolon1908-hue/Codestra-Alertmanager/commit/6482c34bad18a61a38b9b856975610301bd187ef) | passed |
| Codestra-Loki | [PR 37](https://github.com/appolon1908-hue/Codestra-Loki/pull/37) | [a571d8376ebf](https://github.com/appolon1908-hue/Codestra-Loki/commit/a571d8376ebfcd8a9ce3c563f2d2c44206b978cf) | passed |
| Codestra-Telemetry | [PR 54](https://github.com/appolon1908-hue/Codestra-Telemetry/pull/54) | [1af419d5f093](https://github.com/appolon1908-hue/Codestra-Telemetry/commit/1af419d5f093b5a4d1bca9c74422ecf8c54f5c8b) | passed |
| Codestra-Tempo | [PR 30](https://github.com/appolon1908-hue/Codestra-Tempo/pull/30) | [ceab5548196c](https://github.com/appolon1908-hue/Codestra-Tempo/commit/ceab5548196ceed9c704e3bf77851884570e6a84) | passed |
| Superset | [PR 48](https://github.com/appolon1908-hue/Superset/pull/48) | [e3f4c26dcc04](https://github.com/appolon1908-hue/Superset/commit/e3f4c26dcc049f81cbcdb8d5e63e884b50f35306) | passed |
| Codestra-Node-Exporter | [PR 33](https://github.com/appolon1908-hue/Codestra-Node-Exporter/pull/33) | [d0aff2c1255c](https://github.com/appolon1908-hue/Codestra-Node-Exporter/commit/d0aff2c1255cd104681d36e495bf8281a35ea736) | not-triggered |
| Codestra-cAdvisor | [PR 38](https://github.com/appolon1908-hue/Codestra-cAdvisor/pull/38) | [7564a400ad20](https://github.com/appolon1908-hue/Codestra-cAdvisor/commit/7564a400ad20aef39ac4215fa5c4c9416b25034c) | not-triggered |
| Codestra-Redis-Exporter | [PR 37](https://github.com/appolon1908-hue/Codestra-Redis-Exporter/pull/37) | [8f140a075901](https://github.com/appolon1908-hue/Codestra-Redis-Exporter/commit/8f140a0759019b93d344822fedb6ef99caef9bed) | not-triggered |
| Codestra-Blackbox-Exporter | [PR 33](https://github.com/appolon1908-hue/Codestra-Blackbox-Exporter/pull/33) | [2bc967096688](https://github.com/appolon1908-hue/Codestra-Blackbox-Exporter/commit/2bc96709668862b0765510b18b52d36d555909f4) | not-triggered |
| Codestra-Alloy | [PR 34](https://github.com/appolon1908-hue/Codestra-Alloy/pull/34) | [d51b0e8e7943](https://github.com/appolon1908-hue/Codestra-Alloy/commit/d51b0e8e7943668aaa2bd73f262b16c0d5b6a72f) | passed |
| Codestra-OpenBao | [PR 53](https://github.com/appolon1908-hue/Codestra-OpenBao/pull/53) | [f8f32558e343](https://github.com/appolon1908-hue/Codestra-OpenBao/commit/f8f32558e3436e59ca9d6f3e15a05dd78e539ba5) | not-triggered |
| Codestra-Postgres-Exporter | [PR 17](https://github.com/appolon1908-hue/Codestra-Postgres-Exporter/pull/17) | [81c6d92311f6](https://github.com/appolon1908-hue/Codestra-Postgres-Exporter/commit/81c6d92311f6ef0651f1aa2600578bed8c35ff16) | not-triggered |
| Codestra-Marketing- | [PR 14](https://github.com/appolon1908-hue/Codestra-Marketing-/pull/14) | [382e80602bbc](https://github.com/appolon1908-hue/Codestra-Marketing-/commit/382e80602bbcc7af3d4d672cf1d46e6c6f9d2b66) | passed |
| Codestra-Communication-CC | [PR 13](https://github.com/appolon1908-hue/Codestra-Communication-CC/pull/13) | [45146f379dc3](https://github.com/appolon1908-hue/Codestra-Communication-CC/commit/45146f379dc320f09d6f72b2712feeaac5974900) | passed |
| Codesrea-Social- | [PR 13](https://github.com/appolon1908-hue/Codesrea-Social-/pull/13) | [9e19d3c012af](https://github.com/appolon1908-hue/Codesrea-Social-/commit/9e19d3c012afabb88fdaeaf2b413e985411aae34) | passed |
| Codestra-AI | [PR 12](https://github.com/appolon1908-hue/Codestra-AI/pull/12) | [5605077dbd3c](https://github.com/appolon1908-hue/Codestra-AI/commit/5605077dbd3cad64b4cab2705ad50e087c4c75cf) | passed |
| codestra-foundation | [PR 4](https://github.com/appolon1908-hue/codestra-foundation/pull/4) | [751e98f9d2a2](https://github.com/appolon1908-hue/codestra-foundation/commit/751e98f9d2a2d6f2f7ff5bb78f9f1e74f3fd30cf) | passed |
| codestra-production-runtime-authority | [PR 8](https://github.com/appolon1908-hue/codestra-production-runtime-authority/pull/8) | [add427f89ed8](https://github.com/appolon1908-hue/codestra-production-runtime-authority/commit/add427f89ed893b1f969d89bc2569310a4eb914d) | passed |
| Websocket- | [PR 7](https://github.com/appolon1908-hue/Websocket-/pull/7) | [1871a9e352a5](https://github.com/appolon1908-hue/Websocket-/commit/1871a9e352a57eb3987c7f70769ded4317e51493) | passed |
| Database-migrations- | [PR 2](https://github.com/appolon1908-hue/Database-migrations-/pull/2) | [0848d7c406e0](https://github.com/appolon1908-hue/Database-migrations-/commit/0848d7c406e006b134f3311f15d624a45a61f974) | not-triggered |
| codestra-server-c | [PR 6](https://github.com/appolon1908-hue/codestra-server-c/pull/6) | [237a6c6f9a21](https://github.com/appolon1908-hue/codestra-server-c/commit/237a6c6f9a21b1dd9ded16d5c97044d648bdf82e) | passed |
| codestra-ruleset-toolkit | [PR 1](https://github.com/appolon1908-hue/codestra-ruleset-toolkit/pull/1) | [803483b83bf5](https://github.com/appolon1908-hue/codestra-ruleset-toolkit/commit/803483b83bf5543d2b9e440b4dfacb5e8420113d) | not-triggered |

## Checks needing attention

| Repository | Observed blocker |
| --- | --- |
| Middleware- | The API-specific PostgreSQL job passes. Full CI requires separate migration-head/history approval; the protected trust launcher also rejects an unchanged baseline workflow hash. |
| codestra-production-platform | Production merge gate requires exact-candidate and current-base CI. |
| codestra | Trivy scan step failed; this PR changes only the two onboarding documents. |
| backend2 | Dependency audit step failed; requirements are unchanged by this design PR. |
| LARIM-A-Backend | Source/test Ruff check failed and the security workflow also reports failure; application source is unchanged by this design PR. |
| Keycloak | Protected-main bootstrap reports missing independent approval. |

## Remaining rollout work

Review and merge the source changes through each repository's normal gates. Register actual service units and approved endpoint artifacts; provision release-bound backend/tenant identities; configure app instrumentation, collectors, BFF access and gateway quotas; verify fresh telemetry, endpoint reachability, alerts and recovery. Reconciliation currently records desired-versus-observed comparisons and never applies configuration. Successful source tests and catalog records do not establish that every application is connected.

This index records tested implementation commits. Its own documentation commit can be newer than the infrastructure row; use the PR checks for current branch-head CI.
