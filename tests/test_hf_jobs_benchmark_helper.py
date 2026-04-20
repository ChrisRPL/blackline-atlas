from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.scripts import run_model_benchmark_hf_job  # noqa: E402


def test_build_archive_url_strips_dot_git_and_quotes_ref() -> None:
    url = run_model_benchmark_hf_job.build_archive_url(
        "https://github.com/ChrisRPL/blackline-atlas.git",
        "feature/bench test",
    )

    assert (
        url == "https://github.com/ChrisRPL/blackline-atlas/archive/feature%2Fbench%20test.tar.gz"
    )


def test_build_job_manifest_switches_one_model_to_local_runner() -> None:
    manifest = {
        "version": "2026-04-20",
        "default_output_dir": "training/eval_runs/model-benchmark",
        "models": [
            {
                "model_key": "liquid_lfm25_vl_450m_http",
                "title": "Liquid",
                "model_id": "LiquidAI/LFM2.5-VL-450M",
                "runner_kind": "openai_chat_completions_http",
                "enabled": True,
                "provider_id": "openai_chat_completions_http",
                "endpoint_env": "BLACKLINE_LIQUID_BENCHMARK_ENDPOINT",
                "api_key_env": "BLACKLINE_LIQUID_BENCHMARK_API_KEY",
            },
            {
                "model_key": "smolvlm2_500m_http",
                "title": "Smol",
                "model_id": "HuggingFaceTB/SmolVLM2-500M-Video-Instruct",
                "runner_kind": "openai_chat_completions_http",
                "enabled": True,
                "provider_id": "openai_chat_completions_http",
                "endpoint_env": "BLACKLINE_SMOLVLM2_ENDPOINT",
            },
        ],
    }

    patched = run_model_benchmark_hf_job.build_job_manifest(
        manifest=json.loads(json.dumps(manifest)),
        model_key="liquid_lfm25_vl_450m_http",
    )

    liquid, smol = patched["models"]
    assert liquid["enabled"] is True
    assert liquid["runner_kind"] == "transformers_local"
    assert liquid["provider_id"] is None
    assert liquid["endpoint_env"] is None
    assert liquid["api_key_env"] is None
    assert "HF Jobs local transformers fallback." in liquid["notes"]
    assert smol["enabled"] is False


def test_write_job_manifest_creates_temp_manifest(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    manifest_path = repo_dir / "training" / "replay_pack" / "model_benchmark_manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "version": "2026-04-20",
                "default_output_dir": "training/eval_runs/model-benchmark",
                "models": [
                    {
                        "model_key": "liquid_lfm25_vl_450m_http",
                        "title": "Liquid",
                        "model_id": "LiquidAI/LFM2.5-VL-450M",
                        "runner_kind": "openai_chat_completions_http",
                    }
                ],
                "slices": [],
            }
        ),
        encoding="utf-8",
    )

    output_path = run_model_benchmark_hf_job.write_job_manifest(
        repo_dir=repo_dir,
        manifest_relpath="training/replay_pack/model_benchmark_manifest.json",
        model_key="liquid_lfm25_vl_450m_http",
    )

    assert output_path == repo_dir / "training" / "eval_runs" / "job-benchmark-manifest.json"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["models"][0]["runner_kind"] == "transformers_local"
