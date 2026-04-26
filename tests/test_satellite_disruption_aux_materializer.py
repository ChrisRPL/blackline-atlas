from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.scripts.materialize_satellite_disruption_aux_slice import (  # noqa: E402
    materialize_satellite_disruption_aux_slice,
)


def test_materialize_satellite_disruption_aux_slice_maps_train_rows(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    baseline_dir = source_root / "images" / "baseline"
    current_dir = source_root / "images" / "current"
    baseline_dir.mkdir(parents=True)
    current_dir.mkdir(parents=True)
    Image.new("RGB", (4, 4), "white").save(baseline_dir / "case_baseline.png")
    Image.new("RGB", (4, 4), "black").save(current_dir / "case_current.png")
    row = {
        "example_id": "event_0001",
        "baseline_image": "images/baseline/case_baseline.png",
        "current_image": "images/current/case_current.png",
        "target_output": {
            "action": "defer",
            "category": "storm_structure_damage",
            "rationale": "Moderate visible disruption requires review.",
            "bbox_norm": [0.1, 0.2, 0.7, 0.8],
        },
        "source_dataset": "example-source",
        "source_event": "example-event",
        "source_image_name": "example/image",
        "modality": "optical-to-optical",
        "provenance": "example provenance",
        "damage_ratio": 0.2,
        "destruction_ratio": 0.0,
    }
    (source_root / "train_flat.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")

    dataset_path, summary_path = materialize_satellite_disruption_aux_slice(
        source_root=source_root,
        output_dir=tmp_path / "out",
    )

    rows = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines()]
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert len(rows) == 1
    assert rows[0]["case_id"] == "event_0001"
    assert rows[0]["split"] == "train"
    assert rows[0]["expected_action"] == "defer"
    assert rows[0]["expected_candidate"]["event_type"] == "probable_surface_change"
    assert rows[0]["expected_candidate"]["severity"] == "medium"
    assert (tmp_path / "out" / rows[0]["current_image_path"]).exists()
    assert (tmp_path / "out" / rows[0]["baseline_image_path"]).exists()
    assert summary["row_count"] == 1
    assert summary["action_counts"] == {"defer": 1}
