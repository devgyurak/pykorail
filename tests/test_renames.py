"""이름을 바꾼 필드의 폐기 예고, 새 이름, 좌석 상세 튜플, 역 순번."""

from __future__ import annotations

from collections.abc import Callable
from operator import attrgetter
from typing import Any

import pytest

from pykorail.models import Reservation, Seat, SeatDetail, Station, Ticket
from tests.payloads import RESERVATION_INFO, SEAT_INFO, TICKET_RAW

CASES: list[tuple[Callable[[], Any], str, str]] = [
    (lambda: Reservation.from_response(RESERVATION_INFO), "rsv_id", "pnr_no"),
    (lambda: Reservation.from_response(RESERVATION_INFO), "seat_no_count", "seat_count"),
    (lambda: Ticket.from_response(TICKET_RAW), "seat_no_count", "seat_count"),
    (lambda: Seat.from_response(SEAT_INFO), "car", "car_no"),
    (lambda: Seat.from_response(SEAT_INFO), "seat", "seat_no"),
    (lambda: Seat.from_response(SEAT_INFO), "seat_type", "seat_class_name"),
    (lambda: Seat.from_response(SEAT_INFO), "passenger_type", "passenger_type_name"),
    (lambda: Ticket.from_response(TICKET_RAW), "sale_info1", "original_wct_no"),
    (lambda: Ticket.from_response(TICKET_RAW), "sale_info2", "original_refund_sale_date"),
    (lambda: Ticket.from_response(TICKET_RAW), "sale_info3", "original_sale_seq_no"),
    (lambda: Ticket.from_response(TICKET_RAW), "sale_info4", "original_refund_pwd"),
]


class TestDeprecatedNames:
    @pytest.mark.parametrize(("make", "old", "new"), CASES, ids=[f"{old}->{new}" for _, old, new in CASES])
    def test_old_name_warns_and_reads_the_new_value(self, make: Callable[[], Any], old: str, new: str) -> None:
        # given
        obj = make()

        # when
        with pytest.warns(DeprecationWarning, match=old) as record:
            value = attrgetter(old)(obj)

        # then
        assert value == attrgetter(new)(obj)
        assert record[0].filename == __file__, "경고는 옛 이름을 읽은 사용자 코드의 줄을 가리켜야 합니다"

    @pytest.mark.parametrize(("make", "old", "new"), CASES, ids=[f"{old}->{new}" for _, old, new in CASES])
    def test_new_name_does_not_warn(
        self, make: Callable[[], Any], old: str, new: str, recwarn: pytest.WarningsRecorder
    ) -> None:
        # given
        obj = make()

        # when
        attrgetter(new)(obj)

        # then
        assert [w for w in recwarn if issubclass(w.category, DeprecationWarning)] == []


class TestSeatDetail:
    def test_unpacks_into_seats_and_window_number(self) -> None:
        # given
        detail = SeatDetail([Seat.from_response(SEAT_INFO)], "0143")

        # when
        seats, wct_no = detail

        # then
        assert (seats, wct_no) == (detail.seats, detail.wct_no)
        assert wct_no == "0143"


class TestMajorRank:
    @pytest.mark.parametrize(
        ("major", "expected"),
        [("28", 28), ("", None), ("x", None), ("²", None)],
        ids=["ranked", "not-major", "not-a-number", "superscript"],
    )
    def test_reads_the_major_rank_as_an_int(self, major: str, expected: int | None) -> None:
        # given
        station = Station.from_response({"stn_cd": "0115", "stn_nm": "강릉", "major": major})

        # when
        rank = station.major_rank

        # then
        assert rank == expected
