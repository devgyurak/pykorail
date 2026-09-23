"""합성 DynaPath 토큰을 역검증하는 테스트 전용 도구입니다."""

from __future__ import annotations

# 구현의 테이블 변경도 검출하도록 APK 분석 기준값을 별도로 보관합니다.
TABLE = "3FE9jgRD4KdCyuawklqGJYmvfMn15P7US8XbxeLQtWT6OicBAopINs2Vh0HZrz"


def decode_ascii(encoded: str, alphabet: str) -> str:
    """프로덕션 인코더를 호출하지 않고 30진수 청크를 161진수 문자로 풉니다."""
    decoded = bytearray()
    for offset in range(0, len(encoded), 3):
        group = encoded[offset : offset + 3]
        value = 0
        for char in group:
            value = value * 30 + alphabet.index(char)
        if len(group) == 3:
            decoded.extend(divmod(value, 161))
        else:
            assert len(group) == 2
            decoded.append(value)
    return decoded.decode("ascii")


def decode_token(token: str) -> tuple[str, str]:
    """키의 유효 비트를 이어 붙여 독립적으로 본문 알파벳을 복원합니다."""
    assert token[:5] == "bEeEP"
    key_length = TABLE.index(token[5])
    key = decode_ascii(token[6 : 6 + key_length], TABLE)
    # 원시 키 접기는 NUL에서 누산값을 초기화하므로 마지막 NUL 뒤만 남깁니다.
    suffix = key.rsplit("\0", 1)[-1]
    number = int("".join(format(ord(char), "b") for char in suffix) or "0", 2)
    remaining = list(TABLE[:30])
    alphabet = ""
    while remaining:
        number, index = divmod(number, len(remaining))
        alphabet += remaining.pop(index)
    return key, decode_ascii(token[6 + key_length :], alphabet)
