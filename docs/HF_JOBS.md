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
  --config training/configs/lfm25_vl_sft_train_hf_aux_v7.yaml
```

Submit for real:

```bash
python3 training/scripts/submit_train_backend_hf_job.py \
  --config training/configs/lfm25_vl_sft_train_hf_aux_v7.yaml \
  --submit
```

Recent remote configs:

- `training/configs/lfm25_vl_sft_train_hf_aux_v6.yaml`: corrected serializer path with v1.1 auxiliary data
- `training/configs/lfm25_vl_sft_train_hf_aux_v7.yaml`: current conflict-focused v1.3 run
- latest completed adapter: `ChrisRPL/blackline-atlas-lfm25-vl-sft-train-hf-aux-v7-adapter`

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
