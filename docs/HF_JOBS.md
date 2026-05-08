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
python3 training/scripts/run_train_backend.py \
  --config training/configs/lfm25_vl_sft_smoke.yaml
```

Boundary:

- `training/replay_pack/train_01.jsonl` is acquisition truth
- trainer-facing handoff is exported LEAP data, not replay-pack JSONL directly
- the generated bundle is the remote handoff
- local macOS is not the trainer runtime; `leap-finetune` requires CUDA for actual local training

## HF Jobs

HF Jobs owns:

- long GPU runs
- larger eval sweeps
- durable artifact retention
- actual `leap-finetune` execution for Blackline

Current remote path:

```bash
python3 training/scripts/submit_train_backend_hf_job.py \
  --config training/configs/lfm25_vl_sft_train_hf_aux_v8.yaml
```

Submit for real:

```bash
python3 training/scripts/submit_train_backend_hf_job.py \
  --config training/configs/lfm25_vl_sft_train_hf_aux_v8.yaml \
  --submit
```

Recent remote configs:

- `training/configs/lfm25_vl_sft_train_hf_aux_v6.yaml`: corrected serializer path with v1.1 auxiliary data
- `training/configs/lfm25_vl_sft_train_hf_aux_v7.yaml`: completed conflict-focused v1.3 run
- `training/configs/lfm25_vl_sft_train_hf_aux_v8.yaml`: current evidence-first v2.1 run
- latest completed adapter: `ChrisRPL/blackline-atlas-lfm25-vl-sft-train-hf-aux-v8-adapter`
- latest completed job: `69efd6e8d2c8bd8662bd13bf`
- latest diagnostic eval loss: `2.7993 -> 1.2974`

What the submitter does:

- materializes the same checked-in prep seam locally
- packages a self-contained train bundle
- uploads the bundle to a private HF dataset repo by default
- writes a root dataset card plus a per-run manifest there
- stores archives as `bundles/<run_name>.tar.gz`, not nested transfer folders
- submits the remote runner with `HF_TOKEN` secret injection
- installs `leap-finetune` inside the job and trains there

If submit fails after upload:

- the uploaded bundle is still the durable handoff
- local `bundle_manifest.json` records:
  - uploaded repo id
  - uploaded repo path
  - last submit status
  - last submit error
- if the failure is `hf_jobs_insufficient_credits`, add HF Jobs credits and rerun:

```bash
python3 training/scripts/submit_train_backend_hf_job.py \
  --config training/configs/lfm25_vl_sft_train_hf.yaml \
  --skip-prepare \
  --submit
```

Guidance:

- run eval before training
- keep one known-good baseline
- reject adapters with `training/scripts/check_adapter_acceptance.py` unless they beat base on frozen gold
- prefer short smoke loops first
- do not make training the critical path
- keep benchmark compare as a separate explicit step
- treat the trainer's `test_size` split as diagnostics only
- keep authoritative Blackline eval on the frozen held-out slices

## Full-v1b Guarded Runtime Adapter

Current completed run:

- dataset: `ChrisRPL/blackline-atlas-training-corpus-v1`
- adapter: `ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter`
- job: `69f66f889d85bec4d76f0be0`
- train records: `30,858`
- eval records: `3,421`
- eval loss: `3.0021 -> 0.3273`

Corpus-native SimSat gold eval:

- JSON valid: `22 / 22`
- analyst schema valid: `19 / 22`
- action match: `9 / 22`
- downlink recall: `3 / 12`
- false-positive `downlink_now`: `3`

Runtime decision:

- promote as guarded paired-image analyst narration
- do not promote as autonomous alert authority
- keep source-led context, real SimSat/Sentinel imagery, Sentinel quality gates,
  parser repair, and deterministic final action guardrails active
