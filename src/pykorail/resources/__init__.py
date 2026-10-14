"""동기 리소스 재수출. 실제 구현은 :mod:`pykorail._sync.resources` 에 있습니다."""

from __future__ import annotations

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
    "MembershipResource",
    "ReservationResource",
    "Resource",
    "StationResource",
    "TicketResource",
    "TrainResource",
    "to_kst",
]
