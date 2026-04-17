from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.annotated_case import AnnotatedCaseRecord  # noqa: E402


def test_non_demo_eval_pack_rows_parse() -> None:
    dataset_path = ROOT / "training" / "replay_pack" / "non_demo_eval.jsonl"
    rows = [
        AnnotatedCaseRecord.model_validate(json.loads(line))
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    by_case_id = {row.case_id: row for row in rows}

    assert [row.case_id for row in rows] == [
        "beirut_port_blast",
        "baltimore_bridge_collapse",
        "port_sudan_aid_hub_strikes",
        "ras_abu_jarjur_no_material_change",
        "doha_west_weather_limited",
        "vasyshcheve_atb_address_scar_ambiguity",
        "unhcr_baghdad_warehouse_no_material_change",
    ]
    assert rows[0].split == "holdout_geo"
    assert rows[0].holdout_reason == "retrospective_food_security_anchor"
    assert rows[2].split == "holdout_geo"
    assert rows[2].holdout_reason == "current_conflict_aid_hub"
    assert by_case_id["ras_abu_jarjur_no_material_change"].split == "holdout_stress"
    assert (
        by_case_id["ras_abu_jarjur_no_material_change"].holdout_reason
        == "exact_water_control_no_macro_change"
    )
    assert by_case_id["doha_west_weather_limited"].split == "holdout_stress"
    assert (
        by_case_id["doha_west_weather_limited"].holdout_reason == "weather_mixed_use_water_control"
    )
    assert by_case_id["vasyshcheve_atb_address_scar_ambiguity"].split == "holdout_stress"
    assert (
        by_case_id["vasyshcheve_atb_address_scar_ambiguity"].holdout_reason
        == "food_address_to_scar_ambiguity_control"
    )
    assert by_case_id["unhcr_baghdad_warehouse_no_material_change"].split == "holdout_stress"
    assert (
        by_case_id["unhcr_baghdad_warehouse_no_material_change"].holdout_reason
        == "exact_aid_benchmark_no_macro_change"
    )
