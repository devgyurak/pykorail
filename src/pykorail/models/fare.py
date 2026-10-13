"""예매 전 운임 — 열차를 예약하기 전에 미리 보는 기준 운임."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pykorail.models.parsing import amount, text

if TYPE_CHECKING:
    from typing import Self


@dataclass(frozen=True)
class Fare:
    """한 구간 · 한 객실의 운임.

    **결제 금액이 아닙니다.** 할인 전의 기준 운임이고, 실제로 낼 금액은 예약한 뒤
    :attr:`Reservation.price <pykorail.models.reservation.Reservation.price>` 에 있습니다.
    """

    train_no: str
    #: 여정 안의 구간 번호 (``jrnySqno``, ``"0001"`` 부터). 환승 여정은 구간마다 줄이 나뉩니다.
    journey_no: str
    #: 객실 이름 (``psrmClNm``). 열차에 따라 다릅니다 — ``"특실"`` 자리에 ``"우등실"`` 이 오기도 합니다.
    seat_class_name: str
    #: 운임 (``rcvdPrc``). 객실과 무관하게 같습니다. ``Reservation.price``(결제 예정 금액)와
    #: 이름만 같고 다른 값입니다.
    price: int
    #: 요금 (``rcvdFare``). 특실 · 우등실에 붙는 금액이고 일반실은 0 입니다.
    charge: int
    #: 합계 (``sumAmt``) — 운임에 요금을 더한 이 객실의 기준 금액.
    total: int

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> Self:
        return cls(
            train_no=text(data, "trnNo"),
            journey_no=text(data, "jrnySqno"),
            seat_class_name=text(data, "psrmClNm"),
            price=amount(data, "rcvdPrc"),
            charge=amount(data, "rcvdFare"),
            total=amount(data, "sumAmt"),
        )
