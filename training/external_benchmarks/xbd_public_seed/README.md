# xBD Public Seed

Small checked-in xBD-derived seed slice.

Why it exists:

- real public xBD cases in-repo
- benchmarkable without pulling giant archives first
- bridge from `planned` external eval to runnable cohort work

Contents:

- `xbd_seed.jsonl`
  - 4 curated cases
  - 3 positive damage cases
  - 1 real no-damage control
- `source_labels/`
  - original post-disaster label JSONs used to derive bbox + coords
- `images/`
  - ready-to-run materialized eval images

Source:

- dataset: `WayBob/Disaster_Recognition_RemoteSense_EN_CN_JA`
- archive: `xview2_test.tar.gz`
- metadata: `xview2_test.json`
- license: `CC BY-NC-SA 4.0`

Generation notes:

- bbox comes from the union of `features.xy` polygon vertices
- coordinates come from the centroid of `features.lng_lat` polygon vertices
- damage class follows the strongest subtype present in the post label JSON

Build:

```bash
python3 training/scripts/normalize_xbd_slice.py \
  --seed-dataset training/external_benchmarks/xbd_public_seed/xbd_seed.jsonl \
  --output-dir /tmp/xbd_public_seed_build
```

This is a seed slice, not the full xBD benchmark.
