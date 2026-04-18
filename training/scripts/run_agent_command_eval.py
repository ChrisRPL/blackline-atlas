from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DATASET_PATH = Path(__file__).resolve().parent.parent / "replay_pack" / "agent_command_eval.jsonl"
SKIP_FIELD = "__skip__"


@dataclass(frozen=True)
class AgentCommandEvalCase:
    case_id: str
    expected_status: str
    expected_tool: str
    expected_planner_mode: str
    expected_trust_mode: str
    expected_summary_contains: str
    query: str | None = None
    request_tool: str | None = None
    request_area: str | None = None
    request_category: str | None = None
    request_site_id: str | None = None
    request_alert_id: str | None = None
    expected_focus_asset_id: str | None = SKIP_FIELD
    expected_alert_count: int | None = None
    expected_planner_reason: str | None = None
    expected_resolved_area: str | None = SKIP_FIELD
    expected_resolved_category: str | None = SKIP_FIELD
    expected_resolved_site_id: str | None = SKIP_FIELD
    expected_resolved_alert_id: str | None = SKIP_FIELD
    expected_resolved_selected_asset_id: str | None = SKIP_FIELD
    selected_asset_id: str | None = None
    expected_focus_alert_id: str | None = SKIP_FIELD
    expected_top_alert_asset_id: str | None = None
    expected_compare_asset_id: str | None = None


@dataclass(frozen=True)
class AgentCommandEvalResult:
    case: AgentCommandEvalCase
    ok: bool
    mismatches: list[str]
    payload: dict[str, object] | None = None
    error: str | None = None


def load_cases(path: Path) -> list[AgentCommandEvalCase]:
    cases: list[AgentCommandEvalCase] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        cases.append(AgentCommandEvalCase(**payload))
    return cases


def score_case(case: AgentCommandEvalCase, payload: dict[str, object]) -> list[str]:
    mismatches: list[str] = []

    if payload.get("status") != case.expected_status:
        mismatches.append("status")
    if payload.get("tool") != case.expected_tool:
        mismatches.append("tool")

    planner = payload.get("planner")
    if not isinstance(planner, dict) or planner.get("mode") != case.expected_planner_mode:
        mismatches.append("planner_mode")
    if case.expected_planner_reason is not None:
        if not isinstance(planner, dict) or planner.get("reason") != case.expected_planner_reason:
            mismatches.append("planner_reason")

    trust = payload.get("trust")
    if not isinstance(trust, dict) or trust.get("mode") != case.expected_trust_mode:
        mismatches.append("trust_mode")

    if (
        case.expected_focus_asset_id != SKIP_FIELD
        and payload.get("focus_asset_id") != case.expected_focus_asset_id
    ):
        mismatches.append("focus_asset_id")

    if (
        case.expected_focus_alert_id != SKIP_FIELD
        and payload.get("focus_alert_id") != case.expected_focus_alert_id
    ):
        mismatches.append("focus_alert_id")

    alerts = payload.get("alerts")
    top_alert = alerts[0] if isinstance(alerts, list) and alerts else None
    if case.expected_alert_count is not None:
        if not isinstance(alerts, list) or len(alerts) != case.expected_alert_count:
            mismatches.append("alert_count")
    if case.expected_top_alert_asset_id:
        if (
            not isinstance(top_alert, dict)
            or top_alert.get("asset_id") != case.expected_top_alert_asset_id
        ):
            mismatches.append("top_alert_asset_id")

    compare = payload.get("compare")
    if case.expected_compare_asset_id:
        if (
            not isinstance(compare, dict)
            or compare.get("asset_id") != case.expected_compare_asset_id
        ):
            mismatches.append("compare_asset_id")

    resolved = payload.get("resolved")
    if not isinstance(resolved, dict):
        mismatches.append("resolved")
    else:
        if resolved.get("tool") != case.expected_tool:
            mismatches.append("resolved_tool")
        if (
            case.expected_resolved_area != SKIP_FIELD
            and resolved.get("area") != case.expected_resolved_area
        ):
            mismatches.append("resolved_area")
        if (
            case.expected_resolved_category != SKIP_FIELD
            and resolved.get("category") != case.expected_resolved_category
        ):
            mismatches.append("resolved_category")
        if (
            case.expected_resolved_site_id != SKIP_FIELD
            and resolved.get("site_id") != case.expected_resolved_site_id
        ):
            mismatches.append("resolved_site_id")
        if (
            case.expected_resolved_alert_id != SKIP_FIELD
            and resolved.get("alert_id") != case.expected_resolved_alert_id
        ):
            mismatches.append("resolved_alert_id")
        if (
            case.expected_resolved_selected_asset_id != SKIP_FIELD
            and resolved.get("selected_asset_id") != case.expected_resolved_selected_asset_id
        ):
            mismatches.append("resolved_selected_asset_id")

    summary = payload.get("summary")
    if not isinstance(summary, str) or case.expected_summary_contains not in summary:
        mismatches.append("summary")

    return mismatches


def query_case(base_url: str, case: AgentCommandEvalCase) -> dict[str, object]:
    request_body: dict[str, object] = {}
    if case.query is not None:
        request_body["query"] = case.query
    if case.request_tool is not None:
        request_body["tool"] = case.request_tool
    if case.request_area is not None:
        request_body["area"] = case.request_area
    if case.request_category is not None:
        request_body["category"] = case.request_category
    if case.request_site_id is not None:
        request_body["site_id"] = case.request_site_id
    if case.request_alert_id is not None:
        request_body["alert_id"] = case.request_alert_id
    if case.selected_asset_id:
        request_body["selected_asset_id"] = case.selected_asset_id

    request = Request(
        f"{base_url.rstrip('/')}/agent/query",
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=30.0) as response:
        return json.loads(response.read().decode("utf-8"))


def evaluate_case(base_url: str, case: AgentCommandEvalCase) -> AgentCommandEvalResult:
    try:
        payload = query_case(base_url, case)
    except HTTPError as exc:
        return AgentCommandEvalResult(
            case=case,
            ok=False,
            mismatches=["http_error"],
            error=str(exc),
        )
    except (URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return AgentCommandEvalResult(
            case=case,
            ok=False,
            mismatches=["request_error"],
            error=str(exc),
        )

    mismatches = score_case(case, payload)
    return AgentCommandEvalResult(
        case=case,
        ok=not mismatches,
        mismatches=mismatches,
        payload=payload,
    )


def run(base_url: str, dataset: Path) -> int:
    results = [evaluate_case(base_url, case) for case in load_cases(dataset)]

    pass_count = sum(1 for result in results if result.ok)
    print(f"agent_command_eval pass_count={pass_count} total={len(results)}")
    for result in results:
        if result.ok:
            print(
                f"PASS {result.case.case_id} "
                f"tool={result.payload.get('tool')} "
                f"focus={result.payload.get('focus_asset_id')} "
                f"planner={result.payload.get('planner', {}).get('mode')}"
            )
            continue

        detail = ",".join(result.mismatches)
        if result.error:
            detail = f"{detail} error={result.error}"
        print(f"FAIL {result.case.case_id} {detail}")

    return 0 if pass_count == len(results) else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run frozen Blackline Atlas command-flow evals against /agent/query."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--dataset", default=str(DATASET_PATH))
    args = parser.parse_args()
    return run(base_url=args.base_url, dataset=Path(args.dataset))


if __name__ == "__main__":
    raise SystemExit(main())
