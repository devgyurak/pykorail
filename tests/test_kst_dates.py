"""날짜·시각 속성: 형식 파싱, 자정 넘김, 빈 값과 잘린 값, 예약대기."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from pykorail._shared.clock import KST
from pykorail.models import AirportBus, Coupon, MileageEntry, Reservation, RunDate, Ticket, Train
from pykorail.models.parsing import kst_date, kst_datetime
from tests.payloads import (
    BUS_INFO,
    COUPON_INFO,
    MILEAGE_ENTRY_INFO,
    RESERVATION_INFO,
    RUN_DATE_ITEM,
    TICKET_RAW,
    TRAIN_INFO,
)


class TestParsing:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("20261026", date(2026, 10, 26)),
            ("", None),
            ("2026110", None),
            ("20261340", None),
            ("2026-10-26", None),
        ],
        ids=["valid", "empty", "truncated", "impossible-month", "separated"],
    )
    def test_kst_date(self, value: str, expected: date | None) -> None:
        # when
        parsed = kst_date(value)

        # then
        assert parsed == expected

    @pytest.mark.parametrize(
        ("day", "clock", "expected"),
        [
            ("20261026", "093000", datetime(2026, 10, 26, 9, 30, tzinfo=KST)),
            ("20261026", "0930", None),
            ("20261026", "", None),
            ("", "093000", None),
            ("20261026", "250000", None),
            ("20261340", "093000", None),
        ],
        ids=["valid", "truncated-clock", "empty-clock", "empty-day", "impossible-hour", "impossible-month"],
    )
    def test_kst_datetime(self, day: str, clock: str, expected: datetime | None) -> None:
        # when
        parsed = kst_datetime(day, clock)

        # then
        assert parsed == expected


class TestSchedule:
    def test_departure_and_arrival_are_kst_datetimes(self) -> None:
        # given
        train = Train.from_response({**TRAIN_INFO, "h_dpt_tm": "233000", "h_arv_dt": "20260402", "h_arv_tm": "004000"})

        # when & then
        assert train.departure == datetime(2026, 4, 1, 23, 30, tzinfo=KST)
        assert train.arrival == datetime(2026, 4, 2, 0, 40, tzinfo=KST)

    def test_duration_crosses_midnight(self) -> None:
        # given
        train = Train.from_response({**TRAIN_INFO, "h_dpt_tm": "233000", "h_arv_dt": "20260402", "h_arv_tm": "004000"})

        # when
        minutes = train.duration_minutes

        # then
        assert minutes == 70

    def test_duration_spans_more_than_a_day(self) -> None:
        # given
        train = Train.from_response(
            {**TRAIN_INFO, "h_dpt_dt": "20260401", "h_dpt_tm": "100000", "h_arv_dt": "20260403", "h_arv_tm": "100000"}
        )

        # when
        minutes = train.duration_minutes

        # then
        assert minutes == 48 * 60

    def test_same_day_arrival_before_departure_is_read_as_next_day(self) -> None:
        """예약은 도착 날짜가 출발 날짜와 같게 옵니다. 도착이 이르면 자정을 넘긴 것으로 봅니다."""
        # given
        train = Train.from_response({**TRAIN_INFO, "h_dpt_tm": "233000", "h_arv_dt": "20260401", "h_arv_tm": "004000"})

        # when
        minutes = train.duration_minutes

        # then
        assert minutes == 70

    def test_blank_arrival_date_falls_back_to_the_clock(self) -> None:
        # given
        train = Train.from_response({**TRAIN_INFO, "h_arv_dt": ""})

        # when & then
        assert (train.arrival, train.duration_minutes) == (None, 210)

    def test_truncated_departure_clock_has_no_departure(self) -> None:
        # given
        train = Train.from_response({**TRAIN_INFO, "h_dpt_tm": "0900"})

        # when & then
        assert train.departure is None


class TestAirportBus:
    def test_departure_and_arrival_are_kst_datetimes(self) -> None:
        # given
        bus = AirportBus.from_response(BUS_INFO, dep_name="서울", arr_name="인천")

        # when & then
        assert (bus.departure, bus.arrival) == (
            datetime(2026, 10, 16, 6, 0, tzinfo=KST),
            datetime(2026, 10, 16, 6, 50, tzinfo=KST),
        )

    def test_blank_departure_time_has_no_departure(self) -> None:
        # given
        bus = AirportBus.from_response({**BUS_INFO, "dptTm": ""}, dep_name="서울", arr_name="인천")

        # when & then
        assert bus.departure is None


class TestReservation:
    def test_buy_limit_is_the_kst_deadline(self) -> None:
        # when
        reservation = Reservation.from_response(RESERVATION_INFO)

        # then
        assert reservation.buy_limit == datetime(2026, 3, 25, 14, 30, tzinfo=KST)

    def test_waiting_reservation_has_no_buy_limit(self) -> None:
        # given
        waiting = Reservation.from_response({**RESERVATION_INFO, "h_ntisu_lmt_dt": "00000000"})

        # when & then
        assert (waiting.is_waiting, waiting.buy_limit) == (True, None)


class TestCalendarDays:
    def test_ticket_sold_on(self) -> None:
        # when & then
        assert Ticket.from_response(TICKET_RAW).sold_on == date(2026, 3, 20)

    def test_ticket_blank_sale_date_is_none(self) -> None:
        # when & then
        assert Ticket.from_response({**TICKET_RAW, "h_orgtk_sale_dt": ""}).sold_on is None

    def test_run_date_day(self) -> None:
        # when & then
        assert RunDate.from_response({**RUN_DATE_ITEM, "runDt": "20261016"}).day == date(2026, 10, 16)

    def test_mileage_entry_day(self) -> None:
        # when & then
        assert MileageEntry.from_response(MILEAGE_ENTRY_INFO).day == date(2026, 10, 3)

    def test_coupon_validity_window(self) -> None:
        # given
        coupon = Coupon.from_response(COUPON_INFO)

        # when & then
        assert (coupon.starts_on, coupon.ends_on) == (date(2026, 10, 1), date(2026, 12, 31))

    def test_coupon_truncated_window_is_none(self) -> None:
        # given
        coupon = Coupon.from_response({**COUPON_INFO, "h_fdcert_mg_cls_dt": "2026123"})

        # when & then
        assert (coupon.starts_on, coupon.ends_on) == (date(2026, 10, 1), None)


class TestReservationDays:
    RUN_DAY_TRAIN = {**RESERVATION_INFO, "h_run_dt": "20260401", "h_dpt_tm": "233000", "h_arv_tm": "004000"}

    def test_journey_dates_win_over_the_run_date(self) -> None:
        # when
        reservation = Reservation.from_response(self.RUN_DAY_TRAIN, dep_date="20260401", arr_date="20260402")

        # then
        assert (reservation.train.arrival, reservation.train.duration_minutes) == (
            datetime(2026, 4, 2, 0, 40, tzinfo=KST),
            70,
        )

    def test_without_journey_dates_arrival_before_departure_is_next_day(self) -> None:
        """목록 응답만 있을 때: 도착 시각이 출발보다 이르면 다음 날로 봅니다."""
        # when
        reservation = Reservation.from_response(self.RUN_DAY_TRAIN)

        # then
        assert (reservation.train.dep_date, reservation.train.arr_date) == ("20260401", "20260402")

    def test_without_journey_dates_same_day_arrival_stays_on_the_run_date(self) -> None:
        # given
        train = {**RESERVATION_INFO, "h_run_dt": "20260401", "h_dpt_tm": "090000", "h_arv_tm": "123000"}

        # when
        reservation = Reservation.from_response(train)

        # then
        assert (reservation.train.dep_date, reservation.train.arr_date) == ("20260401", "20260401")
