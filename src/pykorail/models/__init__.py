"""응답 모델과 요청 파라미터 객체.

응답 모델(:class:`Schedule`·:class:`Train`·:class:`Ticket`·:class:`Reservation`·
:class:`Seat`·:class:`Station`)은 모두 **불변 데이터클래스**이고 ``from_response``
클래스메서드로만 만듭니다. 생성자는 값 조립, 응답 해석은 ``from_response`` 로
일관되게 갈라져 있습니다.

:class:`Ticket` 과 :class:`Reservation` 은 열차를 **상속하지 않고 참조**합니다
(``ticket.train.dep_name``). 예약이 ``has_seat()`` 같은 메서드를 물려받는 건
말이 안 되기 때문입니다.
"""

from __future__ import annotations

from pykorail.models.card import Card
from pykorail.models.passenger import (
    AdultPassenger,
    ChildPassenger,
    Disability1To3Passenger,
    Disability4To6Passenger,
    Passenger,
    SeniorPassenger,
    ToddlerPassenger,
)
from pykorail.models.refund import RefundFee
from pykorail.models.reservation import Reservation
from pykorail.models.schedule import Schedule, Train
from pykorail.models.seat import Seat
from pykorail.models.station import Station, parse_stations
from pykorail.models.ticket import Ticket, train_info_of

__all__ = [
    "AdultPassenger",
    "Card",
    "ChildPassenger",
    "Disability1To3Passenger",
    "Disability4To6Passenger",
    "Passenger",
    "RefundFee",
    "Reservation",
    "Schedule",
    "Seat",
    "SeniorPassenger",
    "Station",
    "Ticket",
    "ToddlerPassenger",
    "Train",
    "parse_stations",
    "train_info_of",
]
