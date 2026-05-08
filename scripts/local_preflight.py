from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


def main() -> int:
    parser = argparse.ArgumentParser(description="Blackline Atlas local demo preflight")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()

    health_url = f"{args.base_url.rstrip('/')}/health"
    try:
        health = _get_json(health_url, timeout=args.timeout)
    except RuntimeError as exc:
        _print_checks([Check("FastAPI /health", False, str(exc))])
        return 1

    checks = [
        Check("FastAPI /health", health.get("status") == "ok", health_url),
        _dependency_check(health, "simsat_current", required_mode="live_http"),
        _dependency_check(health, "simsat_baseline", required_mode="live_http"),
        _dependency_check(health, "agent_backend", required_mode="live_http"),
        _dependency_check(health, "analyst_backend", required_mode="live_http"),
        _sam_off_path_check(health),
    ]
    _print_checks(checks)
    return 0 if all(check.ok for check in checks) else 1


def _get_json(url: str, *, timeout: float) -> dict[str, Any]:
    request = Request(url, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", response.getcode())
            body = response.read().decode("utf-8")
    except (OSError, TimeoutError, URLError, HTTPError) as exc:
        raise RuntimeError(f"{url} unreachable: {exc}") from exc
    if status != 200:
        raise RuntimeError(f"{url} returned HTTP {status}")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{url} returned non-JSON body") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{url} returned non-object JSON")
    return payload


def _dependency_check(
    health: dict[str, Any],
    key: str,
    *,
    required_mode: str,
) -> Check:
    value = health.get(key)
    if not isinstance(value, dict):
        return Check(key, False, "missing from /health")
    status = value.get("status")
    mode = value.get("mode")
    detail = str(value.get("detail") or "")
    ok = status == "ready" and mode == required_mode
    return Check(key, ok, f"{status}/{mode}: {detail}")


def _sam_off_path_check(health: dict[str, Any]) -> Check:
    config = health.get("config") if isinstance(health.get("config"), dict) else {}
    sam_enabled = bool(config.get("sam3_http_enabled")) if isinstance(config, dict) else True
    sam_required = bool(config.get("sam3_required")) if isinstance(config, dict) else True
    ok = not sam_enabled and not sam_required
    detail = f"SAM3_HTTP_ENABLED={sam_enabled} SAM3_REQUIRED={sam_required}"
    return Check("SAM outside judge path", ok, detail)


def _print_checks(checks: list[Check]) -> None:
    width = max(len(check.name) for check in checks)
    for check in checks:
        label = "ok" if check.ok else "fail"
        print(f"{label:4} {check.name:<{width}}  {check.detail}")


if __name__ == "__main__":
    sys.exit(main())
