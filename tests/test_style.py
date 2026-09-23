"""소스 규약을 AST 로 강제합니다.

앞의 두 가지는 **테스트 코드**에, 마지막 하나는 **패키지와 테스트 전부**에
적용됩니다.

1. **제어 흐름 금지** — 테스트에 분기·반복이 들어가면 "무엇이 검증됐는지"가 실행
   경로에 따라 달라져서, 통과해도 무엇을 통과한 건지 알 수 없게 됩니다. 케이스가
   여러 개면 :func:`pytest.mark.parametrize` 로 펼쳐 실패한 케이스가 이름으로
   드러나게 하세요.

2. **Given–When–Then** — 준비·실행·검증의 경계를 주석으로 명시합니다. 경계가
   보이면 "무엇을 하다가 무엇이 깨졌는지"를 읽는 사람이 바로 압니다.

3. **텍스트 I/O 는 encoding 명시** — 이 저장소는 문서·주석·독스트링이 전부
   한국어입니다. 파이썬의 기본 인코딩은 플랫폼 로케일을 따라가서 Windows 에서는
   UTF-8 이 아닌데(cp1252 · cp949), ``encoding`` 없이 읽으면 **그 환경에서만**
   깨집니다. CI 는 우분투에서만 돌기 때문에 실행으로는 잡히지 않습니다.

컴프리헨션은 값을 뽑아내는 **식**이라 허용합니다 (``[s.name for s in stations]``).
금지 대상은 제어 흐름 **문**(``if`` / ``for`` / ``while``)입니다.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).parent
ROOT = TESTS_DIR.parent
# 분기·반복 금지는 테스트 시나리오에 적용합니다. 역디코더·동기화 같은 지원 도구는
# 별도 모듈에 두며, 이들도 ruff·ty와 아래 SOURCE_FILES의 I/O 규칙 검사를 받습니다.
TEST_FILES = sorted(TESTS_DIR.rglob("test_*.py"))
BANNED = (ast.If, ast.For, ast.While, ast.AsyncFor)

# encoding 검사는 패키지 코드에도 걸립니다. _version.py 는 hatch-vcs 가 빌드 때
# 만들어내는 파일이라 우리가 고칠 수 없어 제외합니다.
# 양쪽 다 rglob 입니다 — 한쪽만 glob 이면 하위 디렉터리가 생겼을 때 조용히 빠집니다.
SOURCE_FILES = sorted(
    path
    for path in [*(ROOT / "src" / "pykorail").rglob("*.py"), *TESTS_DIR.rglob("*.py")]
    if path.name != "_version.py"
)

# 텍스트를 다루는 호출만 봅니다. read_bytes/write_bytes 는 인코딩이 없습니다.
#
# 한계: 이름만 보고 매칭하므로 `gzip.open` 처럼 시그니처가 다른 동명 호출도 걸립니다
# (지금 이 저장소엔 없습니다). 반대로 `subprocess(text=True)` 나 `tempfile` 처럼
# 이름이 다른 텍스트 I/O 는 못 잡습니다. import 를 추적하지 않는 대신 단순함을
# 택한 것이고, 오탐이 나면 여기 목록이나 _has_encoding 을 손보세요.
TEXT_IO_CALLS = frozenset({"open", "read_text", "write_text"})

# encoding 을 **위치 인자**로 넘길 수 있는 자리. (호출 이름, 어트리뷰트 호출인가)
#   open(file, mode, buffering, encoding)        → 3
#   Path(p).open(mode, buffering, encoding)      → 2
#   Path(p).read_text(encoding, errors)          → 0
#   Path(p).write_text(data, encoding, errors)   → 1
ENCODING_POSITION = {
    ("open", False): 3,
    ("open", True): 2,
    ("read_text", True): 0,
    ("write_text", True): 1,
}

# 모드를 **위치 인자**로 받는 자리. read_text/write_text 는 모드 자체가 없어서
# 여기 없습니다 — 없으면 위치 인자를 모드로 보지 않습니다. (`write_text("ab")` 의
# 내용이 모드로 오인되면 미탐이 됩니다.)
#
# 어트리뷰트 호출의 `open` 은 `Path.open` 으로 봅니다. `io.open`/`codecs.open` 은
# 빌트인과 같은 시그니처(모드가 1번)라 여기서 틀리고, **바이너리인데 "encoding 을
# 붙여라" 라고 시키게 됩니다** — 그대로 따르면 ValueError 로 죽습니다. 위 한계
# 주석과 같은 이유(import 를 추적하지 않음)이지만 방향이 위험한 쪽이라 따로
# 적습니다. 그런 호출을 들이면 이 표를 함께 손보세요.
MODE_POSITION = {
    ("open", False): 1,  # open(file, mode)
    ("open", True): 0,  # Path(p).open(mode)
}

# 파일 모드 문자열에만 쓰이는 글자들. 파일 이름이 모드로 오인되는 것을 막습니다
# ("backup.txt" 는 '.' 때문에 걸러집니다).
MODE_CHARS = frozenset("rwxab+t")

GIVEN = re.compile(r"^\s*#\s*given\b", re.I)
WHEN = re.compile(r"^\s*#.*\bwhen\b", re.I)
THEN = re.compile(r"^\s*#.*\bthen\b", re.I)


def _parse(path: Path) -> tuple[ast.Module, list[str]]:
    source = path.read_text(encoding="utf-8")
    return ast.parse(source), source.splitlines()


def _test_functions(tree: ast.Module) -> list[ast.FunctionDef]:
    return [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")]


def control_flow_violations(path: Path) -> list[str]:
    """파일 안의 제어 흐름 문 위치를 모읍니다."""
    tree, _ = _parse(path)
    return [f"{path.name}:{node.lineno} {type(node).__name__}" for node in ast.walk(tree) if isinstance(node, BANNED)]


def _call_name(node: ast.Call) -> str:
    """``Path(p).read_text`` 도 ``open`` 도 마지막 이름만 뽑습니다."""
    return node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")


def _is_binary(node: ast.Call) -> bool:
    """``open(p, "rb")`` 처럼 바이너리 모드면 encoding 을 줄 수 없습니다.

    모드가 몇 번째 위치 인자인지는 호출 형태에 따라 다릅니다 — ``open(p, "rb")`` 는
    두 번째, ``Path(p).open("rb")`` 는 첫 번째, ``read_text``/``write_text`` 는
    아예 없습니다. 여기서 놓치면 "바이너리인데 encoding 을 붙여라" 라고 시키게 되고,
    그대로 따르면 :class:`ValueError` 로 죽습니다. 반대로 자리를 안 세고 아무 문자열
    이나 보면 ``write_text("ab")`` 의 **내용**이 모드로 오인돼 미탐이 됩니다.
    """
    position = MODE_POSITION.get((_call_name(node), isinstance(node.func, ast.Attribute)))
    positional = [
        arg.value
        for index, arg in enumerate(node.args)
        if index == position and isinstance(arg, ast.Constant)  # position 이 None 이면 아무것도 안 걸립니다
    ]
    keyword = [kw.value.value for kw in node.keywords if kw.arg == "mode" and isinstance(kw.value, ast.Constant)]
    modes = [value for value in positional + keyword if isinstance(value, str)]
    return any("b" in mode and set(mode) <= MODE_CHARS for mode in modes)


def _has_encoding(node: ast.Call) -> bool:
    """``encoding`` 을 키워드로든 위치 인자로든 넘겼는지."""
    position = ENCODING_POSITION.get((_call_name(node), isinstance(node.func, ast.Attribute)))
    keyword = any(kw.arg == "encoding" for kw in node.keywords)
    return keyword or (position is not None and len(node.args) > position)


def encoding_violations(path: Path) -> list[str]:
    """``encoding`` 없이 텍스트를 읽고 쓰는 호출을 모읍니다.

    Windows 기본 인코딩은 UTF-8 이 아니므로(cp1252 · cp949), 한국어가 든 파일을
    ``encoding`` 없이 읽으면 그 환경에서만 :class:`UnicodeDecodeError` 가 납니다.
    CI 는 우분투에서만 돌아 실행으로 잡히지 않으니 정적으로 막습니다.
    """
    tree, _ = _parse(path)
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _call_name(node) in TEXT_IO_CALLS and not _is_binary(node)
    ]
    return [f"{path.name}:{node.lineno} {_call_name(node)}()" for node in calls if not _has_encoding(node)]


def gwt_violations(path: Path) -> list[str]:
    """Given–When–Then 주석이 빠진 테스트를 모읍니다.

    ``# when`` 과 ``# then`` 은 모든 테스트에 있어야 합니다. ``# given`` 은 실행
    전에 준비할 코드가 있을 때만 필요합니다 — 준비가 없는데 빈 Given 을 두면
    잡음일 뿐입니다. 예외 검증처럼 실행과 검증이 한 덩어리면 ``# when & then``
    처럼 한 줄로 묶어도 됩니다.
    """
    tree, lines = _parse(path)
    violations: list[str] = []

    def body_lines(fn: ast.FunctionDef) -> list[str]:
        end = fn.end_lineno or fn.lineno
        return lines[fn.lineno - 1 : end]

    def first_marker_line(fn: ast.FunctionDef, pattern: re.Pattern[str]) -> int | None:
        matches = [i for i, line in enumerate(body_lines(fn), fn.lineno) if pattern.match(line)]
        return matches[0] if matches else None

    def first_statement_line(fn: ast.FunctionDef) -> int:
        # 독스트링은 준비 코드가 아닙니다.
        statements = [
            node
            for node in fn.body
            if not (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            )
        ]
        return statements[0].lineno if statements else fn.lineno

    checked = [(fn, first_marker_line(fn, WHEN), first_marker_line(fn, THEN)) for fn in _test_functions(tree)]

    violations.extend(f"{path.name}:{fn.lineno} {fn.name} — '# when' 없음" for fn, when, _ in checked if when is None)
    violations.extend(f"{path.name}:{fn.lineno} {fn.name} — '# then' 없음" for fn, _, then in checked if then is None)
    violations.extend(
        f"{path.name}:{fn.lineno} {fn.name} — '# then' 이 '# when' 보다 앞에 있음"
        for fn, when, then in checked
        if when is not None and then is not None and then < when
    )
    violations.extend(
        f"{path.name}:{fn.lineno} {fn.name} — 준비 코드가 있는데 '# given' 없음"
        for fn, when, _ in checked
        if when is not None and first_statement_line(fn) < when and first_marker_line(fn, GIVEN) is None
    )
    return sorted(violations)


@pytest.mark.parametrize("path", TEST_FILES, ids=lambda p: p.name)
def test_no_control_flow_statements(path: Path) -> None:
    """테스트에는 if/for/while 문을 쓰지 않습니다 — parametrize 로 펼치세요."""
    # given: 이 저장소의 테스트 파일 하나
    # when
    violations = control_flow_violations(path)

    # then
    assert violations == []


@pytest.mark.parametrize("path", TEST_FILES, ids=lambda p: p.name)
def test_every_test_follows_given_when_then(path: Path) -> None:
    """모든 테스트는 준비·실행·검증 경계를 주석으로 드러냅니다."""
    # when
    violations = gwt_violations(path)

    # then
    assert violations == []


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_text_io_declares_encoding(path: Path) -> None:
    """텍스트 I/O 는 encoding 을 명시합니다 — Windows 기본값은 UTF-8 이 아닙니다."""
    # when
    violations = encoding_violations(path)

    # then
    assert violations == []


class TestCheckersActuallyWork:
    """검사기가 조용히 무력화되면 위 세 테스트는 항상 통과합니다."""

    def test_control_flow_checker_catches_an_if(self, tmp_path: Path) -> None:
        # given
        sample = tmp_path / "test_sample.py"
        sample.write_text("def test_f(x):\n    if x:\n        return 1\n    return 0\n", encoding="utf-8")

        # when
        found = control_flow_violations(sample)

        # then
        assert found == ["test_sample.py:2 If"]

    def test_gwt_checker_catches_a_missing_marker(self, tmp_path: Path) -> None:
        # given
        sample = tmp_path / "test_sample.py"
        sample.write_text("def test_f():\n    assert True\n", encoding="utf-8")

        # when
        found = gwt_violations(sample)

        # then
        assert found == [
            "test_sample.py:1 test_f — '# then' 없음",
            "test_sample.py:1 test_f — '# when' 없음",
        ]

    def test_gwt_checker_requires_given_when_there_is_setup(self, tmp_path: Path) -> None:
        # given
        sample = tmp_path / "test_sample.py"
        sample.write_text(
            "def test_f():\n    value = 1\n\n    # when\n    result = value + 1\n\n    # then\n    assert result\n",
            encoding="utf-8",
        )

        # when
        found = gwt_violations(sample)

        # then
        assert found == ["test_sample.py:1 test_f — 준비 코드가 있는데 '# given' 없음"]

    def test_gwt_checker_accepts_a_combined_marker(self, tmp_path: Path) -> None:
        # given
        sample = tmp_path / "test_sample.py"
        sample.write_text("def test_f():\n    # when & then\n    assert True\n", encoding="utf-8")

        # when
        found = gwt_violations(sample)

        # then
        assert found == []

    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            ("from pathlib import Path\n\nPath('x').read_text()\n", ["s.py:3 read_text()"]),
            ("from pathlib import Path\n\nPath('x').write_text('한글')\n", ["s.py:3 write_text()"]),
            ("open('x')\n", ["s.py:1 open()"]),
            # 아래는 전부 통과해야 합니다.
            ("from pathlib import Path\n\nPath('x').read_text(encoding='utf-8')\n", []),
            ("open('x', encoding='utf-8')\n", []),
            ("open('x', 'rb')\n", []),  # 바이너리는 인코딩이 없습니다
            ("open('x', mode='rb')\n", []),
            ("from pathlib import Path\n\nPath('x').read_bytes()\n", []),
            # 아래는 리뷰에서 오탐으로 지적된 것들입니다. 잡히면 회귀입니다.
            ("from pathlib import Path\n\nPath('x').open('rb')\n", []),
            ("from pathlib import Path\n\nPath('x').open('w', encoding='utf-8')\n", []),
            ("from pathlib import Path\n\nPath('x').read_text('utf-8')\n", []),
            ("from pathlib import Path\n\nPath('x').write_text('한글', 'utf-8')\n", []),
            ("open('x', 'w', -1, 'utf-8')\n", []),
            # 파일 이름이나 쓰는 내용이 모드로 오인되면 안 됩니다.
            ("open('backup.txt')\n", ["s.py:1 open()"]),
            ("from pathlib import Path\n\nPath('x').write_text('ab')\n", ["s.py:3 write_text()"]),
        ],
        # pytest 가 비 ASCII id 를 \uXXXX 로 이스케이프해 출력이 읽기 나빠집니다.
        ids=[
            "read_text-without",
            "write_text-without",
            "open-without",
            "read_text-with",
            "open-with",
            "open-binary-positional",
            "open-binary-keyword",
            "read_bytes-not-applicable",
            "path-open-binary",
            "path-open-with-encoding",
            "read_text-positional-encoding",
            "write_text-positional-encoding",
            "open-positional-encoding",
            "filename-is-not-a-mode",
            "write_text-content-is-not-a-mode",
        ],
    )
    def test_encoding_checker(self, tmp_path: Path, source: str, expected: list[str]) -> None:
        # given
        sample = tmp_path / "s.py"
        sample.write_text(source, encoding="utf-8")

        # when
        found = encoding_violations(sample)

        # then
        assert found == expected


def test_every_test_file_is_checked() -> None:
    """33번 줄 글롭이 통째로 빗나가는 것도, 좁아지거나 넓어지는 것도 잡습니다.

    ``TESTS_DIR.rglob("test_*.py")`` 로 다시 훑어 대조하는 형태는 :data:`TEST_FILES`
    와 **같은 식**이라 항상 참입니다 — 검증력이 없습니다. 한쪽 차집합
    (``TEST_FILES - SOURCE_FILES``)도 부족합니다: :data:`TEST_FILES` 는 늘
    :data:`SOURCE_FILES` 의 부분집합이라 글롭이 **좁아지면** 조용히 통과합니다.

    그래서 :data:`SOURCE_FILES` 쪽에서 같은 집합을 다시 만들어 **양방향으로**
    비교합니다. 저쪽은 ``*.py`` 로 훑으므로 ``test_*.py`` 와 독립이고, 한 개만
    새도 좌우가 어긋납니다. ``>= 10`` 은 두 변이 함께 비는 경우 때문에 남깁니다.
    """
    # when
    from_source = {path for path in SOURCE_FILES if path.is_relative_to(TESTS_DIR) and path.name.startswith("test_")}

    # then
    assert len(TEST_FILES) >= 10, "패턴이 오타면 두 변이 같이 비어 동치 비교는 통과합니다"
    assert set(TEST_FILES) == from_source, "33번 줄 글롭이 좁아지거나 넓어졌습니다"


@pytest.mark.parametrize("subdir", ["src/pykorail", "tests"])
def test_encoding_check_covers_every_file(subdir: str) -> None:
    """한쪽을 통째로 빠뜨리는 것뿐 아니라 파일 하나가 새는 것도 잡습니다."""
    # given
    on_disk = {path for path in (ROOT / subdir).rglob("*.py") if path.name != "_version.py"}

    # when
    missing = on_disk - set(SOURCE_FILES)

    # then
    assert missing == set()
