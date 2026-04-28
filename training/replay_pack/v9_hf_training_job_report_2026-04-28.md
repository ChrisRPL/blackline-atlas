# v9 HF Training Job Report

Date: 2026-04-28

## Purpose

Submit the calibration-gated v9 adapter run for `LiquidAI/LFM2.5-VL-450M` using the
`satellite-disruption-triage-aux-v2-2` real-image evidence-first bundle.

## Bundle

- Repo: `ChrisRPL/blackline-atlas-training-bundles`
- Path: `bundles/lfm25_vl_sft_train_hf_aux_v9.tar.gz`
- Train rows: 93
- Eval rows: 51
- Gold gate: `eval_gold_sft.jsonl` from `ChrisRPL/satellite-disruption-triage-aux-v2-2`

## Jobs

- Canceled path-based attempt: `69f0a5f0d70108f37ace0f29`
- URL-based MCP-token job: `69f0a6fed2c8bd8662bd1e64`
- Correct local-token wrapper job: `69f0a8afd70108f37ace0f44`
- Job URL: `https://huggingface.co/jobs/ChrisRPL/69f0a8afd70108f37ace0f44`
- Adapter target: `ChrisRPL/blackline-atlas-lfm25-vl-sft-train-hf-aux-v9-adapter`
- Hardware: `l4x1`
- Timeout: `8h`

The first job was canceled because inspection showed the HF command contained a local
filesystem script path. The corrected job uses the pinned public runner script URL:

`https://raw.githubusercontent.com/ChrisRPL/blackline-atlas/f7e2ee8/training/scripts/run_train_backend_hf_job.py`

The second job used the URL correctly but failed at adapter publication with `403
Forbidden` because the MCP `$HF_TOKEN` secret could not create/write under the
`ChrisRPL` model namespace. The final wrapper job used the local `ChrisRPL` write
token and completed successfully.

## Training Result

- Status: completed
- Adapter published: `ChrisRPL/blackline-atlas-lfm25-vl-sft-train-hf-aux-v9-adapter`
- Trainer steps: 21
- Eval loss: `2.9309 -> 2.9173`
- Assessment: training was stable but too weak to materially learn the required
  evidence-first JSON behavior.

## Smoke Eval Result

Local 3-case eval-gold smoke:

| Model | JSON valid | Evidence schema valid | Action match |
| --- | ---: | ---: | ---: |
| Base `LiquidAI/LFM2.5-VL-450M` | 3/3 | 0/3 | 0/3 |
| v9 adapter | 3/3 | 0/3 | 0/3 |

The adapter still emits descriptive nested JSON rather than the required
`EvidenceFirstCandidate` object. Full 51-case evaluation is not useful until a
run produces nonzero schema-valid outputs in smoke.

## Acceptance Gate

After the adapter is published, run base and adapter summaries on the exact v2.2
eval-gold set:

```bash
python3 training/scripts/run_evidence_vlm_sft_eval.py \
  --dataset work/dataset_v22/satellite-disruption-triage-aux-v2-2/eval_gold_sft.jsonl \
  --output-dir training/eval_runs/evidence-vlm-sft-v9-gold-base

python3 training/scripts/run_evidence_vlm_sft_eval.py \
  --dataset work/dataset_v22/satellite-disruption-triage-aux-v2-2/eval_gold_sft.jsonl \
  --output-dir training/eval_runs/evidence-vlm-sft-v9-gold-adapter \
  --adapter-ref ChrisRPL/blackline-atlas-lfm25-vl-sft-train-hf-aux-v9-adapter

python3 training/scripts/check_adapter_acceptance.py \
  --base-summary training/eval_runs/evidence-vlm-sft-v9-gold-base/summary.json \
  --adapter-summary training/eval_runs/evidence-vlm-sft-v9-gold-adapter/summary.json \
  --output-json training/eval_runs/evidence-vlm-sft-v9-gold-adapter/acceptance.json
```

Promotion requires better `action_match`, nonzero `downlink_now` recall, no false
positive regression, and no schema regression versus the base model.
