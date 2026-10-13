"""결제 전 예약."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from pykorail.models.parsing import hhmm, integer, text
from pykorail.models.schedule import Train

if TYPE_CHECKING:
    from typing import Self

    from pykorail.models.seat import Seat

_WAITING_BUY_LIMIT_DATE = "00000000"
_WAITING_BUY_LIMIT_TIME = "235959"


@dataclass(frozen=True)
class Reservation:
    """아직 결제하지 않은 예약. 구입기한을 넘기면 자동 취소됩니다.

    예약은 열차가 *아니라* 열차를 **참조**합니다 — ``reservation.train.dep_name``
    처럼 쓰세요. 좌석 상세(:attr:`seats`, :attr:`wct_no`)는 생성 시점에 이미 채워져
    있습니다. 반쯤 채워진 예약은 존재하지 않습니다.

    환승 예약은 예약번호 하나에 구간이 둘이라 이 객체가 구간마다 하나씩 생깁니다.
    그때 :attr:`price` 는 그 구간의 금액이 아니라 **예약 전체의 금액**입니다(서버가 두
    항목에 같은 값을 싣습니다). 구간별 금액은 :attr:`seats` 의 좌석 금액에 있습니다.
    """

    train: Train
    rsv_id: str
    seat_no_count: int
    buy_limit_date: str
    buy_limit_time: str
    price: int

    # 취소 요청에 실어 보내는 여정 식별자. 여정이 하나인 보통 예약은 예전부터 쓰던 고정값이고,
    # 환승 예약처럼 여정이 여럿이면 서버가 준 값(첫 여정의 순번 · 여정 수 · 변경번호)입니다 —
    # 고정값으로는 서버가 취소를 거절합니다.
    journey_no: str
    journey_cnt: str
    rsv_chg_no: str

    #: 배정된 좌석들.
    seats: tuple[Seat, ...] = ()
    #: 발매창구 번호. 좌석 상세 조회에서 함께 옵니다.
    wct_no: str | None = None

    @classmethod
    def from_response(
        cls,
        data: dict[str, Any],
        *,
        seats: tuple[Seat, ...] = (),
        wct_no: str | None = None,
        journey_no: str | None = None,
        journey_cnt: str | None = None,
        rsv_chg_no: str | None = None,
    ) -> Self:
        # 예약 응답에는 출발·도착일이 따로 오지 않고 운행일 하나만 옵니다.
        train = Train.from_response(data)
        train = replace(train, dep_date=train.run_date, arr_date=train.run_date)

        return cls(
            train=train,
            rsv_id=text(data, "h_pnr_no"),
            seat_no_count=integer(data, "h_tot_seat_cnt"),
            buy_limit_date=text(data, "h_ntisu_lmt_dt"),
            buy_limit_time=text(data, "h_ntisu_lmt_tm"),
            price=integer(data, "h_rsv_amt"),
            journey_no=journey_no or text(data, "txtJrnySqno", "001"),
            journey_cnt=journey_cnt or text(data, "txtJrnyCnt", "01"),
            rsv_chg_no=rsv_chg_no or text(data, "hidRsvChgNo", "00000"),
            seats=seats,
            wct_no=wct_no,
        )

    @property
    def is_waiting(self) -> bool:
        """실좌석이 아니라 예약대기입니다 — 구입기한이 채워지지 않습니다."""
        return self.buy_limit_date == _WAITING_BUY_LIMIT_DATE or self.buy_limit_time == _WAITING_BUY_LIMIT_TIME

    def __repr__(self) -> str:
        repr_str = f"{self.train!r}, {self.price}원({self.seat_no_count}석)"
        if self.is_waiting:
            return f"{repr_str}, 예약대기"

        limit_date = self.buy_limit_date
        if len(limit_date) >= 8 and limit_date.isdigit():
            limit_date = f"{int(limit_date[4:6])}월 {int(limit_date[6:8])}일"
        return f"{repr_str}, 구입기한 {limit_date} {hhmm(self.buy_limit_time)}"
