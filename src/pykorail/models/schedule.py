"""열차 시간표와 좌석 가용 정보.

모든 응답 모델은 **불변**이고 :meth:`from_response` 로만 만듭니다. 생성자는 순수한
값 조립이고 응답 dict 해석은 전부 ``from_response`` 안에 있어서, "반쯤 채워진
객체"가 돌아다닐 여지가 없습니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from pykorail.models.parsing import hhmm, integer, kst_datetime, mmdd, text

if TYPE_CHECKING:
    from typing import Self

#: ``h_wait_rsv_flg`` 가 없을 때 쓰는 값. "예약대기라는 개념이 적용되지 않는 열차"를
#: 뜻하며, 앱의 음수 관례를 그대로 따릅니다.
WAITING_NOT_APPLICABLE = -1

_SEAT_AVAILABLE = "11"
_WAITING_LIST_OPEN = 9


def _minutes(value: str) -> int | None:
    """``HHMMSS`` → 자정 기준 분. 못 읽으면 ``None``."""
    if len(value) < 4 or not value[:4].isdigit():
        return None
    return int(value[:2]) * 60 + int(value[2:4])


def format_duration(minutes: int) -> str:
    """소요 시간(분)을 읽기 쉬운 한국어로.

    ``355`` 처럼 큰 값을 그냥 "355분" 으로 보여주면 몇 시간짜리인지 바로 안 들어옵니다.
    한 시간이 넘으면 시간 단위로 끊고, 딱 떨어지면 "분" 을 생략합니다::

        45  → "45분"
        60  → "1시간"
        210 → "3시간 30분"
        355 → "5시간 55분"
    """
    hours, remainder = divmod(minutes, 60)
    if hours == 0:
        return f"{remainder}분"
    if remainder == 0:
        return f"{hours}시간"
    return f"{hours}시간 {remainder}분"


@dataclass(frozen=True)
class Schedule:
    """열차 운행 한 건 — 어디서 몇 시에 떠나 어디에 몇 시에 닿는지."""

    train_type: str
    train_type_name: str
    train_group: str
    train_no: str
    delay_time: str
    dep_name: str
    dep_code: str
    dep_date: str
    dep_time: str
    arr_name: str
    arr_code: str
    arr_date: str
    arr_time: str
    run_date: str

    @classmethod
    def _fields_from(cls, data: dict[str, Any]) -> dict[str, Any]:
        """응답 dict → 생성자 인자. 하위 타입이 자기 필드를 얹어 확장합니다."""
        return {
            "train_type": text(data, "h_trn_clsf_cd"),
            "train_type_name": text(data, "h_trn_clsf_nm"),
            "train_group": text(data, "h_trn_gp_cd"),
            "train_no": text(data, "h_trn_no"),
            "delay_time": text(data, "h_expct_dlay_hr"),
            "dep_name": text(data, "h_dpt_rs_stn_nm"),
            "dep_code": text(data, "h_dpt_rs_stn_cd"),
            "dep_date": text(data, "h_dpt_dt"),
            "dep_time": text(data, "h_dpt_tm"),
            "arr_name": text(data, "h_arv_rs_stn_nm"),
            "arr_code": text(data, "h_arv_rs_stn_cd"),
            "arr_date": text(data, "h_arv_dt"),
            "arr_time": text(data, "h_arv_tm"),
            "run_date": text(data, "h_run_dt"),
        }

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> Self:
        return cls(**cls._fields_from(data))

    @property
    def departure(self) -> datetime | None:
        """출발 일시(KST). 날짜나 시각이 없거나 형식이 틀리면 ``None``."""
        return kst_datetime(self.dep_date, self.dep_time)

    @property
    def arrival(self) -> datetime | None:
        """도착 일시(KST). 날짜나 시각이 없거나 형식이 틀리면 ``None``."""
        return kst_datetime(self.arr_date, self.arr_time)

    @property
    def duration_minutes(self) -> int | None:
        """출발~도착 소요 시간(분).

        날짜가 있으면 일시끼리 뺍니다 — 이틀에 걸친 운행도 맞게 잽니다. 도착 일시가 출발보다
        이르면(도착 날짜가 출발과 같게 온 예약처럼) 하루를 더해 자정 넘김으로 봅니다.
        날짜가 없으면 시각만으로 잽니다.
        """
        departure, arrival = self.departure, self.arrival
        if departure is not None and arrival is not None:
            elapsed = arrival - departure
            if elapsed < timedelta(0):
                elapsed += timedelta(days=1)
            return int(elapsed.total_seconds() // 60)

        start, end = _minutes(self.dep_time), _minutes(self.arr_time)
        if start is None or end is None:
            return None
        elapsed = end - start
        return elapsed + 24 * 60 if elapsed < 0 else elapsed

    @property
    def duration_text(self) -> str | None:
        """소요 시간을 "3시간 30분" 형태로. 시각을 못 읽으면 ``None``."""
        minutes = self.duration_minutes
        return None if minutes is None else format_duration(minutes)

    def summary(self) -> str:
        """``[KTX 101] 04/01 09:00~12:30  서울~부산`` 형태의 한 줄 요약.

        좌석 가용 여부가 의미 없는 맥락(승차권 등)에서 이 부분만 재사용합니다.
        """
        train_line = f"[{self.train_type_name[:3]} {self.train_no}]"
        return (
            f"{train_line:<11s}{mmdd(self.dep_date)} "
            f"{hhmm(self.dep_time)}~{hhmm(self.arr_time)}  {self.dep_name}~{self.arr_name}"
        )

    def __repr__(self) -> str:
        return self.summary()


@dataclass(frozen=True)
class Train(Schedule):
    """좌석 가용 정보가 붙은 열차 시간표."""

    reserve_possible: str
    reserve_possible_name: str
    special_seat: str
    general_seat: str
    wait_reserve_flag: int
    #: 출발·도착역의 운행 순서. 호차·좌석 조회가 구간을 이 값으로 가리킵니다.
    dep_run_order: str
    arr_run_order: str
    #: 출발·도착역의 구성 순서. 좌석을 지정한 예매가 운행 순서와 함께 돌려보냅니다.
    dep_cons_order: str
    arr_cons_order: str
    #: 이 열차 행의 좌석 속성 코드 (``"015"`` 등). 운임 · 호차 · 좌석 조회와 좌석 지정 · 환승 예매가
    #: 이 값을 보냅니다 — 예매는 비면 일반석 015 로 대체합니다.
    seat_attribute: str

    @classmethod
    def _fields_from(cls, data: dict[str, Any]) -> dict[str, Any]:
        return {
            **Schedule._fields_from(data),
            "dep_run_order": text(data, "h_dpt_stn_run_ordr"),
            "arr_run_order": text(data, "h_arv_stn_run_ordr"),
            "dep_cons_order": text(data, "h_dpt_stn_cons_ordr"),
            "arr_cons_order": text(data, "h_arv_stn_cons_ordr"),
            "seat_attribute": text(data, "h_seat_att_cd"),
            "reserve_possible": text(data, "h_rsv_psb_flg"),
            "reserve_possible_name": text(data, "h_rsv_psb_nm"),
            "special_seat": text(data, "h_spe_rsv_cd"),
            "general_seat": text(data, "h_gen_rsv_cd"),
            # 필드가 비어 오면 "예약대기 미적용"으로 봅니다 — None 을 그대로 두면
            # 비교 연산(`< 0`)이 터집니다.
            "wait_reserve_flag": integer(data, "h_wait_rsv_flg", WAITING_NOT_APPLICABLE),
        }

    def has_special_seat(self) -> bool:
        return self.special_seat == _SEAT_AVAILABLE

    def has_general_seat(self) -> bool:
        return self.general_seat == _SEAT_AVAILABLE

    def has_seat(self) -> bool:
        return self.has_general_seat() or self.has_special_seat()

    def has_general_waiting_list(self) -> bool:
        return self.wait_reserve_flag == _WAITING_LIST_OPEN

    def has_waiting_list(self) -> bool:
        return self.has_general_waiting_list()

    def __repr__(self) -> str:
        parts = [self.summary()]

        if self.reserve_possible_name:
            parts.append(f"  특실 {'가능' if self.has_special_seat() else '매진'}")
            parts.append(f", 일반실 {'가능' if self.has_general_seat() else '매진'}")
            if self.wait_reserve_flag >= 0:
                parts.append(f", 예약대기 {'가능' if self.has_general_waiting_list() else '매진'}")

        duration = self.duration_text
        parts.append(f" ({duration})" if duration is not None else " (?분)")
        return "".join(parts)
