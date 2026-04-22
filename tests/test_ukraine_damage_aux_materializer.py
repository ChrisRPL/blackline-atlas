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
    fold_dir = repo_root / "classification" / location_root / "fold_0"
    for name in ("pre", "post", "mask"):
        (fold_dir / name).mkdir(parents=True, exist_ok=True)

    csv_path = fold_dir / "fold_0.csv"
    csv_path.write_text(
        "\n".join(
            [
                "pre_image,post_image,mask_image,damage,fold",
                "kamianka_a.png,kamianka_a.png,kamianka_a.png,no-damage,0",
                "kamianka_b.png,kamianka_b.png,kamianka_b.png,minor-damage,0",
                "kamianka_c.png,kamianka_c.png,kamianka_c.png,major-damage,0",
                "kamianka_d.png,kamianka_d.png,kamianka_d.png,destroyed,0",
            ]
        ),
        encoding="utf-8",
    )

    for stem in ("kamianka_a", "kamianka_b", "kamianka_c", "kamianka_d"):
        for folder in ("pre", "post"):
            image = Image.new("RGB", (86, 86), "white")
            image.save(fold_dir / folder / f"{stem}.png")
        mask = Image.new("L", (86, 86), 0)
        for x in range(12, 74):
            for y in range(13, 75):
                mask.putpixel((x, y), 255)
        mask.save(fold_dir / "mask" / f"{stem}.png")

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
        fold=0,
        max_per_damage=1,
    )

    rows = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 4
    assert {row["expected_action"] for row in rows} == {"discard", "defer", "downlink_now"}
    assert all(row["split"] == "train" for row in rows)
    assert rows[0]["bbox"] if "bbox" in rows[0] else True

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["row_count"] == 4
    assert summary["locations"][0]["selected_damages"] == {
        "destroyed": 1,
        "major-damage": 1,
        "minor-damage": 1,
        "no-damage": 1,
    }
