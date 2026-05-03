from __future__ import annotations

from app.schemas.model_status import EvaluatedAdapter, ModelEvalScore, ModelStatus


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
    return ModelStatus(
        base_model="LiquidAI/LFM2.5-VL-450M",
        candidate_adapter="ChrisRPL/blackline-atlas-lfm25-vl-sft-train-hf-aux-v10-adapter",
        training_dataset="ChrisRPL/satellite-disruption-triage-aux-v2-2",
        adapter_signal_role="optional_non_authoritative",
        runtime_authority="deterministic_replay",
        can_affect_alerts=False,
        frozen_gold_cases=51,
        reported_eval_cases=3,
        reported_eval_scope="v2_2_eval_gold_three_case_schema_smoke",
        decision="replay_safe_adapter_rejected",
        recommended_runtime="deterministic_replay",
        summary=(
            "v10 trained and published with strong trainer-loss improvement, but the "
            "generation smoke still produced zero valid evidence-schema outputs and zero "
            "downlink_now matches. Runtime alerts remain deterministic replay only."
        ),
        base_eval=base_smoke,
        adapter_eval=v10_smoke,
        acceptance_failures=[
            "v10 evidence schema valid count is 0/3 on eval-gold smoke",
            "v10 action match is 0/3 on positive eval-gold smoke",
            "v10 predicted zero downlink_now rows on positive smoke cases",
            "full 51-case frozen eval remains blocked until schema smoke passes",
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
        ],
        latest_training_job="69f0ac8bd70108f37ace0f4d",
        training_eval_loss_start=2.9309,
        training_eval_loss_final=1.2123,
    )
