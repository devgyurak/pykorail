"""코레일 앱 서명 인증서에 대응하는 합성 Android ID 생성."""

from __future__ import annotations

import hashlib
import hmac
import re
import struct
from secrets import token_bytes as _token_bytes
from typing import Final

# Korail 7.0.8 APK에서 추출한 공개 서명 인증서 DER입니다. 개인 키가 아닙니다.
# SHA-256: 38ff229cb34c7dda8e28220a2d750cceec28db661a36d95ad92d82f6d3c618f9
_SIGNING_CERTIFICATE: Final = bytes.fromhex(
    "3082019b30820104a00302010202044cfa0d54300d06092a864886f70d01010505003011310f300d060355040313066b6f7261696c"
    "3020170d3130313230343039343334385a180f33303130303430363039343334385a3011310f300d060355040313066b6f7261696c"
    "30819f300d06092a864886f70d010101050003818d0030818902818100c3aa266fdb468cc4e9146fc299b776c683b99baae7fd231472"
    "0ce3c9b8d245b89ddd194c0140bf22001da468c601663d17a9646259c04cdda8e1a7af1e3c0f464bbd86ed316504a2f8cac9b3031d"
    "09f931d669bc5d53a8265f5272da75e1d31147902c89eff86553186ee8afc82d7cbefac3d864c351c8f9ede027aed488ab890203010001"
    "300d06092a864886f70d0101050500038181008b9b751dc8ee0a85b63f8ed8026d3d5b501e2cdc1905c27c69ad1af8e511a003dfe2b0"
    "1fd81b94ccce0b0d6951e6df864efda0406485fd56f49d2e22819c0d63cce9286481c3844c454ed34c5ce70a55bc62f69af5f753792"
    "e61227d8c397a20f42414ebc61773daa1c65c8bba0d7a2f7b7dcbdb92ed1c8d98a0f5eabe3076f2"
)


def generate_android_id() -> str:
    """새 임의 사용자 키로 16자리 소문자 16진수 합성 SSAID를 만듭니다.

    Android 14 SettingsProvider.generateSsaidLocked와 같이 인증서 DER 앞에
    4바이트 big-endian 길이를 붙여 HMAC-SHA256을 계산하고 앞 64비트를 씁니다.
    실제 Android가 발급한 ID는 아닙니다. 반환값을 프로파일에 저장해 재사용하세요.

    근거: AOSP android-14.0.0_r1의 packages/SettingsProvider/src/com/android/
    providers/settings/SettingsProvider.java (generateUserKeyLocked, generateSsaidLocked).
    """
    user_key = _token_bytes(32)
    message = struct.pack(">I", len(_SIGNING_CERTIFICATE)) + _SIGNING_CERTIFICATE
    return hmac.new(user_key, message, hashlib.sha256).hexdigest()[:16]


def validate_android_id(value: str) -> str:
    """저장된 ID를 반환하며, 형식이 잘못됐으면 ValueError를 발생시킵니다."""
    # JSON 복원이나 외부 프로파일은 타입 힌트와 다른 값을 넘길 수 있는 경계입니다.
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{16}", value) is None:
        raise ValueError("android_id는 16자리 소문자 16진수 문자열이어야 합니다")
    return value
