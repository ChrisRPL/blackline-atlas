from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.scripts import run_lfm25_vl_prompted_eval  # noqa: E402


class _FakeGenerator:
    def generate(self, case) -> str:
        _ = case
        return (
            '{"event_type":"probable_access_obstruction","severity":"high",'
            '"confidence":0.95,"bbox":[0.31,0.28,0.72,0.66],'
            '"civilian_impact":"public_mobility_disruption",'
            '"why":"Bridge span is broken.","action":"downlink_now"}'
        )


def test_run_prompted_eval_writes_predictions_and_summary(tmp_path: Path) -> None:
    image_root = tmp_path / "images" / "baltimore_bridge_collapse"
    image_root.mkdir(parents=True)
    (image_root / "current.png").write_bytes(b"png")
    (image_root / "baseline.png").write_bytes(b"png")

    dataset_path = tmp_path / "blackline_candidate_eval.jsonl"
    dataset_path.write_text(
        json.dumps(
            {
                "case_id": "baltimore_bridge_collapse",
                "split": "dev",
                "asset": {
                    "asset_id": "baltimore_bridge_01",
                    "asset_name": "Francis Scott Key Bridge",
                    "asset_type": "bridge",
                    "region": "Baltimore Harbor",
                    "latitude": 39.218,
                    "longitude": -76.531,
                    "hero": False,
                },
                "current_image_path": "images/baltimore_bridge_collapse/current.png",
                "baseline_image_path": "images/baltimore_bridge_collapse/baseline.png",
                "prompt": {
                    "system": "You are Blackline Atlas candidate generation.",
                    "user": "Compare current and baseline.",
                },
                "model_output_text": (
                    '{"event_type":"probable_access_obstruction","severity":"high",'
                    '"confidence":0.95,"bbox":[0.31,0.28,0.72,0.66],'
                    '"civilian_impact":"public_mobility_disruption",'
                    '"why":"Bridge span is broken.","action":"downlink_now"}'
                ),
                "expected_candidate": {
                    "event_type": "probable_access_obstruction",
                    "severity": "high",
                    "confidence": 0.95,
                    "bbox": [0.31, 0.28, 0.72, 0.66],
                    "civilian_impact": "public_mobility_disruption",
                    "why": "Bridge span is broken.",
                    "action": "downlink_now",
                },
                "expected_action": "downlink_now",
                "expected_alert": {
                    "alert_id": "blk_nd_00002",
                    "timestamp": "2024-04-15T15:00:00Z",
                    "asset_id": "baltimore_bridge_01",
                    "asset_name": "Francis Scott Key Bridge",
                    "asset_type": "bridge",
                    "event_type": "probable_access_obstruction",
                    "severity": "high",
                    "confidence": 0.95,
                    "bbox": [0.31, 0.28, 0.72, 0.66],
                    "civilian_impact": "public_mobility_disruption",
                    "why": "Bridge span is broken.",
                    "action": "downlink_now",
                    "source": {
                        "current_frame_id": "cur_baltimore_bridge_01_20240415",
                        "baseline_frame_id": "base_baltimore_bridge_01_20240326",
                        "model_version": "lfm2.5-vl-450m-prompted",
                    },
                    "mapbox_context_ref": None,
                },
                "expected_metrics": {
                    "frames_scanned": 61,
                    "alerts_emitted": 1,
                    "raw_frames_suppressed": 57,
                    "downlink_rate": 0.028,
                },
                "simsat": {
                    "current": {
                        "requested_timestamp": "2024-04-15T15:00:00Z",
                        "request_url": "https://example.test/current",
                        "image_available": True,
                        "datetime": "2024-04-14T16:02:24Z",
                        "cloud_cover": 4.72,
                        "footprint": [],
                        "spectral_bands": ["red", "green", "blue"],
                        "size_km": 5.0,
                        "window_seconds": 864000.0,
                    },
                    "baseline": {
                        "requested_timestamp": "2024-03-26T15:00:00Z",
                        "request_url": "https://example.test/baseline",
                        "image_available": True,
                        "datetime": "2024-03-25T16:02:24Z",
                        "cloud_cover": 0.02,
                        "footprint": [],
                        "spectral_bands": ["red", "green", "blue"],
                        "size_km": 5.0,
                        "window_seconds": 864000.0,
                    },
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    predictions_path, summary_path, summary = run_lfm25_vl_prompted_eval.run_prompted_eval(
        dataset_path=dataset_path,
        output_dir=tmp_path / "out",
        generator=_FakeGenerator(),
    )

    assert predictions_path.exists()
    assert summary_path.exists()
    assert summary["passed"] is True
    prediction = json.loads(predictions_path.read_text(encoding="utf-8").strip())
    assert prediction["case_id"] == "baltimore_bridge_collapse"


def test_load_candidate_eval_cases_resolves_paths_against_dataset_root(tmp_path: Path) -> None:
    image_root = tmp_path / "images" / "hero_port_disruption"
    image_root.mkdir(parents=True)
    (image_root / "current.png").write_bytes(b"png")
    (image_root / "baseline.png").write_bytes(b"png")

    dataset_path = tmp_path / "blackline_candidate_eval.jsonl"
    dataset_path.write_text(
        json.dumps(
            {
                "case_id": "hero_port_disruption",
                "split": "holdout_geo",
                "asset": {
                    "asset_id": "demo_port_01",
                    "asset_name": "Demo Grain Port",
                    "asset_type": "grain_port",
                    "region": "Black Sea",
                    "latitude": 46.501,
                    "longitude": 30.747,
                    "hero": True,
                },
                "current_image_path": "images/hero_port_disruption/current.png",
                "baseline_image_path": "images/hero_port_disruption/baseline.png",
                "prompt": {"system": "sys", "user": "usr"},
                "model_output_text": (
                    '{"event_type":"probable_large_scale_disruption","severity":"high",'
                    '"confidence":0.89,"bbox":[0.19,0.26,0.73,0.84],'
                    '"civilian_impact":"shipping_or_aid_disruption",'
                    '"why":"Port disrupted.","action":"downlink_now"}'
                ),
                "expected_candidate": {
                    "event_type": "probable_large_scale_disruption",
                    "severity": "high",
                    "confidence": 0.89,
                    "bbox": [0.19, 0.26, 0.73, 0.84],
                    "civilian_impact": "shipping_or_aid_disruption",
                    "why": "Port disrupted.",
                    "action": "downlink_now",
                },
                "expected_action": "downlink_now",
                "expected_alert": {
                    "alert_id": "blk_00017",
                    "timestamp": "2026-04-14T18:40:00Z",
                    "asset_id": "demo_port_01",
                    "asset_name": "Demo Grain Port",
                    "asset_type": "grain_port",
                    "event_type": "probable_large_scale_disruption",
                    "severity": "high",
                    "confidence": 0.89,
                    "bbox": [0.19, 0.26, 0.73, 0.84],
                    "civilian_impact": "shipping_or_aid_disruption",
                    "why": "Port disrupted.",
                    "action": "downlink_now",
                    "source": {
                        "current_frame_id": "cur_demo_port_01_20260414",
                        "baseline_frame_id": "base_demo_port_01_20250901",
                        "model_version": "lfm2.5-vl-450m-prompted",
                    },
                    "mapbox_context_ref": None,
                },
                "expected_metrics": {
                    "frames_scanned": 143,
                    "alerts_emitted": 5,
                    "raw_frames_suppressed": 138,
                    "downlink_rate": 0.035,
                },
                "simsat": {
                    "current": {
                        "requested_timestamp": "2026-04-14T18:40:00Z",
                        "request_url": "https://example.test/current",
                        "image_available": True,
                        "datetime": "2026-04-13T08:57:26Z",
                        "cloud_cover": 25.78,
                        "footprint": [],
                        "spectral_bands": ["red", "green", "blue"],
                        "size_km": 5.0,
                        "window_seconds": 864000.0,
                    },
                    "baseline": {
                        "requested_timestamp": "2025-09-01T10:00:00Z",
                        "request_url": "https://example.test/baseline",
                        "image_available": True,
                        "datetime": "2025-08-29T09:07:44Z",
                        "cloud_cover": 0.01,
                        "footprint": [],
                        "spectral_bands": ["red", "green", "blue"],
                        "size_km": 5.0,
                        "window_seconds": 864000.0,
                    },
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    case = run_lfm25_vl_prompted_eval.load_candidate_eval_cases(dataset_path)[0]
    assert case.current_image_path == str(
        (tmp_path / "images/hero_port_disruption/current.png").resolve()
    )
    assert case.baseline_image_path == str(
        (tmp_path / "images/hero_port_disruption/baseline.png").resolve()
    )


def test_build_liquid_conversation_keeps_prompt_text_then_current_then_baseline(
    tmp_path: Path,
) -> None:
    dataset_path = _write_eval_case_dataset(
        tmp_path=tmp_path,
        case_id="bridge_case",
        current_rel="images/bridge_case/current.png",
        baseline_rel="images/bridge_case/baseline.png",
    )
    case = run_lfm25_vl_prompted_eval.load_candidate_eval_cases(dataset_path)[0]

    conversation = run_lfm25_vl_prompted_eval.build_liquid_conversation(
        case,
        current_image="current-image",
        baseline_image="baseline-image",
    )

    assert conversation[1]["content"][0] == {"type": "text", "text": case.prompt["user"]}
    assert conversation[1]["content"][1] == {"type": "image", "image": "current-image"}
    assert conversation[1]["content"][2] == {"type": "image", "image": "baseline-image"}


def test_http_candidate_text_runner_uses_frozen_prompt_and_images(tmp_path: Path) -> None:
    image_root = tmp_path / "images" / "bridge_case"
    image_root.mkdir(parents=True)
    (image_root / "current.png").write_bytes(b"current-bytes")
    (image_root / "baseline.png").write_bytes(b"baseline-bytes")

    dataset_path = _write_eval_case_dataset(
        tmp_path=tmp_path,
        case_id="bridge_case",
        current_rel="images/bridge_case/current.png",
        baseline_rel="images/bridge_case/baseline.png",
    )
    case = run_lfm25_vl_prompted_eval.load_candidate_eval_cases(dataset_path)[0]

    requests: list[dict[str, object]] = []

    def fake_urlopen(request: Request, timeout: float):
        requests.append(
            {
                "timeout": timeout,
                "body": json.loads(request.data.decode("utf-8")),
            }
        )
        return _FakeHTTPResponse(
            body=(
                b'{"choices":[{"message":{"content":"'
                b'{\\"event_type\\":\\"probable_access_obstruction\\",'
                b'\\"severity\\":\\"high\\",\\"confidence\\":0.91,'
                b'\\"bbox\\":[0.1,0.2,0.8,0.9],'
                b'\\"civilian_impact\\":\\"public_mobility_disruption\\",'
                b'\\"why\\":\\"Bridge span damaged.\\",'
                b'\\"action\\":\\"downlink_now\\"}'
                b'"}}]}'
            )
        )

    telemetry = []
    runner = run_lfm25_vl_prompted_eval.HttpCandidateTextRunner(
        model_id="Qwen/Qwen2.5-VL-3B-Instruct",
        endpoint="http://127.0.0.1:9999/v1/chat/completions",
        provider_id="openai_chat_completions_http",
        gateway=run_lfm25_vl_prompted_eval.ModelGateway(
            timeout_seconds=4.0,
            telemetry_sink=telemetry,
            opener=fake_urlopen,
        ),
    )

    text = runner.generate(case)

    assert "Bridge span damaged." in text
    body = requests[0]["body"]
    assert body["model"] == "Qwen/Qwen2.5-VL-3B-Instruct"
    assert body["messages"][0]["content"][0]["text"] == case.prompt["system"]
    assert body["messages"][1]["content"][0]["text"] == case.prompt["user"]
    assert body["messages"][1]["content"][1]["type"] == "image_url"
    assert body["messages"][1]["content"][2]["type"] == "image_url"
    assert telemetry[0].parse_ok is True


def test_http_candidate_text_runner_does_not_fallback_to_expected_output(tmp_path: Path) -> None:
    image_root = tmp_path / "images" / "bridge_case"
    image_root.mkdir(parents=True)
    (image_root / "current.png").write_bytes(b"current-bytes")
    (image_root / "baseline.png").write_bytes(b"baseline-bytes")

    dataset_path = _write_eval_case_dataset(
        tmp_path=tmp_path,
        case_id="bridge_case",
        current_rel="images/bridge_case/current.png",
        baseline_rel="images/bridge_case/baseline.png",
    )
    case = run_lfm25_vl_prompted_eval.load_candidate_eval_cases(dataset_path)[0]

    def fake_urlopen(request: Request, timeout: float):
        _ = request
        _ = timeout
        raise URLError("offline")

    telemetry = []
    runner = run_lfm25_vl_prompted_eval.HttpCandidateTextRunner(
        model_id="LiquidAI/LFM2.5-VL-450M",
        endpoint="http://127.0.0.1:9999/v1/chat/completions",
        provider_id="openai_chat_completions_http",
        gateway=run_lfm25_vl_prompted_eval.ModelGateway(
            timeout_seconds=4.0,
            telemetry_sink=telemetry,
            opener=fake_urlopen,
        ),
    )

    assert runner.generate(case) == ""
    assert telemetry[0].fallback_reason == "http_error"
    assert telemetry[0].parse_ok is False


def test_parse_args_accepts_adapter_ref() -> None:
    args = run_lfm25_vl_prompted_eval.parse_args(
        ["--adapter-ref", "ChrisRPL/blackline-atlas-adapter"]
    )

    assert args.adapter_ref == "ChrisRPL/blackline-atlas-adapter"


def test_load_transformers_runner_wraps_base_model_with_peft_adapter(monkeypatch) -> None:
    processor_calls: list[tuple[str, str | None]] = []
    model_calls: list[tuple[str, str | None, str, str]] = []
    peft_calls: list[tuple[object, str, str | None]] = []

    class _FakeAutoProcessor:
        @classmethod
        def from_pretrained(cls, model_id: str, token: str | None = None):
            processor_calls.append((model_id, token))
            return "processor"

    class _FakeAutoModelForImageTextToText:
        @classmethod
        def from_pretrained(
            cls,
            model_id: str,
            token: str | None = None,
            device_map: str = "auto",
            dtype: str = "auto",
        ):
            model_calls.append((model_id, token, device_map, dtype))
            return {"base_model_id": model_id}

    class _FakePeftModel:
        @classmethod
        def from_pretrained(cls, model: object, adapter_ref: str, token: str | None = None):
            peft_calls.append((model, adapter_ref, token))
            return {"wrapped_model": model, "adapter_ref": adapter_ref}

    monkeypatch.setenv("HF_TOKEN", "hf_test")
    monkeypatch.setitem(sys.modules, "torch", types.SimpleNamespace())
    monkeypatch.setitem(
        sys.modules,
        "PIL",
        types.SimpleNamespace(Image=types.SimpleNamespace(open=lambda path: path)),
    )
    monkeypatch.setitem(
        sys.modules,
        "transformers",
        types.SimpleNamespace(
            AutoModelForImageTextToText=_FakeAutoModelForImageTextToText,
            AutoProcessor=_FakeAutoProcessor,
        ),
    )
    monkeypatch.setitem(sys.modules, "peft", types.SimpleNamespace(PeftModel=_FakePeftModel))

    _, _, processor, model = run_lfm25_vl_prompted_eval._load_transformers_runner(
        model_id="LiquidAI/LFM2.5-VL-450M",
        adapter_ref="ChrisRPL/blackline-atlas-adapter",
    )

    assert processor == "processor"
    assert model["adapter_ref"] == "ChrisRPL/blackline-atlas-adapter"
    assert processor_calls == [("LiquidAI/LFM2.5-VL-450M", "hf_test")]
    assert model_calls == [("LiquidAI/LFM2.5-VL-450M", "hf_test", "auto", "auto")]
    assert peft_calls == [
        (
            {"base_model_id": "LiquidAI/LFM2.5-VL-450M"},
            "ChrisRPL/blackline-atlas-adapter",
            "hf_test",
        )
    ]


def test_load_transformers_runner_requires_peft_for_adapter(monkeypatch) -> None:
    class _FakeAutoProcessor:
        @classmethod
        def from_pretrained(cls, model_id: str, token: str | None = None):
            _ = model_id, token
            return "processor"

    class _FakeAutoModelForImageTextToText:
        @classmethod
        def from_pretrained(cls, model_id: str, **kwargs):
            _ = model_id, kwargs
            return {"base_model_id": model_id}

    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setitem(sys.modules, "torch", types.SimpleNamespace())
    monkeypatch.setitem(
        sys.modules,
        "PIL",
        types.SimpleNamespace(Image=types.SimpleNamespace(open=lambda path: path)),
    )
    monkeypatch.setitem(
        sys.modules,
        "transformers",
        types.SimpleNamespace(
            AutoModelForImageTextToText=_FakeAutoModelForImageTextToText,
            AutoProcessor=_FakeAutoProcessor,
        ),
    )
    monkeypatch.delitem(sys.modules, "peft", raising=False)

    try:
        run_lfm25_vl_prompted_eval._load_transformers_runner(
            model_id="LiquidAI/LFM2.5-VL-450M",
            adapter_ref="ChrisRPL/blackline-atlas-adapter",
        )
    except RuntimeError as exc:
        assert "Missing PEFT dependency" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected missing PEFT dependency error")


def _write_eval_case_dataset(
    *,
    tmp_path: Path,
    case_id: str,
    current_rel: str,
    baseline_rel: str,
) -> Path:
    dataset_path = tmp_path / "blackline_candidate_eval.jsonl"
    dataset_path.write_text(
        json.dumps(
            {
                "case_id": case_id,
                "split": "dev",
                "asset": {
                    "asset_id": "demo_bridge_01",
                    "asset_name": "Demo Logistics Bridge",
                    "asset_type": "bridge",
                    "region": "Lower Danube",
                    "latitude": 45.169,
                    "longitude": 28.801,
                    "hero": False,
                },
                "current_image_path": current_rel,
                "baseline_image_path": baseline_rel,
                "prompt": {
                    "system": "Frozen system prompt",
                    "user": "Frozen user prompt",
                },
                "model_output_text": (
                    '{"event_type":"probable_access_obstruction","severity":"high",'
                    '"confidence":0.95,"bbox":[0.31,0.28,0.72,0.66],'
                    '"civilian_impact":"public_mobility_disruption",'
                    '"why":"Bridge span is broken.","action":"downlink_now"}'
                ),
                "expected_candidate": {
                    "event_type": "probable_access_obstruction",
                    "severity": "high",
                    "confidence": 0.95,
                    "bbox": [0.31, 0.28, 0.72, 0.66],
                    "civilian_impact": "public_mobility_disruption",
                    "why": "Bridge span is broken.",
                    "action": "downlink_now",
                },
                "expected_action": "downlink_now",
                "expected_alert": {
                    "alert_id": "blk_nd_00002",
                    "timestamp": "2024-04-15T15:00:00Z",
                    "asset_id": "demo_bridge_01",
                    "asset_name": "Demo Logistics Bridge",
                    "asset_type": "bridge",
                    "event_type": "probable_access_obstruction",
                    "severity": "high",
                    "confidence": 0.95,
                    "bbox": [0.31, 0.28, 0.72, 0.66],
                    "civilian_impact": "public_mobility_disruption",
                    "why": "Bridge span is broken.",
                    "action": "downlink_now",
                    "source": {
                        "current_frame_id": "cur_demo_bridge_01_20240415",
                        "baseline_frame_id": "base_demo_bridge_01_20240326",
                        "model_version": "lfm2.5-vl-450m-prompted",
                    },
                    "mapbox_context_ref": None,
                },
                "expected_metrics": {
                    "frames_scanned": 61,
                    "alerts_emitted": 1,
                    "raw_frames_suppressed": 57,
                    "downlink_rate": 0.028,
                },
                "simsat": {
                    "current": {
                        "requested_timestamp": "2024-04-15T15:00:00Z",
                        "request_url": "https://example.test/current",
                        "image_available": True,
                        "datetime": "2024-04-14T16:02:24Z",
                        "cloud_cover": 4.72,
                        "footprint": [],
                        "spectral_bands": ["red", "green", "blue"],
                        "size_km": 5.0,
                        "window_seconds": 864000.0,
                    },
                    "baseline": {
                        "requested_timestamp": "2024-03-26T15:00:00Z",
                        "request_url": "https://example.test/baseline",
                        "image_available": True,
                        "datetime": "2024-03-25T16:02:24Z",
                        "cloud_cover": 0.02,
                        "footprint": [],
                        "spectral_bands": ["red", "green", "blue"],
                        "size_km": 5.0,
                        "window_seconds": 864000.0,
                    },
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return dataset_path


class _FakeHTTPResponse:
    def __init__(self, *, body: bytes, status: int = 200) -> None:
        self._body = body
        self.status = status

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        _ = exc_type
        _ = exc
        _ = tb
