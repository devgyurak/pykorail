"""저수준 클라이언트 — 전송 연결과 공유 해석 배선.

응답 판정 자체는 두 계층이 같은 :func:`~pykorail._shared.parse_response` 를 쓰므로
``tests/test_shared_response.py`` 에서 한 번만 검증합니다. 여기에는 ``get``/``post`` 가
그 함수를 거치는지와 ``verbose`` 로그가 **이 계층의 로거**로 나가는지만 둡니다.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from pykorail._async.api import AsyncApiClient
from pykorail.auth.signer import RequestSigner
from pykorail.constants import API_ENDPOINTS
from pykorail.exceptions import AccessRestrictedError, NeedToLoginError
from pykorail.transport import AsyncHttpSession
from tests._async.conftest import AsyncFakeSession, Reply
from tests.payloads import ACCESS_RESTRICTED, STATION_PAYLOAD

URL = API_ENDPOINTS["search_schedule"]


def api_replying(reply: Any, *, verbose: bool = False) -> AsyncApiClient:
    """조회 엔드포인트가 ``reply`` 를 돌려주는 저수준 클라이언트."""
    # AsyncFakeSession.headers 는 평범한 dict 라 프로토콜의 MutableMapping 속성과 불변성이 어긋납니다.
    session = cast(AsyncHttpSession, AsyncFakeSession({"search_schedule": reply}))
    return AsyncApiClient(session, RequestSigner(device_id="fixture-device"), verbose=verbose)


class TestSharedParsingIsWired:
    async def test_get_returns_the_parsed_body(self) -> None:
        # given
        api = api_replying(STATION_PAYLOAD)

        # when
        payload = await api.get(URL)

        # then
        assert payload == STATION_PAYLOAD

    async def test_post_returns_the_parsed_body(self) -> None:
        # given
        api = api_replying(STATION_PAYLOAD)

        # when
        payload = await api.post(URL)

        # then
        assert payload == STATION_PAYLOAD

    async def test_rejection_from_the_shared_parser_surfaces(self) -> None:
        # given
        api = api_replying(Reply(403, ACCESS_RESTRICTED))

        # when & then
        with pytest.raises(AccessRestrictedError):
            await api.post(URL)

    async def test_verbose_logs_the_body_with_this_layers_logger(self, caplog) -> None:
        """verbose 로그는 계층별 로거로 나갑니다 — 동기는 pykorail.api, 그 하위는 별도 이름입니다."""
        # given
        api = api_replying(STATION_PAYLOAD, verbose=True)

        # when
        with caplog.at_level("DEBUG", logger="pykorail.api.async"):
            await api.post(URL)

        # then
        logged = [record.getMessage() for record in caplog.records if record.name == "pykorail.api.async"]
        assert len(logged) == 1
        assert "stn_cd" in logged[0]


class TestCheck:
    async def test_korail_shaped_error_body_keeps_code_mapping(self) -> None:
        """4xx 라도 strResult 가 있으면 기존 h_msg_cd 매핑이 원인을 더 정확히 말합니다."""
        # given
        api = api_replying(Reply(401, {"strResult": "FAIL", "h_msg_cd": "P058"}))
        payload = await api.post(URL)

        # when & then
        with pytest.raises(NeedToLoginError):
            api.check(payload)

    async def test_known_code_still_says_what_the_server_said(self) -> None:
        """타입으로 승격되면서 서버의 안내문이 기본 문구로 바뀌면 원인이 사라집니다."""
        # given
        said = "로그아웃되었습니다. 다시 로그인하여 주십시오."
        api = api_replying({"strResult": "FAIL", "h_msg_cd": "P058", "h_msg_txt": said})
        payload = await api.post(URL)

        # when
        with pytest.raises(NeedToLoginError) as exc:
            api.check(payload)

        # then
        assert (exc.value.msg, exc.value.code) == (said, "P058")
