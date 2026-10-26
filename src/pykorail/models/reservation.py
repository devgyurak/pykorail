"""결제 전 예약."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, NamedTuple

from pykorail.models.parsing import hhmm, integer, kst_date, kst_datetime, text
from pykorail.models.schedule import Train

if TYPE_CHECKING:
    from typing import Self

    from pykorail.models.seat import Seat

_WAITING_BUY_LIMIT_DATE = "00000000"
_WAITING_BUY_LIMIT_TIME = "235959"

#: 여정이 하나인 보통 예약의 취소 요청에 실리는 고정 식별자. 응답에는 이 이름들이 오지
#: 않습니다 — ``txtJrnySqno`` · ``txtJrnyCnt`` · ``hidRsvChgNo`` 는 **요청 폼** 필드 이름이라,
#: 예전에 응답에서 읽던 값은 늘 이 기본값이었습니다. 여정이 여럿인 환승 예약은 리소스가
#: 서버가 준 값으로 덮어씁니다(고정값으로는 서버가 취소를 거절합니다).
_SINGLE_JOURNEY_NO = "001"
_SINGLE_JOURNEY_CNT = "01"
_SINGLE_JOURNEY_CHG_NO = "00000"

#: 시각만 비교할 때 쓰는 임의의 날짜. 날짜는 버리고 시각의 앞뒤만 봅니다.
_ANY_DAY = "20000101"


class SeatDetail(NamedTuple):
    """예약의 좌석 상세 — 좌석 목록과 발매창구 번호.

    튜플이라 ``seats, wct_no = korail.reservations.seats(...)`` 처럼 풀어 써도 됩니다.
    """

    seats: list[Seat]
    wct_no: str | None


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
    pnr_no: str
    seat_count: int
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
        dep_date: str | None = None,
        arr_date: str | None = None,
    ) -> Self:
        # 예약 목록 응답에는 운행일 하나만 있습니다(코레일+ 7.0.8 ``ReservationViewOutTrainInfo``).
        # 출발·도착 날짜는 여정 상세(``ReservationOutJrnyInfo``)가 주므로 넘어오면 그 값을 씁니다.
        # 없으면 운행일을 출발일로 두고, 도착 시각이 출발보다 이르면 다음 날로 봅니다.
        train = Train.from_response(data)
        departure_day = dep_date or train.run_date
        arrival_day = arr_date or (_next_day(departure_day) if _crosses_midnight(train) else departure_day)
        train = replace(train, dep_date=departure_day, arr_date=arrival_day)

        return cls(
            train=train,
            pnr_no=text(data, "h_pnr_no"),
            seat_count=integer(data, "h_tot_seat_cnt"),
            buy_limit_date=text(data, "h_ntisu_lmt_dt"),
            buy_limit_time=text(data, "h_ntisu_lmt_tm"),
            price=integer(data, "h_rsv_amt"),
            journey_no=journey_no or _SINGLE_JOURNEY_NO,
            journey_cnt=journey_cnt or _SINGLE_JOURNEY_CNT,
            rsv_chg_no=rsv_chg_no or _SINGLE_JOURNEY_CHG_NO,
            seats=seats,
            wct_no=wct_no,
        )

    @property
    def is_waiting(self) -> bool:
        """실좌석이 아니라 예약대기입니다 — 구입기한이 채워지지 않습니다."""
        return self.buy_limit_date == _WAITING_BUY_LIMIT_DATE or self.buy_limit_time == _WAITING_BUY_LIMIT_TIME

    @property
    def buy_limit(self) -> datetime | None:
        """구입기한 일시(KST). 예약대기면 기한이 없으므로 ``None``."""
        if self.is_waiting:
            return None
        return kst_datetime(self.buy_limit_date, self.buy_limit_time)

    def __repr__(self) -> str:
        repr_str = f"{self.train!r}, {self.price}원({self.seat_count}석)"
        if self.is_waiting:
            return f"{repr_str}, 예약대기"

        limit_date = self.buy_limit_date
        if len(limit_date) >= 8 and limit_date.isdigit():
            limit_date = f"{int(limit_date[4:6])}월 {int(limit_date[6:8])}일"
        return f"{repr_str}, 구입기한 {limit_date} {hhmm(self.buy_limit_time)}"


def _crosses_midnight(train: Train) -> bool:
    """도착 시각이 출발 시각보다 이르면 자정을 넘긴 것입니다. 시각을 못 읽으면 넘기지 않은 것으로 봅니다."""
    departure = kst_datetime(_ANY_DAY, train.dep_time)
    arrival = kst_datetime(_ANY_DAY, train.arr_time)
    return departure is not None and arrival is not None and arrival < departure


def _next_day(day: str) -> str:
    """``YYYYMMDD`` 의 다음 날. 형식이 틀리면 그대로 돌려줍니다."""
    moment = kst_date(day)
    return day if moment is None else f"{moment + timedelta(days=1):%Y%m%d}"
