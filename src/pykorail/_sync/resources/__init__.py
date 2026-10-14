# 이 파일은 생성물입니다 — 직접 고치지 마세요.
# 원본: src/pykorail/_async/resources/__init__.py
# 다시 만들려면: uv run python scripts/unasync.py
"""리소스 — 엔드포인트를 도메인별로 묶은 API 표면.

:class:`~pykorail.Korail` 이 하나씩 들고 있고, 전부 같은
:class:`~pykorail.api.ApiClient` 를 공유해 세션·서명·로그인 상태를 나눠 씁니다::

    korail.stations.all()
    korail.trains.search("서울", "부산")
    korail.reservations.create(train)
    korail.tickets.all()
    korail.membership.mileage()
    korail.airport_bus.search("광명역", "인천공항T1")
"""

from __future__ import annotations

from pykorail._shared.clock import to_kst
from pykorail._sync.resources.airport_bus import AirportBusResource
from pykorail._sync.resources.base import Resource
from pykorail._sync.resources.membership import MembershipResource
from pykorail._sync.resources.reservations import ReservationResource
from pykorail._sync.resources.stations import StationResource
from pykorail._sync.resources.tickets import TicketResource
from pykorail._sync.resources.trains import TrainResource

__all__ = [
    "AirportBusResource",
    "MembershipResource",
    "ReservationResource",
    "Resource",
    "StationResource",
    "TicketResource",
    "TrainResource",
    "to_kst",
]
