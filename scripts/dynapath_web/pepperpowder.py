"""웹 DynaPath 지문 해시 코어(PepperPowder)의 파이썬 재현.

런타임 후킹으로 확보한 오라클(원시 지문 ``plain`` 599B · 정수 ``key``)로
``plain → cyper`` 구간을 **바이트일치**(151/151 워드)로 재현합니다. 원본은
JScrambler VM 이 실행하는 바이트코드이고, 이 모듈은 그중 ``plain → cyper``
구간만 다룹니다 — ``pp_bin → _qdb`` 문자열 인코딩은 VM 밖에서 이뤄져 범위 밖입니다.

확정한 규칙(``_vfegvbw85``(390B) 디컴파일 + 런타임 오라클 실측):

- ``block_len = (len(plain) + 3) >> 2``  (올림 나눗셈)
- ``rot[i] = (key >> 4i) & 15`` — key 의 4비트 니블 8개가 회전 스케줄입니다.
- ``cyper[0]`` = 첫 ``num2hhss`` 호출의 씨앗(= ``len(plain)``)을 같은 식으로 접은 값.
- ``cyper[j]`` (4바이트 BE 워드) = ``ROTR(word(plain, (j-1)·4) ^ ~key, rot[j % 8])``
  (``j = 1 … block_len``).
- 길이가 4의 배수가 아니면 마지막 워드의 남은 바이트는 ``4 - tail`` 값으로 채웁니다
  (원본의 ``pad`` 구성과 같습니다).
- 결과 ``cyper`` 는 ``block_len + 1`` 워드(4바이트)입니다.

``pp_bin`` 은 ``pp(4B) || cyper`` 입니다. ``_qdb`` 로 가는 인코딩(``pp_bin`` →
a~l 문자열)은 VM 트레이스에 안 잡혀(정규 JS·WebCrypto 쪽) 아직 미확정입니다.

ROTR 은 원본 ``ROTRT(a, b) = (a >>> b) | (a << (32 - b))`` 를 그대로 옮긴 것입니다.
"""

from __future__ import annotations

#: int32 로 접는 마스크.
_MASK32 = 0xFFFFFFFF


def rot_schedule(key: int) -> list[int]:
    """``key`` 의 4비트 니블 8개에서 회전 스케줄을 만듭니다."""
    return [(key & _MASK32) >> (4 * index) & 0xF for index in range(8)]


def rotate_right(value: int, amount: int) -> int:
    """32비트 회전우측 — 원본 ``ROTRT`` 와 같습니다."""
    value &= _MASK32
    amount &= 31
    if amount == 0:
        return value
    return ((value >> amount) | (value << (32 - amount))) & _MASK32


def _int32(value: int) -> int:
    """JS 의 ``|0`` 처럼 값을 int32 로 접습니다."""
    value &= _MASK32
    return value - 0x100000000 if value >= 0x80000000 else value


def _word(plain: bytes, index: int) -> int:
    """``plain`` 의 ``index`` 번째 4바이트 워드(big-endian).

    마지막 워드가 4바이트보다 짧으면 남은 자리를 ``4 - tail`` 값으로 채웁니다 —
    원본이 ``pad`` 를 그렇게 구성합니다.
    """
    segment = plain[index * 4 : index * 4 + 4]
    if len(segment) < 4:
        filler = 4 - len(segment)
        segment = bytes([*segment, *[filler] * filler])
    return int.from_bytes(segment, "big")


def hash_cyper(plain: bytes, key: int) -> bytes:
    """지문 ``plain`` 을 4바이트 워드로 접어 ``cyper`` 를 만듭니다."""
    schedule = rot_schedule(key)
    complement = ~key & _MASK32
    block_len = (len(plain) + 3) >> 2
    out = bytearray()
    for index in range(block_len + 1):
        source = len(plain) if index == 0 else _word(plain, index - 1)
        word = rotate_right(_int32(source ^ complement), schedule[index % 8])
        out += word.to_bytes(4, "big")
    return bytes(out)


__all__ = ["hash_cyper", "rot_schedule", "rotate_right"]
