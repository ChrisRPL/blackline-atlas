from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.schemas.annotated_case import AnnotatedCaseRecord  # noqa: E402
from app.services.scenario_fixtures import build_stub_scenarios  # noqa: E402
from app.services.watchlist_loader import load_watchlist_assets  # noqa: E402

PACK_VERSION = "hero-replay-v1"
DEFAULT_OUTPUT_DIR = ROOT / "training" / "replay_pack"
DEFAULT_MANIFEST_NAME = "hero_replay.json"
DEFAULT_DATASET_NAME = "hero_eval.jsonl"
SCENARIO_ORDER = ("hero_port_disruption", "bridge_access_obstruction")


def build_replay_pack() -> dict[str, Any]:
    settings = get_settings()
    assets = {asset.asset_id: asset for asset in load_watchlist_assets(settings.watchlist_path)}
    scenarios = build_stub_scenarios(
        settings=settings,
        hero_asset=assets["demo_port_01"],
        bridge_asset=assets["demo_bridge_01"],
    )

    cases = [
        _build_case_record(
            asset=assets[scenarios[scenario_id].asset_id],
            scenario=scenarios[scenario_id],
        )
        for scenario_id in SCENARIO_ORDER
    ]

    return {
        "pack_version": PACK_VERSION,
        "case_count": len(cases),
        "cases": cases,
    }


def write_replay_pack(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    manifest_name: str = DEFAULT_MANIFEST_NAME,
    dataset_name: str = DEFAULT_DATASET_NAME,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    pack = build_replay_pack()
    manifest_path = output_dir / manifest_name
    dataset_path = output_dir / dataset_name

    manifest_path.write_text(
        json.dumps(pack, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    dataset_path.write_text(
        "".join(json.dumps(case, sort_keys=True) + "\n" for case in pack["cases"]),
        encoding="utf-8",
    )
    return manifest_path, dataset_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze the tiny Blackline Atlas replay pack into JSON and JSONL.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for generated pack files. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--manifest-name",
        default=DEFAULT_MANIFEST_NAME,
        help=f"Manifest filename. Default: {DEFAULT_MANIFEST_NAME}",
    )
    parser.add_argument(
        "--dataset-name",
        default=DEFAULT_DATASET_NAME,
        help=f"JSONL filename for offline eval. Default: {DEFAULT_DATASET_NAME}",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest_path, dataset_path = write_replay_pack(
        output_dir=args.output_dir,
        manifest_name=args.manifest_name,
        dataset_name=args.dataset_name,
    )
    print(f"wrote {manifest_path}")
    print(f"wrote {dataset_path}")
    return 0


def _build_case_record(*, asset: Any, scenario: Any) -> dict[str, Any]:
    alert = scenario.alerts[0]
    expected_candidate = json.loads(scenario.model_output_text)
    return AnnotatedCaseRecord(
        case_id=scenario.scenario_id,
        asset=asset,
        hero=asset.hero,
        current_frame=scenario.current_frame,
        baseline_frame=scenario.baseline_frame,
        model_output_text=scenario.model_output_text,
        expected_candidate=expected_candidate,
        expected_alert=alert,
        expected_action=alert.action,
        expected_metrics=scenario.metrics,
        split="holdout_geo",
        holdout_reason="hero_demo",
        annotation_source="stub_replay_pack",
    ).model_dump(mode="json")


if __name__ == "__main__":
    raise SystemExit(main())
