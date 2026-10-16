"""응답 모델 파싱과 표현.

모든 모델은 불변이고 ``from_response`` 로만 만듭니다.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, date, datetime

import pytest

from pykorail.models import (
    Car,
    CarSeat,
    Fare,
    Reservation,
    RunDate,
    Schedule,
    Seat,
    SeatAttribute,
    Station,
    Ticket,
    Train,
    Transfer,
    TransferStation,
    netfunnel_action_for,
    parse_stations,
    parse_transfers,
    train_info_of,
)
from pykorail.models.parsing import amount, records
from pykorail.models.schedule import WAITING_NOT_APPLICABLE, format_duration
from tests.payloads import (
    CAR_INFO,
    CAR_SEAT_INFO,
    FIRST_LEG_INFO,
    GENERAL_FARE_INFO,
    PEAK_RUN_DATE_ITEM,
    RESERVATION_INFO,
    RUN_DATE_ITEM,
    SEAT_INFO,
    SEATABLE_TRAIN_INFO,
    SECOND_LEG_INFO,
    SOLD_OUT_SECOND_LEG_INFO,
    SPECIAL_FARE_INFO,
    TICKET_RAW,
    TRAIN_INFO,
)


class TestImmutability:
    @pytest.mark.parametrize(
        ("model", "field"),
        [
            (Train.from_response(TRAIN_INFO), "train_no"),
            (Seat.from_response(SEAT_INFO), "seat"),
            (Ticket.from_response(TICKET_RAW), "seat_no"),
            (Reservation.from_response(RESERVATION_INFO), "rsv_id"),
            (RunDate.from_response(RUN_DATE_ITEM), "run_date"),
            (Transfer.from_response([FIRST_LEG_INFO, SECOND_LEG_INFO]), "legs"),
        ],
    )
    def test_models_are_frozen(self, model: object, field: str) -> None:
        # when & then
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(model, field, "changed")

    def test_replace_produces_a_new_object(self) -> None:
        # given
        train = Train.from_response(TRAIN_INFO)

        # when
        other = dataclasses.replace(train, train_no="999")

        # then
        assert train.train_no == "101"
        assert other.train_no == "999"

    def test_equality_is_by_value(self) -> None:
        # when
        first = Train.from_response(TRAIN_INFO)
        second = Train.from_response(TRAIN_INFO)

        # then
        assert first == second


class TestTrain:
    def test_parses_core_fields(self) -> None:
        # when
        train = Train.from_response(TRAIN_INFO)

        # then
        assert train.train_no == "101"
        assert train.dep_name == "서울"
        assert train.arr_name == "부산"
        assert train.duration_minutes == 210

    def test_duration_wraps_past_midnight(self) -> None:
        # given
        overnight = {**TRAIN_INFO, "h_dpt_tm": "230000", "h_arv_tm": "013000"}

        # when
        train = Train.from_response(overnight)

        # then
        assert train.duration_minutes == 150

    def test_seat_availability(self) -> None:
        # when
        train = Train.from_response(TRAIN_INFO)

        # then
        assert train.has_special_seat()
        assert train.has_general_seat()
        assert train.has_seat()
        assert train.has_waiting_list()

    def test_sold_out(self) -> None:
        # given
        sold_out = {**TRAIN_INFO, "h_spe_rsv_cd": "00", "h_gen_rsv_cd": "00", "h_wait_rsv_flg": "0"}

        # when
        train = Train.from_response(sold_out)

        # then
        assert not train.has_seat()
        assert not train.has_waiting_list()

    def test_missing_wait_flag_is_not_applicable(self) -> None:
        """플래그가 없으면 None 이 아니라 음수여야 합니다 — 비교 연산이 터지면 안 됩니다."""
        # given
        without_flag = {k: v for k, v in TRAIN_INFO.items() if k != "h_wait_rsv_flg"}

        # when
        train = Train.from_response(without_flag)

        # then
        assert train.wait_reserve_flag == WAITING_NOT_APPLICABLE
        assert train.wait_reserve_flag < 0
        assert repr(train)

    def test_repr_survives_empty_payload(self) -> None:
        # when
        train = Train.from_response({})

        # then
        assert repr(train)

    def test_duration_is_none_when_times_missing(self) -> None:
        # when
        train = Train.from_response({})

        # then
        assert train.duration_minutes is None

    def test_summary_omits_seat_availability(self) -> None:
        # given
        train = Train.from_response(TRAIN_INFO)

        # when
        summary = train.summary()

        # then
        assert "특실" not in summary
        assert "특실" in repr(train)


class TestDurationFormat:
    @pytest.mark.parametrize(
        ("minutes", "expected"),
        [
            (0, "0분"),
            (1, "1분"),
            (45, "45분"),
            (59, "59분"),
            (60, "1시간"),
            (61, "1시간 1분"),
            (90, "1시간 30분"),
            (120, "2시간"),
            (210, "3시간 30분"),
            (355, "5시간 55분"),
            (1439, "23시간 59분"),
        ],
    )
    def test_formats_minutes(self, minutes: int, expected: str) -> None:
        # when
        rendered = format_duration(minutes)

        # then
        assert rendered == expected

    def test_train_repr_uses_hours(self) -> None:
        """210분을 그냥 '210분' 으로 보여주면 몇 시간인지 안 들어옵니다."""
        # given
        train = Train.from_response(TRAIN_INFO)

        # when
        rendered = repr(train)

        # then
        assert "(3시간 30분)" in rendered
        assert "210분" not in rendered

    def test_under_an_hour_stays_in_minutes(self) -> None:
        # given
        short_trip = {**TRAIN_INFO, "h_dpt_tm": "090000", "h_arv_tm": "094500"}

        # when
        rendered = repr(Train.from_response(short_trip))

        # then
        assert "(45분)" in rendered

    def test_duration_text_property(self) -> None:
        # when
        text = Train.from_response(TRAIN_INFO).duration_text

        # then
        assert text == "3시간 30분"

    def test_duration_text_is_none_when_unreadable(self) -> None:
        # when
        text = Train.from_response({}).duration_text

        # then
        assert text is None


class TestSchedule:
    def test_from_response_ignores_seat_fields(self) -> None:
        # when
        schedule = Schedule.from_response(TRAIN_INFO)

        # then
        assert schedule.train_no == "101"
        assert not hasattr(schedule, "general_seat")


class TestReservation:
    def test_parses_fields(self) -> None:
        # when
        rsv = Reservation.from_response(RESERVATION_INFO)

        # then
        assert rsv.rsv_id == "1234567890"
        assert rsv.price == 119600
        assert rsv.seat_no_count == 2
        assert not rsv.is_waiting

    def test_composes_a_train_rather_than_inheriting(self) -> None:
        # when
        rsv = Reservation.from_response(RESERVATION_INFO)

        # then
        assert isinstance(rsv.train, Train)
        assert not isinstance(rsv, Train)
        assert rsv.train.dep_name == "서울"

    def test_dates_come_from_run_date(self) -> None:
        # given
        with_other_dates = {**RESERVATION_INFO, "h_dpt_dt": "20260101", "h_arv_dt": "20260101"}

        # when
        rsv = Reservation.from_response(with_other_dates)

        # then
        assert rsv.train.dep_date == "20260401"
        assert rsv.train.arr_date == "20260401"

    def test_journey_defaults(self) -> None:
        # when
        rsv = Reservation.from_response(RESERVATION_INFO)

        # then
        assert (rsv.journey_no, rsv.journey_cnt, rsv.rsv_chg_no) == ("001", "01", "00000")

    @pytest.mark.parametrize(("date", "time"), [("00000000", "143000"), ("20260325", "235959")])
    def test_waiting_detection(self, date: str, time: str) -> None:
        # given
        waiting = {**RESERVATION_INFO, "h_ntisu_lmt_dt": date, "h_ntisu_lmt_tm": time}

        # when
        rsv = Reservation.from_response(waiting)

        # then
        assert rsv.is_waiting
        assert "예약대기" in repr(rsv)

    def test_seats_default_to_empty(self) -> None:
        # when
        rsv = Reservation.from_response(RESERVATION_INFO)

        # then
        assert rsv.seats == ()
        assert rsv.wct_no is None

    def test_seats_are_supplied_at_construction(self) -> None:
        # given
        seats = (Seat.from_response(SEAT_INFO),)

        # when
        rsv = Reservation.from_response(RESERVATION_INFO, seats=seats, wct_no="0143")

        # then
        assert rsv.seats == seats
        assert rsv.wct_no == "0143"


class TestTicket:
    def test_from_ticket_list_unwraps(self) -> None:
        # given
        entry = {"ticket_list": [{"train_info": [TICKET_RAW]}]}

        # when
        ticket = Ticket.from_ticket_list(entry)

        # then
        assert ticket is not None
        assert ticket.seat_no == "5A"
        assert ticket.price == 119600
        assert ticket.seat_no_count == 2

    @pytest.mark.parametrize(
        ("entry", "reason"),
        [
            ({}, "ticket_list 자체가 없음"),
            ({"ticket_list": []}, "빈 리스트"),
            ({"ticket_list": [{}]}, "train_info 가 없음"),
            ({"ticket_list": [{"train_info": []}]}, "빈 train_info"),
            ({"ticket_list": [{"train_info": [{}]}]}, "빈 dict — 유령 승차권이 됩니다"),
            ({"ticket_list": "0"}, "리스트가 아닌 값"),
            ({"ticket_list": [{"train_info": ["0"]}]}, "dict 가 아닌 항목"),
        ],
    )
    def test_incomplete_entries_unwrap_to_none(self, entry: dict, reason: str) -> None:
        """코레일은 필드를 빼먹고 보냅니다 — 항목 하나에 목록 전체가 터지면 안 됩니다."""
        # when
        unwrapped = train_info_of(entry)

        # then
        assert unwrapped is None, reason

    def test_from_ticket_list_returns_none_for_an_empty_entry(self) -> None:
        # when
        ticket = Ticket.from_ticket_list({"ticket_list": []})

        # then
        assert ticket is None

    def test_composes_a_train_rather_than_inheriting(self) -> None:
        # when
        ticket = Ticket.from_response(TICKET_RAW)

        # then
        assert isinstance(ticket.train, Train)
        assert not isinstance(ticket, Train)
        assert ticket.train.train_no == "101"

    def test_seat_no_override_clears_the_range(self) -> None:
        # when
        ticket = Ticket.from_response(TICKET_RAW, seat_no="7C")

        # then
        assert ticket.seat_no == "7C"
        assert ticket.seat_no_end is None

    def test_ticket_no_joins_sale_info(self) -> None:
        # when
        ticket_no = Ticket.from_response(TICKET_RAW).ticket_no

        # then
        assert ticket_no == "0000-20260320-0001-1111"

    def test_repr_shows_seat_range_for_multiple_seats(self) -> None:
        # when
        rendered = repr(Ticket.from_response(TICKET_RAW))

        # then
        assert "5A~5B" in rendered

    def test_repr_shows_single_seat(self) -> None:
        # given
        single = {**TICKET_RAW, "h_seat_cnt": "1"}

        # when
        rendered = repr(Ticket.from_response(single))

        # then
        assert "5A~" not in rendered
        assert "5A" in rendered

    def test_repr_omits_seat_availability(self) -> None:
        """이미 발권된 승차권에 '특실 가능'은 의미가 없습니다."""
        # when
        rendered = repr(Ticket.from_response(TICKET_RAW))

        # then
        assert "특실" not in rendered


class TestSeat:
    def test_parses_prices(self) -> None:
        # when
        seat = Seat.from_response(SEAT_INFO)

        # then
        assert seat.price == 59800
        assert seat.discount == 0
        assert not seat.is_waiting

    def test_empty_seat_number_means_waiting(self) -> None:
        # given
        waiting = {**SEAT_INFO, "h_seat_no": ""}

        # when
        seat = Seat.from_response(waiting)

        # then
        assert seat.is_waiting
        assert "예약대기" in repr(seat)

    def test_blank_price_does_not_raise(self) -> None:
        """예약대기 좌석은 금액 필드가 빈 문자열로 오기도 합니다."""
        # given
        blank_prices = {**SEAT_INFO, "h_rcvd_amt": "", "h_dcnt_amt": None}

        # when
        seat = Seat.from_response(blank_prices)

        # then
        assert seat.price == 0
        assert seat.discount == 0


class TestStation:
    PAYLOAD = {
        "stns": {
            "stn": [
                {
                    "stn_cd": "0115",
                    "stn_nm": "강릉",
                    "longitude": "128.898851",
                    "latitude": "37.764108",
                    "group": "1",
                    "major": "28",
                    "popupType": "0",
                    "popupMessage": "",
                },
                {
                    "stn_cd": "0530",
                    "stn_nm": "가남",
                    "longitude": "127.5340237",
                    "latitude": "37.1969049",
                    "group": "1",
                    "popupType": "0",
                    "popupMessage": "",
                },
            ]
        }
    }

    def test_parses_stations(self) -> None:
        # when
        stations = parse_stations(self.PAYLOAD)

        # then
        assert [s.name for s in stations] == ["강릉", "가남"]
        assert stations[0].code == "0115"
        assert stations[0].latitude == pytest.approx(37.764108)

    def test_major_flag(self) -> None:
        # when
        stations = parse_stations(self.PAYLOAD)

        # then
        assert stations[0].is_major
        assert not stations[1].is_major

    def test_repr(self) -> None:
        # given
        entry = self.PAYLOAD["stns"]["stn"][0]

        # when
        rendered = repr(Station.from_response(entry))

        # then
        assert rendered == "강릉(0115)"

    @pytest.mark.parametrize("payload", [{}, {"stns": {}}, {"stns": {"stn": None}}, {"stns": []}])
    def test_missing_nodes_yield_empty_list(self, payload: dict) -> None:
        # when
        stations = parse_stations(payload)

        # then
        assert stations == []


class TestTrainSeatLookupFields:
    def test_parses_run_orders_and_seat_attribute(self) -> None:
        # when
        train = Train.from_response(SEATABLE_TRAIN_INFO)

        # then
        assert (train.dep_run_order, train.arr_run_order, train.seat_attribute) == ("000001", "000019", "015")

    def test_parses_construction_orders(self) -> None:
        """좌석을 지정한 예매가 운행 순서와 함께 돌려보내는 값입니다."""
        # when
        train = Train.from_response(SEATABLE_TRAIN_INFO)

        # then
        assert (train.dep_cons_order, train.arr_cons_order) == ("000001", "000028")

    def test_missing_fields_are_blank_not_an_error(self) -> None:
        """예약 목록 · 승차권 응답의 열차에는 이 필드들이 없습니다."""
        # when
        train = Train.from_response(TRAIN_INFO)

        # then
        assert (train.dep_run_order, train.arr_run_order, train.seat_attribute) == ("", "", "")
        assert (train.dep_cons_order, train.arr_cons_order) == ("", "")


class TestCar:
    def test_parses_a_car(self) -> None:
        # when
        car = Car.from_response(CAR_INFO)

        # then
        assert car == Car(
            car_no="0003",
            seat_class="1",
            seat_class_name="일반실",
            seat_count=58,
            remaining_seats=19,
            attributes=(SeatAttribute(code="015", name="일반석"),),
        )

    @pytest.mark.parametrize(("remaining", "expected"), [("00019", True), ("00000", False), ("", False)])
    def test_has_seat_follows_the_remaining_count(self, remaining: str, expected: bool) -> None:
        # when
        car = Car.from_response({**CAR_INFO, "h_rest_seat_cnt": remaining})

        # then
        assert car.has_seat() is expected

    @pytest.mark.parametrize(
        "data",
        [
            {key: value for key, value in CAR_INFO.items() if key != "seatAttInfos"},
            {**CAR_INFO, "seatAttInfos": None},
            {**CAR_INFO, "seatAttInfos": []},
        ],
        ids=["absent", "null", "empty"],
    )
    def test_missing_attributes_are_an_empty_tuple(self, data: dict[str, object]) -> None:
        # when
        car = Car.from_response(data)

        # then
        assert car.attributes == ()

    def test_empty_response_does_not_raise(self) -> None:
        # when
        car = Car.from_response({})

        # then
        assert car == Car(car_no="", seat_class="", seat_class_name="", seat_count=0, remaining_seats=0)


class TestCarSeat:
    def test_parses_a_seat(self) -> None:
        # when
        seat = CarSeat.from_response(CAR_SEAT_INFO, car_no="0003", seat_class="1")

        # then
        assert seat == CarSeat(
            car_no="0003",
            seat_class="1",
            seat_no="57",
            label="15A",
            sale_flag="Y",
            direction="009",
            attribute="015",
            extra_attribute="000",
            message="",
        )

    @pytest.mark.parametrize(("flag", "expected"), [("Y", True), ("N", False), ("", False)])
    def test_available_only_when_the_sale_flag_says_so(self, flag: str, expected: bool) -> None:
        # when
        seat = CarSeat.from_response({**CAR_SEAT_INFO, "sale_psb_flg": flag}, car_no="0003", seat_class="1")

        # then
        assert seat.is_available is expected

    def test_empty_response_does_not_raise(self) -> None:
        # when
        seat = CarSeat.from_response({}, car_no="0003", seat_class="1")

        # then
        assert (seat.seat_no, seat.is_available) == ("", False)


class TestRecords:
    def test_follows_the_path_to_the_list(self) -> None:
        # when
        found = records({"x_infos": {"x_info": [{"a": "1"}, {"a": "2"}]}}, "x_infos", "x_info")

        # then
        assert found == [{"a": "1"}, {"a": "2"}]

    @pytest.mark.parametrize(
        "data",
        [
            {},
            {"x_infos": None},
            {"x_infos": {}},
            {"x_infos": {"x_info": None}},
            {"x_infos": {"x_info": ""}},
            {"x_infos": {"x_info": {"a": "1"}}},
            {"x_infos": "결과 없음"},
            {"x_infos": [{"x_info": []}]},
        ],
        ids=[
            "absent",
            "null-wrapper",
            "empty-wrapper",
            "null-list",
            "blank",
            "dict-not-list",
            "text-wrapper",
            "list-wrapper",
        ],
    )
    def test_anything_but_a_list_is_empty(self, data: dict[str, object]) -> None:
        """코레일은 결과가 없을 때 키를 빼거나 null 을 주거나 다른 모양을 보냅니다."""
        # when
        found = records(data, "x_infos", "x_info")

        # then
        assert found == []

    def test_skips_items_that_are_not_records(self) -> None:
        # when
        found = records({"rows": [{"a": "1"}, None, "문자열", {"a": "2"}]}, "rows")

        # then
        assert found == [{"a": "1"}, {"a": "2"}]


class TestTransferStation:
    def test_parses_a_station(self) -> None:
        # when
        station = TransferStation.from_response(
            {"chtnRsStnCd": "0015", "chtnRsStnNm": "대전", "chtnRsStnEngNm": "Daejeon"}
        )

        # then
        assert station == TransferStation(code="0015", name="대전", english_name="Daejeon")

    def test_empty_response_does_not_raise(self) -> None:
        # when
        station = TransferStation.from_response({})

        # then
        assert station == TransferStation(code="", name="", english_name="")


class TestTransfer:
    def test_refers_to_two_trains_in_riding_order(self) -> None:
        # when
        transfer = Transfer.from_response([FIRST_LEG_INFO, SECOND_LEG_INFO])

        # then
        assert [(leg.train_no, leg.dep_name, leg.arr_name) for leg in transfer.legs] == [
            ("101", "서울", "대전"),
            ("1201", "대전", "부산"),
        ]

    @pytest.mark.parametrize("rows", [[], [FIRST_LEG_INFO]], ids=["none", "one"])
    def test_rejects_fewer_than_two_legs(self, rows: list[dict[str, str]]) -> None:
        """하나짜리를 받아 두면 second 를 읽을 때에야 IndexError 로 터집니다."""
        # when & then
        with pytest.raises(ValueError, match="구간"):
            Transfer.from_response(rows)

    def test_station_name_is_where_the_legs_meet(self) -> None:
        # when
        transfer = Transfer.from_response([FIRST_LEG_INFO, SECOND_LEG_INFO])

        # then
        assert transfer.station_name == "대전"

    def test_station_name_is_none_when_the_legs_do_not_meet(self) -> None:
        """도착역과 다음 출발역이 다르면 역 사이를 따로 이동해야 합니다. 한쪽을 환승역이라 넘겨짚지 않습니다."""
        # when
        transfer = Transfer.from_response([FIRST_LEG_INFO, {**SECOND_LEG_INFO, "h_dpt_rs_stn_nm": "서대전"}])

        # then
        assert transfer.station_name is None

    @pytest.mark.parametrize(
        ("second", "expected"),
        [(SECOND_LEG_INFO, True), (SOLD_OUT_SECOND_LEG_INFO, False)],
        ids=["both-available", "second-sold-out"],
    )
    def test_has_seat_needs_both_legs(self, second: dict[str, str], expected: bool) -> None:
        # when
        transfer = Transfer.from_response([FIRST_LEG_INFO, second])

        # then
        assert transfer.has_seat() is expected


class TestParseTransfers:
    def test_groups_rows_by_itinerary_number_in_response_order(self) -> None:
        # given
        later_first = {**FIRST_LEG_INFO, "h_trn_no": "103", "h_trn_seq": "001"}
        later_second = {**SECOND_LEG_INFO, "h_trn_no": "1203", "h_trn_seq": "001"}

        # when
        transfers = parse_transfers([FIRST_LEG_INFO, later_first, SECOND_LEG_INFO, later_second])

        # then
        assert [(t.first.train_no, t.second.train_no) for t in transfers] == [("101", "1201"), ("103", "1203")]

    def test_legs_follow_the_servers_riding_order_not_the_row_order(self) -> None:
        """타는 순서는 서버가 붙인 번호입니다. 줄이 뒤바뀌어 와도 첫 구간이 먼저여야 합니다."""
        # when
        transfers = parse_transfers([SECOND_LEG_INFO, FIRST_LEG_INFO])

        # then
        assert [(t.first.train_no, t.second.train_no) for t in transfers] == [("101", "1201")]

    def test_rows_without_a_riding_order_keep_the_row_order(self) -> None:
        # given
        first = {key: value for key, value in FIRST_LEG_INFO.items() if key != "h_chg_trn_seq"}
        second = {key: value for key, value in SECOND_LEG_INFO.items() if key != "h_chg_trn_seq"}

        # when
        transfers = parse_transfers([first, second])

        # then
        assert [(t.first.train_no, t.second.train_no) for t in transfers] == [("101", "1201")]

    def test_dropped_rows_leave_a_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """버린 행이 있는데 아무 말도 없으면 "여정 없음" 의 원인을 알 길이 없습니다."""
        # given
        third_leg = {**SECOND_LEG_INFO, "h_trn_no": "1205", "h_chg_trn_seq": "3"}

        # when
        with caplog.at_level("WARNING", logger="pykorail.models.transfer"):
            transfers = parse_transfers([FIRST_LEG_INFO, SECOND_LEG_INFO, third_leg])

        # then
        assert transfers == []
        assert [record.getMessage() for record in caplog.records] == [
            "환승 조회 행 3개 중 3개가 두 구간 여정으로 묶이지 않아 버렸습니다 (여정 번호별 행 수: {'000': 3})"
        ]

    def test_clean_pairing_is_silent(self, caplog: pytest.LogCaptureFixture) -> None:
        # when
        with caplog.at_level("WARNING", logger="pykorail.models.transfer"):
            parse_transfers([FIRST_LEG_INFO, SECOND_LEG_INFO])

        # then
        assert caplog.records == []

    def test_no_rows_is_no_itineraries(self) -> None:
        # when
        transfers = parse_transfers([])

        # then
        assert transfers == []


class TestFare:
    def test_parses_a_fare(self) -> None:
        # when
        fare = Fare.from_response(GENERAL_FARE_INFO)

        # then
        assert fare == Fare(
            train_no="101", journey_no="0001", seat_class_name="일반실", price=59800, charge=0, total=59800
        )

    def test_reads_amounts_the_way_the_server_prints_them(self) -> None:
        """서버는 금액을 ``"59,800원"`` 으로 줍니다. 숫자로만 읽으면 오류 없이 0 원이 됩니다."""
        # when
        fare = Fare.from_response(SPECIAL_FARE_INFO)

        # then
        assert (fare.price, fare.charge, fare.total) == (59800, 23900, 83700)

    def test_a_dash_means_no_charge(self) -> None:
        """일반실은 요금 칸이 ``-`` 로 옵니다."""
        # when
        charge = Fare.from_response(GENERAL_FARE_INFO).charge

        # then
        assert charge == 0

    def test_empty_response_does_not_raise(self) -> None:
        # when
        fare = Fare.from_response({})

        # then
        assert fare == Fare(train_no="", journey_no="", seat_class_name="", price=0, charge=0, total=0)


class TestAmount:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("48,000원", 48000),
            ("1,234,500원", 1234500),
            ("900원", 900),
            ("48,000", 48000),
            ("48000", 48000),
            (" 48,000원 ", 48000),
            ("-", 0),
            (48000, 48000),
        ],
        ids=["won", "two-commas", "no-comma", "no-unit", "digits", "padded", "dash", "number"],
    )
    def test_reads_amounts(self, value: object, expected: int) -> None:
        # when
        found = amount({"x": value}, "x")

        # then
        assert found == expected

    @pytest.mark.parametrize(
        "data", [{}, {"x": None}, {"x": ""}, {"x": "무료"}], ids=["absent", "null", "blank", "text"]
    )
    def test_unreadable_amount_is_the_default(self, data: dict[str, object]) -> None:
        # when
        found = amount(data, "x", default=-1)

        # then
        assert found == -1

    def test_a_dash_is_zero_even_with_another_default(self) -> None:
        """``-`` 는 "못 읽음" 이 아니라 "해당 없음" 입니다."""
        # when
        found = amount({"x": "-"}, "x", default=-1)

        # then
        assert found == 0


class TestNetfunnelActionFor:
    """출발일의 NetFunnel ``aid`` 선택 — 성수기 판정은 #117."""

    @pytest.mark.parametrize(
        ("biz_dd_stg_cd", "expected"),
        [("5", "act_8_2"), ("1", "act_8"), ("2", "act_8"), ("3", "act_8"), ("4", "act_8"), ("", "act_8")],
        ids=["peak", "stage-1", "stage-2", "stage-3", "stage-4", "blank"],
    )
    def test_peak_code_picks_the_peak_queue(self, biz_dd_stg_cd: str, expected: str) -> None:
        # given
        day = RunDate.from_response({**RUN_DATE_ITEM, "bizDdStgCd": biz_dd_stg_cd})

        # when
        aid = netfunnel_action_for([day], date(2026, 10, 16))

        # then
        assert aid == expected

    def test_missing_date_falls_back_to_the_default_queue(self) -> None:
        # given
        calendar = [RunDate.from_response(PEAK_RUN_DATE_ITEM)]  # 2026-10-17

        # when
        aid = netfunnel_action_for(calendar, date(2026, 10, 16))

        # then
        assert aid == "act_8"

    def test_empty_calendar_falls_back_to_the_default_queue(self) -> None:
        # when
        aid = netfunnel_action_for([], date(2026, 10, 16))

        # then
        assert aid == "act_8"

    def test_aware_datetime_is_judged_by_the_kst_date(self) -> None:
        """UTC 자정 직후는 KST 로는 이미 다음 날입니다 — 그날 항목을 봐야 합니다."""
        # given
        calendar = [RunDate.from_response(PEAK_RUN_DATE_ITEM)]  # 2026-10-17 성수기
        departure = datetime(2026, 10, 16, 15, 30, tzinfo=UTC)  # KST 2026-10-17 00:30

        # when
        aid = netfunnel_action_for(calendar, departure)

        # then
        assert aid == "act_8_2"
