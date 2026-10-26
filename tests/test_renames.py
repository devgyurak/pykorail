"""이름을 바꾼 필드의 폐기 예고, 새 이름, 좌석 상세 튜플, 역 순번."""

from __future__ import annotations

from collections.abc import Callable
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


class TestRemovedNames:
    @pytest.mark.parametrize(("make", "old"), [(make, old) for make, old, _ in CASES], ids=[old for _, old, _ in CASES])
    def test_old_name_is_gone(self, make: Callable[[], Any], old: str) -> None:
        """0.6.0 에서 폐기 예고한 옛 이름은 0.7.0 에서 지웠습니다 — 읽으면 AttributeError 입니다."""
        # given
        obj = make()

        # when & then
        assert not hasattr(obj, old)


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
