# Blackline Internal Public Seed v0

Purpose:
- one tiny internal benchmark anchor
- runnable now
- honest stopgap until the full internal non-demo slice is materialized from frozen SimSat captures

Current scope:
- `1` case
- `port_sudan_aid_hub_strikes`
- derived from the checked-in comparison artifact at `ui/assets/blackline-portsudan-comparison.png`

Why this exists:
- the internal annotated pack still stores `pending://` image refs
- full internal benchmark materialization needs a capture manifest or live SimSat historical endpoint
- this seed lets us run the benchmark harness on at least one real Blackline case today

Do not treat this as:
- the full internal benchmark
- a training dataset
- a replacement for the `non_demo_eval.jsonl` gold-set program
