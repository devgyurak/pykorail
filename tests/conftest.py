"""가짜 HTTP 세션 — 네트워크 없이 리소스를 돌립니다."""

from __future__ import annotations

import json
from typing import Any

import pytest

from pykorail.client import Korail
from pykorail.constants import API_ENDPOINTS
from tests.payloads import (
    OK,
    REFUND_FEE_PAYLOAD,
    RESERVATION_LIST_PAYLOAD,
    SEARCH_PAYLOAD,
    SEAT_DETAIL_PAYLOAD,
    STATION_PAYLOAD,
    TICKET_LIST_PAYLOAD,
    TICKET_SEAT_PAYLOAD,
)


class FakeResponse:
    def __init__(self, payload: Any) -> None:
        self.text = json.dumps(payload)


class FakeSession:
    """호출을 기록하고 엔드포인트별로 미리 정해 둔 응답을 돌려줍니다."""

    def __init__(self, routes: dict[str, Any]) -> None:
        self.headers: dict[str, str] = {}
        self.routes = routes
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.closed = False

    def _respond(self, method: str, url: str, kwargs: dict[str, Any]) -> FakeResponse:
        self.calls.append((method, url, kwargs))
        for endpoint, payload in self.routes.items():
            if url == API_ENDPOINTS[endpoint]:
                return FakeResponse(payload)
        raise AssertionError(f"예상하지 못한 요청: {url}")

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        return self._respond("GET", url, kwargs)

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        return self._respond("POST", url, kwargs)

    def close(self) -> None:
        self.closed = True

    # ------------------------------------------------------------------ 헬퍼
    def urls(self) -> list[str]:
        return [url for _, url, _ in self.calls]

    def kwargs_for(self, endpoint: str) -> dict[str, Any]:
        """해당 엔드포인트로 나간 **마지막** 요청의 인자."""
        url = API_ENDPOINTS[endpoint]
        return next(kwargs for _, called, kwargs in reversed(self.calls) if called == url)

    def all_kwargs_for(self, endpoint: str) -> list[dict[str, Any]]:
        """해당 엔드포인트로 나간 **모든** 요청의 인자를 보낸 순서대로.

        호출 횟수만 세면 같은 대상을 N번 조회해도 통과합니다 — 무엇을 조회했는지
        확인하려면 요청 하나하나가 필요합니다.
        """
        url = API_ENDPOINTS[endpoint]
        return [kwargs for _, called, kwargs in self.calls if called == url]


@pytest.fixture
def make_korail(monkeypatch: pytest.MonkeyPatch):
    """지정한 라우트를 갖는 클라이언트와 그 가짜 세션을 만듭니다."""

    def factory(routes: dict[str, Any], **kwargs: Any) -> tuple[Korail, FakeSession]:
        session = FakeSession(routes)
        monkeypatch.setattr("pykorail.client.create_session", lambda headers: session)
        return Korail(**kwargs), session

    return factory


@pytest.fixture
def korail(make_korail) -> tuple[Korail, FakeSession]:
    """대부분의 엔드포인트가 성공 응답을 주는 기본 클라이언트."""
    return make_korail(
        {
            "stationdata": STATION_PAYLOAD,
            "search_schedule": SEARCH_PAYLOAD,
            "myreservationview": RESERVATION_LIST_PAYLOAD,
            "myreservationlist": SEAT_DETAIL_PAYLOAD,
            "myticketlist": TICKET_LIST_PAYLOAD,
            "myticketseat": TICKET_SEAT_PAYLOAD,
            "reserve": {**OK, "h_pnr_no": "1234567890"},
            "cancel": OK,
            "pay": OK,
            "refund": OK,
            "refund_commission": REFUND_FEE_PAYLOAD,
            "logout": OK,
        }
    )
