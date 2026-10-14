"""공유 응답 해석 — 상태 코드·이용제한·코레일 형식 판정.

동기·비동기가 같은 :func:`~pykorail._shared.parse_response` 를 쓰므로 판정은 여기서
한 번만 검증합니다. ``tests/_async/test_api.py`` 에는 이 함수를 거치는 배선만 둡니다.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from pykorail._shared import parse_response
from pykorail.exceptions import AccessRestrictedError, HttpStatusError, TransportError
from tests.payloads import ACCESS_RESTRICTED, STATION_PAYLOAD


def body_of(payload: Any) -> str:
    """가짜 세션처럼 문자열은 그대로, 그 밖의 객체는 JSON 으로 실어 보냅니다."""
    return payload if isinstance(payload, str) else json.dumps(payload)


@pytest.mark.parametrize("code", ["-2000", -2000])
def test_access_restriction_keeps_status_code_and_message(code: object) -> None:
    """403 이용제한을 그대로 실어야 "비밀번호 오류"·"결과 없음" 과 구분됩니다."""
    # given
    body = body_of({**ACCESS_RESTRICTED, "code": code})

    # when
    with pytest.raises(HttpStatusError) as exc:
        parse_response(403, body)

    # then
    assert (exc.value.status_code, exc.value.code, exc.value.msg) == (403, "-2000", ACCESS_RESTRICTED["message"])


@pytest.mark.parametrize("status", [403, 200])
@pytest.mark.parametrize("code", ["-2000", -2000])
def test_access_restriction_has_its_own_type_whatever_the_status(status: int, code: object) -> None:
    """이용제한 봉투가 200 으로 와도 "결과 없음" 으로 흘러가면 막힌 채 계속 두드립니다."""
    # given
    body = body_of({**ACCESS_RESTRICTED, "code": code})

    # when
    with pytest.raises(AccessRestrictedError) as exc:
        parse_response(status, body)

    # then
    assert (exc.value.status_code, exc.value.code) == (status, "-2000")


def test_access_restriction_message_leads_with_the_cause() -> None:
    """200 으로 왔을 때 "HTTP 200" 으로 시작하면 로그만 봐서는 성공한 응답처럼 읽힙니다."""
    # given
    body = body_of(ACCESS_RESTRICTED)

    # when
    with pytest.raises(AccessRestrictedError) as exc:
        parse_response(200, body)

    # then
    assert str(exc.value).startswith("이용제한: ")
    assert "(HTTP 200, -2000)" in str(exc.value)


def test_other_rejections_are_not_access_restrictions() -> None:
    """대기 루프가 이용제한만 골라 멈출 수 있도록 다른 거절과 섞지 않습니다."""
    # when
    with pytest.raises(HttpStatusError) as exc:
        parse_response(502, "<html>502 Bad Gateway</html>")

    # then
    assert not isinstance(exc.value, AccessRestrictedError)


@pytest.mark.parametrize(
    "body",
    [STATION_PAYLOAD, {**ACCESS_RESTRICTED, "code": "-2001"}],
    ids=["station-master", "other-code"],
)
def test_bodies_without_str_result_pass_through_on_200_unless_restricted(body: dict[str, Any]) -> None:
    """판정은 code=-2000 하나로 좁습니다 — strResult 없는 정상 응답이나 다른 코드는 통과합니다."""
    # when
    payload = parse_response(200, body_of(body))

    # then
    assert payload == body


def test_tracking_id_stays_out_of_the_message() -> None:
    """``id`` 는 요청 추적값일 수 있어 로그·트레이스백에 남기지 않습니다."""
    # given
    body = body_of(ACCESS_RESTRICTED)

    # when
    with pytest.raises(HttpStatusError) as exc:
        parse_response(403, body)

    # then
    assert ACCESS_RESTRICTED["id"] not in str(exc.value)


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("<html>502 Bad Gateway</html>", "HTTP 502: <html>502 Bad Gateway</html> (None)"),
        ("", "HTTP 502: 응답 본문 없음 (None)"),
        ("[1, 2]", "HTTP 502: 응답 본문 없음 (None)"),
        ("{}", "HTTP 502: 응답 본문 없음 (None)"),
    ],
)
def test_unrecognized_error_bodies_still_report_the_status(body: str, expected: str) -> None:
    """프록시의 HTML 오류 페이지처럼 JSON 이 아니어도 상태 코드는 남아야 합니다."""
    # when
    with pytest.raises(HttpStatusError) as exc:
        parse_response(502, body)

    # then
    assert str(exc.value) == expected


def test_long_error_body_is_truncated_in_the_message() -> None:
    """본문이 길어도 예외 메시지가 통째로 실리지 않습니다."""
    # when
    with pytest.raises(HttpStatusError) as exc:
        parse_response(502, "x" * 300)

    # then
    assert exc.value.msg == "x" * 200


def test_non_json_success_is_a_plain_transport_error() -> None:
    """200 인데 JSON 이 아니면 서버 거절이 아니라 응답 형식 문제입니다."""
    # when
    with pytest.raises(TransportError) as exc:
        parse_response(200, "not json")

    # then
    assert type(exc.value) is TransportError


def test_non_object_success_is_a_transport_error() -> None:
    """JSON 이지만 객체가 아니면(목록 등) 해석할 필드가 없습니다."""
    # when
    with pytest.raises(TransportError) as exc:
        parse_response(200, "[1, 2]")

    # then
    assert "객체가 아닙니다" in str(exc.value)


def test_korail_shaped_4xx_body_passes_through_for_code_mapping() -> None:
    """4xx 라도 strResult 가 있으면 호출부의 h_msg_cd 매핑이 그대로 돌도록 통과시킵니다."""
    # given
    body = {"strResult": "FAIL", "h_msg_cd": "P058"}

    # when
    payload = parse_response(401, body_of(body))

    # then
    assert payload == body


def test_http_status_error_is_a_transport_error() -> None:
    """기존 ``except TransportError`` 호출부가 새 예외도 잡아야 합니다."""
    # when
    is_transport_error = issubclass(HttpStatusError, TransportError)

    # then
    assert is_transport_error
