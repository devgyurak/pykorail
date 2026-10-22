"""보호 스크립트가 쓰는 인코딩 원시연산을 재현합니다.

세션 VM(``dyna/<token>.js``)과 로더(``dynaPath.do``)는 모두 문자열 테이블을
커스텀 base64 + RC4 로 감싸고, 바이트코드 블롭은 정수 파라미터로 XOR 합니다.
원시연산의 순서와 알파벳은 알고리즘의 일부이므로 그대로 옮깁니다.
"""

from __future__ import annotations

#: 문자열 테이블이 쓰는 커스텀 base64 알파벳. 표준과 달리 소문자가 대문자보다
#: 먼저 온다 — 순서가 곧 알고리즘의 일부라서 바꾸면 모든 문자열이 깨진다.
BASE64_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+/="

#: 문자열 리터럴에 등장하는 단순 이스케이프.
_SIMPLE_ESCAPES = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "b": "\b",
    "f": "\f",
    "v": "\v",
    "0": "\0",
    "\\": "\\",
    "'": "'",
    '"': '"',
}


def base64_decode(text: str) -> bytes:
    """커스텀 알파벳으로 인코딩된 문자열을 바이트로 풉니다.

    6비트를 모아 8비트가 될 때마다 방출합니다. 알파벳에 없는 문자는 JS 구현과
    마찬가지로 건너뜁니다(패딩 문자 포함).
    """
    bits = 0
    value = 0
    out = bytearray()
    for char in text:
        index = BASE64_ALPHABET.find(char)
        if index < 0:
            continue
        value = (value << 6) | index
        bits += 6
        if bits >= 8:
            bits -= 8
            out.append((value >> bits) & 0xFF)
    return bytes(out)


def rc4(data: bytes, key: str) -> bytes:
    """표준 RC4 다. 키는 문자열의 코드포인트를 그대로 씁니다."""
    state = list(range(256))
    j = 0
    for i in range(256):
        j = (j + state[i] + ord(key[i % len(key)])) % 256
        state[i], state[j] = state[j], state[i]
    out = bytearray(len(data))
    i = j = 0
    for position, byte in enumerate(data):
        i = (i + 1) % 256
        j = (j + state[i]) % 256
        state[i], state[j] = state[j], state[i]
        out[position] = byte ^ state[(state[i] + state[j]) % 256]
    return bytes(out)


def xor_decode(blob: str, model: int, multiplier: int) -> bytes:
    """바이트코드 블롭을 XOR 로 풉니다.

    JS 의 ``Math.imul((i + 1) ^ model, multiplier) & 0xff`` 를 그대로 옮긴
    것입니다 — 곱셈은 32비트로 감싸이고(``Math.imul``), 그 하위 바이트만 씁니다.
    """
    out = bytearray(len(blob))
    for i, char in enumerate(blob):
        mask = ((((i + 1) ^ model) * multiplier) & 0xFFFFFFFF) & 0xFF
        out[i] = (ord(char) & 0xFF) ^ mask
    return bytes(out)


def unescape_js_string(literal: str) -> str:
    """JS 문자열 리터럴 본문의 ``\\xNN``·``\\uNNNN``·단순 이스케이프를 풉니다.

    난독화된 값은 ``\\xNN`` 바이트열로 저장되므로, 소스를 읽을 때 반드시 거쳐야
    합니다. 알 수 없는 이스케이프는 JS 처럼 문자 그대로 남깁니다.
    """
    out: list[str] = []
    i = 0
    length = len(literal)
    while i < length:
        char = literal[i]
        if char != "\\" or i + 1 >= length:
            out.append(char)
            i += 1
            continue
        marker = literal[i + 1]
        if marker == "x" and i + 4 <= length:
            out.append(chr(int(literal[i + 2 : i + 4], 16)))
            i += 4
        elif marker == "u" and i + 6 <= length:
            out.append(chr(int(literal[i + 2 : i + 6], 16)))
            i += 6
        else:
            out.append(_SIMPLE_ESCAPES.get(marker, marker))
            i += 2
    return "".join(out)
