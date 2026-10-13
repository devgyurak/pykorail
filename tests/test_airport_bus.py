"""공항버스 리소스(``korail.airport_bus``)와 그 모델 — 정류장 · 시간표 · 좌석."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest

from pykorail.exceptions import KorailError, StationNotFoundError
from pykorail.models import AdultPassenger, AirportBus, BusStop, ChildPassenger
from pykorail.resources.clock import KST
from tests.payloads import (
    BUS_INFO,
    BUS_SCHEDULE_PAYLOAD,
    BUS_SEAT_MAP_PAYLOAD,
    BUS_STOPS_PAYLOAD,
    NO_BUSES_PAYLOAD,
    NO_RESULTS,
)

ROUTES = {"code": BUS_STOPS_PAYLOAD, "bus_schedule": BUS_SCHEDULE_PAYLOAD, "bus_seat_map": BUS_SEAT_MAP_PAYLOAD}

MORNING = datetime(2026, 10, 16, 6, 0, tzinfo=KST)

#: 앱 공통 필드 넷 + ``ScdlQryIn`` 가운데 값이 있는 것. 실서버에서 이 구성으로 성공했습니다.
SCHEDULE_FORM_FIELDS = [
    "Device",
    "Version",
    "AppVersion",
    "Key",
    "dptDt",
    "dptRsStnCd",
    "arvRsStnCd",
    "trnGpCd",
    "psrmClCd",
    "dptTm",
]

#: 앱 공통 필드 넷 + ``TResidualSeatsResearchIn`` 가운데 값이 있는 것. 실서버에서 이 구성으로 성공했습니다.
SEAT_FORM_FIELDS = [
    "Device",
    "Version",
    "AppVersion",
    "Key",
    "trnClsfCd",
    "trnGpCd",
    "runDt",
    "trnNo",
    "srcarNo",
    "psrmClCd",
    "dptRsStnCd",
    "arvRsStnCd",
    "dptStnRunOrdr",
    "arvStnRunOrdr",
    "totPsgCnt",
    "isArrow",
]


class TestStops:
    """정류장 목록 — ``common.code.do``."""

    def test_pairs_codes_with_names(self, make_korail) -> None:
        """이름과 코드가 따로 온 두 목록을 순서대로 짝짓습니다."""
        # given
        client, _ = make_korail(ROUTES)

        # when
        stops = client.airport_bus.stops()

        # then
        assert stops == [
            BusStop("0501", "광명역"),
            BusStop("0921", "인천공항T1"),
            BusStop("0923", "인천공항T2"),
            BusStop("0924", "송도국제교"),
        ]

    def test_asks_for_the_three_keys_as_repeated_fields(self, make_korail) -> None:
        """같은 이름의 필드를 세 번 싣습니다. dict 의 값에 목록을 넣으면 문자열 하나로 인코딩됩니다."""
        # given
        client, session = make_korail(ROUTES)

        # when
        client.airport_bus.stops()

        # then
        assert session.kwargs_for("code")["data"][4:] == [
            ("code", "app.limousine.stationNm"),
            ("code", "app.limousine.stationCd"),
            ("code", "app.limousine.airportBusMsg"),
        ]

    def test_carries_the_app_identity_first(self, make_korail) -> None:
        # given
        client, session = make_korail(ROUTES)

        # when
        client.airport_bus.stops()

        # then
        assert [name for name, _ in session.kwargs_for("code")["data"][:4]] == [
            "Device",
            "Version",
            "AppVersion",
            "Key",
        ]

    def test_second_call_uses_the_cache(self, make_korail) -> None:
        # given
        client, session = make_korail(ROUTES)
        client.airport_bus.stops()

        # when
        client.airport_bus.stops()

        # then
        assert len(session.all_kwargs_for("code")) == 1, "두 번째 호출은 캐시를 써야 합니다"

    def test_refresh_fetches_again(self, make_korail) -> None:
        # given
        client, session = make_korail(ROUTES)
        client.airport_bus.stops()

        # when
        client.airport_bus.stops(refresh=True)

        # then
        assert len(session.all_kwargs_for("code")) == 2

    def test_callers_cannot_break_the_cache(self, make_korail) -> None:
        # given
        client, _ = make_korail(ROUTES)
        client.airport_bus.stops().clear()

        # when
        stops = client.airport_bus.stops()

        # then
        assert len(stops) == 4

    @pytest.mark.parametrize(
        "body",
        [
            {"strResult": "SUCC"},
            {**BUS_STOPS_PAYLOAD, "app.limousine.stationCd": None},
            {**BUS_STOPS_PAYLOAD, "app.limousine.stationNm": "광명역"},
        ],
        ids=["absent", "null-codes", "names-not-a-list"],
    )
    def test_anything_but_two_lists_is_no_stops(self, make_korail, body: dict[str, object]) -> None:
        # given
        client, _ = make_korail({**ROUTES, "code": body})

        # when
        stops = client.airport_bus.stops()

        # then
        assert stops == []

    def test_lists_of_different_lengths_are_not_paired(self, make_korail, caplog) -> None:
        """잘라서 맞추면 어느 이름이 어느 코드인지 어긋난 채로 조회가 나갑니다."""
        # given
        body = {**BUS_STOPS_PAYLOAD, "app.limousine.stationCd": ["0501", "0921", "0923"]}
        client, _ = make_korail({**ROUTES, "code": body})

        # when
        stops = client.airport_bus.stops()

        # then
        assert stops == []
        assert "이름(4개)과 코드(3개)" in caplog.text

    def test_refusal_becomes_an_exception(self, make_korail) -> None:
        # given
        client, _ = make_korail({**ROUTES, "code": {"strResult": "FAIL", "h_msg_cd": "ERR999999"}})

        # when & then
        with pytest.raises(KorailError):
            client.airport_bus.stops()


class TestSearch:
    """시간표 — ``lmu.scdlQry.do``."""

    def test_lists_the_buses(self, make_korail) -> None:
        # given
        client, _ = make_korail(ROUTES)

        # when
        buses = client.airport_bus.search("광명역", "인천공항T1", MORNING)

        # then
        assert [(bus.bus_no, bus.dep_time, bus.remaining_seats, bus.has_seat()) for bus in buses] == [
            ("08008", "060000", 24, True),
            ("08010", "063000", 0, False),
        ]

    def test_buses_carry_the_stop_names_they_were_searched_by(self, make_korail) -> None:
        """시간표 응답에는 정류장 코드만 옵니다. 이름은 조회에 쓴 것을 함께 넣습니다."""
        # given
        client, _ = make_korail(ROUTES)

        # when
        bus = client.airport_bus.search("광명역", "인천공항T1", MORNING)[0]

        # then
        assert (bus.dep_code, bus.dep_name, bus.arr_code, bus.arr_name) == ("0501", "광명역", "0921", "인천공항T1")

    def test_sends_exact_form_fields(self, make_korail) -> None:
        """폼 필드 이름이 바뀌면 서버가 조용히 빈 결과를 줍니다."""
        # given
        client, session = make_korail(ROUTES)

        # when
        client.airport_bus.search("광명역", "인천공항T1", MORNING)

        # then
        assert list(session.kwargs_for("bus_schedule")["data"]) == SCHEDULE_FORM_FIELDS

    def test_sends_stops_by_code_and_the_moment_in_kst(self, make_korail) -> None:
        # given
        client, session = make_korail(ROUTES)

        # when
        client.airport_bus.search("인천공항T2", "광명역", MORNING)

        # then
        data = session.kwargs_for("bus_schedule")["data"]
        sent = {key: data[key] for key in SCHEDULE_FORM_FIELDS[4:]}
        assert sent == {
            "dptDt": "20261016",
            "dptRsStnCd": "0923",
            "arvRsStnCd": "0501",
            "trnGpCd": "980",
            "psrmClCd": "1",
            "dptTm": "060000",
        }

    def test_aware_moment_is_converted_to_kst(self, make_korail) -> None:
        """UTC 21:30 은 KST 로 다음 날 06:30 입니다."""
        # given
        client, session = make_korail(ROUTES)

        # when
        client.airport_bus.search("광명역", "인천공항T1", datetime(2026, 10, 15, 21, 30, tzinfo=UTC))

        # then
        data = session.kwargs_for("bus_schedule")["data"]
        assert (data["dptDt"], data["dptTm"]) == ("20261016", "063000")

    def test_unknown_stop_is_rejected_before_the_schedule_request(self, make_korail) -> None:
        # given
        client, session = make_korail(ROUTES)

        # when
        with pytest.raises(StationNotFoundError, match="존재하지 않는 정류장입니다: '인천공항'"):
            client.airport_bus.search("광명역", "인천공항")

        # then
        assert session.all_kwargs_for("bus_schedule") == []

    def test_unknown_stop_suggests_the_close_names(self, make_korail) -> None:
        # given
        client, _ = make_korail(ROUTES)

        # when
        with pytest.raises(StationNotFoundError) as exc:
            client.airport_bus.search("광명", "인천공항T1")

        # then
        assert exc.value.suggestions["광명"] == ["광명역"]

    @pytest.mark.parametrize(
        "body",
        [NO_RESULTS, {**BUS_SCHEDULE_PAYLOAD, "trainList": None}, {**BUS_SCHEDULE_PAYLOAD, "trainList": []}],
        ids=["no-results", "null", "empty"],
    )
    def test_no_buses_is_an_empty_list(self, make_korail, body: dict[str, object]) -> None:
        # given
        client, _ = make_korail({**ROUTES, "bus_schedule": body})

        # when
        buses = client.airport_bus.search("광명역", "인천공항T1", MORNING)

        # then
        assert buses == []

    def test_direction_korail_does_not_sell_is_an_empty_list(self, make_korail) -> None:
        """인천공항 → 광명역은 실서버가 "결과 없음" 으로 답합니다. 파는 편이 없는 것이지 오류가 아닙니다."""
        # given
        client, session = make_korail({**ROUTES, "bus_schedule": NO_BUSES_PAYLOAD})

        # when
        buses = client.airport_bus.search("인천공항T1", "광명역", MORNING)

        # then
        data = session.kwargs_for("bus_schedule")["data"]
        assert (buses, data["dptRsStnCd"], data["arvRsStnCd"]) == ([], "0921", "0501")

    def test_goes_in_the_form_body_unsigned(self, make_korail) -> None:
        # given
        client, session = make_korail(ROUTES)

        # when
        client.airport_bus.search("광명역", "인천공항T1", MORNING)

        # then
        kwargs = session.kwargs_for("bus_schedule")
        assert "params" not in kwargs
        assert "x-dynapath-m-token" not in kwargs.get("headers", {})


class TestSeats:
    """좌석 배치 — ``lms.TResidualSeatsResearch.do``."""

    def test_lists_the_seats(self, make_korail) -> None:
        # given
        client, _ = make_korail(ROUTES)
        bus = client.airport_bus.search("광명역", "인천공항T1", MORNING)[0]

        # when
        seats = client.airport_bus.seats(bus)

        # then
        assert [(seat.car_no, seat.seat_no, seat.label, seat.is_available) for seat in seats] == [
            ("0001", "1", "1", True),
            ("0001", "2", "2", False),
        ]

    def test_seats_are_general_class(self, make_korail) -> None:
        # given
        client, _ = make_korail(ROUTES)
        bus = client.airport_bus.search("광명역", "인천공항T1", MORNING)[0]

        # when
        seats = client.airport_bus.seats(bus)

        # then
        assert {seat.seat_class for seat in seats} == {"1"}

    def test_sends_exact_form_fields(self, make_korail) -> None:
        # given
        client, session = make_korail(ROUTES)
        bus = client.airport_bus.search("광명역", "인천공항T1", MORNING)[0]

        # when
        client.airport_bus.seats(bus)

        # then
        assert list(session.kwargs_for("bus_seat_map")["data"]) == SEAT_FORM_FIELDS

    def test_sends_the_bus_as_the_schedule_gave_it(self, make_korail) -> None:
        """편의 값은 시간표 행 그대로, 호차는 상수입니다. 편 번호의 0 을 떼거나 채우지 않습니다."""
        # given
        client, session = make_korail(ROUTES)
        bus = client.airport_bus.search("광명역", "인천공항T1", MORNING)[0]

        # when
        client.airport_bus.seats(bus)

        # then
        data = session.kwargs_for("bus_seat_map")["data"]
        sent = {key: data[key] for key in SEAT_FORM_FIELDS[4:]}
        assert sent == {
            "trnClsfCd": "98",
            "trnGpCd": "980",
            "runDt": "20261016",
            "trnNo": "08008",
            "srcarNo": "0001",
            "psrmClCd": "1",
            "dptRsStnCd": "0501",
            "arvRsStnCd": "0921",
            "dptStnRunOrdr": "000001",
            "arvStnRunOrdr": "000002",
            "totPsgCnt": "1",
            "isArrow": "false",
        }

    def test_headcount_adds_every_passenger(self, make_korail) -> None:
        # given
        client, session = make_korail(ROUTES)
        bus = client.airport_bus.search("광명역", "인천공항T1", MORNING)[0]

        # when
        client.airport_bus.seats(bus, [AdultPassenger(2), ChildPassenger(1)])

        # then
        assert session.kwargs_for("bus_seat_map")["data"]["totPsgCnt"] == "3"

    @pytest.mark.parametrize("attribute", ["bus_no", "bus_type", "group", "dep_run_order", "arr_run_order"])
    def test_bus_without_the_needed_values_is_rejected_before_any_request(self, make_korail, attribute: str) -> None:
        # given
        client, session = make_korail(ROUTES)
        bus = dataclasses.replace(client.airport_bus.search("광명역", "인천공항T1", MORNING)[0], **{attribute: ""})

        # when
        with pytest.raises(ValueError, match=attribute):
            client.airport_bus.seats(bus)

        # then
        assert session.all_kwargs_for("bus_seat_map") == []

    @pytest.mark.parametrize(
        "body",
        [
            {key: value for key, value in BUS_SEAT_MAP_PAYLOAD.items() if key != "seatList"},
            {**BUS_SEAT_MAP_PAYLOAD, "seatList": None},
        ],
        ids=["absent", "null"],
    )
    def test_no_seats_is_an_empty_list(self, make_korail, body: dict[str, object]) -> None:
        # given
        client, _ = make_korail({**ROUTES, "bus_seat_map": body})
        bus = client.airport_bus.search("광명역", "인천공항T1", MORNING)[0]

        # when
        seats = client.airport_bus.seats(bus)

        # then
        assert seats == []

    def test_car_number_falls_back_when_the_server_leaves_it_out(self, make_korail) -> None:
        # given
        body = {key: value for key, value in BUS_SEAT_MAP_PAYLOAD.items() if key != "scar_no"}
        client, _ = make_korail({**ROUTES, "bus_seat_map": body})
        bus = client.airport_bus.search("광명역", "인천공항T1", MORNING)[0]

        # when
        seats = client.airport_bus.seats(bus)

        # then
        assert {seat.car_no for seat in seats} == {"0001"}

    def test_goes_in_the_form_body_unsigned(self, make_korail) -> None:
        # given
        client, session = make_korail(ROUTES)
        bus = client.airport_bus.search("광명역", "인천공항T1", MORNING)[0]

        # when
        client.airport_bus.seats(bus)

        # then
        kwargs = session.kwargs_for("bus_seat_map")
        assert "params" not in kwargs
        assert "x-dynapath-m-token" not in kwargs.get("headers", {})


class TestAirportBusModel:
    def test_reads_zero_padded_numbers(self) -> None:
        """서버는 남은 좌석을 여섯 자리, 운임을 열네 자리로 0 을 채워 줍니다."""
        # when
        bus = AirportBus.from_response(BUS_INFO, dep_name="광명역", arr_name="인천공항T1")

        # then
        assert (bus.remaining_seats, bus.price) == (24, 16000)

    def test_missing_fields_do_not_break_the_model(self) -> None:
        # when
        bus = AirportBus.from_response({}, dep_name="광명역", arr_name="인천공항T1")

        # then
        assert (bus.bus_no, bus.remaining_seats, bus.price, bus.has_seat()) == ("", 0, 0, False)

    def test_repr_reads_like_a_timetable_row(self) -> None:
        # when
        shown = repr(AirportBus.from_response(BUS_INFO, dep_name="광명역", arr_name="인천공항T1"))

        # then
        assert shown == "[공항버스 08008] 10/16 06:00~06:50  광명역~인천공항T1  24석"

    @pytest.mark.parametrize(
        ("model", "field"),
        [
            (AirportBus.from_response(BUS_INFO, dep_name="광명역", arr_name="인천공항T1"), "bus_no"),
            (BusStop("0501", "광명역"), "name"),
        ],
        ids=["bus", "stop"],
    )
    def test_models_are_frozen(self, model: object, field: str) -> None:
        # when & then
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(model, field, "changed")
