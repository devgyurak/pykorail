"""요청/응답 계층 — 리소스들이 공유하는 저수준 클라이언트.

:class:`~pykorail.client.Korail` 과 각 리소스가 이 객체 하나를 나눠 씁니다.
HTTP 왕복·서명·에러 변환처럼 "어느 리소스에서나 똑같은 일"만 담고, 엔드포인트별
폼 필드는 리소스 쪽에 둡니다.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from pykorail.constants import API_KEY, APP_VERSION, DEVICE
from pykorail.exceptions import AccessRestrictedError, HttpStatusError, TransportError, error_for_code
from pykorail.models.parsing import text

if TYPE_CHECKING:
    from pykorail.auth.signer import RequestSigner
    from pykorail.transport import HttpSession, Response

logger = logging.getLogger(__name__)


@dataclass
class Account:
    """로그인 세션 상태.

    여러 리소스가 읽고(``mbCrdNo``) 로그인만 쓰기 때문에, 클라이언트와 리소스가
    같은 인스턴스를 공유합니다.
    """

    logined: bool = False
    membership_number: str | None = None
    name: str | None = None
    email: str | None = None
    phone_number: str | None = None

    def clear(self) -> None:
        self.logined = False
        self.membership_number = None
        self.name = None
        self.email = None
        self.phone_number = None


#: 실행 환경 검증에 걸렸을 때 오는 이용제한 봉투의 ``code`` (이슈 #27).
ACCESS_RESTRICTED_CODE: Final = "-2000"


class ApiClient:
    """서명·전송·응답 해석을 담당합니다."""

    def __init__(self, session: HttpSession, signer: RequestSigner, verbose: bool = False) -> None:
        self._session = session
        self._signer = signer
        self.verbose = verbose
        self.account = Account()

    # ------------------------------------------------------------------- 전송
    def sign(self, url: str, *, include_sid: bool = True) -> tuple[dict[str, str], str | None]:
        """``url`` 에 필요한 ``(헤더, Sid)``. 서명 대상이 아니면 ``({}, None)``."""
        return self._signer.sign(url, include_sid=include_sid)

    def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return self._parse(self._session.get(url, **_kwargs(params=params, headers=headers)))

    def post(
        self,
        url: str,
        *,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return self._parse(self._session.post(url, **_kwargs(data=data, params=params, headers=headers)))

    def close(self) -> None:
        self._session.close()

    # ------------------------------------------------------------------- 해석
    def base_payload(self) -> dict[str, Any]:
        """거의 모든 요청에 실리는 앱 신원 필드."""
        return {"Device": DEVICE, "Version": APP_VERSION, "Key": API_KEY}

    @staticmethod
    def check(payload: dict[str, Any]) -> None:
        """``strResult=FAIL`` 이면 코드에 맞는 예외를 던집니다."""
        if payload.get("strResult") == "FAIL":
            raise error_for_code(payload.get("h_msg_cd"), payload.get("h_msg_txt"))

    def _parse(self, response: Response) -> dict[str, Any]:
        if self.verbose:
            logger.debug("%s", response.text)
        status = response.status_code
        try:
            parsed = json.loads(response.text)
        except json.JSONDecodeError as exc:
            if status >= 400:
                raise HttpStatusError(status, response.text[:200] or None) from exc
            raise TransportError(f"코레일 응답을 JSON 으로 읽지 못했습니다: {response.text[:200]!r}") from exc
        # 4xx·5xx 라도 코레일 형식(strResult)이면 h_msg_cd 매핑을 그대로 탑니다.
        # 그 밖의 거절 본문(403 이용제한의 code·message 등)을 통과시키면 호출부가
        # strResult 부재를 "비밀번호 오류"·"결과 없음" 으로 읽어 원인이 사라집니다.
        korail_shaped = isinstance(parsed, dict) and "strResult" in parsed
        # 이용제한 봉투(code=-2000)는 상태 코드와 무관하게 거절로 봅니다. 관측된 것은 HTTP 403
        # 응답뿐이고(#27) 200 으로 온 캡처는 없습니다 — 방어적 처리입니다. 같은 봉투가 200 으로
        # 왔을 때 그대로 돌려주면 호출부가 strResult 부재를 "결과 없음"·"비밀번호 오류" 로 읽고,
        # 막힌 채로 같은 요청을 반복하게 됩니다.
        restricted = isinstance(parsed, dict) and not korail_shaped and text(parsed, "code") == ACCESS_RESTRICTED_CODE
        if (status >= 400 and not korail_shaped) or restricted:
            body = parsed if isinstance(parsed, dict) else {}
            error_type = AccessRestrictedError if restricted else HttpStatusError
            # ``id`` 는 요청 추적값일 수 있어 예외 메시지에 싣지 않습니다.
            raise error_type(status, text(body, "message") or None, text(body, "code") or None)
        if not isinstance(parsed, dict):
            raise TransportError(f"코레일 응답이 객체가 아닙니다: {type(parsed).__name__}")
        return parsed


def _kwargs(**candidates: Any) -> dict[str, Any]:
    """``None`` 인 인자를 빼고 넘깁니다.

    ``post(url)`` 과 ``post(url, data=None)`` 은 라이브러리에 따라 다르게 처리될 수
    있어(빈 바디 vs 바디 없음), 앱이 보내는 모양을 유지하려면 아예 안 넘겨야 합니다.
    """
    return {key: value for key, value in candidates.items() if value is not None}
