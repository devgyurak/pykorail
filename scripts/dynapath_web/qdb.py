"""``pp_bin`` → ``_qdb`` 문자열 인코딩의 파이썬 재현.

원본은 JScrambler VM **밖**(정규 JS)에서 이뤄집니다. 두 단계입니다:

``ww`` — 바이트열을 **base-102** 문자열로 인코딩합니다. 5바이트를 빅엔디언으로
누적(``Ny = Ny*256 + byte``)해 6자리(``Ny % 102``, ``Ny // 102``)로 펼칩니다.
마지막 자투리(5의 배수가 아닌 꼬리)는 그 바이트 수를 담는 최소 자리수만 씁니다.
각 자리값(0~101)은 문자코드 ``25 + 자리값`` 으로 매핑됩니다(오라클 역산으로 확정 —
값 범위 25~126, 정확히 102개).

``lb`` — 그 문자열을 **base-12** 두 자리로 다시 인코딩합니다. 값 ``v`` 마다
low(``v % 12``)→``a~l``, high(``v // 12``)→``a~i`` 를 이어 붙여 문자셋이 정확히
``a~l`` 이 됩니다.

파이프라인 전체: ``plain + key + pp → pp_bin(=pp‖cyper) → qdb``.
"""

from __future__ import annotations

#: ``ww`` 가 쓰는 진법. ``Ny % 102`` · ``Ny // 102`` 로 자리를 뽑습니다.
_BASE102 = 102

#: ``ww`` 자리값(0~101)에 더하는 문자코드 오프셋.
_CHARCODE_OFFSET = 25

#: ``ww`` 가 한 묶음으로 누적하는 바이트 수.
_CHUNK = 5


def _digits_for(byte_length: int) -> int:
    """``byte_length`` 바이트를 담는 base-102 자리수를 돌려줍니다."""
    capacity = (1 << (8 * byte_length)) - 1
    count = 1
    while _BASE102**count <= capacity:
        count += 1
    return count


def ww(data: bytes) -> list[int]:
    """바이트열을 base-102 문자코드 목록으로 바꿉니다(``pp_bin`` → 문자열)."""
    codes: list[int] = []
    for offset in range(0, len(data), _CHUNK):
        chunk = data[offset : offset + _CHUNK]
        value = int.from_bytes(chunk, "big")
        digits = [0] * _digits_for(len(chunk))
        for position in range(len(digits) - 1, -1, -1):
            digits[position] = value % _BASE102
            value //= _BASE102
        codes.extend(_CHARCODE_OFFSET + digit for digit in digits)
    return codes


def lb(codes: list[int]) -> str:
    """base-102 문자코드 목록을 ``a~l`` base-12 두 자리 문자열로 바꿉니다."""
    out: list[str] = []
    for code in codes:
        out.append(chr(97 + code % 12))
        out.append(chr(97 + code // 12))
    return "".join(out)


def encode_qdb(pp_bin: bytes) -> str:
    """``pp_bin`` 을 ``_qdb`` 문자열로 인코딩합니다 — ``qdb = lb(ww(pp_bin))``."""
    return lb(ww(pp_bin))


__all__ = ["encode_qdb", "lb", "ww"]
