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
  --config training/configs/lfm25_vl_sft_train_hf.yaml
```

Submit for real:

```bash
python3 training/scripts/submit_train_backend_hf_job.py \
  --config training/configs/lfm25_vl_sft_train_hf.yaml \
  --submit
```

Recommended first remote config:

- `training/configs/lfm25_vl_sft_train_hf.yaml`

What the submitter does:

- materializes the same checked-in prep seam locally
- packages a self-contained train bundle
- uploads the bundle to a private HF dataset repo by default
- submits the remote runner with `HF_TOKEN` secret injection
- installs `leap-finetune` inside the job and trains there

Guidance:

- run eval before training
- keep one known-good baseline
- prefer short smoke loops first
- do not make training the critical path
- keep benchmark compare as a separate explicit step
- treat the trainer's `test_size` split as diagnostics only
- keep authoritative Blackline eval on the frozen held-out slices
