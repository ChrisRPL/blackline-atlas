from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.scripts.materialize_ukraine_damage_aux_slice import (  # noqa: E402
    materialize_ukraine_damage_aux_slice,
)


def test_materialize_ukraine_damage_aux_slice(tmp_path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    location_root = "kamianka_data"
    rows_by_fold = {
        0: [
            ("kamianka_a.png", "no-damage"),
            ("kamianka_b.png", "minor-damage"),
            ("kamianka_c.png", "major-damage"),
            ("kamianka_d.png", "destroyed"),
        ],
        1: [
            ("kamianka_a.png", "no-damage"),
            ("kamianka_e.png", "minor-damage"),
            ("kamianka_f.png", "major-damage"),
            ("kamianka_g.png", "destroyed"),
        ],
    }

    for fold, rows in rows_by_fold.items():
        fold_dir = repo_root / "classification" / location_root / f"fold_{fold}"
        for name in ("pre", "post", "mask"):
            (fold_dir / name).mkdir(parents=True, exist_ok=True)
        csv_lines = ["pre_image,post_image,mask_image,damage,fold"]
        for stem, damage in rows:
            csv_lines.append(f"{stem},{stem},{stem},{damage},{fold}")
        (fold_dir / f"fold_{fold}.csv").write_text("\n".join(csv_lines), encoding="utf-8")

        for stem, _damage in rows:
            for folder in ("pre", "post"):
                image = Image.new("RGB", (86, 86), "white")
                image.save(fold_dir / folder / stem)
            mask = Image.new("L", (86, 86), 0)
            for x in range(12, 74):
                for y in range(13, 75):
                    mask.putpixel((x, y), 255)
            mask.save(fold_dir / "mask" / stem)

    def fake_hf_hub_download(*, repo_id: str, repo_type: str, filename: str) -> str:
        assert repo_id == "fake/repo"
        assert repo_type == "dataset"
        return str(repo_root / filename)

    monkeypatch.setattr(
        "training.scripts.materialize_ukraine_damage_aux_slice.hf_hub_download",
        fake_hf_hub_download,
    )

    dataset_path, summary_path = materialize_ukraine_damage_aux_slice(
        repo_id="fake/repo",
        output_dir=tmp_path / "out",
        location_roots=(location_root,),
        folds=(0, 1),
        max_per_damage=2,
    )

    rows = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 7
    assert {row["expected_action"] for row in rows} == {"discard", "defer", "downlink_now"}
    assert all(row["split"] == "train" for row in rows)
    assert rows[0]["bbox"] if "bbox" in rows[0] else True

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["row_count"] == 7
    assert summary["locations"][0]["selected_damages"] == {
        "destroyed": 2,
        "major-damage": 2,
        "minor-damage": 2,
        "no-damage": 1,
    }
    assert summary["locations"][0]["selected_folds"] == [0, 1]
    assert summary["folds"] == [0, 1]
    assert rows[0]["benchmark_source"] == "UkraineDamageAssessment"
    assert len({row["benchmark_case_id"] for row in rows}) == 7
