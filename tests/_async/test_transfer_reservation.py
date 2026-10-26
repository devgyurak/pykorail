"""환승 여정의 예매 — ``reservations.create_transfer``."""

from __future__ import annotations

import dataclasses

import pytest

from pykorail.exceptions import KorailError, SoldOutError
from pykorail.models import AdultPassenger, ChildPassenger, Seat, Transfer
from pykorail.options import SeatClass
from tests.payloads import (
    FIRST_LEG_SEAT_INFO,
    RESERVABLE_FIRST_LEG_INFO,
    RESERVABLE_SECOND_LEG_INFO,
    RESERVABLE_TRANSFER_SEARCH_PAYLOAD,
    RESERVATION_LIST_PAYLOAD,
    RESERVE_OK,
    SEAT_DETAIL_PAYLOAD,
    SEAT_INFO,
    SECOND_LEG_SEAT_INFO,
    STATION_PAYLOAD,
    TRANSFER_RESERVATION_ENTRIES,
    TRANSFER_RESERVATION_LIST_PAYLOAD,
    TRANSFER_SEAT_DETAIL_PAYLOAD,
)

ROUTES = {
    "stationdata": STATION_PAYLOAD,
    "search_schedule": RESERVABLE_TRANSFER_SEARCH_PAYLOAD,
    "reserve": RESERVE_OK,
    "myreservationview": TRANSFER_RESERVATION_LIST_PAYLOAD,
    "myreservationlist": TRANSFER_SEAT_DETAIL_PAYLOAD,
}

#: 서버가 구간을 거꾸로 실어 준 목록. 본 적은 없지만, 순서에 기대면 그날 조용히 틀립니다.
REVERSED_LIST_PAYLOAD = {
    "strResult": "SUCC",
    "jrny_infos": {"jrny_info": [{"train_infos": {"train_info": TRANSFER_RESERVATION_ENTRIES[::-1]}}]},
}

#: 여정 하나가 차지하는 필드. 뒤에 여정 번호(1 · 2)가 붙습니다.
JOURNEY_FIELDS = [
    "txtJrnyTpCd",
    "txtJrnySqno",
    "txtTrnNo",
    "txtTrnClsfCd",
    "txtTrnGpCd",
    "txtRunDt",
    "txtDptDt",
    "txtDptTm",
    "txtDptRsStnCd",
    "txtDptStnConsOrdr",
    "txtDptStnRunOrdr",
    "txtArvRsStnCd",
    "txtArvStnConsOrdr",
    "txtArvStnRunOrdr",
    "txtChgFlg",
    "txtPsrmClCd",
]

#: 어른 한 명의 환승 예매. 7.0.8 실서버에서 성공이 기록된 요청의 필드 구성 · 순서와 같습니다.
FORM_FIELDS = [
    "Device",
    "Version",
    "AppVersion",
    "Key",
    "txtMenuId",
    "txtJobId",
    "hidFreeFlg",
    "txtStndFlg",
    "txtTotPsgCnt",
    "txtSeatAttCd1",
    "txtSeatAttCd2",
    "txtSeatAttCd3",
    "txtSeatAttCd4",
    "txtSeatAttCd5",
    "txtSeatAttCd4_1",
    "txtJrnyCnt",
    "txtCompaCnt1",
    "txtPsgTpCd1",
    "txtDiscKndCd1",
    *(f"{name}1" for name in JOURNEY_FIELDS),
    *(f"{name}2" for name in JOURNEY_FIELDS),
]


@pytest.fixture
async def found(make_korail):
    """클라이언트, 가짜 세션, 조회한 환승 여정 하나."""
    client, session = make_korail(ROUTES)
    return client, session, (await client.trains.search_transfers("서울", "부산"))[0]


class TestCreateTransfer:
    async def test_returns_one_reservation_per_leg(self, found) -> None:
        """예약번호는 하나이고, 구간마다 그 구간의 열차를 가진 예약이 하나씩 옵니다."""
        # given
        client, _, transfer = found

        # when
        reservations = await client.reservations.create_transfer(transfer)

        # then
        assert [(r.pnr_no, r.train.train_no, r.train.dep_name, r.train.arr_name) for r in reservations] == [
            ("1234567890", "101", "서울", "대전"),
            ("1234567890", "1201", "대전", "부산"),
        ]

    async def test_each_leg_carries_its_own_seats(self, found) -> None:
        """상세의 여정을 여정 번호로 맞춥니다. 둘째 구간이 첫 구간의 좌석을 들고 오면 안 됩니다."""
        # given
        client, _, transfer = found

        # when
        first, second = await client.reservations.create_transfer(transfer)

        # then
        assert (first.seats, second.seats) == (
            (Seat.from_response(FIRST_LEG_SEAT_INFO),),
            (Seat.from_response(SECOND_LEG_SEAT_INFO),),
        )

    async def test_returns_exactly_two(self, found) -> None:
        """구간이 둘인 여정만 받으니 결과도 늘 둘입니다. 길이를 말하는 타입으로 돌려줍니다."""
        # given
        client, _, transfer = found

        # when
        reservations = await client.reservations.create_transfer(transfer)

        # then
        assert (type(reservations), len(reservations)) == (tuple, 2)

    async def test_legs_come_in_riding_order_even_if_the_list_is_reversed(self, make_korail) -> None:
        """타는 순서는 목록의 순서가 아니라 여정 순번입니다."""
        # given
        client, _ = make_korail({**ROUTES, "myreservationview": REVERSED_LIST_PAYLOAD})
        transfer = (await client.trains.search_transfers("서울", "부산"))[0]

        # when
        first, second = await client.reservations.create_transfer(transfer)

        # then
        assert (first.train.train_no, second.train.train_no) == ("101", "1201")

    async def test_looks_the_seat_detail_up_once_for_both_legs(self, found) -> None:
        # given
        client, session, transfer = found

        # when
        await client.reservations.create_transfer(transfer)

        # then
        assert len(session.all_kwargs_for("myreservationlist")) == 1, "구간마다 따로 조회하지 않습니다"

    async def test_sends_exact_form_fields_in_the_app_order(self, found) -> None:
        """실제 좌석 둘이 걸린 요청입니다. 필드가 하나 빠지거나 늘면 다른 요청이 됩니다."""
        # given
        client, session, transfer = found

        # when
        await client.reservations.create_transfer(transfer)

        # then
        assert list(session.kwargs_for("reserve")["data"]) == FORM_FIELDS

    async def test_asks_for_an_ordinary_reservation_of_two_journeys(self, found) -> None:
        """좌석 지정이 아니라 서버가 좌석을 정하는 보통 예매이고, 여정이 둘입니다."""
        # given
        client, session, transfer = found

        # when
        await client.reservations.create_transfer(transfer)

        # then
        data = session.kwargs_for("reserve")["data"]
        sent = {key: data[key] for key in FORM_FIELDS[4:16]}
        assert sent == {
            "txtMenuId": "11",
            "txtJobId": "1101",
            "hidFreeFlg": "N",
            "txtStndFlg": "N",
            "txtTotPsgCnt": "1",
            "txtSeatAttCd1": "000",
            "txtSeatAttCd2": "000",
            "txtSeatAttCd3": "000",
            "txtSeatAttCd4": "015",
            "txtSeatAttCd5": "000",
            "txtSeatAttCd4_1": "019",
            "txtJrnyCnt": "2",
        }

    async def test_seat_attribute_is_sent_per_leg(self, found) -> None:
        """첫 구간은 ``txtSeatAttCd4``, 둘째 구간은 ``txtSeatAttCd4_1`` — 각자 그 열차 행의 값입니다."""
        # given
        client, session, transfer = found

        # when
        await client.reservations.create_transfer(transfer)

        # then
        data = session.kwargs_for("reserve")["data"]
        assert (data["txtSeatAttCd4"], data["txtSeatAttCd4_1"]) == (
            RESERVABLE_FIRST_LEG_INFO["h_seat_att_cd"],
            RESERVABLE_SECOND_LEG_INFO["h_seat_att_cd"],
        )

    async def test_blank_seat_attribute_falls_back_to_the_ordinary_seat(self, found) -> None:
        """앱도 행의 좌석 속성이 비면 좌석 종류의 기본값을 씁니다."""
        # given
        client, session, transfer = found
        legs = tuple(dataclasses.replace(leg, seat_attribute="") for leg in transfer.legs)

        # when
        await client.reservations.create_transfer(Transfer(legs=legs))

        # then
        data = session.kwargs_for("reserve")["data"]
        assert (data["txtSeatAttCd4"], data["txtSeatAttCd4_1"]) == ("015", "015")

    async def test_sends_both_legs_in_riding_order(self, found) -> None:
        """여정 종류는 환승, 순번은 001 · 002, 열차 값은 조회가 준 그대로입니다."""
        # given
        client, session, transfer = found

        # when
        await client.reservations.create_transfer(transfer)

        # then
        data = session.kwargs_for("reserve")["data"]
        keys = ("txtJrnyTpCd", "txtJrnySqno", "txtTrnNo", "txtDptRsStnCd", "txtArvRsStnCd", "txtChgFlg", "txtPsrmClCd")
        assert [tuple(data[f"{key}{n}"] for key in keys) for n in (1, 2)] == [
            ("14", "001", "101", "0001", "0015", "N", "1"),
            ("14", "002", "1201", "0015", "0020", "N", "1"),
        ]

    async def test_sends_each_leg_its_own_section_orders(self, found) -> None:
        # given
        client, session, transfer = found

        # when
        await client.reservations.create_transfer(transfer)

        # then
        data = session.kwargs_for("reserve")["data"]
        keys = ("txtDptStnConsOrdr", "txtDptStnRunOrdr", "txtArvStnConsOrdr", "txtArvStnRunOrdr")
        assert [tuple(data[f"{key}{n}"] for key in keys) for n in (1, 2)] == [
            ("000001", "000001", "000012", "000005"),
            ("000012", "000007", "000040", "000021"),
        ]

    async def test_special_class_applies_to_both_legs(self, found) -> None:
        # given
        client, session, transfer = found

        # when
        await client.reservations.create_transfer(transfer, seat_class=SeatClass.SPECIAL)

        # then
        data = session.kwargs_for("reserve")["data"]
        assert (data["txtPsrmClCd1"], data["txtPsrmClCd2"]) == ("2", "2")

    async def test_sends_one_block_per_kind_of_passenger(self, found) -> None:
        # given
        client, session, transfer = found

        # when
        await client.reservations.create_transfer(transfer, [AdultPassenger(2), ChildPassenger(1)])

        # then
        data = session.kwargs_for("reserve")["data"]
        sent = {key: data[key] for key in data if key.startswith(("txtTotPsgCnt", "txtCompaCnt", "txtPsgTpCd"))}
        assert sent == {
            "txtTotPsgCnt": "3",
            "txtCompaCnt1": "2",
            "txtPsgTpCd1": "1",
            "txtCompaCnt2": "1",
            "txtPsgTpCd2": "3",
        }

    async def test_does_not_name_any_seats(self, found) -> None:
        """좌석은 서버가 정합니다. 좌석 지정 예매의 칸은 나가지 않습니다."""
        # given
        client, session, transfer = found

        # when
        await client.reservations.create_transfer(transfer)

        # then
        named = [key for key in session.kwargs_for("reserve")["data"] if key.startswith(("txtSrcar", "txtSeatNo"))]
        assert named == []

    async def test_goes_in_the_form_body_signed_without_sid(self, found) -> None:
        # given
        client, session, transfer = found

        # when
        await client.reservations.create_transfer(transfer)

        # then
        kwargs = session.kwargs_for("reserve")
        assert "params" not in kwargs
        assert "x-dynapath-m-token" in kwargs["headers"]
        assert "Sid" not in kwargs["data"]


class TestCancellingATransferReservation:
    """기존의 고정값(순번 001 · 여정 수 01)으로는 서버가 환승 예약의 취소를 거절합니다(ERR800052)."""

    @pytest.mark.parametrize("leg", [0, 1], ids=["by-the-first-leg", "by-the-second-leg"])
    async def test_cancels_the_whole_reservation_whichever_leg_is_passed(self, found, leg: int) -> None:
        """첫 여정의 순번과 예약의 여정 수를 보내야 두 구간이 함께 취소됩니다 (실서버 확인)."""
        # given
        client, session, transfer = found
        reservations = await client.reservations.create_transfer(transfer)
        session.routes["cancel"] = RESERVE_OK

        # when
        await client.reservations.cancel(reservations[leg])

        # then
        data = session.kwargs_for("cancel")["data"]
        sent = {key: data[key] for key in ("txtPnrNo", "txtJrnySqno", "txtJrnyCnt", "hidRsvChgNo")}
        assert sent == {"txtPnrNo": "1234567890", "txtJrnySqno": "0001", "txtJrnyCnt": "0002", "hidRsvChgNo": "000"}

    async def test_first_journey_is_the_lowest_sequence_not_the_first_row(self, make_korail) -> None:
        """서버가 목록의 순서를 바꿔 줘도 첫 여정의 순번(0001)을 보내야 합니다."""
        # given
        client, session = make_korail({**ROUTES, "myreservationview": REVERSED_LIST_PAYLOAD, "cancel": RESERVE_OK})
        reservation = (await client.reservations.all())[0]

        # when
        await client.reservations.cancel(reservation)

        # then
        data = session.kwargs_for("cancel")["data"]
        assert (data["txtJrnySqno"], data["txtJrnyCnt"]) == ("0001", "0002")

    async def test_rows_without_a_reservation_number_are_not_grouped_together(self, make_korail) -> None:
        """예약번호가 빈 항목 둘이 서로 형제로 묶여 환승 예약처럼 취급되면 안 됩니다."""
        # given
        blank = [{**entry, "h_pnr_no": ""} for entry in TRANSFER_RESERVATION_ENTRIES]
        listing = {"strResult": "SUCC", "jrny_infos": {"jrny_info": [{"train_infos": {"train_info": blank}}]}}
        client, _ = make_korail({**ROUTES, "myreservationview": listing})

        # when
        reservations = await client.reservations.all()

        # then
        assert [(r.journey_no, r.journey_cnt, r.rsv_chg_no) for r in reservations] == [("001", "01", "00000")] * 2

    async def test_reservations_from_the_list_cancel_the_same_way(self, make_korail) -> None:
        """예매 직후가 아니라 나중에 목록에서 받은 예약으로도 취소돼야 합니다."""
        # given
        client, session = make_korail({**ROUTES, "cancel": RESERVE_OK})
        second = (await client.reservations.all())[1]

        # when
        await client.reservations.cancel(second)

        # then
        data = session.kwargs_for("cancel")["data"]
        assert (data["txtJrnySqno"], data["txtJrnyCnt"], data["hidRsvChgNo"]) == ("0001", "0002", "000")

    async def test_found_reservation_cancels_the_same_way(self, make_korail) -> None:
        # given
        client, session = make_korail({**ROUTES, "cancel": RESERVE_OK})
        reservation = await client.reservations.find("1234567890")

        # when
        await client.reservations.cancel(reservation)

        # then
        assert session.kwargs_for("cancel")["data"]["txtJrnyCnt"] == "0002"

    async def test_ordinary_reservation_still_cancels_with_the_values_it_always_sent(self, make_korail) -> None:
        """여정이 하나인 예약은 예전부터 이 값으로 취소되고 있습니다. 건드리지 않습니다."""
        # given
        routes = {"myreservationview": RESERVATION_LIST_PAYLOAD, "myreservationlist": SEAT_DETAIL_PAYLOAD}
        client, session = make_korail({**routes, "cancel": RESERVE_OK})
        reservation = (await client.reservations.all())[0]

        # when
        await client.reservations.cancel(reservation)

        # then
        data = session.kwargs_for("cancel")["data"]
        assert (data["txtJrnySqno"], data["txtJrnyCnt"], data["hidRsvChgNo"]) == ("001", "01", "00000")

    async def test_missing_sequence_and_change_number_fall_back(self, make_korail) -> None:
        """서버가 순번이나 변경번호를 빼고 줘도 취소 요청은 만들어져야 합니다."""
        # given
        bare = [
            {k: v for k, v in leg.items() if k not in ("h_jrny_sqno", "h_rsv_chg_no")}
            for leg in TRANSFER_RESERVATION_ENTRIES
        ]
        listing = {"strResult": "SUCC", "jrny_infos": {"jrny_info": [{"train_infos": {"train_info": bare}}]}}
        client, session = make_korail({**ROUTES, "myreservationview": listing, "cancel": RESERVE_OK})
        reservation = (await client.reservations.all())[0]

        # when
        await client.reservations.cancel(reservation)

        # then
        data = session.kwargs_for("cancel")["data"]
        assert (data["txtJrnySqno"], data["txtJrnyCnt"], data["hidRsvChgNo"]) == ("0001", "0002", "000")


class TestTransferReservationAmounts:
    async def test_price_is_the_whole_reservation_on_every_leg(self, found) -> None:
        """서버는 예약 전체의 금액을 두 항목에 똑같이 싣습니다. 더하면 두 배가 됩니다."""
        # given
        client, _, transfer = found

        # when
        first, second = await client.reservations.create_transfer(transfer)

        # then
        assert (first.price, second.price) == (41500, 41500)

    async def test_per_leg_amounts_are_on_the_seats(self, found) -> None:
        # given
        client, _, transfer = found

        # when
        reservations = await client.reservations.create_transfer(transfer)

        # then
        assert [sum(seat.price for seat in r.seats) for r in reservations] == [23700, 17800]


class TestCreateTransferRefusesBeforeAnyRequest:
    """실제 좌석이 걸린 요청이라, 틀린 입력은 서버에 보내기 전에 막습니다."""

    async def test_a_single_train_is_not_a_transfer(self, found) -> None:
        # given
        client, session, transfer = found

        # when
        with pytest.raises(TypeError, match="Transfer"):
            await client.reservations.create_transfer(transfer.first)

        # then
        assert session.all_kwargs_for("reserve") == []

    async def test_three_legs_are_not_sent(self, found) -> None:
        """앱은 두 편까지만 싣습니다. 셋을 같은 방식으로 늘려 보내는 것은 추측입니다."""
        # given
        client, session, transfer = found
        three = Transfer(legs=(*transfer.legs, transfer.second))

        # when
        with pytest.raises(ValueError, match="3구간"):
            await client.reservations.create_transfer(three)

        # then
        assert session.all_kwargs_for("reserve") == []

    async def test_no_passengers_at_all(self, found) -> None:
        # given
        client, _, transfer = found

        # when & then
        with pytest.raises(ValueError, match="승객이 한 명 이상"):
            await client.reservations.create_transfer(transfer, [AdultPassenger(0)])

    @pytest.mark.parametrize("leg", [0, 1], ids=["first-leg", "second-leg"])
    @pytest.mark.parametrize("attribute", ["dep_cons_order", "arr_cons_order", "dep_run_order", "arr_run_order"])
    async def test_leg_without_the_needed_values(self, found, leg: int, attribute: str) -> None:
        """어느 구간이든 구간 순서가 비면 빈 칸으로 보내지 않고 멈춥니다."""
        # given
        client, session, transfer = found
        legs = list(transfer.legs)
        legs[leg] = dataclasses.replace(legs[leg], **{attribute: ""})

        # when
        with pytest.raises(ValueError, match=attribute):
            await client.reservations.create_transfer(Transfer(legs=tuple(legs)))

        # then
        assert session.all_kwargs_for("reserve") == []


class TestCreateTransferWhenTheServerRefuses:
    async def test_refusal_becomes_an_exception(self, make_korail) -> None:
        """한 구간이라도 매진이면 서버가 거절합니다. 한 구간만 잡힌 예약이 생기지 않습니다."""
        # given
        client, _ = make_korail({**ROUTES, "reserve": {"strResult": "FAIL", "h_msg_cd": "IRT010110"}})
        transfer = (await client.trains.search_transfers("서울", "부산"))[0]

        # when & then
        with pytest.raises(SoldOutError):
            await client.reservations.create_transfer(transfer)

    async def test_raises_when_the_reservation_cannot_be_found_afterwards(self, make_korail) -> None:
        # given
        client, _ = make_korail({**ROUTES, "reserve": {"strResult": "SUCC", "h_pnr_no": "0000000000"}})
        transfer = (await client.trains.search_transfers("서울", "부산"))[0]

        # when & then
        with pytest.raises(KorailError, match="다시 조회하지 못했습니다"):
            await client.reservations.create_transfer(transfer)

    async def test_raises_with_the_reservation_number_when_a_leg_is_missing(self, make_korail) -> None:
        """구간이 하나만 보이면 조용히 하나만 돌려주지 않습니다. 예약은 이미 있으니 번호를 알려 줍니다."""
        # given
        listing = {
            "strResult": "SUCC",
            "jrny_infos": {"jrny_info": [{"train_infos": {"train_info": TRANSFER_RESERVATION_ENTRIES[:1]}}]},
        }
        client, _ = make_korail({**ROUTES, "myreservationview": listing})
        transfer = (await client.trains.search_transfers("서울", "부산"))[0]

        # when & then
        with pytest.raises(KorailError, match=r"예약\(1234567890\)에서 구간 2개를 찾지 못했습니다: 1개"):
            await client.reservations.create_transfer(transfer)


class TestSeatsFollowTheirJourney:
    """예약 목록 · 조회도 여정 번호로 좌석을 맞춥니다 — 환승 예약의 둘째 구간이 첫 구간의 좌석을 들고 오지 않게."""

    async def test_all_gives_each_leg_its_own_seats(self, make_korail) -> None:
        # given
        client, _ = make_korail(ROUTES)

        # when
        reservations = await client.reservations.all()

        # then
        assert [[seat.seat_no for seat in r.seats] for r in reservations] == [["5A"], ["41"]]

    async def test_ordinary_reservation_still_gets_the_only_journey(self, make_korail) -> None:
        """여정 번호가 없는 보통 예약은 지금처럼 첫 여정의 좌석을 받습니다."""
        # given
        client, _ = make_korail(
            {"myreservationview": RESERVATION_LIST_PAYLOAD, "myreservationlist": SEAT_DETAIL_PAYLOAD}
        )

        # when
        reservation = (await client.reservations.all())[0]

        # then
        assert reservation.seats == (Seat.from_response(SEAT_INFO),)

    async def test_unmatched_journey_number_falls_back_to_the_first(self, make_korail) -> None:
        """목록의 여정 번호가 상세에 없으면 좌석을 비우지 않고 첫 여정으로 돌아갑니다."""
        # given
        detail = {
            **TRANSFER_SEAT_DETAIL_PAYLOAD,
            "jrny_infos": {"jrny_info": [{"h_jrny_sqno": "0009", "seat_infos": {"seat_info": [FIRST_LEG_SEAT_INFO]}}]},
        }
        client, _ = make_korail({**ROUTES, "myreservationlist": detail})

        # when
        reservations = await client.reservations.all()

        # then
        assert [[seat.seat_no for seat in r.seats] for r in reservations] == [["5A"], ["5A"]]

    async def test_car_number_given_as_a_number_is_read(self, make_korail) -> None:
        """실서버는 호차 번호를 숫자로 주기도 합니다."""
        # given
        client, _ = make_korail(ROUTES)

        # when
        second = (await client.reservations.all())[1]

        # then
        assert [(seat.car_no, seat.seat_no) for seat in second.seats] == [("2", "41")]

    async def test_public_seats_still_returns_the_first_journey(self, make_korail) -> None:
        # given
        client, _ = make_korail(ROUTES)

        # when
        seats, wct_no = await client.reservations.seats("1234567890")

        # then
        assert ([seat.seat_no for seat in seats], wct_no) == (["5A"], "0143")
