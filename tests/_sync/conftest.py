# 이 파일은 생성물입니다 — 직접 고치지 마세요.
# 원본: tests/_async/conftest.py
# 다시 만들려면: uv run python scripts/unasync.py
"""가짜 비동기 HTTP 세션 — 네트워크 없이 리소스를 돌립니다.

``tests/_sync/conftest.py`` 는 이 파일에서 생성됩니다(``scripts/unasync.py``).
동기 쪽 가짜 세션을 고치려면 여기를 고치고 스크립트를 돌리세요.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from pykorail._sync import client as client_module
from pykorail._sync.client import Korail
from pykorail.constants import API_ENDPOINTS
from tests.payloads import (
    FARE_PAYLOAD,
    OK,
    REFUND_FEE_PAYLOAD,
    RESERVATION_LIST_PAYLOAD,
    SEARCH_PAYLOAD,
    SEAT_CARS_PAYLOAD,
    SEAT_DETAIL_PAYLOAD,
    SEAT_MAP_PAYLOAD,
    STATION_PAYLOAD,
    TICKET_LIST_PAYLOAD,
    TICKET_SEAT_PAYLOAD,
    TRANSFER_STATIONS_PAYLOAD,
)


@dataclass(frozen=True)
class Reply:
    """상태 코드나 원문 본문을 지정해야 하는 라우트 응답.

    ``body`` 가 ``str`` 이면 그대로, 아니면 JSON 으로 실립니다. 라우트에 dict 만
    두면 HTTP 200 JSON 응답입니다.
    """

    status_code: int
    body: Any


class Replies:
    """요청마다 다음 응답을 차례로 돌려주는 라우트. 다 쓰면 마지막 응답을 되풀이합니다.

    같은 엔드포인트를 여러 번 부르면서 응답이 달라져야 하는 흐름(조회 결과 이어 받기)에
    씁니다. 라우트에 응답 하나만 두면 몇 번을 불러도 같은 응답입니다.
    """

    def __init__(self, *payloads: Any) -> None:
        self._payloads = payloads
        self._served = 0

    def take(self) -> Any:
        payload = self._payloads[min(self._served, len(self._payloads) - 1)]
        self._served += 1
        return payload


class FakeResponse:
    def __init__(self, payload: Any) -> None:
        reply = payload if isinstance(payload, Reply) else Reply(200, payload)
        self.status_code = reply.status_code
        self.text = reply.body if isinstance(reply.body, str) else json.dumps(reply.body)


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
                return FakeResponse(payload.take() if isinstance(payload, Replies) else payload)
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
        monkeypatch.setattr(client_module, "create_session", lambda headers: session)
        return Korail(**kwargs), session

    return factory


@pytest.fixture
def korail(make_korail) -> tuple[Korail, FakeSession]:
    """대부분의 엔드포인트가 성공 응답을 주는 기본 클라이언트."""
    return make_korail(
        {
            "stationdata": STATION_PAYLOAD,
            "search_schedule": SEARCH_PAYLOAD,
            "seat_cars": SEAT_CARS_PAYLOAD,
            "seat_map": SEAT_MAP_PAYLOAD,
            "fare": FARE_PAYLOAD,
            "transfer_stations": TRANSFER_STATIONS_PAYLOAD,
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
