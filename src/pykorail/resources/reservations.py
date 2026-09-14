"""예약 리소스."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pykorail.constants import API_ENDPOINTS
from pykorail.exceptions import KorailError, NoResultsError
from pykorail.models.card import Card
from pykorail.models.parsing import text
from pykorail.models.passenger import AdultPassenger, Passenger
from pykorail.models.reservation import Reservation
from pykorail.models.seat import Seat
from pykorail.options import ReserveOption
from pykorail.resources.base import Resource

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pykorail.models.schedule import Train
    from pykorail.options import ReserveOptionCode

#: 좌석이 있는 열차를 예매할 때의 특실 선택 규칙. 값은 "특실을 고를지" 여부입니다.
_SEATED_PREFERS_SPECIAL = {
    ReserveOption.GENERAL_ONLY: lambda train: False,
    ReserveOption.SPECIAL_ONLY: lambda train: True,
    ReserveOption.GENERAL_FIRST: lambda train: not train.has_general_seat(),
    ReserveOption.SPECIAL_FIRST: lambda train: train.has_special_seat(),
}

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
        return [self._complete(entry) for entry in self._entries()]

    def find(self, rsv_id: str | None) -> Reservation | None:
        """``rsv_id`` 와 일치하는 예약 하나. 없으면 ``None``.

        목록을 전부 조립하지 않고 **일치하는 예약의 좌석만** 조회합니다. 예약이
        N건이어도 찾았을 때 요청은 2회(목록 + 그 예약의 좌석)이고, 목록에 없으면
        1회에서 멈춥니다 — 전에는 모든 예약의 좌석 상세를 긁은 뒤 하나만 골라
        버려서, 예매 한 번에 요청이 N+2회 나갔습니다.
        """
        if not rsv_id:
            return None
        matched = next((entry for entry in self._entries() if text(entry, "h_pnr_no") == rsv_id), None)
        return None if matched is None else self._complete(matched)

    def _entries(self) -> list[dict[str, Any]]:
        """예약 목록 응답에서 예약 항목들을 평평하게 꺼냅니다. 없으면 빈 리스트."""
        payload = self._api.get(API_ENDPOINTS["myreservationview"], params=self._api.base_payload())
        try:
            self._api.check(payload)
        except NoResultsError:
            return []

        return [
            train_info
            for journey in payload.get("jrny_infos", {}).get("jrny_info", [])
            for train_info in journey.get("train_infos", {}).get("train_info", [])
        ]

    def _complete(self, entry: dict[str, Any]) -> Reservation:
        """예약 항목 하나에 좌석 상세를 붙여 완성합니다 (요청 1회).

        좌석을 나중에 주입하지 않고 여기서 미리 조회해 생성자에 넘깁니다 —
        반쯤 채워진 예약이 돌아다니면 안 됩니다 (AGENTS.md §2-3).
        """
        seats, wct_no = self.seats(entry.get("h_pnr_no"))
        return Reservation.from_response(entry, seats=tuple(seats), wct_no=wct_no)

    def seats(self, rsv_id: str | None = None) -> tuple[list[Seat], str | None]:
        """예약의 좌석 상세와 발매창구 번호(``wct_no``).

        조회 결과가 없으면 ``([], None)`` 을 돌려줍니다 — 호출부가 항상 튜플로
        풀 수 있어야 하므로 실패해도 모양을 유지합니다.
        """
        payload = self._api.get(
            API_ENDPOINTS["myreservationlist"],
            params={**self._api.base_payload(), "hidPnrNo": rsv_id},
        )
        try:
            self._api.check(payload)
        except NoResultsError:
            return [], None

        wct_no = payload.get("h_wct_no")
        journeys = payload.get("jrny_infos", {}).get("jrny_info", [])
        if not journeys:
            return [], wct_no

        seat_info = journeys[0].get("seat_infos", {}).get("seat_info", [])
        return [Seat.from_response(seat) for seat in seat_info], wct_no

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

        rsv_id = payload.get("h_pnr_no")
        reservation = self.find(rsv_id)
        if reservation is None:
            raise KorailError(f"예매는 성공했지만 예약({rsv_id})을 다시 조회하지 못했습니다")
        return reservation

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
