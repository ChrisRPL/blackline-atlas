# External Benchmark Slices

Purpose:

- normalize public external datasets into Blackline’s `blackline_candidate_eval.jsonl`
- keep internal and external eval on the same runner
- avoid inventing a second benchmark format

Current normalizers:

- `python3 training/scripts/normalize_xbd_slice.py`
- `python3 training/scripts/normalize_spacenet8_slice.py`

Ready slice:

- `training/external_benchmarks/xbd_public_seed`
  - checked-in xBD public seed
  - 4 cases
  - 3 positive damage cases
  - 1 real no-damage control
  - notes: `training/external_benchmarks/xbd_public_seed/README.md`
- `training/external_benchmarks/spacenet8_public_seed`
  - checked-in SpaceNet 8 public seed
  - 4 cases
  - 2 flooded positives
  - 2 clean controls
  - notes: `training/external_benchmarks/spacenet8_public_seed/README.md`

Input style:

- each normalizer expects a small curated seed JSONL
- seed rows point to local image paths
- the normalizer copies those images into the output slice directory

Output style:

- `blackline_candidate_eval.jsonl`
- `images/<case_id>/current.*`
- `images/<case_id>/baseline.*`

Why curated seeds first:

- official dataset raw formats are large and awkward
- we want a small, auditable benchmark slice, not a giant one-shot import
- this keeps bbox/action/impact mapping explicit per external source

Recommended first slices:

- `xBD`
  - destroyed / major / minor / no-damage building-cluster cases
- `SpaceNet 8`
  - flooded road-segment cases
  - flooded building-cluster cases
