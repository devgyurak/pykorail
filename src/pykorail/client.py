"""코레일 스마트 예매 클라이언트.

:class:`Korail` 은 세션 수명(로그인·로그아웃·연결)만 책임지고, 실제 엔드포인트는
:mod:`pykorail.resources` 의 리소스들이 나눠 갖습니다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pykorail.api import ApiClient
from pykorail.auth.signer import RequestSigner
from pykorail.constants import (
    API_ENDPOINTS,
    API_KEY,
    APP_DISPLAY_VERSION,
    APP_VERSION,
    DEFAULT_HEADERS,
    DEVICE,
    EMAIL_REGEX,
    HYPHENLESS_PHONE_REGEX,
    PHONE_NUMBER_REGEX,
)
from pykorail.crypto import encrypt_password
from pykorail.device.android_id import validate_android_id
from pykorail.exceptions import LoginFailedError
from pykorail.resources import ReservationResource, StationResource, TicketResource, TrainResource
from pykorail.transport import create_session

if TYPE_CHECKING:
    from types import TracebackType

    from pykorail.device import DeviceProfileLike


class Korail:
    """코레일 스마트 앱 API 를 감싼 동기 클라이언트.

    생성자는 네트워크를 건드리지 않습니다 — 객체를 만드는 일과 로그인하는 일은
    별개입니다. 한 줄로 끝내고 싶으면 :meth:`logged_in` 을 쓰세요::

        with Korail.logged_in("me@example.com", "password") as korail:
            trains = korail.trains.search("서울", "부산")

    또는 명시적으로::

        korail = Korail()
        korail.login("me@example.com", "password")

    ``device_profile`` 은 DynaPath의 기기 ID·모델·OS를 지정합니다.
    User-Agent는 프로파일과 무관하게 ``korailtalk`` 을 사용합니다::

        from pykorail.device import profile_by_id, random_profile

        profile = profile_by_id(saved_id, android_id=saved_android_id) or random_profile()
        # profile.id와 profile.android_id를 함께 저장합니다.
        korail = Korail(device_profile=profile)

    Attributes:
        stations: 역 마스터 조회·검증 (:class:`~pykorail.resources.StationResource`).
        trains: 시간표 조회 (:class:`~pykorail.resources.TrainResource`).
        reservations: 예매·결제·취소 (:class:`~pykorail.resources.ReservationResource`).
        tickets: 승차권 조회·환불 (:class:`~pykorail.resources.TicketResource`).
        android_id: 실제 서명에 쓰는 ID. 저장한 뒤 생성자의 동명 인자로 복원할 수 있습니다.

    Raises:
        ValueError: android_id 형식이 잘못됐거나 프로파일의 ID와 충돌합니다.
    """

    def __init__(
        self,
        verbose: bool = False,
        device_profile: DeviceProfileLike | None = None,
        validate_stations: bool = True,
        *,
        android_id: str | None = None,
    ) -> None:
        if android_id is not None:
            validate_android_id(android_id)
            profile_id = getattr(device_profile, "android_id", None)
            if profile_id is not None and profile_id != android_id:
                raise ValueError("android_id가 device_profile.android_id와 다릅니다")
        # 유효성 오류가 나면 HTTP 세션을 만들지 않습니다.
        signer = RequestSigner(device_profile, device_id=android_id)
        self._android_id = signer.android_id
        headers = dict(DEFAULT_HEADERS)
        self._api = ApiClient(create_session(headers), signer, verbose)
        self._idx: str | None = None
        self.device_profile = device_profile

        self.stations = StationResource(self._api)
        self.trains = TrainResource(self._api, self.stations, validate_stations)
        self.reservations = ReservationResource(self._api)
        self.tickets = TicketResource(self._api)

    @classmethod
    def logged_in(
        cls,
        korail_id: str,
        korail_pw: str,
        *,
        verbose: bool = False,
        device_profile: DeviceProfileLike | None = None,
        validate_stations: bool = True,
        android_id: str | None = None,
    ) -> Korail:
        """클라이언트를 만들고 곧바로 로그인합니다.

        실패하면 연결을 닫고 예외를 다시 올립니다 — 로그인 못 한 클라이언트가
        소켓만 붙든 채 돌아다니면 안 됩니다.

        Raises:
            LoginFailedError: :meth:`login` 이 실패했습니다.
            ValueError: android_id 형식이 잘못됐거나 프로파일의 ID와 충돌합니다.
        """
        korail = cls(
            verbose=verbose, device_profile=device_profile, validate_stations=validate_stations, android_id=android_id
        )
        try:
            korail.login(korail_id, korail_pw)
        except BaseException:
            korail.close()
            raise
        return korail

    # ------------------------------------------------------------- 세션 상태
    @property
    def android_id(self) -> str:
        """프로파일 지정 여부와 무관하게 저장·복원할 수 있는 서명 기기 ID입니다."""
        return self._android_id

    @property
    def verbose(self) -> bool:
        return self._api.verbose

    @verbose.setter
    def verbose(self, value: bool) -> None:
        self._api.verbose = value

    @property
    def logined(self) -> bool:
        return self._api.account.logined

    @property
    def membership_number(self) -> str | None:
        return self._api.account.membership_number

    @property
    def name(self) -> str | None:
        return self._api.account.name

    @property
    def email(self) -> str | None:
        return self._api.account.email

    @property
    def phone_number(self) -> str | None:
        return self._api.account.phone_number

    # ------------------------------------------------------------- 컨텍스트 관리
    def __enter__(self) -> Korail:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """HTTP 연결을 정리합니다. 로그아웃은 하지 않습니다."""
        self._api.close()

    # --------------------------------------------------------------------- 인증
    def _encrypt_password(self, password: str) -> str:
        """서버에서 1회용 암호화 키를 받아 비밀번호를 암호화합니다.

        함께 내려오는 ``idx`` 는 로그인 폼에 되돌려 줘야 하므로 보관합니다.
        """
        payload = self._api.post(API_ENDPOINTS["code"], data={"code": "app.login.cphd"})
        cipher_info = payload.get("app.login.cphd")
        cipher = cipher_info if isinstance(cipher_info, dict) else {}
        idx, key = cipher.get("idx"), cipher.get("key")

        # ``strResult`` 가 SUCC 여도 idx·key 가 빠지거나 빈 값으로 올 수 있습니다.
        # 날로 인덱싱하면 KeyError 가 그대로 새어 나가 "로그인 실패는 전부
        # LoginFailedError" 라는 login() 의 계약이 깨집니다.
        if payload.get("strResult") != "SUCC" or not idx or not key:
            raise LoginFailedError("비밀번호 암호화 키를 발급받지 못했습니다", payload.get("h_msg_cd"))

        # ``idx`` 는 로그인 폼에 문자열로 실려 나갑니다. 서버가 숫자로 내려보내도
        # 폼 인코딩 결과는 같지만, ``_idx`` 의 타입(``str | None``)이 거짓말이
        # 되지 않게 여기서 확정합니다. 형식을 이유로 거부하지는 않습니다 —
        # 관측한 적 없는 형태 하나로 로그인을 통째로 막는 쪽이 더 위험합니다.
        self._idx = str(idx)
        try:
            return encrypt_password(password, key)
        except (AttributeError, TypeError, ValueError) as exc:
            # 키가 문자열이 아니거나 길이가 AES 규격(16·24·32바이트)에 안 맞는 경우.
            # pycryptodome 의 예외를 날것으로 올리면 호출자가 잡을 타입이 없습니다.
            raise LoginFailedError(f"발급받은 암호화 키를 쓸 수 없습니다: {exc}") from exc

    def login(self, korail_id: str, korail_pw: str) -> None:
        """로그인합니다. 실패는 전부 예외입니다 — 성공 여부를 반환하지 않습니다.

        빈 자격증명·암호화 키 발급 실패는 예외인데 비밀번호가
        틀린 것만 ``False`` 를 돌려주던 시절이 있었습니다. 반환값을 확인하지 않은
        호출자는 로그인하지 못한 채로 조회에 들어가 한참 뒤 엉뚱한 ``P058`` 을
        보게 됩니다. 실패 경로를 하나로 모아 그 구멍을 없앱니다.

        Raises:
            LoginFailedError: 아이디/비밀번호가 비었거나,
                암호화 키 발급이 실패했거나, 서버가 자격증명을
                거부했습니다.
            HttpStatusError: 서버가 자격증명을 보기 전에 요청을 거절했습니다 (HTTP
                4xx·5xx, 또는 HTTP 200 이라도 ``code=-2000`` 이용제한 봉투). 비밀번호
                문제가 아닙니다.
        """
        if not korail_id or not korail_pw:
            raise LoginFailedError("아이디와 비밀번호가 필요합니다")

        # 아이디 형태에 따라 서버가 조회할 컬럼이 달라집니다: 5=이메일, 4=휴대폰, 2=회원번호.
        if EMAIL_REGEX.match(korail_id):
            input_flag = "5"
        elif PHONE_NUMBER_REGEX.fullmatch(korail_id) or HYPHENLESS_PHONE_REGEX.fullmatch(korail_id):
            input_flag = "4"
            # 7.0.8 성공 캡처는 하이픈 없는 번호와 휴대폰 구분값을 함께 보냅니다.
            korail_id = korail_id.replace("-", "")
        else:
            input_flag = "2"

        encrypted_pw = self._encrypt_password(korail_pw)

        url = API_ENDPOINTS["login"]
        # 현재 앱은 로그인에 DynaPath 헤더만 싣고 Sid 폼 필드는 보내지 않습니다.
        headers, _ = self._api.sign(url, include_sid=False)
        data = {
            "Device": DEVICE,
            "Version": APP_VERSION,
            "AppVersion": APP_DISPLAY_VERSION,
            "Key": API_KEY,
            "txtInputFlg": input_flag,
            "txtMemberNo": korail_id,
            "txtPwd": encrypted_pw,
            "checkValidPw": "Y",
            "idx": self._idx,
        }
        payload = self._api.post(url, data=data, headers=headers)
        account = self._api.account

        if payload.get("strResult") == "SUCC" and payload.get("strMbCrdNo"):
            # 프로필 필드는 날로 인덱싱하지 않습니다. 서버가 이름·이메일·번호 중
            # 하나를 빼먹으면 ``account.logined = True`` 를 이미 세운 뒤 KeyError 가
            # 터져, 반쯤 갱신된 계정과 "로그인 실패는 전부 LoginFailedError" 라는
            # 계약이 함께 깨집니다. 서버는 SUCC 와 회원번호를 줬고 세션 쿠키도
            # 받았으니 로그인은 성공한 것입니다 — 표시용 필드가 비었다고 실패로
            # 뒤집으면 서버는 로그인 상태인데 클라이언트만 아니라고 우기게 됩니다.
            account.logined = True
            account.membership_number = payload["strMbCrdNo"]
            account.name = payload.get("strCustNm")
            account.email = payload.get("strEmailAdr")
            account.phone_number = payload.get("strCpNo")
            return

        account.clear()
        # 서버가 준 이유를 그대로 전달합니다 — "비밀번호가 틀렸습니다" 와 "휴면
        # 계정입니다" 는 사용자가 해야 할 일이 다른데, 하나로 뭉개면 알 길이 없습니다.
        raise LoginFailedError(
            payload.get("h_msg_txt") or "아이디 또는 비밀번호가 올바르지 않습니다",
            payload.get("h_msg_cd"),
        )

    def logout(self) -> None:
        """서버 로그인 세션을 끊습니다.

        HTTP 연결은 그대로 둡니다 — 로그아웃은 프로토콜 상태이고 연결은 자원이라
        수명이 다릅니다. 같은 클라이언트로 다른 계정에 다시 로그인하려면 연결이
        살아 있어야 합니다. 연결까지 정리하려면 :meth:`close` 를 부르거나
        ``with`` 문을 쓰세요.
        """
        self._api.get(API_ENDPOINTS["logout"])
        self._api.account.clear()
