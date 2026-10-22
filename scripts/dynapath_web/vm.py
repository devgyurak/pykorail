"""세션 VM(``dyna/<token>.js``)의 바이트코드 블롭을 정적으로 해제합니다.

VM 은 여러 개의 블롭을 ``'이름':'<난독화 문자열>'`` 프로퍼티로 품고, ``_vbee``
호출에서 ``(model, multiplier)`` 두 정수로 XOR 해제합니다. 해제 결과는
JScrambler VM JSON(``{"bytecode": {...}, "constants": [...], "functions": [...]}``)
입니다. 어떤 파라미터 쌍이 어떤 블롭에 맞는지는 소스에 직접 드러나지 않으므로,
블롭마다 파라미터 후보를 차례로 시도해 JSON 으로 파싱되는 조합을 찾습니다.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .codec import unescape_js_string, xor_decode

#: ``'이름':'<100자 이상>'`` 프로퍼티. 짧은 값은 블롭이 아니라서 제외한다.
_LITERAL_BLOB = re.compile(r"([A-Za-z0-9_]+)'\s*:\s*'([^']{100,})'")

#: ``_vbee`` 호출은 인자 모양이 여러 가지다(``_vbee,blob,key,0xT,0xV`` 도 있고
#: ``Z9['fn'](_vbee,blob,key,0xT,0xV)`` 도 있다). 두 정수 파라미터는 언제나
#: 호출 인자의 끝이므로, ``_vbee`` 뒤 가까운 곳의 첫 ``0xT, 0xV`` 쌍을 집는다.
#: 잘못 집힌 쌍은 아래 JSON 파싱에서 조용히 걸러진다.
_DECODE_CALL = re.compile(r"_vbee\b[\s\S]{0,200}?((?:0x[0-9a-fA-F]{2,})\s*,\s*(?:0x[0-9a-fA-F]{2,}))")


def extract_literal_blobs(source: str) -> dict[str, str]:
    """난독화 문자열 리터럴 블롭 ``{이름: 값}`` 을 뽑습니다.

    ``\\x``·``\\u`` 이스케이프를 포함한 값만 블롭 후보로 봅니다 — 순수 텍스트
    프로퍼티(설정·주석)는 XOR 대상이 아닙니다.
    """
    blobs: dict[str, str] = {}
    for name, raw in _LITERAL_BLOB.findall(source):
        if "\\x" in raw or "\\u" in raw:
            blobs[name] = unescape_js_string(raw)
    return blobs


def extract_decode_params(source: str) -> list[tuple[int, int]]:
    """``_vbee`` 호출에 등장하는 ``(model, multiplier)`` 쌍을 순서대로 돌려줍니다."""
    pairs: list[tuple[int, int]] = []
    for match in _DECODE_CALL.finditer(source):
        model, multiplier = (part.strip() for part in match.group(1).split(","))
        pair = (int(model, 16), int(multiplier, 16))
        if pair not in pairs:
            pairs.append(pair)
    return pairs


def decode_blocks(source: str) -> list[dict[str, Any]]:
    """블롭을 XOR 해제해 JScrambler VM JSON 블록 목록으로 돌려줍니다.

    블롭 이름 기준으로 정렬해, 같은 자산이면 언제나 같은 순서가 나오게 합니다.
    """
    blobs = extract_literal_blobs(source)
    params = extract_decode_params(source)
    blocks: list[dict[str, Any]] = []
    for name in sorted(blobs):
        for model, multiplier in params:
            try:
                parsed = json.loads(xor_decode(blobs[name], model, multiplier).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if isinstance(parsed, dict) and ("bytecode" in parsed or "functions" in parsed):
                blocks.append({"blob": name, "params": [model, multiplier], **parsed})
                break
    return blocks
