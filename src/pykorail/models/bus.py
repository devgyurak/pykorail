"""공항버스 — 정류장과 시간표.

공항버스의 좌석은 열차의 좌석 조회와 같은 모양으로 옵니다
(:class:`~pykorail.models.car.CarSeat`).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pykorail.models.parsing import amount, hhmm, integer, mmdd, text

if TYPE_CHECKING:
    from typing import Self

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BusStop:
    """공항버스 정류장."""

    code: str
    name: str


def parse_bus_stops(payload: dict[str, Any]) -> list[BusStop]:
    """공통 코드 응답에서 정류장 목록을 읽습니다. 못 읽으면 빈 목록.

    정류장은 한 건씩이 아니라 **이름 목록과 코드 목록 두 개**로 따로 옵니다. 순서대로
    짝지어야 해서, 두 목록의 길이가 다르면 어느 이름이 어느 코드인지 알 수 없습니다 —
    잘라서 맞추지 않고 경고를 남긴 뒤 빈 목록을 돌려줍니다. 어긋난 짝으로 조회하면
    엉뚱한 구간의 시간표가 오류 없이 돌아옵니다.
    """
    names, codes = payload.get("app.limousine.stationNm"), payload.get("app.limousine.stationCd")
    if not isinstance(names, list) or not isinstance(codes, list):
        return []
    if len(names) != len(codes):
        logger.warning("공항버스 정류장의 이름(%d개)과 코드(%d개)의 수가 달라 읽지 않았습니다", len(names), len(codes))
        return []
    return [BusStop(code=str(code), name=str(name)) for code, name in zip(codes, names, strict=True)]


@dataclass(frozen=True)
class AirportBus:
    """공항버스 한 편.

    정류장 이름은 시간표 응답에 없습니다(코드만 옵니다). 조회할 때 받은 정류장 목록에서
    이름을 찾아 함께 넣습니다.
    """

    #: 편 번호 (``trnNo``, ``"08008"``). 서버가 준 문자열 그대로입니다 — 좌석 조회에 돌려보냅니다.
    bus_no: str
    dep_code: str
    dep_name: str
    arr_code: str
    arr_name: str
    #: 운행일 · 출발일 · 도착일 ``YYYYMMDD``, 출발 · 도착 시각 ``HHMMSS``.
    run_date: str
    dep_date: str
    dep_time: str
    arr_date: str
    arr_time: str
    #: 운행 그룹 코드 (``trnGpCd``, ``"980"``) 와 종별 코드 (``stlbTrnClsfCd``, ``"98"``).
    group: str
    bus_type: str
    #: 출발 · 도착 정류장의 운행 순서. 좌석 조회가 구간을 이 값으로 가리킵니다.
    dep_run_order: str
    arr_run_order: str
    #: 남은 좌석 수 (``gnrmRestSeatNum``).
    remaining_seats: int
    #: 운임(원) (``rcvdPrc``). 어른 한 명 기준입니다.
    price: int

    @classmethod
    def from_response(cls, data: dict[str, Any], *, dep_name: str, arr_name: str) -> Self:
        return cls(
            bus_no=text(data, "trnNo"),
            dep_code=text(data, "dptRsStnCd"),
            dep_name=dep_name,
            arr_code=text(data, "arvRsStnCd"),
            arr_name=arr_name,
            run_date=text(data, "runDt"),
            dep_date=text(data, "dptDt"),
            dep_time=text(data, "dptTm"),
            arr_date=text(data, "arvDt"),
            arr_time=text(data, "arvTm"),
            group=text(data, "trnGpCd"),
            bus_type=text(data, "stlbTrnClsfCd"),
            dep_run_order=text(data, "dptStnRunOrdr"),
            arr_run_order=text(data, "arvStnRunOrdr"),
            remaining_seats=integer(data, "gnrmRestSeatNum"),
            price=amount(data, "rcvdPrc"),
        )

    def has_seat(self) -> bool:
        return self.remaining_seats > 0

    def __repr__(self) -> str:
        return (
            f"[공항버스 {self.bus_no}] {mmdd(self.dep_date)} {hhmm(self.dep_time)}~{hhmm(self.arr_time)}  "
            f"{self.dep_name}~{self.arr_name}  {self.remaining_seats}석"
        )
