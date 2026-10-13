"""리소스 — 엔드포인트를 도메인별로 묶은 API 표면.

:class:`~pykorail.client.Korail` 이 하나씩 들고 있고, 전부 같은
:class:`~pykorail.api.ApiClient` 를 공유해 세션·서명·로그인 상태를 나눠 씁니다::

    korail.stations.list()
    korail.trains.search("서울", "부산")
    korail.reservations.create(train)
    korail.tickets.list()
    korail.membership.mileage()
    korail.airport_bus.search("광명역", "인천공항T1")
"""

from __future__ import annotations

from pykorail.resources.airport_bus import AirportBusResource
from pykorail.resources.base import Resource
from pykorail.resources.clock import to_kst
from pykorail.resources.membership import MembershipResource
from pykorail.resources.reservations import ReservationResource
from pykorail.resources.stations import StationResource
from pykorail.resources.tickets import TicketResource
from pykorail.resources.trains import TrainResource

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
