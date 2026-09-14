"""응답 모델 파싱과 표현.

모든 모델은 불변이고 ``from_response`` 로만 만듭니다.
"""

from __future__ import annotations

import dataclasses

import pytest

from pykorail.models import Reservation, Schedule, Seat, Station, Ticket, Train, parse_stations, train_info_of
from pykorail.models.schedule import WAITING_NOT_APPLICABLE, format_duration
from tests.payloads import RESERVATION_INFO, SEAT_INFO, TICKET_RAW, TRAIN_INFO


class TestImmutability:
    @pytest.mark.parametrize(
        ("model", "field"),
        [
            (Train.from_response(TRAIN_INFO), "train_no"),
            (Seat.from_response(SEAT_INFO), "seat"),
            (Ticket.from_response(TICKET_RAW), "seat_no"),
            (Reservation.from_response(RESERVATION_INFO), "rsv_id"),
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
