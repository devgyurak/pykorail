"""비동기 원본에서 동기 코드를 생성합니다 (unasync).

``src/pykorail/_async`` · ``tests/_async`` 가 **원본**이고, ``src/pykorail/_sync`` ·
``tests/_sync`` 는 여기서 만드는 **생성물**입니다. ``_sync`` 를 직접 고치지 마세요 —
다음 생성에서 사라집니다. 고칠 때는 ``_async`` 를 고치고 이 스크립트를 돌립니다:

    uv run python scripts/unasync.py          # 생성
    uv run python scripts/unasync.py --check   # 생성물이 최신인지

``--check`` 는 ``tests/test_packaging.py`` 와 CI 린트 잡이 돌립니다.

httpcore 의 ``scripts/unasync.py`` 에서 두 가지 장치를 가져왔습니다:
- ``--check`` 로 원본에서 다시 만들어 커밋된 파일과 **통째로** 비교합니다.
- 쓰이지 않는 치환 규칙이 있으면 실패합니다 — 규칙이 썩는 것을 막습니다.
거기에 하나를 더했습니다:
- 생성 결과에 ``await`` · ``async`` · ``Async`` 같은 흔적이 남으면 실패합니다. 규칙을
  하나 빠뜨려 비동기 코드가 조용히 동기 파일로 새는 것을 막습니다.

``async for`` 는 규칙을 두지 않았습니다. 지금 원본에 쓰이는 곳이 없어 규칙을 넣으면
"쓰이지 않는 규칙" 검사에 걸리고, 쓰이기 시작하면 아래 흔적 검사가 ``async`` 를 잡아
규칙을 더하라고 알려 줍니다.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: (원본 디렉터리, 생성 디렉터리). 둘 다 저장소 루트 기준 상대 경로입니다.
PAIRS = (
    ("src/pykorail/_async", "src/pykorail/_sync"),
    ("tests/_async", "tests/_sync"),
)

#: 치환 규칙. **순서가 중요합니다** — 위에서부터 차례로 적용됩니다.
#:
#: ``create_async_session`` 이 ``_async`` 규칙보다 먼저 와야 합니다. 반대로 두면
#: ``create_async_session`` 이 ``create_sync_session`` 이 되어 버립니다.
RAW_SUBS: tuple[tuple[str, str], ...] = (
    # 로거 이름은 문자열 리터럴로만 바꿉니다. import 경로(`from pykorail._async.api import ...`)는
    # 건드리지 않아야 합니다 — 따옴표까지 포함해 그 줄만 겨냥합니다.
    (r'"pykorail\._async\.api"', '"pykorail.api"'),
    (r"create_async_session", "create_session"),
    # ``Async`` 뒤에 대문자 이름이 올 때만 뗍니다. ``unasync`` 같은 소문자 단어와
    # ``asyncio`` 는 건드리지 않습니다.
    (r"\bAsync(?=[A-Z][A-Za-z0-9_]*)", ""),
    (r"\basync def\b", "def"),
    (r"\basync with\b", "with"),
    (r"\bawait\b +", ""),
    (r"__aenter__", "__enter__"),
    (r"__aexit__", "__exit__"),
    (r"_async", "_sync"),
)

SUBS = tuple((re.compile(pattern), replacement) for pattern, replacement in RAW_SUBS)

#: 생성물에 남아 있으면 규칙이 샌 흔적. 한국어 "비동기" 도 같이 봅니다 — 규칙으로
#: 지워지지 않고 동기 파일에 그대로 실려 나가기 때문입니다.
LEFTOVERS = (
    re.compile(r"\bawait\b"),
    re.compile(r"\basync\b"),
    re.compile(r"\bAsync[A-Za-z0-9_]*\b"),
    re.compile(r"create_async_session"),
    re.compile(r"_async"),
    re.compile(r"비동기"),
)

HEADER = (
    "# 이 파일은 생성물입니다 — 직접 고치지 마세요.\n"
    "# 원본: {source}\n"
    "# 다시 만들려면: uv run python scripts/unasync.py\n"
)

#: 규칙이 실제로 쓰였는지 기록.
USED: set[tuple[str, str]] = set()


def unasync_text(text: str) -> str:
    """치환 규칙을 차례로 적용합니다. 쓰인 규칙을 :data:`USED` 에 기록합니다."""
    for pattern, replacement in SUBS:
        text, count = pattern.subn(replacement, text)
        if count:
            USED.add((pattern.pattern, replacement))
    return text


def render(source: Path) -> str:
    """원본 하나를 생성물 텍스트로 만듭니다(헤더 포함)."""
    body = unasync_text(source.read_text(encoding="utf-8"))
    header = HEADER.format(source=source.relative_to(ROOT).as_posix())
    return header + body


def source_files() -> list[tuple[Path, Path]]:
    """(원본, 생성물) 쌍을 모두 모읍니다."""
    pairs: list[tuple[Path, Path]] = []
    for from_dir, to_dir in PAIRS:
        source_root = ROOT / from_dir
        for source in sorted(source_root.rglob("*.py")):
            pairs.append((source, ROOT / to_dir / source.relative_to(source_root)))
    return pairs


def ruff_fix(paths: list[Path]) -> None:
    """생성물에 저장소 포매터를 겁니다 — 검사가 흔들리지 않게.

    ``ruff format`` 만으로는 부족합니다. ``_async`` 규칙이 ``_sync`` 로 바뀌면
    ``pykorail._shared`` 와의 isort 순서가 뒤집힙니다(``_async < _shared < _sync``).
    원본은 ``_async`` 가 앞이라 정렬돼 있지만 생성물은 ``_shared`` 가 앞이어야 하므로,
    import 정렬(``--select I``)까지 생성 단계에서 마저 해 줍니다.
    """
    if not paths:
        return
    arguments = [str(path) for path in paths]
    subprocess.run([sys.executable, "-m", "ruff", "check", "--fix", "--select", "I", "--quiet", *arguments], check=True)
    subprocess.run([sys.executable, "-m", "ruff", "format", "--quiet", *arguments], check=True)


def check_usages() -> None:
    """쓰이지 않은 규칙이 있으면 실패합니다."""
    unused = [rule for rule in RAW_SUBS if rule not in USED]
    if unused:
        print("쓰이지 않는 치환 규칙:", file=sys.stderr)
        for pattern, replacement in unused:
            print(f"  {pattern!r} -> {replacement!r}", file=sys.stderr)
        raise SystemExit(1)


def check_leftovers(relative: str, text: str) -> None:
    """생성물에 비동기 흔적이 남았는지 봅니다. 헤더는 검사에서 뺍니다."""
    header_lines = len(HEADER.splitlines())
    for number, line in enumerate(text.splitlines()[header_lines:], start=header_lines + 1):
        for pattern in LEFTOVERS:
            if pattern.search(line):
                print(f"{relative}:{number} 에 비동기 흔적: {line.strip()!r}", file=sys.stderr)
                raise SystemExit(1)


def generate(verbose: bool = True) -> None:
    targets: list[Path] = []
    for source, target in source_files():
        rendered = render(source)
        check_leftovers(target.relative_to(ROOT).as_posix(), rendered)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
        targets.append(target)
        if verbose:
            print(f"{source.relative_to(ROOT)} -> {target.relative_to(ROOT)}")
    ruff_fix(targets)
    check_usages()


def check() -> None:
    """원본에서 다시 만든 결과가 커밋된 파일과 같은지 봅니다.

    생성물을 **제자리에** 다시 만들고 ruff 를 건 뒤 커밋본과 비교합니다. 임시
    디렉터리에 만들면 ruff 의 first-party 판정(``[tool.ruff] src``)이 파일 위치에
    따라 달라져, 제자리 생성과 결과가 어긋납니다. 비교가 끝나면 원래 내용으로
    되돌립니다.
    """
    pairs = source_files()
    for source, target in pairs:
        check_leftovers(target.relative_to(ROOT).as_posix(), render(source))
    check_usages()

    originals = {target: (target.read_text(encoding="utf-8") if target.exists() else None) for _, target in pairs}
    problems: list[str] = []
    try:
        for source, target in pairs:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(render(source), encoding="utf-8")
        ruff_fix([target for _, target in pairs])
        for _, target in pairs:
            generated = target.read_text(encoding="utf-8")
            if generated != originals[target]:
                problems.append(target.relative_to(ROOT).as_posix())
    finally:
        # 원래 없던 생성물은 빈 파일로 남기지 않고 지웁니다.
        for target, text in originals.items():
            if text is None:
                target.unlink(missing_ok=True)
            else:
                target.write_text(text, encoding="utf-8")

    # 원본 없는 생성물(고아)도 잡습니다.
    expected = {target.resolve() for _, target in pairs}
    for _, to_dir in PAIRS:
        for candidate in sorted((ROOT / to_dir).rglob("*.py")):
            if candidate.resolve() not in expected:
                problems.append(f"{candidate.relative_to(ROOT).as_posix()} (원본 없음)")

    if problems:
        print("생성물이 최신이 아닙니다. `uv run python scripts/unasync.py` 를 돌리세요:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        raise SystemExit(1)


def main() -> None:
    if "--check" in sys.argv:
        check()
        print("생성물 최신 — 문제 없음")
    else:
        generate()


if __name__ == "__main__":
    main()
