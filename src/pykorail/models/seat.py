"""좌석 한 자리."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pykorail._shared.deprecation import renamed
from pykorail.models.parsing import integer, text

if TYPE_CHECKING:
    from typing import Self


@dataclass(frozen=True)
class Seat:
    """예약·승차권에 딸린 좌석 하나.

    좌석번호가 비어 있으면 실좌석이 아니라 예약대기 자리입니다.
    """

    car_no: str
    seat_no: str
    seat_class_name: str
    passenger_type_name: str
    price: int
    original_price: int
    discount: int

    # 옛 이름(0.6.0 까지). 0.7.0 에서 지웁니다.
    car = renamed("car", "car_no")
    seat = renamed("seat", "seat_no")
    seat_type = renamed("seat_type", "seat_class_name")
    passenger_type = renamed("passenger_type", "passenger_type_name")

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> Self:
        return cls(
            car_no=text(data, "h_srcar_no"),
            seat_no=text(data, "h_seat_no"),
            seat_class_name=text(data, "h_psrm_cl_nm"),
            passenger_type_name=text(data, "h_psg_tp_dv_nm"),
            price=integer(data, "h_rcvd_amt"),
            original_price=integer(data, "h_seat_prc"),
            discount=integer(data, "h_dcnt_amt"),
        )

    @property
    def is_waiting(self) -> bool:
        return self.seat_no == ""

    def __repr__(self) -> str:
        price = f"[{self.price}원({self.discount}원 할인)]"
        if self.is_waiting:
            return f"예약대기 ({self.seat_class_name}) {self.passenger_type_name}{price}"
        return f"{self.car_no}호차 {self.seat_no} ({self.seat_class_name}) {self.passenger_type_name} {price}"
