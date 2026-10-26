"""호차와 그 안의 좌석 — 좌석을 고르기 위한 조회 결과.

예약이 끝난 뒤의 배정 좌석(:class:`~pykorail.models.seat.Seat`)과는 다른 것입니다.
여기 있는 것은 **아직 팔리지 않았을 수도 있는** 열차의 좌석 배치입니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pykorail.models.parsing import integer, records, text

if TYPE_CHECKING:
    from typing import Self

#: ``sale_psb_flg`` 가 이 값이면 살 수 있는 좌석입니다.
_SELLABLE = "Y"


@dataclass(frozen=True)
class SeatAttribute:
    """호차에서 고를 수 있는 좌석 속성 하나 (순방향 · 창측 등)."""

    code: str
    name: str

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> Self:
        return cls(code=text(data, "seatAttCd"), name=text(data, "seatAttNm"))


@dataclass(frozen=True)
class Car:
    """열차의 호차 하나.

    ``car_no`` 는 서버가 준 문자열 그대로입니다(``"0003"``). 좌석 조회에 그대로
    돌려보내는 값이라 숫자로 바꾸지 않습니다 — 배정 좌석의 ``Seat.car_no`` 와 같습니다.
    """

    car_no: str
    seat_class: str
    seat_class_name: str
    seat_count: int
    remaining_seats: int
    attributes: tuple[SeatAttribute, ...] = ()

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> Self:
        return cls(
            car_no=text(data, "h_srcar_no"),
            seat_class=text(data, "h_psrm_cl_cd"),
            seat_class_name=text(data, "h_psrm_cl_nm"),
            seat_count=integer(data, "h_seat_cnt"),
            remaining_seats=integer(data, "h_rest_seat_cnt"),
            attributes=tuple(SeatAttribute.from_response(item) for item in records(data, "seatAttInfos")),
        )

    def has_seat(self) -> bool:
        return self.remaining_seats > 0


@dataclass(frozen=True)
class CarSeat:
    """호차 안의 좌석 하나.

    좌석을 가리킬 때는 화면 표시용 ``label`` 이 아니라 식별자 ``seat_no`` 를 씁니다.
    """

    car_no: str
    #: 이 좌석을 조회한 객실 구분 코드. 좌석 응답에는 없고 조회 조건에서 옵니다 —
    #: 좌석을 지정해 예매할 때 어느 객실인지 다시 묻지 않으려고 좌석에 붙여 둡니다.
    seat_class: str
    seat_no: str
    label: str
    sale_flag: str
    direction: str
    attribute: str
    extra_attribute: str
    message: str

    @classmethod
    def from_response(cls, data: dict[str, Any], *, car_no: str, seat_class: str) -> Self:
        return cls(
            car_no=car_no,
            seat_class=seat_class,
            seat_no=text(data, "seat_no"),
            label=text(data, "seat_spec"),
            sale_flag=text(data, "sale_psb_flg"),
            direction=text(data, "dir_seat_att_cd"),
            attribute=text(data, "rq_seat_att_cd"),
            extra_attribute=text(data, "etc_seat_att_cd"),
            message=text(data, "intg_msg"),
        )

    @property
    def is_available(self) -> bool:
        """지금 살 수 있는 좌석인지."""
        return self.sale_flag == _SELLABLE
