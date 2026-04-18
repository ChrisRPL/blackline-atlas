# Prompted Baseline Gate — 2026-04-18

Model:

- `LiquidAI/LFM2.5-VL-450M`

Frozen pack:

- non-demo corpus rebuilt from `10` exact captured cases
- split shape:
  - `dev`: `1`
  - `holdout_geo`: `3`
  - `holdout_stress`: `6`

## First pass

- pass rate: `4 / 10`
- schema valid: `7 / 10`
- false positives: `0`

Failure shape:

- all `4` real positives were discarded
- `2` exact controls failed only because confidence came back as `"high"`
- `1` inland food positive truncated before `action`

## Hardening pass

Small fix only:

- prompt tightened:
  - numeric confidence only
  - event/action guidance clearer
- parser repair:
  - map qualitative confidence strings to numeric values

Second pass:

- pass rate: `6 / 10`
- schema valid: `9 / 10`
- false positives: `0`

What stayed broken:

- all `4` real positives still undercalled
- predicted action counts stayed:
  - `discard`: `9`
  - `downlink_now`: `0`

## Decision

- training-prep lane: `yes`
- adapter tuning: `no`

Reason:

- structure is mostly sane now
- recall on exact positive anchors is still too weak
- the next gain should come from better positive coverage, not from pretending the model is already train-ready

## Next tranche call

1. reopen `water` positive hunt as the top category gap
2. keep `aid_02` behind water until a parcel-tight inland depot reappears
3. use more controls only as support work, not as the main growth lane
