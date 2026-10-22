"""웹 DynaPath 지문 해시 코어(PepperPowder)의 파이썬 재현.

런타임 후킹으로 확보한 두 오라클(원시 지문 ``plain`` · 정수 ``key`` · 회전
스케줄 ``rot`` · 씨앗 ``seed``)로 ``plain → cyper`` 구간을 **바이트일치**로
재현합니다. 원본은 JScrambler VM 이 실행하는 바이트코드이고, 이 모듈은 그중
``plain → cyper`` 구간만 다룹니다 — ``cyper → _qdb`` 문자열 인코딩은 범위 밖입니다.

재현한 규칙(오라클 실측으로 확정, 200B·400B 두 표본에서 검증):

- ``rot[i] = (key >> 4i) & 15`` — key 의 4비트 니블 8개가 회전 스케줄이 됩니다.
- ``cyper[j]`` (4바이트 big-endian 워드) = ``ROTR(word(plain, (j-1)·4) ^ ~key, rot[j % 8])``.
- ``cyper[0]`` 은 지문 워드가 아니라 **씨앗값**으로 시작합니다.
- 워드 수는 두 표본 모두 ``len(plain) / 4`` 였습니다.

남은 두 가지(확정 못 함):

- **씨앗 출처.** 원본 ``_vfegvbw85`` 는 첫 ``num2hhss`` 호출의 5번째 인자로
  ``plain.length`` 를 넘기고, 그 값은 200바이트 지문에서 602, 400바이트에서
  569 였습니다(바이트 배열 길이가 아님). 또한 원본의 ``block_len = plain.length >> 2``
  는 150·142 인데 관측한 cyper 워드 수는 50·100 이라 두 값을 그대로 연결하지
  못했습니다 — 이 모듈은 그래서 씨앗을 명시적 입력으로 받고 워드 수는
  ``len(plain) / 4`` 로 둡니다.
- ``cyper → _qdb`` 문자열 인코딩(``pack`` / ``num2ascii`` / ``_CharCode2Base61Value``).

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

    ``seed`` 는 원본이 ``plain.length`` 로 넘기는 값입니다(모듈 독스트링 참고) —
    바이트 길이가 아니라 VM 이 본 ``plain`` 의 길이라 호출자가 명시합니다.
    """
    schedule = rot_schedule(key)
    complement = ~key & _MASK32
    out = bytearray()
    for index in range(len(plain) // 4):
        source = seed if index == 0 else int.from_bytes(plain[(index - 1) * 4 : (index - 1) * 4 + 4], "big")
        word = rotate_right(_int32(source ^ complement), schedule[index % 8])
        out += word.to_bytes(4, "big")
    return bytes(out)


__all__ = ["hash_cyper", "rot_schedule", "rotate_right"]
