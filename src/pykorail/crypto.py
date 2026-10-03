"""앱이 쓰는 대칭키 원시연산.

앱의 이중 Base64 플래그와 줄바꿈을 보존합니다. 근거와 검증 범위는
``docs/protocol-evidence-7.0.8.json`` 을 참고하세요.
"""

from __future__ import annotations

import base64

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad


def encrypt_sid(device: str, ts: int, key: bytes) -> str:
    """``Sid`` 폼 필드 값을 만듭니다.

    키를 IV 로 재사용하는 AES-CBC 입니다(앱과 동일). 결과 끝의 개행도 앱이 보내는
    그대로이므로 유지합니다.
    """
    cipher = AES.new(key, AES.MODE_CBC, iv=key)
    ciphertext = cipher.encrypt(pad(f"{device}{ts}".encode(), 16))
    return base64.b64encode(ciphertext).decode("utf-8") + "\n"


def encrypt_password(password: str, key: str) -> str:
    """로그인 비밀번호를 서버가 발급한 1회용 키로 암호화합니다.

    키 문자열이 그대로 AES 키이고 그 앞 16바이트가 IV 입니다. base64 를 두 번
    씌웁니다. AESCrypto.encrypt의 안쪽 플래그는 NO_WRAP(2), LoginRepositoryImpl의
    바깥쪽 플래그는 URL_SAFE(8)입니다. 바깥쪽은 NO_WRAP이 없으므로 76자마다
    LF를 붙이며 마지막 줄에도 LF가 있습니다. UTF-8 바이트 길이를 기준으로 합니다.
    """
    cipher = AES.new(key.encode("utf-8"), AES.MODE_CBC, key[:16].encode("utf-8"))
    ciphertext = cipher.encrypt(pad(password.encode("utf-8"), AES.block_size))
    inner = base64.b64encode(ciphertext)
    outer = base64.urlsafe_b64encode(inner).decode("ascii")
    return "".join(outer[offset : offset + 76] + "\n" for offset in range(0, len(outer), 76))
