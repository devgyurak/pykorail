# 이 파일은 생성물입니다 — 직접 고치지 마세요.
# 원본: src/pykorail/_async/resources/trains.py
# 다시 만들려면: uv run python scripts/unasync.py
"""열차 조회 리소스."""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from pykorail._shared.blank import without_blanks
from pykorail._shared.clock import KST, to_kst
from pykorail._sync.resources.base import Resource
from pykorail.constants import API_ENDPOINTS, APP_VERSION, DEVICE
from pykorail.exceptions import NoResultsError, PastDepartureError
from pykorail.models.car import Car, CarSeat
from pykorail.models.fare import Fare
from pykorail.models.parsing import records
from pykorail.models.passenger import (
    AdultPassenger,
    ChildPassenger,
    Disability1To3Passenger,
    Disability4To6Passenger,
    GuideDogPassenger,
    Passenger,
    SeniorPassenger,
    ToddlerPassenger,
)
from pykorail.models.run_date import RunDate
from pykorail.models.schedule import Train
from pykorail.models.transfer import Transfer, TransferStation, parse_transfers
from pykorail.options import SeatClass, TrainType

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pykorail._sync.api import ApiClient
    from pykorail._sync.resources.stations import StationResource
    from pykorail.options import SeatClassCode, TrainTypeCode

#: 과거 판정 유예. 호출자가 ``datetime.now()`` 를 그대로 넘겨도 계산·왕복 지연 때문에
#: 걸리는 일이 없도록 조금 봐줍니다. 이보다 더 지난 시각은 열차가 이미 떠났다는 뜻이라
#: 조회할 이유가 없습니다.
PAST_TOLERANCE = timedelta(minutes=1)

#: ``max_pages`` 의 상한. 한 쪽이 보통 열 편이라 하루치 시간표를 덮고도 남습니다. 이보다 큰
#: 값은 오타이거나 과한 자동 요청이라 요청 전에 막습니다 — 쪽마다 요청이 한 번씩 나가고,
#: 코레일은 과도한 자동 요청에 계정을 제재합니다.
MAX_PAGES = 20

#: 조회의 여정 종류 (``radJobId``). 같은 엔드포인트가 이 값으로 직통과 환승을 가릅니다.
_DIRECT = "1"
_TRANSFER = "2"

#: 운임 조회의 환승 구분 (``chtnDvCd``). 코레일+ 7.0.8 의 ``PrcFareIn`` 생성부가 직통에 1, 환승에 2 를
#: 넣습니다. 위의 여정 종류와 값은 같지만 다른 필드라 따로 둡니다.
_FARE_DIRECT = "1"
_FARE_TRANSFER = "2"


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
        max_pages: int = 1,
    ) -> list[Train]:
        """열차를 조회합니다.

        Args:
            dep: 출발역 이름 (예: ``"서울"``).
            arr: 도착역 이름.
            depart_after: 이 시각 **이후** 출발하는 열차를 그날 하루에서 찾습니다.
                naive datetime 은 KST 로 봅니다(코레일 시간표가 KST 기준이라 ``09:00`` 은
                UTC 서버에서도 한국시간 오전 9시입니다). tz 가 붙어 있으면 KST 로 변환합니다.
                생략하면 지금(KST).
            train_type: :class:`~pykorail.options.TrainType` 코드.
            passengers: 생략하면 어른 1명.
            include_no_seats: 매진 열차도 포함합니다.
            include_waiting_list: 예약대기 가능 열차도 포함합니다.
            include_nearby_stations: 인근역 출발·도착 열차도 함께 봅니다 (앱의
                "인접역"). ``dep_name``/``arr_name`` 이 요청한 역과 달라질 수 있습니다.
                결과가 더해지는 것이 아니라 후보가 넓어지는 것이라 켜면 뒤쪽 직통편이
                밀려날 수 있어 기본값은 꺼짐입니다 — 자세한 것은 ``docs/reference.md``.
            max_pages: 이어 받을 쪽 수의 상한. 서버는 요청 한 번에 한 쪽만 줍니다.
                2 이상이면 마지막 열차의 출발 시각부터 다시 조회해 이어 붙이고, 새
                열차가 더 나오지 않으면 상한 전에 멈춥니다. 쪽마다 요청이 한 번씩
                더 나가므로 필요한 만큼만 올리세요. 최대 :data:`MAX_PAGES`.

        Raises:
            ValueError: ``max_pages`` 가 1 보다 작거나 :data:`MAX_PAGES` 보다 큽니다.
            StationNotFoundError: ``dep``/``arr`` 이 역 마스터에 없습니다.
            PastDepartureError: ``depart_after`` 가 이미 지난 시각입니다.
            NoResultsError: 조건에 맞는 열차가 없습니다.
        """
        if not 1 <= max_pages <= MAX_PAGES:
            raise ValueError(f"max_pages 는 1 이상 {MAX_PAGES} 이하여야 합니다: {max_pages}")
        if self.validate_stations:
            self._stations.ensure_exist(dep, arr)

        moment = to_kst(depart_after)
        self._ensure_not_past(moment)
        reduced = Passenger.reduce(passengers or [AdultPassenger()])

        # 다음 쪽은 커서가 아니라 **같은 요청의 출발 일시만 바꿔** 받습니다. 앱의 일반 조회
        # 화면이 그렇게 합니다(코레일+ 7.0.8 TrainScheduleViewModel: 다음 쪽 요청은
        # txtGoAbrdDt · txtGoHour 두 값만 갈아 끼운 TrainScheduleIn). 그래서 쪽 경계의
        # 열차가 다시 내려올 수 있어 열차 단위로 중복을 거릅니다.
        found: dict[tuple[str, ...], Train] = {}
        cursor = moment
        for _ in range(max_pages):
            try:
                page = self._page(dep, arr, cursor, train_type, reduced, include_nearby_stations)
            except NoResultsError:
                if not found:
                    raise
                break
            fresh = {self._identity(train): train for train in page if self._identity(train) not in found}
            if not fresh:
                break
            found.update(fresh)
            following = page[-1].departure
            # 시각을 못 읽거나 앞으로 나아가지 못하면 같은 쪽을 다시 받게 되므로 멈춥니다.
            if following is None or following <= cursor:
                break
            cursor = following

        trains = [train for train in found.values() if self._keep(train, include_no_seats, include_waiting_list)]
        if not trains:
            raise NoResultsError()
        return trains

    def _page(
        self,
        dep: str,
        arr: str,
        moment: datetime,
        train_type: TrainTypeCode,
        passengers: Sequence[Passenger],
        include_nearby_stations: bool,
    ) -> list[Train]:
        """``moment`` 부터의 직통 조회 결과 한 쪽. 필터를 거치지 않은 서버 응답 그대로입니다."""
        rows = self._rows(dep, arr, moment, train_type, passengers, include_nearby_stations, _DIRECT)
        return [Train.from_response(row) for row in rows]

    def _rows(
        self,
        dep: str,
        arr: str,
        moment: datetime,
        train_type: TrainTypeCode,
        passengers: Sequence[Passenger],
        include_nearby_stations: bool,
        job: str,
    ) -> list[dict[str, Any]]:
        """조회 요청 한 번의 열차 행들. ``job`` 이 직통(:data:`_DIRECT`) · 환승(:data:`_TRANSFER`)을 가릅니다."""

        def total(passenger_type: type[Passenger]) -> int:
            return sum(p.count for p in passengers if isinstance(p, passenger_type))

        url = API_ENDPOINTS["search_schedule"]
        headers, _ = self._api.sign(url)
        # 조회는 다른 엔드포인트와 달리 Key 를 싣지 않고 빈 Sid 를 보냅니다 (앱 동작 그대로).
        data = {
            "Device": DEVICE,
            "Version": APP_VERSION,
            "Sid": "",
            "txtMenuId": "11",
            "radJobId": job,
            "selGoTrain": train_type,
            "txtTrnGpCd": train_type,
            "txtGoStart": dep,
            "txtGoEnd": arr,
            "txtGoAbrdDt": moment.strftime("%Y%m%d"),
            "txtGoHour": moment.strftime("%H%M%S"),
            # 안내견은 별도 칸이 없고 **어른 칸에 더해집니다** (코레일톡+ 7.0.8
            # TrainScheduleViewModel.buildTrainScheduleIn: GUIDE_DOG 와 어른 · 청소년이 같은
            # 합계로 txtPsgFlg_1 에 들어갑니다). 청소년(TEENAGER)은 pykorail 이 다루지 않습니다.
            "txtPsgFlg_1": total(AdultPassenger) + total(GuideDogPassenger),
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

        return records(payload, "trn_infos", "trn_info")

    @staticmethod
    def _identity(train: Train) -> tuple[str, ...]:
        """쪽 사이에서 같은 열차를 알아보는 키. 인근역 조회는 한 열차가 역 쌍만 달리해 여러 번 나옵니다."""
        return (train.train_no, train.dep_date, train.dep_time, train.dep_code, train.arr_code)

    def transfer_stations(self, dep: str, arr: str) -> list[TransferStation]:
        """두 역 사이에서 갈아탈 수 있는 역들을 조회합니다. 로그인하지 않아도 됩니다.

        요청 필드는 코레일+ 7.0.8 의 ``ChtnStnIn`` 에서 확인했습니다. 역을 **코드**로
        보내므로 ``validate_stations`` 설정과 무관하게 역 마스터를 봅니다.

        Raises:
            StationNotFoundError: ``dep``/``arr`` 이 역 마스터에 없습니다.
        """
        self._stations.ensure_exist(dep, arr)
        codes = {station.name: station.code for station in self._stations.all()}

        url = API_ENDPOINTS["transfer_stations"]
        headers, _ = self._api.sign(url)
        form = without_blanks({**self._api.common_payload(), "dptRsStnCd": codes[dep], "arvRsStnCd": codes[arr]})

        payload = self._api.post(url, data=form, headers=headers)
        self._api.check(payload)

        return [TransferStation.from_response(info) for info in records(payload, "chtnList")]

    def search_transfers(
        self,
        dep: str,
        arr: str,
        depart_after: datetime | None = None,
        train_type: TrainTypeCode = TrainType.ALL,
        passengers: Sequence[Passenger] | None = None,
        include_no_seats: bool = False,
    ) -> list[Transfer]:
        """한 번 갈아타는 여정을 조회합니다. 직통이 없는 구간에서 씁니다.

        :meth:`search` 와 같은 요청이고 여정 종류(``radJobId``)만 환승입니다. 응답의 열차
        행을 여정 단위로 묶어 돌려줍니다 — 묶는 규칙은
        :func:`~pykorail.models.transfer.parse_transfers` 에 있습니다.

        Args:
            dep: 출발역 이름.
            arr: 도착역 이름.
            depart_after: 이 시각 이후 출발. :meth:`search` 와 같은 규칙으로 KST 로 봅니다.
            train_type: :class:`~pykorail.options.TrainType` 코드.
            passengers: 생략하면 어른 1명.
            include_no_seats: 한 구간이라도 매진인 여정까지 포함합니다. 기본은 두 구간
                모두 좌석이 있는 여정만.

        Raises:
            StationNotFoundError: ``dep``/``arr`` 이 역 마스터에 없습니다.
            PastDepartureError: ``depart_after`` 가 이미 지난 시각입니다.
            NoResultsError: 조건에 맞는 환승 여정이 없습니다.
        """
        if self.validate_stations:
            self._stations.ensure_exist(dep, arr)

        moment = to_kst(depart_after)
        self._ensure_not_past(moment)
        reduced = Passenger.reduce(passengers or [AdultPassenger()])

        rows = self._rows(dep, arr, moment, train_type, reduced, False, _TRANSFER)
        transfers = [transfer for transfer in parse_transfers(rows) if include_no_seats or transfer.has_seat()]
        if not transfers:
            raise NoResultsError()
        return transfers

    def run_dates(self) -> list[RunDate]:
        """운행 달력 — 오늘부터 약 두 달치의 날짜별 운행 정보를 조회합니다. 로그인하지 않아도 됩니다.

        출발일이 성수기인지(:attr:`~pykorail.models.run_date.RunDate.is_peak_season`)에
        따라 NetFunnel 대기열의 ``aid`` 가 달라집니다 — 어느 값을 쓸지는
        :func:`~pykorail.models.run_date.netfunnel_action_for` 로 고르세요.

        **캐시하지 않습니다** — 호출마다 요청합니다. 반복해서 쓸 때는 한 번 받아
        재사용하세요.

        요청 폼은 코레일톡+ 7.0.8 의 ``RunDateIn``(``CommonIn`` 상속)이고, 응답 목록 키는
        ``runningCalendar`` 입니다. 서명 대상이 아니고 ``Sid`` 도 붙지 않습니다
        (2026-10-16 캡처).
        """
        url = API_ENDPOINTS["run_dates"]
        headers, _ = self._api.sign(url)
        form = {**self._api.common_payload(), "timeStamp": str(time.time_ns() // 1_000_000)}

        payload = self._api.post(url, data=form, headers=headers)
        self._api.check(payload)

        return [RunDate.from_response(info) for info in records(payload, "runningCalendar")]

    def fares(self, journey: Train | Transfer) -> list[Fare]:
        """예약하기 전에 운임을 조회합니다. 로그인하지 않아도 됩니다.

        열차 한 편이나 환승 여정을 넘깁니다. **기준 운임**이라 할인은 반영되지 않습니다 —
        실제로 낼 금액은 예약한 뒤 ``Reservation.price`` 에 있습니다.

        요청 필드는 코레일+ 7.0.8 의 ``PrcFareIn`` · ``PrcFareInItem`` 에서 확인했습니다.
        열차별 값은 열차마다 필드를 따로 두지 않고 **칸마다 쉼표로 이어** 보냅니다.

        Raises:
            TypeError: 열차도 환승 여정도 아닌 것을 넘겼습니다.
            ValueError: 열차에 운임 조회에 필요한 값이 없습니다. :meth:`search` ·
                :meth:`search_transfers` 가 돌려준 열차를 넘기세요.
        """
        if not isinstance(journey, (Train, Transfer)):
            # 예약(Reservation)처럼 이름이 비슷한 것을 넘기면 속성 오류로는 원인을 알기 어렵습니다.
            raise TypeError(f"Train 이나 Transfer 를 넘기세요: {type(journey).__name__}")
        if isinstance(journey, Transfer):
            legs, kind = journey.legs, _FARE_TRANSFER
        else:
            legs, kind = (journey,), _FARE_DIRECT
        # 열은 사용자가 아는 이름(Train 의 속성)으로 들고 있다가, 빈 값이 있으면 그 이름으로 알립니다.
        columns = {
            "dep_code": [leg.dep_code for leg in legs],
            "arr_code": [leg.arr_code for leg in legs],
            "run_date": [leg.run_date for leg in legs],
            "train_no": [leg.train_no for leg in legs],
            "seat_attribute": [leg.seat_attribute for leg in legs],
            "train_group": [leg.train_group for leg in legs],
            "train_type": [leg.train_type for leg in legs],
        }
        missing = sorted(name for name, values in columns.items() if not all(values))
        if missing:
            # 빈 값을 이어 붙이면 칸 수가 맞지 않는 요청이 되고, 서버는 그것을 오류가 아니라
            # 다른 조회로 읽습니다. 예약 목록 · 승차권의 열차에는 좌석 속성이 없습니다.
            raise ValueError(f"운임 조회에 필요한 값이 열차에 없습니다: {', '.join(missing)}")

        url = API_ENDPOINTS["fare"]
        # 서명은 붙이되 Sid 는 싣지 않습니다 (앱의 요청 모델에 Sid 가 없습니다).
        headers, _ = self._api.sign(url, include_sid=False)
        # **without_blanks 를 쓰지 않습니다.** 앱은 요청 모델을 펼친 **뒤에** 열차별 여덟 칸을
        # 따로 넣어서, 값이 빈 gdNo(상품번호)도 그대로 실립니다. 칸의 순서도 앱이 넣는 순서입니다.
        form = {
            **self._api.common_payload(),
            "txtMenuId": "11",
            # 여정의 종류이지 열차 수가 아닙니다. 지금은 환승이 늘 두 구간이라 trnCnt 와 값이 같을 뿐입니다.
            "chtnDvCd": kind,
            "trnCnt": str(len(legs)),
            "dptRsStnCd": ",".join(columns["dep_code"]),
            "arvRsStnCd": ",".join(columns["arr_code"]),
            "runDt": ",".join(columns["run_date"]),
            "trnNo": ",".join(columns["train_no"]),
            "gdNo": ",".join("" for _ in legs),
            "rqSeatAttCd": ",".join(columns["seat_attribute"]),
            "trnGpCd": ",".join(columns["train_group"]),
            "stlbTrnClsfCd": ",".join(columns["train_type"]),
        }

        payload = self._api.post(url, data=form, headers=headers)
        self._api.check(payload)

        return [Fare.from_response(info) for info in records(payload, "prcList")]

    def cars(
        self,
        train: Train,
        passengers: Sequence[Passenger] | None = None,
        seat_class: SeatClassCode = SeatClass.GENERAL,
    ) -> list[Car]:
        """열차의 호차 목록을 조회합니다. **로그인이 필요합니다.**

        좌석을 직접 고르려면 여기서 호차를 고른 뒤 :meth:`seats` 로 그 호차의 좌석을
        봅니다. 요청 필드는 코레일+ 7.0.8 의 ``TrainResearchIn`` 에서 확인했습니다.

        Args:
            train: :meth:`search` 가 돌려준 열차.
            passengers: 생략하면 어른 1명. 인원수가 함께 앉을 수 있는 좌석 판단에 쓰입니다.
            seat_class: :class:`~pykorail.options.SeatClass` 코드. 기본은 일반실.

        Raises:
            NeedToLoginError: 로그인하지 않았습니다.
        """
        url = API_ENDPOINTS["seat_cars"]
        headers, _ = self._api.sign(url)
        form = without_blanks(
            {
                **self._api.common_payload(),
                "txtMenuId": "11",
                "txtRunDt": train.run_date,
                "txtDptDt": train.dep_date,
                # 열차번호는 다섯 자리로 채워 보냅니다 (조회 결과가 "101" 로 와도 "00101").
                "txtTrnNo": train.train_no.zfill(5),
                "txtDptTm": train.dep_time,
                "txtTrnClsfCd": train.train_type,
                "txtTrnGpCd": train.train_group,
                "txtDptRsStnCd": train.dep_code,
                "txtArvRsStnCd": train.arr_code,
                "txtPsrmClCd": seat_class,
                "txtSeatAttCd": train.seat_attribute,
                "txtDptStnRunOrdr": train.dep_run_order,
                "txtArvStnRunOrdr": train.arr_run_order,
                "txtTotPsgCnt": str(self._headcount(passengers)),
            }
        )

        payload = self._api.post(url, data=form, headers=headers)
        self._api.check(payload)

        return [Car.from_response(info) for info in records(payload, "srcar_infos", "srcar_info")]

    def seats(
        self,
        train: Train,
        car: Car,
        passengers: Sequence[Passenger] | None = None,
        seat_class: SeatClassCode | None = None,
    ) -> list[CarSeat]:
        """호차 하나의 좌석 배치와 좌석별 판매 가능 여부를 조회합니다. **로그인이 필요합니다.**

        ``car`` 는 같은 로그인 세션에서 :meth:`cars` 로 받은 것이어야 합니다 — 앱의 화면
        순서(호차 목록 → 좌석 배치)가 그렇고, 호차 목록 없이 바로 부르면 서버가 인증
        오류를 돌려준 사례가 있습니다. ``passengers`` 는 :meth:`cars` 에 넘긴 값과 같게
        넘기세요.

        요청 필드는 코레일+ 7.0.8 의 ``TResidualSeatsResearchIn`` 에서 확인했습니다.

        Args:
            train: :meth:`search` 가 돌려준 열차.
            car: :meth:`cars` 가 돌려준 호차.
            passengers: 생략하면 어른 1명.
            seat_class: 생략하면 호차의 객실(``car.seat_class``)을 씁니다. 호차 목록에
                넘긴 값을 다시 넘길 필요가 없습니다.

        Raises:
            ValueError: 호차에 객실 코드가 없는데 ``seat_class`` 도 넘기지 않았습니다.
            NeedToLoginError: 로그인하지 않았습니다.
        """
        room = seat_class or car.seat_class
        if not room:
            # 빈 값으로 두면 without_blanks 가 psrmClCd 를 통째로 빼 버려, 서버가 어떤 객실로
            # 해석할지 알 수 없는 요청이 나갑니다. 일반실로 넘겨짚지 않고 여기서 멈춥니다.
            raise ValueError("호차에 객실 코드가 없습니다 — seat_class 를 직접 넘기세요")

        url = API_ENDPOINTS["seat_map"]
        headers, _ = self._api.sign(url)
        form = without_blanks(
            {
                **self._api.common_payload(),
                "trnClsfCd": train.train_type,
                "trnGpCd": train.train_group,
                "runDt": train.run_date,
                "trnNo": train.train_no.zfill(5),
                # 서버가 준 호차 번호("0001")를 그대로 돌려보냅니다.
                "srcarNo": car.car_no,
                "psrmClCd": room,
                "dptRsStnCd": train.dep_code,
                "arvRsStnCd": train.arr_code,
                "seatAttCd": train.seat_attribute,
                "dptStnRunOrdr": train.dep_run_order,
                "arvStnRunOrdr": train.arr_run_order,
                "totPsgCnt": str(self._headcount(passengers)),
                # 앱 요청 모델의 기본값. 불리언이 문자열 "false" 로 펼쳐집니다.
                "isArrow": "false",
            }
        )

        payload = self._api.post(url, data=form, headers=headers)
        self._api.check(payload)

        return [
            CarSeat.from_response(info, car_no=car.car_no, seat_class=room) for info in records(payload, "seatList")
        ]

    @staticmethod
    def _headcount(passengers: Sequence[Passenger] | None) -> int:
        """좌석 조회에 싣는 총 인원. 생략하면 어른 1명."""
        return sum(passenger.count for passenger in Passenger.reduce(passengers or [AdultPassenger()]))

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
