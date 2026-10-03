"""요청 서명 — 어떤 경로에 어떤 인증 재료를 붙일지 결정합니다."""

from __future__ import annotations

import random
import string
from typing import TYPE_CHECKING

from pykorail.auth.dynapath import DynaPathMasterEngine
from pykorail.constants import DEVICE, DYNAPATH_PATHS, SID_KEY
from pykorail.crypto import encrypt_sid
from pykorail.device.android_id import generate_android_id, validate_android_id

if TYPE_CHECKING:
    from pykorail.device import DeviceProfileLike

# APK의 a.b.a(): 소문자·대문자·숫자 62자 중 4자를 선택합니다.
_NONCE_ALPHABET = string.ascii_letters + string.digits


class RequestSigner:
    """DynaPath 서명이 필요한 요청에 헤더와 ``Sid`` 를 만들어 줍니다.

    엔진 인스턴스를 들고 있으므로 클라이언트당 하나만 두고 재사용하세요 —
    엔진 생성 시각이 서명에 들어갑니다.
    """

    def __init__(
        self,
        profile: DeviceProfileLike | None = None,
        device: str = DEVICE,
        device_id: str | None = None,
        sid_key: bytes = SID_KEY,
    ) -> None:
        self._engine = DynaPathMasterEngine.from_profile(profile)
        self._device = device
        # 명시적 오버라이드는 기존 서명 API를 유지합니다. 외부 프로파일의
        # 선택 필드를 getattr로 읽어 3필드 DeviceProfileLike와도 호환됩니다.
        profile_id = getattr(profile, "android_id", None)
        if device_id is not None:
            self._device_id = device_id
        elif profile_id is not None:
            self._device_id = validate_android_id(profile_id)
        else:
            self._device_id = generate_android_id()
        self._sid_key = sid_key

    @property
    def android_id(self) -> str:
        """이 서명기가 모든 요청에 재사용하는 기기 ID입니다."""
        return self._device_id

    def sign(self, url: str, *, include_sid: bool = True) -> tuple[dict[str, str], str | None]:
        """``url`` 에 필요한 ``(헤더, Sid)`` 를 만듭니다.

        서명 대상이 아닌 경로면 ``({}, None)`` 을 돌려줍니다. Sid를 사용하는
        요청에서는 토큰과 같은 시각으로 생성합니다. 로그인처럼 Sid를 보내지
        않는 호출은 ``include_sid=False`` 로 불필요한 암호화도 생략합니다.
        """
        if not any(path in url for path in DYNAPATH_PATHS):
            return {}, None

        nonce = "".join(random.choices(_NONCE_ALPHABET, k=4))
        token, ts = self._engine.generate_token_with_timestamp(self._device_id, nonce)
        sid = encrypt_sid(self._device, ts, self._sid_key) if include_sid else None
        return {"x-dynapath-m-token": token}, sid
