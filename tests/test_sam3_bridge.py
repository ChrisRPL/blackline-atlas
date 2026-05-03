from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.sam3_bridge import LocalSam3Runner, create_app
from app.schemas.asset import Asset
from app.schemas.frame import FrameEnvelope, FrameRecord
from app.schemas.sam3_evidence import Sam3EvidenceMask, Sam3SourceContext
from app.services.sam3_evidence import build_sam3_report_from_masks


def _asset() -> Asset:
    return Asset(
        asset_id="live_kharkiv_shelling",
        asset_name="Reported strike damage in Kharkiv",
        asset_type="civilian_building_cluster",
        region="Kharkiv, Ukraine",
        latitude=49.99,
        longitude=36.23,
    )


def _frame(frame_id: str, image_ref: str) -> FrameEnvelope:
    return FrameEnvelope(
        frame=FrameRecord(
            frame_id=frame_id,
            asset_id="live_kharkiv_shelling",
            captured_at="2026-04-30T12:00:00Z",
            image_ref=image_ref,
            source="simsat_sentinel",
        )
    )


def test_local_sam3_bridge_http_contract_returns_schema(monkeypatch, tmp_path: Path) -> None:
    current_path = tmp_path / "current.png"
    baseline_path = tmp_path / "baseline.png"
    current_path.write_bytes(b"placeholder")
    baseline_path.write_bytes(b"placeholder")
    asset = _asset()
    current = _frame("current-1", str(current_path))
    baseline = _frame("baseline-1", str(baseline_path))

    class FakeRunner:
        backend = "transformers"
        model_id = "facebook/sam3"
        loaded = True
        device = "cpu"
        _report_backend = "sam3_transformers"

        def analyze(self, *, asset, current, baseline, prompts, source_context):
            return build_sam3_report_from_masks(
                asset=asset,
                current=current,
                baseline=baseline,
                prompts=prompts,
                masks=[
                    Sam3EvidenceMask(
                        label="rubble pile",
                        prompt="rubble pile",
                        score=0.86,
                        bbox_norm=(0.2, 0.2, 0.3, 0.32),
                        area_ratio=0.012,
                    )
                ],
                model_version="facebook/sam3",
                backend="sam3_transformers",
                source_context=source_context,
            )

    monkeypatch.setattr("app.sam3_bridge._get_runner", lambda: FakeRunner())
    client = TestClient(create_app())

    response = client.post(
        "/sam3",
        json={
            "asset": asset.model_dump(mode="json"),
            "current_frame": current.model_dump(mode="json"),
            "baseline_frame": baseline.model_dump(mode="json"),
            "source_context": Sam3SourceContext(
                title="Reported shelling damaged apartment buildings.",
                region="Kharkiv, Ukraine",
                satellite_relevance="high",
                target_prompts=["rubble pile", "apartment block"],
            ).model_dump(mode="json"),
            "prompts": ["rubble pile"],
            "model_version": "facebook/sam3",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["backend"] == "sam3_transformers"
    assert payload["decision"] == "segmentation_ready"
    assert payload["source_context"]["satellite_relevance"] == "high"
    assert payload["masks"][0]["prompt"] == "rubble pile"


def test_local_sam3_runner_does_not_load_model_when_images_are_missing() -> None:
    asset = _asset()
    current = _frame("current-missing", "missing/current.png")
    baseline = _frame("baseline-missing", "missing/baseline.png")
    runner = LocalSam3Runner(
        backend="transformers",
        model_id="facebook/sam3",
        score_threshold=0.5,
        mask_threshold=0.5,
        allow_cpu=True,
    )

    report = runner.analyze(
        asset=asset,
        current=current,
        baseline=baseline,
        prompts=["rubble pile"],
        source_context=None,
    )

    assert report.decision == "unavailable"
    assert report.triage_action == "discard"
    assert runner.loaded is False
    assert "could not resolve both local image paths" in report.summary
