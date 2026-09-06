# Stage 6 Safety Control Redesign

Status: design only; no runtime application authorized.

## Defect

The former gate required environment declarations on 17 running workloads.
Ten are frozen and Docker cannot change a container environment without
recreation. Requiring declaration presence while prohibiting recreation made
the gate unsatisfiable.

The replacement gate asserts effective denial at the network and governed
gateway boundaries. Environment variables remain useful declarations on newly
created workloads, but are not proof of enforcement for frozen containers.

## Seven-control mapping

| Control | Enforcement without recreation | Required read-back |
|---|---|---|
| `LIVE_ADVERTISING_ENABLED=false` | Disconnect unrestricted networks; internal-only network plus gateway deny for advertising capabilities and provider destinations. | Network membership, host egress rules, gateway route/capability denial, negative provider probe. |
| `SOCIAL_PUBLISHING_ENABLED=false` | Internal-only network; gateway rejects publish capability; host egress denies social-provider destinations. | Same three policy read-backs plus rejected synthetic publish. |
| `EXTERNAL_MODEL_CALLS_ENABLED=false` | Internal-only network; gateway denies model-call routes; host egress denies model-provider destinations. | Network/gateway/firewall read-back and rejected model probe. |
| `LIVE_SMS_DELIVERY=false` | Internal-only network; gateway denies SMS delivery; host egress denies SMS providers. | Rejected synthetic SMS and zero provider connection. |
| `LIVE_EMAIL_DELIVERY=false` | Internal-only network; gateway denies email delivery; host egress denies SMTP and email-provider destinations. | Rejected synthetic email, no TCP/UDP provider path, no queued delivery. |
| `LIVE_PSTN_DIALING=false` | Internal-only network; gateway denies PSTN capability; host egress denies SIP/RTP/provider destinations. | Rejected synthetic dial and no provider session. |
| `PRODUCTION_DIALING=DISABLED` | Gateway denies production-dialing subject/scope; host policy denies production telephony destinations. | Identity/gateway denial and no PSTN session. |

`EXTERNAL_DELIVERY_ENABLED=false` becomes the derived umbrella assertion that
all applicable delivery channels above are denied. It is not counted as an
eighth independent enforcement mechanism.

All seven guarantees are enforceable without container recreation. Network
membership may be changed on a running container, but that is still a runtime
mutation and requires a separately approved, per-container operation with the
original network membership captured for rollback. Frozen containers remain
frozen: no restart, recreation, image change, command change, mount change, or
environment change is permitted.

## Replacement gate

A workload is safety-complete only when all applicable properties pass:

1. exact approved network membership, with no unrestricted egress network;
2. host egress policy default-deny and exact internal/gateway allowlist;
3. gateway capability denial for every prohibited effect;
4. negative probes demonstrate denial without contacting a real provider;
5. no queued, pending, or completed external effect exists;
6. immutable container identity and frozen disposition remain unchanged.

Any missing read-back fails closed. Klyrow/Postal remains
`OUT_OF_SCOPE_ACTIVE_PRODUCTION_DO_NOT_TOUCH` and must never be used as a test
destination.

## Unfreeze decisions

No safety guarantee above intrinsically requires recreation. Environment
declaration parity, image-baked policy, command/mount changes, or a service
whose required internal connectivity cannot be preserved would require an
owner unfreeze decision. Current count requiring unfreeze for the proposed
network/gateway enforcement design: zero. No workload is unfrozen by this
document.
