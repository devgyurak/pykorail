"""리소스 — 엔드포인트를 도메인별로 묶은 API 표면.

:class:`~pykorail.client.AsyncKorail` 이 하나씩 들고 있고, 전부 같은
:class:`~pykorail.api.AsyncApiClient` 를 공유해 세션·서명·로그인 상태를 나눠 씁니다::

    await korail.stations.all()
    await korail.trains.search("서울", "부산")
    await korail.reservations.create(train)
    await korail.tickets.all()
    await korail.membership.mileage()
    await korail.airport_bus.search("광명역", "인천공항T1")
"""

from __future__ import annotations

from pykorail._async.resources.airport_bus import AsyncAirportBusResource
from pykorail._async.resources.base import AsyncResource
from pykorail._async.resources.membership import AsyncMembershipResource
from pykorail._async.resources.reservations import AsyncReservationResource
from pykorail._async.resources.stations import AsyncStationResource
from pykorail._async.resources.tickets import AsyncTicketResource
from pykorail._async.resources.trains import AsyncTrainResource
from pykorail._shared.clock import to_kst

__all__ = [
    "AsyncAirportBusResource",
    "AsyncMembershipResource",
    "AsyncReservationResource",
    "AsyncResource",
    "AsyncStationResource",
    "AsyncTicketResource",
    "AsyncTrainResource",
    "to_kst",
]
