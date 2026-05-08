from __future__ import annotations

from app.schemas.model_status import EvaluatedAdapter, ModelEvalScore, ModelStatus

FULL_V1B_ADAPTER = "ChrisRPL/blackline-atlas-lfm25-vl-sft-hf-corpus-full-v1b-adapter"
FULL_V1B_DATASET = "ChrisRPL/blackline-atlas-training-corpus-v1"


def build_model_status() -> ModelStatus:
    base_smoke = ModelEvalScore(
        action_match=0,
        schema_valid=0,
        downlink_recall=0,
        downlink_total=3,
        false_positives=0,
    )
    v10_smoke = ModelEvalScore(
        action_match=0,
        schema_valid=0,
        downlink_recall=0,
        downlink_total=3,
        false_positives=0,
    )
    full_v1b_eval = ModelEvalScore(
        action_match=9,
        schema_valid=19,
        downlink_recall=3,
        downlink_total=12,
        false_positives=3,
    )
    return ModelStatus(
        base_model="LiquidAI/LFM2.5-VL-450M",
        candidate_adapter=FULL_V1B_ADAPTER,
        training_dataset=FULL_V1B_DATASET,
        adapter_signal_role="optional_non_authoritative",
        runtime_authority="source_led_sentinel_liquid_guarded",
        can_affect_alerts=False,
        frozen_gold_cases=22,
        reported_eval_cases=22,
        reported_eval_scope="hf_corpus_simsat_gold_eval_full_22",
        decision="evidence_adapter_guarded_runtime",
        recommended_runtime="source_led_sentinel_liquid_guarded",
        summary=(
            "full-v1b trained on the 30,858-row HF corpus and completed a corpus-native "
            "SimSat gold eval with 22/22 valid JSON and 19/22 schema-valid reports. "
            "Action match remains 9/22, so the adapter is wired for guarded Liquid analyst "
            "summaries behind source-led Sentinel evidence, not autonomous alert decisions."
        ),
        base_eval=base_smoke,
        adapter_eval=full_v1b_eval,
        acceptance_failures=[
            "full-v1b action match is 9/22 on corpus-native SimSat gold eval",
            "full-v1b downlink recall is 3/12 on positive SimSat gold cases",
            "full-v1b produced 3 false-positive downlink_now predictions on negative cases",
            (
                "runtime must keep parser repair, source-led context, and Sentinel "
                "quality gates active"
            ),
        ],
        evaluated_adapters=[
            EvaluatedAdapter(
                adapter="ChrisRPL/blackline-atlas-lfm25-vl-sft-train-hf-aux-v8-adapter",
                training_dataset="ChrisRPL/satellite-disruption-triage-aux-v2-1",
                training_job="69efd6e8d2c8bd8662bd13bf",
                status="superseded_rejected",
                eval_scope="runtime_evidence_public_seed_and_xbd_seed",
                eval_cases=5,
                train_rows=None,
                eval_rows=None,
                eval_loss_start=2.7993,
                eval_loss_final=1.2974,
                score=ModelEvalScore(
                    action_match=1,
                    schema_valid=2,
                    downlink_recall=0,
                    downlink_total=3,
                    false_positives=0,
                ),
                failure_summary=(
                    "Published and partially schema-valid, but missed all positive "
                    "downlink_now disruption cases."
                ),
            ),
            EvaluatedAdapter(
                adapter="ChrisRPL/blackline-atlas-lfm25-vl-sft-train-hf-aux-v9-adapter",
                training_dataset="ChrisRPL/satellite-disruption-triage-aux-v2-2",
                training_job="69f0a8afd70108f37ace0f44",
                status="superseded_rejected",
                eval_scope="v2_2_eval_gold_three_case_schema_smoke",
                eval_cases=3,
                train_rows=93,
                eval_rows=51,
                eval_loss_start=2.9309,
                eval_loss_final=2.9173,
                score=ModelEvalScore(
                    action_match=0,
                    schema_valid=0,
                    downlink_recall=0,
                    downlink_total=3,
                    false_positives=0,
                ),
                failure_summary=(
                    "Training was stable but too weak to learn evidence-first JSON behavior."
                ),
            ),
            EvaluatedAdapter(
                adapter="ChrisRPL/blackline-atlas-lfm25-vl-sft-train-hf-aux-v10-adapter",
                training_dataset="ChrisRPL/satellite-disruption-triage-aux-v2-2",
                training_job="69f0ac8bd70108f37ace0f4d",
                status="published_rejected",
                eval_scope="v2_2_eval_gold_three_case_schema_smoke",
                eval_cases=3,
                train_rows=93,
                eval_rows=51,
                eval_loss_start=2.9309,
                eval_loss_final=1.2123,
                score=v10_smoke,
                failure_summary=(
                    "Trainer loss improved, but generation still failed the required "
                    "evidence schema and action contract."
                ),
            ),
            EvaluatedAdapter(
                adapter=FULL_V1B_ADAPTER,
                training_dataset=FULL_V1B_DATASET,
                training_job="69f66f889d85bec4d76f0be0",
                status="published_guarded_runtime",
                eval_scope="hf_corpus_simsat_gold_eval_full_22",
                eval_cases=22,
                train_rows=30858,
                eval_rows=3421,
                eval_loss_start=3.0021,
                eval_loss_final=0.3273,
                score=full_v1b_eval,
                failure_summary=(
                    "Good enough for guarded analyst narration: valid JSON is stable, but "
                    "action quality is not strong enough to control alert emission."
                ),
            ),
        ],
        latest_training_job="69f66f889d85bec4d76f0be0",
        training_eval_loss_start=3.0021,
        training_eval_loss_final=0.3273,
    )
