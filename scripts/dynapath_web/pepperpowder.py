"""웹 DynaPath 지문 해시 코어(PepperPowder)의 파이썬 재현.

런타임 후킹으로 확보한 오라클(원시 지문 ``plain`` 200B · 정수 ``key`` · 회전
스케줄 ``rot``)로 **cyper 200B 를 바이트일치**로 재현합니다. 원본은 JScrambler
VM 이 실행하는 바이트코드이고, 이 모듈은 ``지문 → cyper`` 구간만 다룹니다 —
``cyper → _qdb`` 문자열 인코딩 구간은 아직 미확보라 범위 밖입니다.

재현한 규칙(오라클 실측으로 확정):

- ``rot[i] = (key >> 4i) & 15`` — key 의 4비트 니블 8개가 회전 스케줄이 됩니다.
- ``cyper[j]`` (4바이트 big-endian 워드) = ``ROTR(word(plain, (j-1)·4) ^ ~key, rot[j % 8])``
  (``j = 1 … 49``).
- ``cyper[0]`` 은 지문 워드가 아니라 별도 씨앗값으로 시작합니다. 오라클에서 관측한
  씨앗은 ``3·len(plain) + 2``(= 602) 였지만, 씨앗을 만드는 바깥 함수
  (``num2hhss``)의 바이트코드는 확보하지 못해 **규칙은 미확정**입니다 — 그래서
  이 모듈은 씨앗을 명시적 입력으로 받습니다.

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


def hash_cyper(plain: bytes, key: int, seed: int) -> bytes:
    """지문 ``plain`` 을 4바이트 워드로 접어 ``cyper`` 를 만듭니다.

    ``seed`` 는 :func:`seed_value` 가 관측값 602 를 재현하는지 확인하지 못한
    자리라 호출자가 명시합니다.
    """
    schedule = rot_schedule(key)
    complement = ~key & _MASK32
    words = len(plain) // 4
    out = bytearray()
    for index in range(words):
        source = seed if index == 0 else int.from_bytes(plain[(index - 1) * 4 : (index - 1) * 4 + 4], "big")
        word = rotate_right(_int32(source ^ complement), schedule[index % 8])
        out += word.to_bytes(4, "big")
    return bytes(out)


def seed_value(plain: bytes) -> int:
    """오라클에서 관측한 씨앗값 ``3·len(plain) + 2`` 를 돌려줍니다.

    바깥 함수 ``num2hhss`` 의 바이트코드가 없어 규칙인지 우연인지 확정하지
    못했습니다 — 이 함수는 "관측값 재현"이지 "알고리즘 확정"이 아닙니다.
    """
    return 3 * len(plain) + 2


__all__ = ["hash_cyper", "rot_schedule", "rotate_right", "seed_value"]
