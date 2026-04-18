from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_eval_module():
    script_path = (
        Path(__file__).resolve().parent.parent
        / "training"
        / "scripts"
        / "run_agent_command_eval.py"
    )
    spec = importlib.util.spec_from_file_location("run_agent_command_eval", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


eval_module = _load_eval_module()
AgentCommandEvalCase = eval_module.AgentCommandEvalCase
load_cases = eval_module.load_cases
score_case = eval_module.score_case


def test_load_agent_command_eval_cases(tmp_path: Path) -> None:
    dataset = tmp_path / "agent_eval.jsonl"
    dataset.write_text(
        (
            '{"case_id":"case_01","query":"show latest alerts","expected_status":"ok",'
            '"expected_tool":"latest_alerts","expected_planner_mode":"live",'
            '"expected_trust_mode":"replay_safe","expected_focus_asset_id":"demo_bridge_01",'
            '"expected_summary_contains":"latest alerts"}\n'
        ),
        encoding="utf-8",
    )

    cases = load_cases(dataset)

    assert len(cases) == 1
    assert cases[0].case_id == "case_01"
    assert cases[0].expected_tool == "latest_alerts"


def test_score_case_reports_mismatch_labels() -> None:
    case = AgentCommandEvalCase(
        case_id="biggest_black_sea",
        query="show biggest disruptions near Black Sea",
        expected_status="ok",
        expected_tool="biggest_disruptions",
        expected_planner_mode="live",
        expected_trust_mode="replay_safe",
        expected_focus_asset_id="demo_port_01",
        expected_focus_alert_id="blk_00017",
        expected_alert_count=1,
        expected_top_alert_asset_id="demo_port_01",
        expected_compare_asset_id="demo_port_01",
        expected_summary_contains="biggest disruptions",
    )

    mismatches = score_case(
        case,
        {
            "status": "ok",
            "tool": "latest_alerts",
            "planner": {"mode": "fallback"},
            "trust": {"mode": "degraded"},
            "focus_asset_id": "demo_bridge_01",
            "focus_alert_id": "blk_00018",
            "alerts": [
                {"asset_id": "demo_bridge_01"},
                {"asset_id": "demo_port_01"},
            ],
            "compare": {"asset_id": "demo_bridge_01"},
            "summary": "wrong summary",
        },
    )

    assert mismatches == [
        "tool",
        "planner_mode",
        "trust_mode",
        "focus_asset_id",
        "focus_alert_id",
        "alert_count",
        "top_alert_asset_id",
        "compare_asset_id",
        "summary",
    ]
