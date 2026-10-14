# 이 파일은 생성물입니다 — 직접 고치지 마세요.
# 원본: src/pykorail/_async/api.py
# 다시 만들려면: uv run python scripts/unasync.py
"""요청/응답 계층 — 리소스들이 공유하는 저수준 클라이언트.

:class:`~pykorail.client.Korail` 과 각 리소스가 이 객체 하나를 나눠 씁니다.
HTTP 왕복·서명·에러 변환처럼 "어느 리소스에서나 똑같은 일"만 담고, 엔드포인트별
폼 필드는 리소스 쪽에 둡니다.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pykorail._shared.account import Account
from pykorail._shared.response import parse_response
from pykorail.constants import API_KEY, APP_DISPLAY_VERSION, APP_VERSION, DEVICE
from pykorail.exceptions import error_for_code

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pykorail.auth.signer import RequestSigner
    from pykorail.transport import HttpSession, Response

logger = logging.getLogger("pykorail.api")


class ApiClient:
    """서명·전송·응답 해석을 담당합니다."""

    def __init__(self, session: HttpSession, signer: RequestSigner, verbose: bool = False) -> None:
        self._session = session
        self._signer = signer
        self.verbose = verbose
        self.account = Account()
        self._closed = False

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
        data: dict[str, Any] | Sequence[tuple[str, Any]] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """폼 본문으로 POST 합니다.

        ``data`` 는 보통 dict 입니다. 같은 이름의 필드를 여러 번 실어야 할 때만
        ``(이름, 값)`` 쌍의 목록으로 넘깁니다 — dict 의 값에 목록을 넣으면 curl_cffi 가
        그것을 반복 필드가 아니라 문자열 하나로 인코딩합니다.
        """
        return self._parse(self._session.post(url, **_kwargs(data=data, params=params, headers=headers)))

    def close(self) -> None:
        # close() 를 두 번 불러도 안전하게 합니다. ``with`` 블록 안에서 직접 close() 를
        # 부르면 블록을 나갈 때 __exit__ 이 한 번 더 닫습니다 — curl_cffi 의 세션은 그때
        # TypeError 를 낼 수 있습니다.
        if self._closed:
            return
        self._closed = True
        self._session.close()

    # ------------------------------------------------------------------- 해석
    def base_payload(self) -> dict[str, Any]:
        """거의 모든 요청에 실리는 앱 신원 필드."""
        return {"Device": DEVICE, "Version": APP_VERSION, "Key": API_KEY}

    def common_payload(self) -> dict[str, Any]:
        """7.0.8 요청 모델의 공통 필드 — :meth:`base_payload` 에 ``AppVersion`` 이 더해진 것.

        7.0.8 에서 새로 확인한 엔드포인트는 요청 모델이 이 네 필드로 시작합니다
        (선언 순서 그대로). 기존 엔드포인트의 폼은 건드리지 않으려고 따로 둡니다.
        """
        return {"Device": DEVICE, "Version": APP_VERSION, "AppVersion": APP_DISPLAY_VERSION, "Key": API_KEY}

    @staticmethod
    def check(payload: dict[str, Any]) -> None:
        """``strResult=FAIL`` 이면 코드에 맞는 예외를 던집니다."""
        if payload.get("strResult") == "FAIL":
            raise error_for_code(payload.get("h_msg_cd"), payload.get("h_msg_txt"))

    def _parse(self, response: Response) -> dict[str, Any]:
        if self.verbose:
            logger.debug("%s", response.text)
        return parse_response(response.status_code, response.text)


def _kwargs(**candidates: Any) -> dict[str, Any]:
    """``None`` 인자를 빼고 넘깁니다.

    ``post(url)`` 과 ``post(url, data=None)`` 은 라이브러리에 따라 다르게 처리될 수
    있어(빈 바디 vs 바디 없음), 앱이 보내는 모양을 유지하려면 아예 안 넘겨야 합니다.
    """
    return {key: value for key, value in candidates.items() if value is not None}
