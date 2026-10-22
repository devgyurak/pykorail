"""로더(``dynaPath.do``)의 난독화 문자열 테이블을 해제합니다.

로더는 ``y('key', -0x12b)`` 형태의 호출로 문자열을 꺼냅니다. ``y`` 는 전역
문자열 배열의 항목을 커스텀 base64 + RC4 로 푼 값이고, 인덱스는
``num + DELTA - BASE`` 로 계산됩니다. 이 상수들이 곧 알고리즘의 일부입니다.
"""

from __future__ import annotations

import re

from .codec import base64_decode, rc4, unescape_js_string

#: 문자열 배열을 정의하는 리터럴. 50개 이상인 배열만 본다.
_STRING_ARRAY = re.compile(r"\[((?:'[^']*'|\"[^\"]*\"),?){50,}\]")

#: 배열 안의 문자열 리터럴 하나. 홑따옴표/쌍따옴표 둘 다 받는다.
_ARRAY_ITEM = re.compile(r"'((?:[^'\\]|\\.)*)'|\"((?:[^\"\\]|\\.)*)\"")

#: ``y('key', -0x12b)`` 또는 ``y('key', -b.w)`` 호출.
_Y_CALL = re.compile(r"""y\(\s*'((?:[^'\\]|\\.)*)'\s*,\s*(-(?:b\.[A-Za-z]+|0x[0-9a-fA-F]+|\d+))\s*\)""")

#: ``idx = num + DELTA - BASE``. 두 항은 원본에서 매직 넘버로 굳어 있다.
_BASE = 0x12B
_DELTA = 0x1CD

#: ``-b.<name>`` 로 참조되는 숫자 상수. 로더의 로컬 상수 객체에서 온다.
_CONSTANTS = {"w": 0x9D, "m": 0x6A, "p": 0x6C, "D": 0x70, "F": 0x9F}


def extract_string_array(source: str) -> list[str]:
    """로더 소스에서 전역 문자열 배열을 뽑아 이스케이프를 풉니다.

    JS 를 실행하지 않고 리터럴만 파싱합니다 — eval 없이 같은 결과를 내는 것이
    CI 에서 안전하기 때문입니다.
    """
    match = _STRING_ARRAY.search(source)
    if match is None:
        return []
    return [unescape_js_string(quoted or double) for quoted, double in _ARRAY_ITEM.findall(match.group(0))]


def _resolve_operand(expression: str) -> int:
    """``-b.w`` 나 ``-0x7a`` 같은 오프셋 표현을 정수로 접습니다."""
    if expression.startswith("-b."):
        return -_CONSTANTS[expression[len("-b.") :]]
    return int(expression, 16)


def decode_loader_strings(source: str) -> list[dict[str, object]]:
    """로더가 꺼내는 문자열을 ``{key, index, value}`` 목록으로 돌려줍니다.

    같은 (key, index) 는 한 번만 담습니다. 순서는 소스에 처음 등장한 순서입니다.
    """
    array = extract_string_array(source)
    seen: set[tuple[str, int]] = set()
    decoded: list[dict[str, object]] = []
    for match in _Y_CALL.finditer(source):
        key = unescape_js_string(match.group(1))
        index = _resolve_operand(match.group(2)) + _DELTA - _BASE
        if (key, index) in seen:
            continue
        seen.add((key, index))
        value = rc4(base64_decode(array[index]), key).decode("latin-1") if 0 <= index < len(array) else None
        decoded.append({"key": key, "index": index, "value": value})
    return decoded
