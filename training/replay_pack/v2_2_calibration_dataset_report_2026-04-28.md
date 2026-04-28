# v2.2 Calibration Dataset Report

Date: 2026-04-28

Hub repo:

- `ChrisRPL/satellite-disruption-triage-aux-v2-2`
- https://huggingface.co/datasets/ChrisRPL/satellite-disruption-triage-aux-v2-2

Source:

- `ChrisRPL/satellite-disruption-triage-aux-v2-1`

## Purpose

This is a compact calibration/gold repair slice for the current VLM bottleneck:
the v8 adapter under-calls positive disruption cases and predicts zero
`downlink_now` rows on positive smoke tests.

v2.2 is intentionally not a bulk dataset. It is an event-held-out,
real-image calibration pack focused on civilian explosion disruption.

## Counts

| Split | Rows | Event | Location |
|---|---:|---|---|
| train_calibration | 93 | Bata ammunition depot explosions | Bata, Equatorial Guinea |
| eval_gold | 51 | Beirut port ammonium nitrate explosion | Beirut, Lebanon |
| total | 144 | 2 events | 2 locations |

Class balance:

| Split | downlink_now | defer | discard |
|---|---:|---:|---:|
| train_calibration | 37 | 29 | 27 |
| eval_gold | 17 | 17 | 17 |
| total | 54 | 46 | 44 |

Other facts:

- images: 288
- hard negatives: 44
- modality: 144 optical-to-SAR rows
- license: CC-BY-NC-4.0
- uploaded size: about 105 MB

## Validation

All checks passed locally and after Hub upload:

- JSONL parse
- ordered flat schema
- evidence-first enum/schema validation
- bbox policy
- image path existence
- image file validity
- event-held-out split
- location-held-out split
- duplicate row check

Verified downloadable Hub files:

- `images/baseline/bright_bata-explosion_0000_baseline.png`
- `images/current/bright_beirut-explosion_0000_current.png`

## Decision

Use v2.2 as the next adapter calibration/eval source before submitting any v9
training run. Do not train immediately from v2.2 until the eval command and
acceptance gate are configured to treat `eval_gold_flat.jsonl` as the promotion
gate.

Known limitations:

- only two explosion events
- optical-to-SAR modality gap remains
- inherited/rule-derived labels, not human expert review
- non-commercial license
