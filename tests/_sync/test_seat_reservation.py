# 이 파일은 생성물입니다 — 직접 고치지 마세요.
# 원본: tests/_async/test_seat_reservation.py
# 다시 만들려면: uv run python scripts/unasync.py
"""좌석을 지정한 예매 — ``reservations.create_with_seats``."""

from __future__ import annotations

import dataclasses

import pytest

from pykorail.exceptions import KorailError, SoldOutError
from pykorail.models import AdultPassenger, ChildPassenger, Seat
from pykorail.options import SeatClass
from tests.payloads import (
    RESERVATION_LIST_PAYLOAD,
    RESERVE_OK,
    SEAT_CARS_PAYLOAD,
    SEAT_DETAIL_PAYLOAD,
    SEAT_INFO,
    SEAT_MAP_PAYLOAD,
    SEATABLE_SEARCH_PAYLOAD,
    STATION_PAYLOAD,
)

ROUTES = {
    "stationdata": STATION_PAYLOAD,
    "search_schedule": SEATABLE_SEARCH_PAYLOAD,
    "seat_cars": SEAT_CARS_PAYLOAD,
    "seat_map": SEAT_MAP_PAYLOAD,
    "reserve": RESERVE_OK,
    "myreservationview": RESERVATION_LIST_PAYLOAD,
    "myreservationlist": SEAT_DETAIL_PAYLOAD,
}

#: 어른 한 명이 좌석 하나를 고른 요청. 7.0.8 실서버에서 성공이 기록된 요청의 필드 구성 · 순서와 같습니다.
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
    "txtJrnyCnt",
    "txtSrcarCnt",
    "txtCompaCnt1",
    "txtPsgTpCd1",
    "txtDiscKndCd1",
    "txtJrnyTpCd1",
    "txtJrnySqno1",
    "txtTrnNo1",
    "txtTrnClsfCd1",
    "txtTrnGpCd1",
    "txtRunDt1",
    "txtDptDt1",
    "txtDptTm1",
    "txtDptRsStnCd1",
    "txtDptStnConsOrdr1",
    "txtDptStnRunOrdr1",
    "txtArvRsStnCd1",
    "txtArvStnConsOrdr1",
    "txtArvStnRunOrdr1",
    "txtChgFlg1",
    "txtPsrmClCd1",
    "txtSrcarNo1",
    "txtSeatNo1",
]


@pytest.fixture
def chosen(make_korail):
    """로그인한 클라이언트, 가짜 세션, 조회한 열차, 그 열차의 첫 호차에서 받은 좌석들."""
    client, session = make_korail(ROUTES)
    train = (client.trains.search("서울", "부산"))[0]
    seats = client.trains.seats(train, (client.trains.cars(train))[0])
    return client, session, train, seats


class TestCreateWithSeats:
    def test_returns_the_reservation(self, chosen) -> None:
        # given
        client, _, train, seats = chosen

        # when
        reservation = client.reservations.create_with_seats(train, seats[:1])

        # then
        assert reservation.rsv_id == "1234567890"

    def test_returned_reservation_carries_its_seats(self, chosen) -> None:
        """예매 뒤 예약을 다시 조회해 좌석 상세까지 채워 돌려줍니다."""
        # given
        client, _, train, seats = chosen

        # when
        reservation = client.reservations.create_with_seats(train, seats[:1])

        # then
        assert reservation.seats == (Seat.from_response(SEAT_INFO),)

    def test_sends_exact_form_fields_in_the_app_order(self, chosen) -> None:
        """실제 좌석이 걸린 요청입니다. 필드가 하나 빠지거나 늘면 다른 요청이 됩니다."""
        # given
        client, session, train, seats = chosen

        # when
        client.reservations.create_with_seats(train, seats[:1])

        # then
        assert list(session.kwargs_for("reserve")["data"]) == FORM_FIELDS

    def test_asks_for_a_seat_designated_reservation(self, chosen) -> None:
        # given
        client, session, train, seats = chosen

        # when
        client.reservations.create_with_seats(train, seats[:1])

        # then
        data = session.kwargs_for("reserve")["data"]
        sent = {key: data[key] for key in FORM_FIELDS[4:16]}
        assert sent == {
            "txtMenuId": "11",
            "txtJobId": "1103",
            "hidFreeFlg": "N",
            "txtStndFlg": "N",
            "txtTotPsgCnt": "1",
            "txtSeatAttCd1": "000",
            "txtSeatAttCd2": "000",
            "txtSeatAttCd3": "000",
            "txtSeatAttCd4": "015",
            "txtSeatAttCd5": "000",
            "txtJrnyCnt": "1",
            "txtSrcarCnt": "1",
        }

    def test_sends_the_train_rows_seat_attribute(self, chosen) -> None:
        """좌석 속성은 고른 좌석이 아니라 열차 행의 값입니다 — 행이 015 가 아니면 그 값이 나갑니다."""
        # given
        client, session, train, seats = chosen
        other = dataclasses.replace(train, seat_attribute="019")

        # when
        client.reservations.create_with_seats(other, seats[:1])

        # then
        assert session.kwargs_for("reserve")["data"]["txtSeatAttCd4"] == "019"

    def test_blank_seat_attribute_falls_back_to_the_ordinary_seat(self, chosen) -> None:
        """앱도 행의 좌석 속성이 비면 좌석 종류의 기본값(일반석 015)을 씁니다."""
        # given
        client, session, train, seats = chosen
        blank = dataclasses.replace(train, seat_attribute="")

        # when
        client.reservations.create_with_seats(blank, seats[:1])

        # then
        assert session.kwargs_for("reserve")["data"]["txtSeatAttCd4"] == "015"

    def test_sends_the_train_as_the_search_gave_it(self, chosen) -> None:
        """열차번호는 0 을 채우지 않고, 구간은 구성 순서와 운행 순서를 함께 가리킵니다."""
        # given
        client, session, train, seats = chosen

        # when
        client.reservations.create_with_seats(train, seats[:1])

        # then
        data = session.kwargs_for("reserve")["data"]
        sent = {key: data[key] for key in FORM_FIELDS[19:35]}
        assert sent == {
            "txtJrnyTpCd1": "11",
            "txtJrnySqno1": "001",
            "txtTrnNo1": "101",
            "txtTrnClsfCd1": train.train_type,
            "txtTrnGpCd1": train.train_group,
            "txtRunDt1": train.run_date,
            "txtDptDt1": train.dep_date,
            "txtDptTm1": train.dep_time,
            "txtDptRsStnCd1": "0001",
            "txtDptStnConsOrdr1": "000001",
            "txtDptStnRunOrdr1": "000001",
            "txtArvRsStnCd1": "0020",
            "txtArvStnConsOrdr1": "000028",
            "txtArvStnRunOrdr1": "000019",
            "txtChgFlg1": "N",
            "txtPsrmClCd1": "1",
        }

    def test_sends_each_seat_by_car_number_and_seat_identifier(self, chosen) -> None:
        """좌석은 화면 표시("15A")가 아니라 식별자("57")로, 호차는 서버가 준 문자열 그대로 보냅니다."""
        # given
        client, session, train, seats = chosen

        # when
        client.reservations.create_with_seats(train, seats, [AdultPassenger(2)])

        # then
        data = session.kwargs_for("reserve")["data"]
        sent = {key: value for key, value in data.items() if key.startswith(("txtSrcar", "txtSeatNo"))}
        assert sent == {
            "txtSrcarCnt": "2",
            "txtSrcarNo1": "0003",
            "txtSeatNo1": "57",
            "txtSrcarNo2": "0003",
            "txtSeatNo2": "58",
        }

    def test_accepts_a_generator_of_seats(self, chosen) -> None:
        """예제의 대괄호를 괄호로 바꿔 넘겨도 됩니다. 한 번 훑으면 비는 것을 그대로 쓰면 엉뚱한 오류가 납니다."""
        # given
        client, session, train, seats = chosen
        available = (seat for seat in seats if seat.is_available)

        # when
        reservation = client.reservations.create_with_seats(train, available)

        # then
        data = session.kwargs_for("reserve")["data"]
        assert (reservation.rsv_id, data["txtSrcarCnt"], data["txtSeatNo1"]) == ("1234567890", "1", "57")

    def test_seat_count_is_seats_not_cars(self, chosen) -> None:
        """``txtSrcarCnt`` 는 이름과 달리 호차 수가 아닙니다. 다른 호차의 좌석을 섞어도 좌석 수입니다."""
        # given
        client, session, train, seats = chosen
        other_car = dataclasses.replace(seats[1], car_no="0004")

        # when
        client.reservations.create_with_seats(train, [seats[0], other_car], [AdultPassenger(2)])

        # then
        data = session.kwargs_for("reserve")["data"]
        assert (data["txtSrcarCnt"], data["txtSrcarNo1"], data["txtSrcarNo2"]) == ("2", "0003", "0004")

    def test_sends_one_block_per_kind_of_passenger(self, chosen) -> None:
        # given
        client, session, train, seats = chosen

        # when
        client.reservations.create_with_seats(train, seats, [AdultPassenger(1), ChildPassenger(1)])

        # then
        data = session.kwargs_for("reserve")["data"]
        sent = {key: data[key] for key in data if key.startswith(("txtCompaCnt", "txtPsgTpCd", "txtDiscKndCd"))}
        assert sent == {
            "txtCompaCnt1": "1",
            "txtPsgTpCd1": "1",
            "txtDiscKndCd1": "000",
            "txtCompaCnt2": "1",
            "txtPsgTpCd2": "3",
            "txtDiscKndCd2": "000",
        }
        assert data["txtTotPsgCnt"] == "2"

    def test_special_class_seats_are_reserved_in_special_class(self, chosen) -> None:
        """객실은 좌석을 조회한 조건을 따라갑니다. 따로 넘기지 않습니다."""
        # given
        client, session, train, _ = chosen
        special = client.trains.seats(train, (client.trains.cars(train))[0], seat_class=SeatClass.SPECIAL)

        # when
        client.reservations.create_with_seats(train, special[:1])

        # then
        assert session.kwargs_for("reserve")["data"]["txtPsrmClCd1"] == "2"

    def test_goes_in_the_form_body_not_the_query(self, chosen) -> None:
        """앱은 이 요청을 폼 본문으로 보냅니다(@FormUrlEncoded). ``create`` 의 요청과 다릅니다."""
        # given
        client, session, train, seats = chosen

        # when
        client.reservations.create_with_seats(train, seats[:1])

        # then
        assert "params" not in session.kwargs_for("reserve")

    def test_is_signed_but_carries_no_sid(self, chosen) -> None:
        # given
        client, session, train, seats = chosen

        # when
        client.reservations.create_with_seats(train, seats[:1])

        # then
        kwargs = session.kwargs_for("reserve")
        assert "x-dynapath-m-token" in kwargs["headers"]
        assert "Sid" not in kwargs["data"]

    def test_leaves_out_blank_card_numbers(self, chosen) -> None:
        """앱은 값이 빈 필드를 싣지 않습니다. 할인카드가 없는 승객의 카드번호 칸은 나가지 않습니다."""
        # given
        client, session, train, seats = chosen

        # when
        client.reservations.create_with_seats(train, seats[:1])

        # then
        blank = [key for key in session.kwargs_for("reserve")["data"] if key.startswith("txtCardNo_")]
        assert blank == []


class TestCreateWithSeatsRefusesBeforeAnyRequest:
    """실제 좌석이 걸린 요청이라, 틀린 입력은 서버에 보내기 전에 막습니다."""

    def test_seat_count_must_match_the_passengers(self, chosen) -> None:
        # given
        client, session, train, seats = chosen

        # when
        with pytest.raises(ValueError, match="좌석 1개, 승객 2명"):
            client.reservations.create_with_seats(train, seats[:1], [AdultPassenger(2)])

        # then
        assert session.all_kwargs_for("reserve") == []

    def test_no_seats_at_all(self, chosen) -> None:
        # given
        client, _, train, _ = chosen

        # when & then
        with pytest.raises(ValueError, match="좌석 0개"):
            client.reservations.create_with_seats(train, [])

    def test_no_passengers_at_all(self, chosen) -> None:
        """인원이 0 인 승객은 합쳐지며 버려집니다. 좌석 0개와 맞아떨어져 지나가면 안 됩니다."""
        # given
        client, session, train, _ = chosen

        # when
        with pytest.raises(ValueError, match="승객이 한 명 이상"):
            client.reservations.create_with_seats(train, [], [AdultPassenger(0)])

        # then
        assert session.all_kwargs_for("reserve") == []

    def test_same_seat_twice(self, chosen) -> None:
        # given
        client, _, train, seats = chosen

        # when & then
        with pytest.raises(ValueError, match="같은 좌석"):
            client.reservations.create_with_seats(train, [seats[0], seats[0]], [AdultPassenger(2)])

    def test_mixed_seat_classes(self, chosen) -> None:
        # given
        client, _, train, seats = chosen
        special = dataclasses.replace(seats[1], seat_class="2")

        # when & then
        with pytest.raises(ValueError, match="같은 객실"):
            client.reservations.create_with_seats(train, [seats[0], special], [AdultPassenger(2)])

    def test_seat_without_a_class(self, chosen) -> None:
        # given
        client, _, train, seats = chosen
        unknown = dataclasses.replace(seats[0], seat_class="")

        # when & then
        with pytest.raises(ValueError, match="같은 객실"):
            client.reservations.create_with_seats(train, [unknown])

    @pytest.mark.parametrize("field", ["car_no", "seat_no"])
    def test_seat_without_an_identifier(self, chosen, field: str) -> None:
        # given
        client, _, train, seats = chosen
        broken = dataclasses.replace(seats[0], **{field: ""})

        # when & then
        with pytest.raises(ValueError, match="빈 좌석"):
            client.reservations.create_with_seats(train, [broken])

    def test_generator_of_the_wrong_things_still_says_what_to_pass(self, chosen) -> None:
        # given
        client, _, train, _ = chosen
        assigned = (seat for seat in [Seat.from_response(SEAT_INFO)])

        # when & then
        with pytest.raises(TypeError, match="CarSeat"):
            client.reservations.create_with_seats(train, assigned)

    def test_assigned_seat_is_not_a_seat_to_choose(self, chosen) -> None:
        """예약의 배정 좌석(``Seat``)을 넘기면 속성 오류 대신 무엇을 넘겨야 하는지 알려 줍니다."""
        # given
        client, _, train, _ = chosen

        # when & then
        with pytest.raises(TypeError, match="CarSeat"):
            client.reservations.create_with_seats(train, [Seat.from_response(SEAT_INFO)])

    @pytest.mark.parametrize("attribute", ["dep_cons_order", "arr_cons_order", "dep_run_order", "arr_run_order"])
    def test_train_without_the_needed_values(self, chosen, attribute: str) -> None:
        """예약 목록 · 승차권의 열차에는 구간 순서가 없습니다. 빈 칸으로 보내지 않고 멈춥니다."""
        # given
        client, session, train, seats = chosen
        incomplete = dataclasses.replace(train, **{attribute: ""})
        before = len(session.calls)

        # when
        with pytest.raises(ValueError, match=attribute):
            client.reservations.create_with_seats(incomplete, seats[:1])

        # then
        assert len(session.calls) == before, "요청 전에 멈춰야 합니다"


class TestCreateWithSeatsWhenTheServerRefuses:
    def test_refusal_becomes_an_exception(self, make_korail) -> None:
        # given
        client, _ = make_korail({**ROUTES, "reserve": {"strResult": "FAIL", "h_msg_cd": "IRT010110"}})
        train = (client.trains.search("서울", "부산"))[0]
        seats = client.trains.seats(train, (client.trains.cars(train))[0])

        # when & then
        with pytest.raises(SoldOutError):
            client.reservations.create_with_seats(train, seats[:1])

    def test_raises_when_the_reservation_cannot_be_found_afterwards(self, make_korail) -> None:
        """예매는 됐는데 목록에 없으면, 성공한 척 넘어가지 않습니다."""
        # given
        client, _ = make_korail({**ROUTES, "reserve": {"strResult": "SUCC", "h_pnr_no": "0000000000"}})
        train = (client.trains.search("서울", "부산"))[0]
        seats = client.trains.seats(train, (client.trains.cars(train))[0])

        # when & then
        with pytest.raises(KorailError, match="다시 조회하지 못했습니다"):
            client.reservations.create_with_seats(train, seats[:1])
