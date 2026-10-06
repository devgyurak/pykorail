"""응답 해석 — HTTP 상태 코드와 코레일 응답 형식을 함께 봅니다."""

from __future__ import annotations

from typing import Any, cast

import pytest

from pykorail.api import ApiClient
from pykorail.auth.signer import RequestSigner
from pykorail.constants import API_ENDPOINTS
from pykorail.exceptions import HttpStatusError, NeedToLoginError, TransportError
from pykorail.transport import HttpSession
from tests.conftest import FakeSession, Reply
from tests.payloads import ACCESS_RESTRICTED

URL = API_ENDPOINTS["search_schedule"]


def api_replying(reply: Any) -> ApiClient:
    """조회 엔드포인트가 ``reply`` 를 돌려주는 저수준 클라이언트."""
    # FakeSession.headers 는 평범한 dict 라 프로토콜의 MutableMapping 속성과 불변성이 어긋납니다.
    session = cast(HttpSession, FakeSession({"search_schedule": reply}))
    return ApiClient(session, RequestSigner(device_id="fixture-device"))


class TestHttpStatus:
    @pytest.mark.parametrize("code", ["-2000", -2000])
    def test_access_restriction_keeps_status_code_and_message(self, code: object) -> None:
        """403 이용제한을 그대로 실어야 "비밀번호 오류"·"결과 없음" 과 구분됩니다."""
        # given
        api = api_replying(Reply(403, {**ACCESS_RESTRICTED, "code": code}))

        # when
        with pytest.raises(HttpStatusError) as exc:
            api.post(URL)

        # then
        assert (exc.value.status_code, exc.value.code, exc.value.msg) == (403, "-2000", ACCESS_RESTRICTED["message"])

    @pytest.mark.parametrize("code", ["-2000", -2000])
    def test_access_restriction_on_200_is_still_rejected(self, code: object) -> None:
        """이용제한 봉투가 200 으로 와도 "결과 없음" 으로 흘러가면 막힌 채 계속 두드립니다."""
        # given
        api = api_replying(Reply(200, {**ACCESS_RESTRICTED, "code": code}))

        # when
        with pytest.raises(HttpStatusError) as exc:
            api.post(URL)

        # then
        assert (exc.value.status_code, exc.value.code) == (200, "-2000")

    def test_other_bodies_without_str_result_pass_through_on_200(self) -> None:
        """역 마스터처럼 strResult 없이 오는 정상 응답은 막지 않습니다."""
        # given
        api = api_replying(Reply(200, {"stns": {"stn": []}}))

        # when
        payload = api.post(URL)

        # then
        assert payload == {"stns": {"stn": []}}

    def test_tracking_id_stays_out_of_the_message(self) -> None:
        """``id`` 는 요청 추적값일 수 있어 로그·트레이스백에 남기지 않습니다."""
        # given
        api = api_replying(Reply(403, ACCESS_RESTRICTED))

        # when
        with pytest.raises(HttpStatusError) as exc:
            api.post(URL)

        # then
        assert ACCESS_RESTRICTED["id"] not in str(exc.value)

    @pytest.mark.parametrize(
        ("body", "expected"),
        [
            ("<html>502 Bad Gateway</html>", "HTTP 502: <html>502 Bad Gateway</html> (None)"),
            ("", "HTTP 502: 응답 본문 없음 (None)"),
            ([1, 2], "HTTP 502: 응답 본문 없음 (None)"),
            ({}, "HTTP 502: 응답 본문 없음 (None)"),
        ],
    )
    def test_unrecognized_error_bodies_still_report_the_status(self, body: object, expected: str) -> None:
        """프록시의 HTML 오류 페이지처럼 JSON 이 아니어도 상태 코드는 남아야 합니다."""
        # given
        api = api_replying(Reply(502, body))

        # when
        with pytest.raises(HttpStatusError) as exc:
            api.post(URL)

        # then
        assert str(exc.value) == expected

    def test_korail_shaped_error_body_keeps_code_mapping(self) -> None:
        """4xx 라도 strResult 가 있으면 기존 h_msg_cd 매핑이 원인을 더 정확히 말합니다."""
        # given
        api = api_replying(Reply(401, {"strResult": "FAIL", "h_msg_cd": "P058"}))
        payload = api.post(URL)

        # when & then
        with pytest.raises(NeedToLoginError):
            api.check(payload)

    def test_non_json_success_is_a_plain_transport_error(self) -> None:
        """200 인데 JSON 이 아니면 서버 거절이 아니라 응답 형식 문제입니다."""
        # given
        api = api_replying(Reply(200, "not json"))

        # when
        with pytest.raises(TransportError) as exc:
            api.post(URL)

        # then
        assert type(exc.value) is TransportError

    def test_http_status_error_is_a_transport_error(self) -> None:
        """기존 ``except TransportError`` 호출부가 새 예외도 잡아야 합니다."""
        # when
        is_transport_error = issubclass(HttpStatusError, TransportError)

        # then
        assert is_transport_error
