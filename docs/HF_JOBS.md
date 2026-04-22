# Hugging Face Jobs Plan

Rule:

- same checked-in scripts
- same exported LEAP handoff
- bigger machine only

## Local first

Local owns:

- row selection
- capture freeze
- corpus build
- LEAP export
- prompted baseline
- tiny smoke checks

Current local path:

```bash
python3 training/scripts/build_lfm25_vl_corpus.py \
  --capture-manifest /tmp/non_demo_simsat_capture/simsat_capture_manifest.json \
  --replay-dataset training/replay_pack/train_01.jsonl \
  --output-dir /tmp/train_01_corpus

python3 training/scripts/export_leap_vlm_sft.py \
  --candidate-eval-dataset /tmp/train_01_corpus/blackline_candidate_eval.jsonl \
  --output-dir /tmp/train_01_leap

python3 training/scripts/train_adapter.py \
  --config training/configs/lfm25_vl_sft_smoke.yaml \
  --print-plan
```

Boundary:

- `training/replay_pack/train_01.jsonl` is acquisition truth
- trainer-facing handoff is exported LEAP data, not replay-pack JSONL directly

## HF Jobs

HF Jobs owns:

- long GPU runs
- larger eval sweeps
- durable artifact retention

Same path, remote machine:

- use the same config files
- point output to `/outputs/...`
- keep heavy runs there

Recommended first remote config:

- `training/configs/lfm25_vl_full_eval.yaml`

Guidance:

- run eval before training
- keep one known-good baseline
- prefer short smoke loops first
- do not make training the critical path
- keep benchmark compare as a separate explicit step
