# Hugging Face Jobs Plan

## Local dev owns

- app code
- schemas
- UI
- replay
- caching
- eval harness code
- prompt engineering

## HF Jobs owns

- long-running data prep
- eval jobs
- optional fine-tuning
- artifact export

## Guidance

- run eval before training
- keep one known-good baseline
- prefer short loops
- do not make training the critical path

