"""baseline 스펙과 현재 스펙을 비교해 드리프트 리포트를 만듭니다."""

from __future__ import annotations

from typing import Any


def _changed(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, list[str]]:
    """목록 필드의 추가·삭제를 계산합니다."""
    before = set(baseline.get("loader_values", []))
    after = set(current.get("loader_values", []))
    functions_before = set(baseline.get("vm_functions", []))
    functions_after = set(current.get("vm_functions", []))
    constants_before = set(baseline.get("vm_constants", []))
    constants_after = set(current.get("vm_constants", []))
    assets_before = dict(baseline.get("assets", {}))
    assets_after = dict(current.get("assets", {}))
    return {
        "assets_changed": sorted(
            name for name in assets_before.keys() & assets_after.keys() if assets_before[name] != assets_after[name]
        ),
        "assets_added": sorted(assets_after.keys() - assets_before.keys()),
        "assets_removed": sorted(assets_before.keys() - assets_after.keys()),
        "loader_values_added": sorted(after - before),
        "loader_values_removed": sorted(before - after),
        "functions_added": sorted(functions_after - functions_before),
        "functions_removed": sorted(functions_before - functions_after),
        "constants_added": sorted(constants_after - constants_before),
        "constants_removed": sorted(constants_before - constants_after),
    }


def compare(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """두 스펙을 비교합니다. ``drifted`` 가 참이면 무언가 달라졌습니다."""
    changes = _changed(baseline, current)
    drifted = baseline.get("signature") != current.get("signature") or any(changes.values())
    return {
        "drifted": drifted,
        "baseline_signature": baseline.get("signature"),
        "current_signature": current.get("signature"),
        **changes,
    }


def _bullets(title: str, items: list[str], limit: int = 40) -> list[str]:
    if not items:
        return []
    shown = items[:limit]
    suffix = [f"- … 외 {len(items) - limit}건"] if len(items) > limit else []
    return [f"### {title}", "", *[f"- `{item}`" for item in shown], *suffix, ""]


def report_markdown(baseline: dict[str, Any], current: dict[str, Any], diff: dict[str, Any]) -> str:
    """사람이 읽는 드리프트 리포트(Markdown)를 만듭니다."""
    status = "드리프트 감지" if diff["drifted"] else "변화 없음"
    lines = [
        "# DynaPath 웹 VM 드리프트 리포트",
        "",
        f"- 판정: **{status}**",
        f"- baseline 시그니처: `{diff['baseline_signature']}`",
        f"- 현재 시그니처: `{diff['current_signature']}`",
        "",
    ]
    lines += _bullets("변경된 자산", diff["assets_changed"])
    lines += _bullets("추가된 자산", diff["assets_added"])
    lines += _bullets("사라진 자산", diff["assets_removed"])
    lines += _bullets("추가된 로더 디코딩 값", diff["loader_values_added"])
    lines += _bullets("사라진 로더 디코딩 값", diff["loader_values_removed"])
    lines += _bullets("추가된 VM 함수", diff["functions_added"])
    lines += _bullets("사라진 VM 함수", diff["functions_removed"])
    lines += _bullets("추가된 VM 상수", diff["constants_added"])
    lines += _bullets("사라진 VM 상수", diff["constants_removed"])
    if not diff["drifted"]:
        lines += ["baseline 과 같습니다 — 보호 스크립트가 회전하지 않았습니다.", ""]
    return "\n".join(lines)
