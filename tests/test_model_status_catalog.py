from __future__ import annotations

from app.services.model_status_catalog import build_model_status


def test_model_status_catalog_keeps_adapters_research_only() -> None:
    status = build_model_status()

    assert status.candidate_adapter.endswith("aux-v10-adapter")
    assert status.training_dataset.endswith("satellite-disruption-triage-aux-v2-2")
    assert status.adapter_signal_role == "optional_non_authoritative"
    assert status.runtime_authority == "deterministic_replay"
    assert status.can_affect_alerts is False
    assert status.adapter_eval.schema_valid == 0
    assert status.adapter_eval.action_match == 0
    assert status.latest_training_job == "69f0ac8bd70108f37ace0f4d"
    assert status.evaluated_adapters[-1].status == "published_rejected"
