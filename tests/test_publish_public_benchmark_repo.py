from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.scripts import publish_public_benchmark_repo  # noqa: E402


def test_resolve_public_seed_slices_selects_only_ready_public_defaults() -> None:
    manifest = publish_public_benchmark_repo.load_manifest(
        ROOT / "training" / "replay_pack" / "model_benchmark_manifest.json"
    )

    slices = publish_public_benchmark_repo.resolve_public_seed_slices(
        manifest=manifest,
        slice_ids=publish_public_benchmark_repo.DEFAULT_PUBLIC_SLICE_IDS,
    )

    assert [slice_config.slice_id for slice_config in slices] == [
        "internal_public_seed_v0",
        "xbd_public_seed_v0",
        "spacenet8_public_seed_v0",
    ]


def test_materialize_public_benchmark_repo_copies_only_canonical_public_files(
    tmp_path: Path,
) -> None:
    manifest = publish_public_benchmark_repo.load_manifest(
        ROOT / "training" / "replay_pack" / "model_benchmark_manifest.json"
    )
    slices = publish_public_benchmark_repo.resolve_public_seed_slices(
        manifest=manifest,
        slice_ids=publish_public_benchmark_repo.DEFAULT_PUBLIC_SLICE_IDS,
    )

    output_dir = publish_public_benchmark_repo.materialize_public_benchmark_repo(
        output_dir=tmp_path / "public_benchmark_repo",
        slices=slices,
    )

    assert (output_dir / "README.md").exists()
    manifest_payload = json.loads(
        (output_dir / "benchmark_manifest.json").read_text(encoding="utf-8")
    )
    assert [item["slice_id"] for item in manifest_payload["slices"]] == [
        "internal_public_seed_v0",
        "xbd_public_seed_v0",
        "spacenet8_public_seed_v0",
    ]

    internal_dir = output_dir / "internal_public_seed_v0"
    assert (internal_dir / "blackline_candidate_eval.jsonl").exists()
    assert (internal_dir / "images").exists()
    assert not (internal_dir / "README.md").exists()

    xbd_dir = output_dir / "xbd_public_seed_v0"
    assert (xbd_dir / "blackline_candidate_eval.jsonl").exists()
    assert (xbd_dir / "source_labels").exists()
    assert (xbd_dir / "images").exists()
    assert not (xbd_dir / "xbd_seed.jsonl").exists()
    assert not (xbd_dir / "README.md").exists()

    spacenet_dir = output_dir / "spacenet8_public_seed_v0"
    assert (spacenet_dir / "blackline_candidate_eval.jsonl").exists()
    assert (spacenet_dir / "source_labels").exists()
    assert (spacenet_dir / "images").exists()
    assert not (spacenet_dir / "spacenet8_seed.jsonl").exists()
    assert not (spacenet_dir / "README.md").exists()

    readme = (output_dir / "README.md").read_text(encoding="utf-8")
    assert "Blackline Atlas Civilian Disruption Benchmark Seeds" in readme
    assert "What this repo is not:" in readme
    assert "`internal_public_seed_v0`: Blackline internal public seed" in readme
