"""리소스 — 엔드포인트를 도메인별로 묶은 API 표면.

동기 클래스는 :mod:`pykorail._sync.resources` 를, ``Async*`` 클래스는
:mod:`pykorail._async.resources` 를 재수출합니다. 둘은 같은 원본에서 나온 짝이라
리소스 이름과 시그니처가 같습니다.
"""

from __future__ import annotations

from pykorail._async.resources import (
    AsyncAirportBusResource,
    AsyncMembershipResource,
    AsyncReservationResource,
    AsyncResource,
    AsyncStationResource,
    AsyncTicketResource,
    AsyncTrainResource,
)
from pykorail._shared.clock import to_kst
from pykorail._sync.resources import (
    AirportBusResource,
    MembershipResource,
    ReservationResource,
    Resource,
    StationResource,
    TicketResource,
    TrainResource,
)

__all__ = [
    "AirportBusResource",
    "AsyncAirportBusResource",
    "AsyncMembershipResource",
    "AsyncReservationResource",
    "AsyncResource",
    "AsyncStationResource",
    "AsyncTicketResource",
    "AsyncTrainResource",
    "MembershipResource",
    "ReservationResource",
    "Resource",
    "StationResource",
    "TicketResource",
    "TrainResource",
    "to_kst",
]
