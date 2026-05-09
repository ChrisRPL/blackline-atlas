# Bottleneck Plan 2026-04-25

## Current Bottlenecks

1. Model signal
   - Published `aux_v5` adapter did not improve frozen gold action behavior.
   - Root cause found: train export and local eval used different image ordering.
   - Fix landed in the shared VLM conversation builder.

2. Training scale
   - Internal Train 01 is still small at `33` rows.
   - Public auxiliary pool now increases trainer-side scale to `2,450` rows.
   - This is enough for the current adapter run, but not enough for a production claim.

3. Label shape
   - Internal rows still have no `defer` examples.
   - Auxiliary `satellite-disruption-triage-aux-v1-3` import adds `1,104 defer` rows before merge.
   - Next internal data work should add real ambiguity / weak-signal rows.

4. Demo reliability
   - Demo must not depend on the adapter becoming good in the next run.
   - Required demo path is deterministic replay plus cached fallback.
   - Adapter output is a bonus only after it beats base on frozen gold.

## Current Counts

- internal train: `33`
- auxiliary train: `2,417`
- LEAP-exportable train: `2,450`
- frozen gold eval: `22`
- current trainer action mix:
  - `discard`: `569`
  - `defer`: `1,165`
  - `downlink_now`: `716`

## Next Decisions

1. Score `lfm25_vl_sft_train_hf_aux_v7` on the frozen `22`-case gold corpus.
2. Accept the adapter only if it beats the base model and does not increase false positives.
3. If rejected, keep the adapter as a research artifact and leave the demo on replay/cached fallback.
4. In parallel, harden the replay demo path.
5. Add internal `defer` rows before more high-confidence positives.
