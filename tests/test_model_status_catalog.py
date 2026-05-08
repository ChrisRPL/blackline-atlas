from __future__ import annotations

from app.services.model_status_catalog import build_model_status


def test_model_status_catalog_promotes_full_v1b_as_guarded_analyst_adapter() -> None:
    status = build_model_status()

    assert status.candidate_adapter.endswith("hf-corpus-full-v1b-adapter")
    assert status.training_dataset.endswith("blackline-atlas-training-corpus-v1")
    assert status.adapter_signal_role == "optional_non_authoritative"
    assert status.runtime_authority == "source_led_sentinel_liquid_guarded"
    assert status.can_affect_alerts is False
    assert status.adapter_eval.schema_valid == 19
    assert status.adapter_eval.action_match == 9
    assert status.latest_training_job == "69f66f889d85bec4d76f0be0"
    assert status.evaluated_adapters[-1].status == "published_guarded_runtime"
    assert "not autonomous alert decisions" in status.summary
