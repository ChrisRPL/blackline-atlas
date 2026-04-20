# SpaceNet 8 Public Seed

Small checked-in SpaceNet 8 seed slice.

Why it exists:

- real public flood-disruption cases in-repo
- enough to benchmark flood transfer without a giant ingest
- keeps external eval useful, but still secondary to Blackline gold data

Contents:

- `spacenet8_seed.jsonl`
  - 4 curated cases
  - 2 flooded positives
  - 2 clean controls
- `source_labels/`
  - original public annotation GeoJSONs
- `images/`
  - ready-to-run materialized eval images

Source:

- dataset: `SpaceNet 8 Flood Detection Challenge`
- bucket: `s3://spacenet-dataset/spacenet/SN8_floods/`
- AOI: `Germany_Training_Public`

Generation notes:

- bbox comes from the union of `Wkt_Pix` geometry in the public reference CSV
- coordinates come from the centroid of matching features in the public tile GeoJSON
- positives and controls are benchmark-only transfer cases
- these rows do not count toward the internal Blackline gold-set target

Build:

```bash
python3 training/scripts/normalize_spacenet8_slice.py \
  --seed-dataset training/external_benchmarks/spacenet8_public_seed/spacenet8_seed.jsonl \
  --output-dir /tmp/spacenet8_public_seed_build
```
