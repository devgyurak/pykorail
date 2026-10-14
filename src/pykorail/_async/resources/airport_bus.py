"""공항버스 리소스 — 정류장 · 시간표 · 좌석."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pykorail._async.resources.base import AsyncResource
from pykorail._shared.clock import to_kst
from pykorail.constants import API_ENDPOINTS
from pykorail.exceptions import NoResultsError, StationNotFoundError
from pykorail.models.bus import AirportBus, BusStop, parse_bus_stops
from pykorail.models.car import CarSeat
from pykorail.models.parsing import records, text
from pykorail.models.passenger import AdultPassenger, Passenger

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from pykorail._async.api import AsyncApiClient

#: 정류장 목록을 받는 공통 코드 키. 앱의 공항버스 화면이 이 셋을 한 번에 요청합니다.
_STOP_CODES = ("app.limousine.stationNm", "app.limousine.stationCd", "app.limousine.airportBusMsg")

#: 공항버스의 운행 그룹 코드 (``trnGpCd``). 시간표의 모든 행에 이 값이 실려 옵니다.
_GROUP = "980"

#: 객실 구분. 공항버스에는 일반실뿐입니다.
_SEAT_CLASS = "1"

#: 공항버스는 한 대라 호차가 늘 하나입니다. 앱도 이 값을 상수로 보냅니다.
_CAR_NO = "0001"


class AsyncAirportBusResource(AsyncResource):
    """``korail.airport_bus`` — 공항버스 정류장 · 시간표 · 좌석 조회. 전부 로그인 없이 됩니다.

    코레일이 파는 공항버스는 광명역에서 인천공항으로 가는 편뿐입니다.
    """

    def __init__(self, api: AsyncApiClient) -> None:
        super().__init__(api)
        self._stops: list[BusStop] | None = None

    async def stops(self, refresh: bool = False) -> list[BusStop]:
        """공항버스 정류장 목록.

        앱처럼 공통 코드 조회에 정류장 이름 · 코드 · 안내문 키를 한 번에 실어 보냅니다.
        정류장은 거의 바뀌지 않고 :meth:`search` 가 이름을 코드로 바꾸는 데 쓰므로
        **리소스 수명 동안 캐시**합니다. 새로 받으려면 ``refresh=True``.
        """
        if refresh or self._stops is None:
            # 같은 이름의 필드(code)를 여러 번 실어야 해서 dict 가 아니라 쌍의 목록으로 보냅니다.
            form = [*self._api.common_payload().items(), *(("code", code) for code in _STOP_CODES)]
            payload = await self._api.post(API_ENDPOINTS["code"], data=form)
            self._api.check(payload)
            self._stops = parse_bus_stops(payload)
        return list(self._stops)

    async def search(self, dep: str, arr: str, depart_after: datetime | None = None) -> list[AirportBus]:
        """공항버스 시간표를 조회합니다. 없으면 빈 리스트.

        **코레일이 파는 것은 광명역에서 떠나는 편뿐입니다** — 광명역 → 인천공항T1 ·
        인천공항T2. 반대 방향이나 송도국제교가 낀 구간은 조회가 "결과 없음" 으로 와서
        빈 리스트가 됩니다. 앱도 출발 정류장을 하나로 고정하고 도착만 고르게 합니다.

        요청 필드는 코레일+ 7.0.8 의 ``ScdlQryIn`` 에서 확인했습니다.

        Args:
            dep: 출발 정류장 **이름** (:meth:`stops` 의 ``name``).
            arr: 도착 정류장 이름.
            depart_after: 그날, 이 시각 이후 출발. tz 없으면 KST 로 해석합니다. 생략하면 지금.

        Raises:
            StationNotFoundError: 정류장 목록에 없는 이름입니다.
        """
        by_name = {stop.name: stop for stop in await self.stops()}
        unknown = [name for name in (dep, arr) if name not in by_name]
        if unknown:
            raise StationNotFoundError(unknown, by_name.keys(), noun="정류장")
        moment = to_kst(depart_after)

        url = API_ENDPOINTS["bus_schedule"]
        headers, _ = self._api.sign(url)
        form = {
            **self._api.common_payload(),
            "dptDt": f"{moment:%Y%m%d}",
            "dptRsStnCd": by_name[dep].code,
            "arvRsStnCd": by_name[arr].code,
            "trnGpCd": _GROUP,
            "psrmClCd": _SEAT_CLASS,
            "dptTm": f"{moment:%H%M%S}",
        }

        payload = await self._api.post(url, data=form, headers=headers)
        try:
            self._api.check(payload)
        except NoResultsError:
            return []

        return [AirportBus.from_response(row, dep_name=dep, arr_name=arr) for row in records(payload, "trainList")]

    async def seats(self, bus: AirportBus, passengers: Sequence[Passenger] | None = None) -> list[CarSeat]:
        """공항버스 한 편의 좌석 배치를 조회합니다.

        열차의 좌석 조회와 같은 모양의 응답이라 같은 모델(:class:`~pykorail.models.car.CarSeat`)
        로 돌려줍니다. 요청 필드는 코레일+ 7.0.8 의 ``TResidualSeatsResearchIn`` 에서, 넣는 값은
        앱의 공항버스 좌석 화면에서 확인했습니다 — 편의 값은 시간표 행 그대로, 호차는 상수입니다.

        Args:
            bus: :meth:`search` 가 돌려준 편.
            passengers: 생략하면 어른 1명.

        Raises:
            ValueError: 편에 좌석 조회에 필요한 값이 없습니다.
        """
        needed = {
            "bus_type": bus.bus_type,
            "group": bus.group,
            "run_date": bus.run_date,
            "bus_no": bus.bus_no,
            "dep_code": bus.dep_code,
            "arr_code": bus.arr_code,
            "dep_run_order": bus.dep_run_order,
            "arr_run_order": bus.arr_run_order,
        }
        missing = sorted(name for name, value in needed.items() if not value)
        if missing:
            raise ValueError(f"좌석 조회에 필요한 값이 편에 없습니다: {', '.join(missing)}")
        headcount = sum(passenger.count for passenger in Passenger.reduce(passengers or [AdultPassenger()]))

        url = API_ENDPOINTS["bus_seat_map"]
        headers, _ = self._api.sign(url)
        form = {
            **self._api.common_payload(),
            "trnClsfCd": needed["bus_type"],
            "trnGpCd": needed["group"],
            "runDt": needed["run_date"],
            # 편 번호는 시간표가 준 그대로입니다 ("08008").
            "trnNo": needed["bus_no"],
            "srcarNo": _CAR_NO,
            "psrmClCd": _SEAT_CLASS,
            "dptRsStnCd": needed["dep_code"],
            "arvRsStnCd": needed["arr_code"],
            "dptStnRunOrdr": needed["dep_run_order"],
            "arvStnRunOrdr": needed["arr_run_order"],
            "totPsgCnt": str(headcount),
            # 앱 요청 모델의 기본값. 불리언이 문자열 "false" 로 펼쳐집니다.
            "isArrow": "false",
        }

        payload = await self._api.post(url, data=form, headers=headers)
        self._api.check(payload)

        car_no = text(payload, "scar_no") or _CAR_NO
        return [
            CarSeat.from_response(info, car_no=car_no, seat_class=_SEAT_CLASS) for info in records(payload, "seatList")
        ]
