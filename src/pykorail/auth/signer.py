"""요청 서명 — 어떤 경로에 어떤 인증 재료를 붙일지 결정합니다."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from pykorail.auth.dynapath import DeclarationDynaPathEngine
from pykorail.constants import DEVICE, DYNAPATH_LOGIN_OP, DYNAPATH_PATHS, SID_KEY
from pykorail.crypto import encrypt_sid
from pykorail.device.android_id import generate_android_id, validate_android_id

if TYPE_CHECKING:
    from pykorail.auth.dynapath import DynaPathEngine
    from pykorail.device import DeviceProfileLike

#: 모든 요청의 기본 op id. 선언 토큰의 op 는 **엔드포인트별이 아니라 요청 전체에 하나**입니다
#: (로그인·조회 모두 같은 op). 이 엔진은 APK ``a/J0.java`` 의 ``288904575606514493``(ec=
#: 978212327729758430 동반)을 쓰고, 실서버 전체 흐름에서 수용 확인했습니다. 다만 **캡처된 실기기
#: 토큰은 다른 op ``893617653734745139`` 를 썼습니다**(그 봉투엔 ec 없음) — op/ec 는 앱 버전·상태에
#: 따라 다르고, 서버가 지금은 프리픽스만 보므로 어느 쪽이든 통과합니다. 캡처 값으로 맞추는 것은
#: wire 변경이라 별도 결정이 필요합니다(근거: ``docs/protocol-evidence-7.0.10.json``).
_DEFAULT_OP_ID: Final = DYNAPATH_LOGIN_OP
#: 로그인 엔드포인트 URL 조각. 실제 앱은 로그인 선언 토큰에만 request-binding 을 싣습니다
#: (APK ``J0.a``: ``bArr7 = op==288904575606514493 ? bArr : null``). 선언 op 는 모든 경로에서
#: 같으므로, "요청 바인딩" 여부는 op 가 아니라 이 URL 로 가립니다.
_LOGIN_FRAGMENT: Final = "/classes/com.korail.mobile.login.Login"
#: 명시 매핑. 로그인만 특정 URL 로 알려져 있지만 값은 기본 op 와 같습니다(위 설명).
_OP_IDS: Final[dict[str, int]] = {_LOGIN_FRAGMENT: DYNAPATH_LOGIN_OP}


def _op_id_for(url: str) -> int:
    """URL 조각으로 op id 를 고릅니다. 소프트웨어 선언 토큰의 op 는 모든 경로에서 같습니다."""
    return next((op_id for fragment, op_id in _OP_IDS.items() if fragment in url), _DEFAULT_OP_ID)


class RequestSigner:
    """DynaPath 서명이 필요한 요청에 헤더와 ``Sid`` 를 만들어 줍니다.

    기본 엔진 :class:`DeclarationDynaPathEngine` 은 기기 사실(model·release·android_id 등)을
    선언 봉투에 담아 실토큰을 재현합니다 — ``android_id`` 는 ``device_id`` 로 토큰의 ``iid``
    에 실립니다. 엔진은 ``Korail(dynapath_engine=...)`` 로 교체할 수 있습니다.
    """

    def __init__(
        self,
        profile: DeviceProfileLike | None = None,
        device: str = DEVICE,
        device_id: str | None = None,
        sid_key: bytes = SID_KEY,
        *,
        engine: DynaPathEngine | None = None,
    ) -> None:
        # device_id 는 이제 선언 토큰의 iid 로 실리므로(ASCII 16바이트로 인코딩) 유효한
        # android_id 여야 합니다. 명시적 오버라이드도 생성 시점에 검증해, 잘못된 값이
        # 한참 뒤 sign() 에서 날것의 ValueError 로 터지지 않고 여기서 바로 걸리게 합니다.
        # 외부 프로파일의 선택 필드는 getattr로 읽어 3필드 DeviceProfileLike와도 호환됩니다.
        profile_id = getattr(profile, "android_id", None)
        if device_id is not None:
            self._device_id = validate_android_id(device_id)
        elif profile_id is not None:
            self._device_id = validate_android_id(profile_id)
        else:
            self._device_id = generate_android_id()
        # 기본은 순수 파이썬 선언 토큰 엔진(.so 불필요, 실서버 수용 확인). 프로파일이
        # 있으면 model·release·sdk 를 끌어오고, 없으면 현행 플래그십 기본값을 씁니다.
        # 실기기 board·attestation 값을 담은 다른 엔진을 DynaPathEngine 계약으로 주입 가능.
        if engine is not None:
            self._engine: DynaPathEngine = engine
        elif profile is not None:
            self._engine = DeclarationDynaPathEngine.from_profile(profile)
        else:
            self._engine = DeclarationDynaPathEngine()
        self._device = device
        self._sid_key = sid_key

    @property
    def android_id(self) -> str:
        """이 서명기의 기기 ID 입니다. 기본 선언 엔진에서는 토큰의 ``iid`` 로 실립니다."""
        return self._device_id

    def sign(self, url: str, *, include_sid: bool = True) -> tuple[dict[str, str], str | None]:
        """``url`` 에 필요한 ``(헤더, Sid)`` 를 만듭니다.

        서명 대상이 아닌 경로면 ``({}, None)`` 을 돌려줍니다. Sid를 사용하는
        요청에서는 토큰과 같은 시각으로 생성합니다. 로그인처럼 Sid를 보내지
        않는 호출은 ``include_sid=False`` 로 불필요한 암호화도 생략합니다.
        """
        if not any(path in url for path in DYNAPATH_PATHS):
            return {}, None

        op_id = _op_id_for(url)
        # 선언 op 는 모든 경로에서 같으므로 request-binding 여부는 로그인 URL 로 가립니다.
        request_bound = _LOGIN_FRAGMENT in url
        token, ts = self._engine.generate_token_with_timestamp(
            request_bound=request_bound, op_id=op_id, device_id=self._device_id
        )
        sid = encrypt_sid(self._device, ts, self._sid_key) if include_sid else None
        return {"x-dynapath-m-token": token}, sid
