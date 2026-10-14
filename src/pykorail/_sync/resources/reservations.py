# 이 파일은 생성물입니다 — 직접 고치지 마세요.
# 원본: src/pykorail/_async/resources/reservations.py
# 다시 만들려면: uv run python scripts/unasync.py
"""예약 리소스."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pykorail._shared.blank import without_blanks
from pykorail._sync.resources.base import Resource
from pykorail.constants import API_ENDPOINTS
from pykorail.exceptions import KorailError, NoResultsError
from pykorail.models.car import CarSeat
from pykorail.models.card import Card
from pykorail.models.parsing import records, text
from pykorail.models.passenger import AdultPassenger, Passenger
from pykorail.models.reservation import Reservation
from pykorail.models.seat import Seat
from pykorail.models.transfer import Transfer
from pykorail.options import ReserveOption, SeatClass

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from pykorail.models.schedule import Train
    from pykorail.options import ReserveOptionCode, SeatClassCode

#: 좌석이 있는 열차를 예매할 때의 특실 선택 규칙. 값은 "특실을 고를지" 여부입니다.
_SEATED_PREFERS_SPECIAL = {
    ReserveOption.GENERAL_ONLY: lambda train: False,
    ReserveOption.SPECIAL_ONLY: lambda train: True,
    ReserveOption.GENERAL_FIRST: lambda train: not train.has_general_seat(),
    ReserveOption.SPECIAL_FIRST: lambda train: train.has_special_seat(),
}

#: 좌석을 지정한 예매의 작업 구분 (``txtJobId``). 앱의 좌석 선택 화면이
#: ``ReservationJobId.SEAT`` 를 싣고, 그 값이 1103 입니다.
_JOB_SEAT_DESIGNATED = "1103"

#: 좌석을 서버가 정하는 보통 예매의 작업 구분. 앱의 환승 예매가 ``TicketReservationType.DEFAULT`` 를 싣습니다.
_JOB_DEFAULT = "1101"

#: 여정 종류 (``txtJrnyTpCd``). 앱은 환승 여정의 구간에 직통과 다른 값을 넣습니다.
_JOURNEY_DIRECT = "11"
_JOURNEY_TRANSFER = "14"

#: 열차 행에 좌석 속성이 없을 때 쓰는 값 (일반석). 앱도 행의 값이 비면 좌석 종류의 기본값을 씁니다.
_DEFAULT_SEAT_ATTRIBUTE = "015"

#: 환승 예매가 받는 구간 수. 앱은 선행 · 후행 두 편까지만 싣습니다.
_TRANSFER_LEGS = 2

#: 좌석이 없어 예약대기를 걸 때의 규칙. 가용 좌석이 없으니 선호만 반영합니다.
_WAITING_PREFERS_SPECIAL = {
    ReserveOption.GENERAL_ONLY: False,
    ReserveOption.GENERAL_FIRST: False,
    ReserveOption.SPECIAL_ONLY: True,
    ReserveOption.SPECIAL_FIRST: True,
}


class ReservationResource(Resource):
    """``korail.reservations`` — 예매·조회·취소."""

    def all(self) -> list[Reservation]:
        """결제 전 예약 목록. 없으면 빈 리스트.

        각 예약의 좌석 상세까지 채워서 돌려주므로 예약 수만큼 추가 요청이 나갑니다.
        하나만 필요하면 :meth:`find` 를 쓰세요 — 그쪽은 2회로 끝납니다.
        """
        entries = self._entries()
        return [self._complete(entry, entries) for entry in entries]

    def find(self, rsv_id: str | None) -> Reservation | None:
        """``rsv_id`` 와 일치하는 예약 하나. 없으면 ``None``.

        목록을 전부 조립하지 않고 **일치하는 예약의 좌석만** 조회합니다. 예약이
        N건이어도 찾았을 때 요청은 2회(목록 + 그 예약의 좌석)이고, 목록에 없으면
        1회에서 멈춥니다 — 전에는 모든 예약의 좌석 상세를 긁은 뒤 하나만 골라
        버려서, 예매 한 번에 요청이 N+2회 나갔습니다.
        """
        if not rsv_id:
            return None
        entries = self._entries()
        matched = next((entry for entry in entries if text(entry, "h_pnr_no") == rsv_id), None)
        return None if matched is None else self._complete(matched, entries)

    def _entries(self) -> list[dict[str, Any]]:
        """예약 목록 응답에서 예약 항목들을 평평하게 꺼냅니다. 없으면 빈 리스트."""
        payload = self._api.get(API_ENDPOINTS["myreservationview"], params=self._api.base_payload())
        try:
            self._api.check(payload)
        except NoResultsError:
            return []

        return [
            train_info
            for journey in records(payload, "jrny_infos", "jrny_info")
            for train_info in records(journey, "train_infos", "train_info")
        ]

    def _complete(self, entry: dict[str, Any], entries: list[dict[str, Any]]) -> Reservation:
        """예약 항목 하나에 좌석 상세를 붙여 완성합니다 (요청 1회).

        좌석을 나중에 주입하지 않고 여기서 미리 조회해 생성자에 넘깁니다 —
        반쯤 채워진 예약이 돌아다니면 안 됩니다 (AGENTS.md §2-3).
        """
        journeys, wct_no = self._journeys(entry.get("h_pnr_no"))
        return Reservation.from_response(
            entry,
            seats=self._seats_of(journeys, entry),
            wct_no=wct_no,
            **self._cancel_key(entry, entries),
        )

    @staticmethod
    def _cancel_key(entry: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, str]:
        """여정이 여럿인 예약을 취소할 때 되돌려 보낼 값. 여정이 하나면 빈 dict.

        취소는 예약번호 단위라 어느 구간의 예약을 넘겨도 **첫 여정의 순번과 예약의 여정 수**를
        보냅니다 — 그렇게 보내야 두 구간이 함께 취소됩니다(2026-10-13 실서버 확인). 여정이
        하나인 예약은 건드리지 않습니다. 그쪽은 예전부터 쓰던 고정값으로 취소되고 있습니다.
        """
        rsv_id = text(entry, "h_pnr_no")
        if not rsv_id:
            # 예약번호가 빈 항목끼리 서로 형제로 묶이지 않게 합니다.
            return {}
        siblings = [other for other in entries if text(other, "h_pnr_no") == rsv_id]
        if len(siblings) < _TRANSFER_LEGS:
            return {}
        # 목록의 순서에 기대지 않고 순번이 가장 앞선 여정을 첫 여정으로 봅니다.
        first = min(siblings, key=lambda other: text(other, "h_jrny_sqno"))
        return {
            "journey_no": text(first, "h_jrny_sqno") or "0001",
            "journey_cnt": f"{len(siblings):04d}",
            "rsv_chg_no": text(first, "h_rsv_chg_no") or "000",
        }

    def seats(self, rsv_id: str | None = None) -> tuple[list[Seat], str | None]:
        """예약의 좌석 상세와 발매창구 번호(``wct_no``).

        조회 결과가 없으면 ``([], None)`` 을 돌려줍니다 — 호출부가 항상 튜플로
        풀 수 있어야 하므로 실패해도 모양을 유지합니다. 환승 예약처럼 여정이 여럿이면
        **첫 여정의 좌석**입니다 — 구간별 좌석은 :meth:`all` 이 돌려주는 예약에 있습니다.
        """
        journeys, wct_no = self._journeys(rsv_id)
        if not journeys:
            return [], wct_no

        return [Seat.from_response(seat) for seat in records(journeys[0], "seat_infos", "seat_info")], wct_no

    def _journeys(self, rsv_id: str | None) -> tuple[list[dict[str, Any]], str | None]:
        """예약 상세의 여정들과 발매창구 번호. 결과가 없으면 ``([], None)``."""
        payload = self._api.get(
            API_ENDPOINTS["myreservationlist"],
            params={**self._api.base_payload(), "hidPnrNo": rsv_id},
        )
        try:
            self._api.check(payload)
        except NoResultsError:
            return [], None

        return records(payload, "jrny_infos", "jrny_info"), payload.get("h_wct_no")

    @staticmethod
    def _seats_of(journeys: list[dict[str, Any]], entry: dict[str, Any]) -> tuple[Seat, ...]:
        """예약 항목 하나에 해당하는 여정의 좌석.

        환승 예약은 예약번호 하나에 여정이 둘이고, 목록의 항목과 상세의 여정이 같은
        여정 번호(``h_jrny_sqno``)를 가집니다. 번호가 없거나 맞는 여정이 없으면 첫 여정을
        씁니다 — 여정이 하나뿐인 보통 예약은 늘 그쪽입니다.
        """
        sequence = text(entry, "h_jrny_sqno")
        matched = next((j for j in journeys if sequence and text(j, "h_jrny_sqno") == sequence), None)
        journey = matched if matched is not None else next(iter(journeys), None)
        if journey is None:
            return ()
        return tuple(Seat.from_response(seat) for seat in records(journey, "seat_infos", "seat_info"))

    def create(
        self,
        train: Train,
        passengers: Sequence[Passenger] | None = None,
        option: ReserveOptionCode = ReserveOption.GENERAL_FIRST,
    ) -> Reservation:
        """열차를 예매합니다. 좌석이 없고 예약대기가 열려 있으면 대기를 겁니다.

        Raises:
            KorailError: 서버가 예매를 거부했거나(매진 등), 예매 후 예약을 다시
                조회하지 못했습니다.
        """
        if train.has_seat() or train.wait_reserve_flag < 0:
            reserving_seat = True
            is_special_seat = _SEATED_PREFERS_SPECIAL[option](train)
        else:
            # 좌석이 없고 예약대기가 열려 있는 열차 — 대기를 겁니다.
            reserving_seat = False
            is_special_seat = _WAITING_PREFERS_SPECIAL[option]

        reduced = Passenger.reduce(passengers or [AdultPassenger()])
        total_count = sum(p.count for p in reduced)

        url = API_ENDPOINTS["reserve"]
        headers, _ = self._api.sign(url)
        data = {
            **self._api.base_payload(),
            "txtMenuId": "11",
            "txtJobId": "1101" if reserving_seat else "1102",
            "txtGdNo": "",
            "hidFreeFlg": "N",
            "txtTotPsgCnt": total_count,
            "txtSeatAttCd1": "000",
            "txtSeatAttCd2": "000",
            "txtSeatAttCd3": "000",
            "txtSeatAttCd4": "015",
            "txtSeatAttCd5": "000",
            "txtStndFlg": "N",
            "txtSrcarCnt": "0",
            "txtJrnyCnt": "1",
            "txtJrnySqno1": "001",
            "txtJrnyTpCd1": "11",
            "txtDptDt1": train.dep_date,
            "txtDptRsStnCd1": train.dep_code,
            "txtDptTm1": train.dep_time,
            "txtArvRsStnCd1": train.arr_code,
            "txtTrnNo1": train.train_no,
            "txtRunDt1": train.run_date,
            "txtTrnClsfCd1": train.train_type,
            "txtTrnGpCd1": train.train_group,
            "txtPsrmClCd1": "2" if is_special_seat else "1",
            "txtChgFlg1": "",
            # 편도 예매라 2번째 여정 필드는 비워 보냅니다 (폼이 존재 자체를 요구합니다).
            "txtJrnySqno2": "",
            "txtJrnyTpCd2": "",
            "txtDptDt2": "",
            "txtDptRsStnCd2": "",
            "txtDptTm2": "",
            "txtArvRsStnCd2": "",
            "txtTrnNo2": "",
            "txtRunDt2": "",
            "txtTrnClsfCd2": "",
            "txtPsrmClCd2": "",
            "txtChgFlg2": "",
        }
        for index, passenger in enumerate(reduced, 1):
            data.update(passenger.get_dict(index))

        payload = self._api.get(url, params=data, headers=headers)
        self._api.check(payload)

        return self._reserved(payload)

    def create_with_seats(
        self,
        train: Train,
        seats: Iterable[CarSeat],
        passengers: Sequence[Passenger] | None = None,
    ) -> Reservation:
        """고른 좌석으로 열차를 예매합니다.

        좌석은 :meth:`TrainResource.seats <pykorail.resources.trains.TrainResource.seats>`
        가 돌려준 것을 넘깁니다. 객실(일반실 · 특실)은 좌석에 붙어 있어 따로 넘기지 않습니다.

        요청은 코레일+ 7.0.8 의 ``TicketReservationIn`` 을 폼으로 펼친 모양입니다 —
        :meth:`create` 의 폼과는 다릅니다. 앱의 좌석 선택 화면이 작업 구분을 좌석 지정으로
        두고 고른 좌석을 호차 번호 · 좌석 식별자 쌍으로 싣습니다.

        Args:
            train: :meth:`TrainResource.search <pykorail.resources.trains.TrainResource.search>`
                가 돌려준 열차.
            seats: 예매할 좌석. **승객 한 명에 하나씩**이어야 하고, 전부 같은 객실이어야 합니다.
                호차는 서로 달라도 됩니다.
            passengers: 생략하면 어른 1명.

        Raises:
            TypeError: 좌석이 아닌 것을 넘겼습니다.
            ValueError: 좌석 수가 승객 수와 다르거나, 같은 좌석을 두 번 넘겼거나, 객실이
                섞였거나, 열차에 예매에 필요한 값이 없습니다. 요청 전에 막습니다.
            KorailError: 서버가 예매를 거부했거나(이미 팔린 좌석 등), 예매 후 예약을 다시
                조회하지 못했습니다.
        """
        # 제너레이터도 받습니다. 그대로 두면 타입 검사가 한 번 돌며 다 써 버리고, 이어지는
        # len() 이 "CarSeat 를 넘기라" 대신 알 수 없는 TypeError 를 냅니다.
        seats = tuple(seats)
        reduced = Passenger.reduce(passengers or [AdultPassenger()])
        total_count = sum(p.count for p in reduced)
        seat_class = self._seat_class_of(seats, total_count)

        journey = self._journey_of(train, "좌석 지정 예매")

        url = API_ENDPOINTS["reserve"]
        # 서명은 붙이되 Sid 는 싣지 않습니다 (앱의 요청 모델에 Sid 가 없습니다).
        headers, _ = self._api.sign(url, include_sid=False)
        # 필드의 순서는 앱이 요청 모델을 펼치는 순서입니다: 공통 → 예매 → 승객 → 여정 → 좌석.
        form: dict[str, Any] = {
            **self._api.common_payload(),
            "txtMenuId": "11",
            "txtJobId": _JOB_SEAT_DESIGNATED,
            "hidFreeFlg": "N",
            "txtStndFlg": "N",
            "txtTotPsgCnt": str(total_count),
            "txtSeatAttCd1": "000",
            "txtSeatAttCd2": "000",
            "txtSeatAttCd3": "000",
            # 좌석 속성은 고른 좌석이 아니라 **열차 행**의 값입니다. 좌석 선택 화면은
            # 조회가 넘긴 TicketReservationIn 을 복사하면서 작업 구분 · 좌석 목록만
            # 바꾸므로, 여기서도 행의 값을 그대로 싣고 비면 좌석 종류의 기본값을 씁니다.
            "txtSeatAttCd4": train.seat_attribute or _DEFAULT_SEAT_ATTRIBUTE,
            "txtSeatAttCd5": "000",
            "txtJrnyCnt": "1",
            # 호차 수가 아니라 고른 **좌석** 수입니다.
            "txtSrcarCnt": str(len(seats)),
        }
        form.update(self._passenger_blocks(reduced))
        form.update(self._journey_block(journey, 1, _JOURNEY_DIRECT, seat_class))
        for index, seat in enumerate(seats, 1):
            # 서버가 준 호차 번호("0003")와 좌석 식별자("57")를 그대로 돌려보냅니다.
            form[f"txtSrcarNo{index}"] = seat.car_no
            form[f"txtSeatNo{index}"] = seat.seat_no

        payload = self._api.post(url, data=without_blanks(form), headers=headers)
        self._api.check(payload)

        return self._reserved(payload)

    def create_transfer(
        self,
        transfer: Transfer,
        passengers: Sequence[Passenger] | None = None,
        *,
        seat_class: SeatClassCode = SeatClass.GENERAL,
    ) -> tuple[Reservation, Reservation]:
        """환승 여정의 두 구간을 한 번에 예매합니다.

        구간을 따로 예매하면 첫 구간만 잡히고 둘째가 매진될 수 있습니다. 이 요청은 두
        구간을 예약번호 하나로 묶어 잡습니다. 좌석은 서버가 정합니다.

        요청은 코레일+ 7.0.8 의 ``TicketReservationIn`` 을 폼으로 펼친 모양입니다. 앱의
        환승 예매가 두 구간을 여정 목록에 차례로 싣고, 구간마다 그 열차 행의 좌석 속성을
        함께 보냅니다.

        Args:
            transfer: :meth:`TrainResource.search_transfers
                <pykorail.resources.trains.TrainResource.search_transfers>` 가 돌려준 여정.
            passengers: 생략하면 어른 1명.
            seat_class: 두 구간에 함께 적용할 객실. 기본은 일반실.

        Returns:
            타는 순서대로 **구간마다 하나씩**, 예약 둘. 둘은 예약번호(``rsv_id``)가 같고,
            각자 그 구간의 열차와 좌석을 가집니다. :meth:`cancel` 에는 둘 중 어느 것을
            넘겨도 **예약 전체**가 취소됩니다. ``price`` 는 구간의 금액이 아니라 예약
            전체의 금액이라 둘을 더하면 안 됩니다.

        Raises:
            TypeError: 환승 여정이 아닌 것을 넘겼습니다.
            ValueError: 구간이 둘이 아니거나, 승객이 없거나, 열차에 예매에 필요한 값이
                없습니다. 요청 전에 막습니다.
            KorailError: 서버가 예매를 거부했거나(한 구간이라도 매진 등), 예매 후 예약의
                두 구간을 다시 조회하지 못했습니다. 뒤의 경우 예약은 만들어져 있고
                메시지에 예약번호가 실립니다.
        """
        if not isinstance(transfer, Transfer):
            # 열차 한 편을 넘기면 legs 가 없다는 속성 오류로는 원인을 알기 어렵습니다.
            raise TypeError("transfer 에는 trains.search_transfers() 가 돌려준 Transfer 를 넘기세요")
        if len(transfer.legs) != _TRANSFER_LEGS:
            # 앱은 두 편까지만 싣습니다. 셋 이상을 같은 방식으로 늘려 보내는 것은 추측입니다.
            raise ValueError(f"환승 예매는 두 구간 여정만 됩니다: {len(transfer.legs)}구간")
        reduced = Passenger.reduce(passengers or [AdultPassenger()])
        total_count = sum(p.count for p in reduced)
        if total_count < 1:
            raise ValueError("승객이 한 명 이상이어야 합니다")
        leading, trailing = transfer.legs
        first, second = self._journey_of(leading, "환승 예매"), self._journey_of(trailing, "환승 예매")

        url = API_ENDPOINTS["reserve"]
        # 서명은 붙이되 Sid 는 싣지 않습니다 (앱의 요청 모델에 Sid 가 없습니다).
        headers, _ = self._api.sign(url, include_sid=False)
        # 필드의 순서는 앱이 요청 모델을 펼치는 순서입니다: 공통 → 예매 → 승객 → 여정 둘.
        form: dict[str, Any] = {
            **self._api.common_payload(),
            "txtMenuId": "11",
            "txtJobId": _JOB_DEFAULT,
            "hidFreeFlg": "N",
            "txtStndFlg": "N",
            "txtTotPsgCnt": str(total_count),
            "txtSeatAttCd1": "000",
            "txtSeatAttCd2": "000",
            "txtSeatAttCd3": "000",
            # 좌석 속성은 구간마다 따로입니다. 첫 구간이 4, 둘째 구간이 4_1 입니다.
            "txtSeatAttCd4": leading.seat_attribute or _DEFAULT_SEAT_ATTRIBUTE,
            "txtSeatAttCd5": "000",
            "txtSeatAttCd4_1": trailing.seat_attribute or _DEFAULT_SEAT_ATTRIBUTE,
            "txtJrnyCnt": str(_TRANSFER_LEGS),
        }
        form.update(self._passenger_blocks(reduced))
        form.update(self._journey_block(first, 1, _JOURNEY_TRANSFER, seat_class))
        form.update(self._journey_block(second, 2, _JOURNEY_TRANSFER, seat_class))

        payload = self._api.post(url, data=without_blanks(form), headers=headers)
        self._api.check(payload)

        rsv_id = payload.get("h_pnr_no")
        entries = [entry for entry in self._entries() if rsv_id and text(entry, "h_pnr_no") == rsv_id]
        if not entries:
            raise self._lost(rsv_id)
        if len(entries) != _TRANSFER_LEGS:
            # 구간이 둘이 아니면 어느 항목이 어느 구간인지 말할 수 없습니다. 예약은 이미
            # 만들어져 있으니 예약번호를 실어 알립니다 — 조용히 하나만 돌려주지 않습니다.
            raise KorailError(
                f"예매는 성공했지만 예약({rsv_id})에서 구간 {_TRANSFER_LEGS}개를 찾지 못했습니다: {len(entries)}개"
            )
        # 구간마다 좌석 상세를 따로 조회하지 않고 한 번 받아 여정 번호로 나눕니다.
        journeys, wct_no = self._journeys(rsv_id)
        # 타는 순서는 목록의 순서가 아니라 여정 순번입니다.
        first, second = (
            Reservation.from_response(
                entry,
                seats=self._seats_of(journeys, entry),
                wct_no=wct_no,
                **self._cancel_key(entry, entries),
            )
            for entry in sorted(entries, key=lambda entry: text(entry, "h_jrny_sqno"))
        )
        return first, second

    @staticmethod
    def _journey_of(train: Train, what: str) -> dict[str, str]:
        """예매 폼에 실을 열차의 값들. 하나라도 비면 요청 전에 멈춥니다.

        값이 비면 without_blanks 가 그 칸을 통째로 빼서 다른 요청이 됩니다. 실제 좌석이
        걸린 요청이라 넘겨짚지 않습니다. 이름은 사용자가 아는 Train 의 속성입니다.
        """
        journey = {
            "train_no": train.train_no,
            "train_type": train.train_type,
            "train_group": train.train_group,
            "run_date": train.run_date,
            "dep_date": train.dep_date,
            "dep_time": train.dep_time,
            "dep_code": train.dep_code,
            "dep_cons_order": train.dep_cons_order,
            "dep_run_order": train.dep_run_order,
            "arr_code": train.arr_code,
            "arr_cons_order": train.arr_cons_order,
            "arr_run_order": train.arr_run_order,
        }
        missing = sorted(name for name, value in journey.items() if not value)
        if missing:
            raise ValueError(f"{what}에 필요한 값이 열차에 없습니다: {', '.join(missing)}")
        return journey

    @staticmethod
    def _passenger_blocks(reduced: Sequence[Passenger]) -> dict[str, Any]:
        """승객 종류마다 한 묶음. 번호는 1 부터 붙습니다."""
        blocks: dict[str, Any] = {}
        for index, passenger in enumerate(reduced, 1):
            blocks[f"txtCompaCnt{index}"] = str(passenger.count)
            blocks[f"txtPsgTpCd{index}"] = passenger.typecode
            blocks[f"txtDiscKndCd{index}"] = passenger.discount_type
            blocks[f"txtCardNo_{index}"] = passenger.card_no
        return blocks

    @staticmethod
    def _journey_block(journey: dict[str, str], index: int, journey_type: str, seat_class: str) -> dict[str, str]:
        """여정 하나의 필드 묶음. ``index`` 가 필드 이름 끝의 번호이자 여정 순번입니다."""
        return {
            f"txtJrnyTpCd{index}": journey_type,
            f"txtJrnySqno{index}": f"{index:03d}",
            # 열차번호는 조회가 준 그대로입니다. 앱도 가공하지 않습니다.
            f"txtTrnNo{index}": journey["train_no"],
            f"txtTrnClsfCd{index}": journey["train_type"],
            f"txtTrnGpCd{index}": journey["train_group"],
            f"txtRunDt{index}": journey["run_date"],
            f"txtDptDt{index}": journey["dep_date"],
            f"txtDptTm{index}": journey["dep_time"],
            f"txtDptRsStnCd{index}": journey["dep_code"],
            f"txtDptStnConsOrdr{index}": journey["dep_cons_order"],
            f"txtDptStnRunOrdr{index}": journey["dep_run_order"],
            f"txtArvRsStnCd{index}": journey["arr_code"],
            f"txtArvStnConsOrdr{index}": journey["arr_cons_order"],
            f"txtArvStnRunOrdr{index}": journey["arr_run_order"],
            f"txtChgFlg{index}": "N",
            f"txtPsrmClCd{index}": seat_class,
        }

    @staticmethod
    def _seat_class_of(seats: Sequence[CarSeat], total_count: int) -> str:
        """고른 좌석들을 검사하고 그 객실 구분 코드를 돌려줍니다."""
        if not all(isinstance(seat, CarSeat) for seat in seats):
            # 배정 좌석(Seat)처럼 이름이 비슷한 것을 넘기면 속성 오류로는 원인을 알기 어렵습니다.
            raise TypeError("seats 에는 trains.seats() 가 돌려준 CarSeat 를 넘기세요")
        if total_count < 1:
            # 인원이 0 인 승객만 넘기면 합쳐지며 전부 버려집니다. 좌석 0개와 맞아떨어져
            # 아래 검사를 지나치지 않게 먼저 막습니다.
            raise ValueError("승객이 한 명 이상이어야 합니다")
        if len(seats) != total_count:
            raise ValueError(f"좌석은 승객 한 명에 하나씩 넘기세요: 좌석 {len(seats)}개, 승객 {total_count}명")
        if len({(seat.car_no, seat.seat_no) for seat in seats}) != len(seats):
            raise ValueError("같은 좌석을 두 번 넘겼습니다")
        if any(not seat.car_no or not seat.seat_no for seat in seats):
            raise ValueError("호차 번호나 좌석 식별자가 빈 좌석이 있습니다")
        classes = {seat.seat_class for seat in seats}
        if len(classes) != 1 or "" in classes:
            raise ValueError(f"좌석은 전부 같은 객실이어야 합니다: {sorted(classes)}")
        return classes.pop()

    def _reserved(self, payload: dict[str, Any]) -> Reservation:
        """예매 응답의 예약번호로 예약을 다시 조회해 돌려줍니다."""
        rsv_id = payload.get("h_pnr_no")
        reservation = self.find(rsv_id)
        if reservation is None:
            raise self._lost(rsv_id)
        return reservation

    @staticmethod
    def _lost(rsv_id: Any) -> KorailError:
        """예매는 됐는데 목록에서 그 예약을 찾지 못했을 때의 예외. 성공한 척 넘어가지 않습니다."""
        return KorailError(f"예매는 성공했지만 예약({rsv_id})을 다시 조회하지 못했습니다")

    def pay(self, reservation: Reservation, card: Card) -> None:
        """신용카드로 결제해 예약을 승차권으로 확정합니다.

        Args:
            reservation: 결제할 예약. :attr:`~pykorail.models.reservation.Reservation.wct_no`
                가 채워져 있어야 합니다 (:meth:`all`/:meth:`find` 가 채워 줍니다).
            card: 결제 수단 (:class:`~pykorail.models.card.Card`).

        Raises:
            KorailError: 결제가 거부됐습니다.
        """
        if not isinstance(reservation, Reservation):
            raise TypeError("reservation must be a Reservation instance")
        if not isinstance(card, Card):
            raise TypeError("card must be a Card instance")

        payload = self._api.post(
            API_ENDPOINTS["pay"],
            data={
                **self._api.base_payload(),
                "hidPnrNo": reservation.rsv_id,
                "hidWctNo": reservation.wct_no,
                "hidTmpJobSqno1": "000000",
                "hidTmpJobSqno2": "000000",
                "hidRsvChgNo": "000",
                "hidInrecmnsGridcnt": "1",
                "hidStlMnsSqno1": "1",
                "hidStlMnsCd1": "02",
                "hidMnsStlAmt1": str(reservation.price),
                "hidCrdInpWayCd1": "@",
                "hidStlCrCrdNo1": card.number,
                "hidVanPwd1": card.password,
                "hidCrdVlidTrm1": card.expire,
                "hidIsmtMnthNum1": card.installment,
                "hidAthnDvCd1": card.auth_type,
                "hidAthnVal1": card.verify_number,
                "hiduserYn": "Y",
            },
        )
        self._api.check(payload)

    def cancel(self, reservation: Reservation) -> None:
        """예약을 취소합니다.

        취소는 예약번호 단위입니다. 환승 예약은 어느 구간의 예약을 넘겨도 두 구간이 함께
        취소됩니다.

        Raises:
            KorailError: 서버가 취소를 거부했습니다.
        """
        if not isinstance(reservation, Reservation):
            raise TypeError("reservation must be a Reservation instance")

        payload = self._api.post(
            API_ENDPOINTS["cancel"],
            data={
                **self._api.base_payload(),
                "txtPnrNo": reservation.rsv_id,
                "txtJrnySqno": reservation.journey_no,
                "txtJrnyCnt": reservation.journey_cnt,
                "hidRsvChgNo": reservation.rsv_chg_no,
            },
        )
        self._api.check(payload)
