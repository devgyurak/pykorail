"""웹 DynaPath 자산을 해제해 스펙·드리프트 산출물을 만드는 CLI.

예:

    python -m scripts.dynapath_web \\
        --asset loader=assets/dynaPath.do.js \\
        --asset vm=assets/dyna_token.js \\
        --baseline scripts/dynapath_web/baseline.json \\
        --out artifacts --fail-on-drift

종료 코드는 0(정상) · 1(드리프트) · 2(사용법 오류)입니다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .disasm import disassemble
from .drift import compare, report_markdown
from .fetch import fetch_text
from .spec import build_spec, filter_spec
from .vm import decode_blocks


def _parse_asset(values: list[str], fetch_values: list[str]) -> dict[str, str]:
    """``이름=경로`` 와 ``이름=URL`` 인자를 합쳐 ``{이름: 소스}`` 로 만듭니다."""
    assets: dict[str, str] = {}
    for value in values:
        name, _, path = value.partition("=")
        if not name or not path:
            raise SystemExit(f"--asset 은 이름=경로 형식이어야 합니다: {value!r}")
        assets[name] = Path(path).read_text(encoding="utf-8")
    for value in fetch_values:
        name, _, url = value.partition("=")
        if not name or not url:
            raise SystemExit(f"--fetch 는 이름=URL 형식이어야 합니다: {value!r}")
        assets[name] = fetch_text(url)
    return assets


def _write_artifacts(out: Path, spec: dict, report: str, blocks: list[dict]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "algorithm-spec.json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "drift-report.md").write_text(report, encoding="utf-8")
    (out / "decoded-bytecode.json").write_text(
        json.dumps(blocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dynapath_web", description="웹 DynaPath 자산 해제·드리프트 검사")
    parser.add_argument("--asset", action="append", default=[], metavar="NAME=PATH", help="로컬 자산 (반복 가능)")
    parser.add_argument("--fetch", action="append", default=[], metavar="NAME=URL", help="원격 자산 (반복 가능)")
    parser.add_argument("--baseline", metavar="PATH", help="비교할 baseline 스펙 JSON")
    parser.add_argument("--only", metavar="NAMES", help="비교에 쓸 자산 이름(쉼표 구분). 예: helper,loader,vm")
    parser.add_argument("--out", metavar="DIR", help="산출물을 쓸 디렉터리")
    parser.add_argument("--print-spec", action="store_true", help="스펙을 표준출력으로 인쇄")
    parser.add_argument("--pseudocode", metavar="NAME", help="해당 VM 자산의 의사코드를 표준출력으로 인쇄")
    parser.add_argument("--fail-on-drift", action="store_true", help="드리프트면 종료 코드 1")
    args = parser.parse_args(argv)

    assets = _parse_asset(args.asset, args.fetch)
    if not assets:
        parser.error("최소 한 개의 --asset 또는 --fetch 가 필요합니다")

    spec = build_spec(assets)
    only = {name.strip() for name in args.only.split(",") if name.strip()} if args.only else None
    if only is not None:
        spec = filter_spec(spec, only)

    if args.pseudocode:
        blocks = decode_blocks(assets.get(args.pseudocode, ""))
        for block in blocks:
            for function in block.get("functions", []):
                if isinstance(function.get("bytecode"), str):
                    print(f"===== {block['blob']} :: {function.get('name')} =====")
                    print("\n".join(disassemble(function["bytecode"], block.get("constants"))))

    if args.print_spec:
        print(json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=True))

    report = ""
    if args.baseline:
        baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        if only is not None:
            baseline = filter_spec(baseline, only)
        diff = compare(baseline, spec)
        report = report_markdown(baseline, spec, diff)
        print(report)
        if args.out:
            _write_artifacts(Path(args.out), spec, report, decode_blocks(assets.get("vm", "")))
        if diff["drifted"] and args.fail_on_drift:
            return 1
        return 0

    if args.out:
        _write_artifacts(
            Path(args.out),
            spec,
            report or "(baseline 이 없어 드리프트 판정을 건너뜁니다)\n",
            decode_blocks(assets.get("vm", "")),
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
