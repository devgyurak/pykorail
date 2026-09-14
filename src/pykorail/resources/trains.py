"""열차 조회 리소스."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from pykorail.constants import API_ENDPOINTS, APP_VERSION, DEVICE, KST_OFFSET_HOURS
from pykorail.exceptions import NoResultsError, PastDepartureError
from pykorail.models.passenger import (
    AdultPassenger,
    ChildPassenger,
    Disability1To3Passenger,
    Disability4To6Passenger,
    Passenger,
    SeniorPassenger,
    ToddlerPassenger,
)
from pykorail.models.schedule import Train
from pykorail.options import TrainType
from pykorail.resources.base import Resource

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pykorail.api import ApiClient
    from pykorail.options import TrainTypeCode
    from pykorail.resources.stations import StationResource

KST = timezone(timedelta(hours=KST_OFFSET_HOURS))

#: 과거 판정 유예. 호출자가 ``datetime.now()`` 를 그대로 넘겨도 계산·왕복 지연 때문에
#: 걸리는 일이 없도록 조금 봐줍니다. 이보다 더 지난 시각은 열차가 이미 떠났다는 뜻이라
#: 조회할 이유가 없습니다.
PAST_TOLERANCE = timedelta(minutes=1)


def to_kst(moment: datetime | None) -> datetime:
    """KST 기준 시각으로 정규화합니다.

    ``None`` 이면 지금, naive 면 이미 KST 인 것으로 보고 tz 만 붙이고, aware 면
    KST 로 변환합니다. 서버가 보내 주는 날짜·시각이 전부 KST 라 기준을 여기 하나로
    모읍니다 — 실행 머신의 로컬 타임존에 결과가 흔들리면 안 됩니다.
    """
    if moment is None:
        return datetime.now(KST)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=KST)
    return moment.astimezone(KST)


class TrainResource(Resource):
    """``korail.trains`` — 시간표 조회."""

    def __init__(self, api: ApiClient, stations: StationResource, validate_stations: bool = True) -> None:
        super().__init__(api)
        self._stations = stations
        self.validate_stations = validate_stations

    def search(
        self,
        dep: str,
        arr: str,
        depart_after: datetime | None = None,
        train_type: TrainTypeCode = TrainType.ALL,
        passengers: Sequence[Passenger] | None = None,
        include_no_seats: bool = False,
        include_waiting_list: bool = False,
        include_nearby_stations: bool = False,
    ) -> list[Train]:
        """열차를 조회합니다.

        Args:
            dep: 출발역 이름 (예: ``"서울"``).
            arr: 도착역 이름.
            depart_after: 이 시각 **이후** 출발하는 열차를 그날 하루에서 찾습니다.
                naive datetime 은 KST 로 봅니다(코레일 시간표가 KST 기준이므로,
                ``datetime(2026, 4, 1, 9)`` 는 한국시간 오전 9시입니다). tz 가 붙어
                있으면 KST 로 변환합니다. 생략하면 지금(KST).
            train_type: :class:`~pykorail.options.TrainType` 코드.
            passengers: 생략하면 어른 1명.
            include_no_seats: 매진 열차도 포함합니다.
            include_waiting_list: 예약대기 가능 열차도 포함합니다.
            include_nearby_stations: 인근역 출발·도착 열차도 함께 봅니다 (앱의
                "인접역"). ``dep_name``/``arr_name`` 이 요청한 역과 달라질 수 있습니다.
                결과가 더해지는 것이 아니라 후보가 넓어지는 것이라 켜면 뒤쪽 직통편이
                밀려날 수 있어 기본값은 꺼짐입니다 — 자세한 것은 ``docs/reference.md``.

        Raises:
            StationNotFoundError: ``dep``/``arr`` 이 역 마스터에 없습니다.
            PastDepartureError: ``depart_after`` 가 이미 지난 시각입니다.
            NoResultsError: 조건에 맞는 열차가 없습니다.
        """
        if self.validate_stations:
            self._stations.ensure_exist(dep, arr)

        moment = to_kst(depart_after)
        self._ensure_not_past(moment)
        reduced = Passenger.reduce(passengers or [AdultPassenger()])

        def total(passenger_type: type[Passenger]) -> int:
            return sum(p.count for p in reduced if isinstance(p, passenger_type))

        url = API_ENDPOINTS["search_schedule"]
        headers, _ = self._api.sign(url)
        # 조회는 다른 엔드포인트와 달리 Key 를 싣지 않고 빈 Sid 를 보냅니다 (앱 동작 그대로).
        data = {
            "Device": DEVICE,
            "Version": APP_VERSION,
            "Sid": "",
            "txtMenuId": "11",
            "radJobId": "1",
            "selGoTrain": train_type,
            "txtTrnGpCd": train_type,
            "txtGoStart": dep,
            "txtGoEnd": arr,
            "txtGoAbrdDt": moment.strftime("%Y%m%d"),
            "txtGoHour": moment.strftime("%H%M%S"),
            "txtPsgFlg_1": total(AdultPassenger),
            "txtPsgFlg_2": total(ChildPassenger) + total(ToddlerPassenger),
            "txtPsgFlg_3": total(SeniorPassenger),
            "txtPsgFlg_4": total(Disability1To3Passenger),
            "txtPsgFlg_5": total(Disability4To6Passenger),
            "txtSeatAttCd_2": "000",
            "txtSeatAttCd_3": "000",
            "txtSeatAttCd_4": "015",
            "ebizCrossCheck": "N",
            "srtCheckYn": "N",  # SRT 함께 보기
            "rtYn": "N",  # 왕복
            "adjStnScdlOfrFlg": "Y" if include_nearby_stations else "N",  # 인접역 보기
            "mbCrdNo": self._api.account.membership_number,
        }

        payload = self._api.post(url, params=data, headers=headers)
        self._api.check(payload)

        trains = [Train.from_response(info) for info in payload.get("trn_infos", {}).get("trn_info", [])]
        trains = [train for train in trains if self._keep(train, include_no_seats, include_waiting_list)]
        if not trains:
            raise NoResultsError()
        return trains

    @staticmethod
    def _ensure_not_past(moment: datetime) -> None:
        """이미 지난 시각이면 요청을 보내기 전에 막습니다.

        서버는 과거 시각에도 빈 결과를 줄 뿐이라, 오래 도는 취소표 대기 루프가
        출발 시각을 넘겨도 아무 신호 없이 계속 돕니다. 여기서 끊어 줍니다.
        """
        now = datetime.now(KST)
        if moment < now - PAST_TOLERANCE:
            raise PastDepartureError(moment, now)

    @staticmethod
    def _keep(train: Train, include_no_seats: bool, include_waiting_list: bool) -> bool:
        """조회 결과 필터. ``include_no_seats`` 는 사실상 "전부 보기"입니다."""
        return (
            train.has_seat()
            or (include_no_seats and not train.has_seat())
            or (include_waiting_list and train.has_waiting_list())
        )
