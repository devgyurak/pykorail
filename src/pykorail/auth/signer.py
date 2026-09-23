"""요청 서명 — 어떤 경로에 어떤 인증 재료를 붙일지 결정합니다."""

from __future__ import annotations

import random
import string
from typing import TYPE_CHECKING

from pykorail.auth.dynapath import DynaPathMasterEngine
from pykorail.constants import DEVICE, DEVICE_ID, DYNAPATH_PATHS, SID_KEY
from pykorail.crypto import encrypt_sid

if TYPE_CHECKING:
    from pykorail.device import DeviceProfileLike

_NONCE_ALPHABET = string.ascii_uppercase + string.digits


class RequestSigner:
    """DynaPath 서명이 필요한 요청에 헤더와 ``Sid`` 를 만들어 줍니다.

    엔진 인스턴스를 들고 있으므로 클라이언트당 하나만 두고 재사용하세요 —
    엔진 생성 시각이 서명에 들어갑니다.
    """

    def __init__(
        self,
        profile: DeviceProfileLike | None = None,
        device: str = DEVICE,
        device_id: str = DEVICE_ID,
        sid_key: bytes = SID_KEY,
    ) -> None:
        self._engine = DynaPathMasterEngine.from_profile(profile)
        self._device = device
        self._device_id = device_id
        self._sid_key = sid_key

    def sign(self, url: str) -> tuple[dict[str, str], str | None]:
        """``url`` 에 필요한 ``(헤더, Sid)`` 를 만듭니다.

        서명 대상이 아닌 경로면 ``({}, None)`` 을 돌려줍니다. 토큰과 ``Sid`` 는
        같은 타임스탬프로 만들어야 서버가 짝을 맞춰 검증할 수 있습니다.
        """
        if not any(path in url for path in DYNAPATH_PATHS):
            return {}, None

        nonce = "".join(random.choices(_NONCE_ALPHABET, k=4))
        token, ts = self._engine.generate_token_with_timestamp(self._device_id, nonce)
        return {"x-dynapath-m-token": token}, encrypt_sid(self._device, ts, self._sid_key)
