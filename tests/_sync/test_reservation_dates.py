# 이 파일은 생성물입니다 — 직접 고치지 마세요.
# 원본: tests/_async/test_reservation_dates.py
# 다시 만들려면: uv run python scripts/unasync.py
"""예약에서 나온 열차의 날짜가 폼에 실리는 값, 그리고 환승 구간마다 자기 여정의 날짜."""

from __future__ import annotations

from typing import Any

from tests.payloads import (
    FIRST_LEG_SEAT_INFO,
    RESERVATION_INFO,
    SEAT_CARS_PAYLOAD,
    SEAT_INFO,
    SECOND_LEG_SEAT_INFO,
    TRANSFER_RESERVATION_ENTRIES,
    TRANSFER_RESERVATION_LIST_PAYLOAD,
)

#: 운행일 2026-04-01 의 23시 30분 출발이 다음 날 0시 40분에 닿는 예약. 상세 응답의 날짜가 출발일을 정합니다.
MIDNIGHT_VIEW = {**RESERVATION_INFO, "h_run_dt": "20260401", "h_dpt_tm": "233000", "h_arv_tm": "004000"}


def _detail(journeys: list[Any]) -> dict[str, Any]:
    return {"strResult": "SUCC", "h_wct_no": "0143", "jrny_infos": {"jrny_info": journeys}}


class TestCarsFormAfterMidnight:
    def test_departure_day_comes_from_the_journey(self, make_korail) -> None:
        """운행일 다음 날 자정 이후에 출발하는 예약은 출발일 칸에 실제 출발일이 실립니다."""
        # given
        journey = {"h_dpt_dt": "20260402", "h_arv_dt": "20260402", "seat_infos": {"seat_info": [SEAT_INFO]}}
        client, session = make_korail(
            {
                "myreservationview": {
                    "strResult": "SUCC",
                    "jrny_infos": {"jrny_info": [{"train_infos": {"train_info": [MIDNIGHT_VIEW]}}]},
                },
                "myreservationlist": _detail([journey]),
                "seat_cars": SEAT_CARS_PAYLOAD,
            }
        )
        reservation = (client.reservations.all())[0]

        # when
        client.trains.cars(reservation.train)

        # then
        data = session.kwargs_for("seat_cars")["data"]
        assert (data["txtRunDt"], data["txtDptDt"]) == ("20260401", "20260402")

    def test_without_journey_dates_the_run_date_stays(self, make_korail) -> None:
        """여정 상세가 날짜를 주지 않으면 예전처럼 운행일을 출발일로 씁니다."""
        # given
        journey = {"seat_infos": {"seat_info": [SEAT_INFO]}}
        client, session = make_korail(
            {
                "myreservationview": {
                    "strResult": "SUCC",
                    "jrny_infos": {"jrny_info": [{"train_infos": {"train_info": [MIDNIGHT_VIEW]}}]},
                },
                "myreservationlist": _detail([journey]),
                "seat_cars": SEAT_CARS_PAYLOAD,
            }
        )
        reservation = (client.reservations.all())[0]

        # when
        client.trains.cars(reservation.train)

        # then
        assert session.kwargs_for("seat_cars")["data"]["txtDptDt"] == "20260401"


class TestTransferLegDates:
    def test_each_leg_takes_its_own_journey_dates(self, make_korail) -> None:
        # given
        journeys = [
            {
                "h_jrny_sqno": "0001",
                "h_dpt_dt": "20260401",
                "h_arv_dt": "20260401",
                "seat_infos": {"seat_info": [FIRST_LEG_SEAT_INFO]},
            },
            {
                "h_jrny_sqno": "0002",
                "h_dpt_dt": "20260402",
                "h_arv_dt": "20260402",
                "seat_infos": {"seat_info": [SECOND_LEG_SEAT_INFO]},
            },
        ]
        client, _ = make_korail(
            {"myreservationview": TRANSFER_RESERVATION_LIST_PAYLOAD, "myreservationlist": _detail(journeys)}
        )

        # when
        first, second = client.reservations.all()

        # then
        assert (first.train.dep_date, second.train.dep_date) == ("20260401", "20260402")

    def test_unmatched_leg_does_not_borrow_the_first_leg_date(self, make_korail) -> None:
        """여정 번호가 맞지 않는 구간은 첫 구간의 날짜를 받지 않고 운행일을 씁니다."""
        # given
        unmatched_view = {
            "strResult": "SUCC",
            "h_jrny_cnt": "2",
            "jrny_infos": {
                "jrny_info": [
                    {
                        "train_infos": {
                            "train_info": [
                                TRANSFER_RESERVATION_ENTRIES[0],
                                {**TRANSFER_RESERVATION_ENTRIES[1], "h_jrny_sqno": "0009", "h_run_dt": "20260402"},
                            ]
                        }
                    }
                ]
            },
        }
        journeys = [
            {
                "h_jrny_sqno": "0001",
                "h_dpt_dt": "20260401",
                "h_arv_dt": "20260401",
                "seat_infos": {"seat_info": [FIRST_LEG_SEAT_INFO]},
            },
        ]
        client, _ = make_korail({"myreservationview": unmatched_view, "myreservationlist": _detail(journeys)})

        # when
        _, second = client.reservations.all()

        # then
        assert second.train.dep_date == "20260402"  # 둘째 구간의 운행일
        assert second.train.dep_date != "20260401"  # 첫 구간의 날짜는 빌리지 않습니다
