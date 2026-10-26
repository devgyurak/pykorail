# 이 파일은 생성물입니다 — 직접 고치지 마세요.
# 원본: tests/_async/test_resources.py
# 다시 만들려면: uv run python scripts/unasync.py
"""리소스별 동작 — 조회·예매·결제·승차권."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest

from pykorail._shared.blank import without_blanks
from pykorail._shared.clock import KST, to_kst
from pykorail._sync.resources import trains
from pykorail._sync.resources.trains import MAX_PAGES, PAST_TOLERANCE
from pykorail.constants import API_ENDPOINTS
from pykorail.exceptions import (
    AccessRestrictedError,
    KorailError,
    NeedToLoginError,
    NoResultsError,
    PastDepartureError,
    StationNotFoundError,
)
from pykorail.models import AdultPassenger, Card, ChildPassenger, Reservation, Seat, Ticket, Transfer
from pykorail.options import SeatClass
from tests._sync.conftest import Replies, Reply
from tests.payloads import (
    ACCESS_RESTRICTED,
    CAR_INFO,
    FARE_PAYLOAD,
    FIRST_LEG_INFO,
    MANY_RESERVATION_IDS,
    MANY_RESERVATIONS_PAYLOAD,
    NEARBY_SEARCH_PAYLOAD,
    NO_RESULTS,
    OK,
    REFUND_FEE_PAYLOAD,
    RESERVATION_LIST_PAYLOAD,
    RESERVE_OK,
    SEARCH_PAYLOAD,
    SEAT_CARS_PAYLOAD,
    SEAT_DETAIL_PAYLOAD,
    SEAT_INFO,
    SEAT_MAP_PAYLOAD,
    SEATABLE_SEARCH_PAYLOAD,
    SECOND_LEG_INFO,
    SOLD_OUT_INFO,
    STATION_PAYLOAD,
    TICKET_LIST_PAYLOAD,
    TICKET_SEAT_PAYLOAD,
    TRAIN_INFO,
    TRANSFER_FARE_PAYLOAD,
    TRANSFER_SEARCH_PAYLOAD,
    TRANSFER_STATIONS_PAYLOAD,
)

#: 예약이 여럿인 목록에 좌석 상세를 얹은 라우트. 응답 자체는 payloads 에 있습니다.
MANY_RESERVATIONS_ROUTES = {
    "myreservationview": MANY_RESERVATIONS_PAYLOAD,
    "myreservationlist": SEAT_DETAIL_PAYLOAD,
}

#: 위 목록에 열차 조회·예매를 얹어 create() 까지 돌릴 수 있게 하는 라우트.
SEARCHABLE_ROUTES = {
    "stationdata": STATION_PAYLOAD,
    "search_schedule": SEARCH_PAYLOAD,
    "reserve": RESERVE_OK,
}

#: 과거 조회 가드에 걸리지 않도록 넉넉히 미래인 기준 시각. 초까지 고정해야
#: 전송값을 정확히 단언할 수 있습니다.
FUTURE = (datetime.now(KST) + timedelta(days=30)).replace(hour=9, minute=30, second=0, microsecond=0)
FUTURE_UTC = (datetime.now(UTC) + timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)


def train_departing(train_no: str, departs: datetime, **overrides: str) -> dict[str, str]:
    """``departs`` 에 떠나는 열차 한 편의 응답. 필드 이름은 ``TRAIN_INFO`` 그대로입니다."""
    return {
        **TRAIN_INFO,
        "h_trn_no": train_no,
        "h_dpt_dt": departs.strftime("%Y%m%d"),
        "h_dpt_tm": departs.strftime("%H%M%S"),
        "h_run_dt": departs.strftime("%Y%m%d"),
        **overrides,
    }


def search_page(*trains: dict[str, str]) -> dict[str, object]:
    return {"strResult": "SUCC", "trn_infos": {"trn_info": list(trains)}}


#: 쪽 이어 받기용 열차들. ``FUTURE``(09:30) 이후 한 시간 간격으로 떠납니다.
TRAIN_1000 = train_departing("101", FUTURE.replace(hour=10, minute=0))
TRAIN_1100 = train_departing("103", FUTURE.replace(hour=11, minute=0))
TRAIN_1200 = train_departing("105", FUTURE.replace(hour=12, minute=0))

#: 첫 쪽과, 그 마지막 열차의 출발 시각부터 다시 조회했을 때의 다음 쪽. 서버는 그 시각의
#: 열차를 다시 싣고 시작하므로 103 이 두 쪽에 모두 나옵니다.
FIRST_PAGE = search_page(TRAIN_1000, TRAIN_1100)
SECOND_PAGE = search_page(TRAIN_1100, TRAIN_1200)
#: 더 받을 것이 없을 때: 마지막 열차만 다시 내려옵니다.
NOTHING_NEW_PAGE = search_page(TRAIN_1100)


def paged_routes(*pages: object) -> dict[str, object]:
    return {"stationdata": STATION_PAYLOAD, "search_schedule": Replies(*pages)}


#: 호차 · 좌석 조회까지 돌릴 수 있는 라우트. 조회 결과에 운행 순서 · 좌석 속성이 들어 있습니다.
SEAT_ROUTES = {
    "stationdata": STATION_PAYLOAD,
    "search_schedule": SEATABLE_SEARCH_PAYLOAD,
    "seat_cars": SEAT_CARS_PAYLOAD,
    "seat_map": SEAT_MAP_PAYLOAD,
}

#: 앱의 요청 모델(TrainResearchIn)에서 값이 있을 때 실리는 필드 전체.
CARS_FORM_FIELDS = {
    "Device",
    "Version",
    "AppVersion",
    "Key",
    "txtMenuId",
    "txtRunDt",
    "txtDptDt",
    "txtTrnNo",
    "txtDptTm",
    "txtTrnClsfCd",
    "txtTrnGpCd",
    "txtDptRsStnCd",
    "txtArvRsStnCd",
    "txtPsrmClCd",
    "txtSeatAttCd",
    "txtDptStnRunOrdr",
    "txtArvStnRunOrdr",
    "txtTotPsgCnt",
}

#: 앱의 요청 모델(TResidualSeatsResearchIn)에서 값이 있을 때 실리는 필드 전체.
SEATS_FORM_FIELDS = {
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
    "seatAttCd",
    "dptStnRunOrdr",
    "arvStnRunOrdr",
    "totPsgCnt",
    "isArrow",
}


class TestToKst:
    def test_naive_is_treated_as_kst(self) -> None:
        # when
        result = to_kst(datetime(2026, 4, 1, 9, 0))

        # then
        assert result.tzinfo == KST
        assert result.hour == 9

    def test_aware_is_converted(self) -> None:
        # given
        utc_midnight = datetime(2026, 4, 1, 0, 0, tzinfo=UTC)

        # when
        result = to_kst(utc_midnight)

        # then
        assert result.hour == 9

    def test_none_is_now_in_kst(self) -> None:
        # when
        result = to_kst(None)

        # then
        assert result.tzinfo == KST

    def test_trains_keeps_re_exposing_the_shared_names(self) -> None:
        """``resources.trains`` 로 가져오던 옛 경로가 그대로 남아 있어야 합니다."""
        # when & then
        assert trains.KST is KST
        assert trains.to_kst is to_kst


class TestStations:
    def test_parses_and_caches(self, korail) -> None:
        # given
        client, session = korail

        # when
        first = client.stations.all()
        second = client.stations.all()

        # then
        assert [s.name for s in first] == ["서울", "부산", "대전"]
        assert first == second
        assert len(session.calls) == 1, "두 번째 호출은 캐시를 써야 합니다"

    def test_refresh_refetches(self, korail) -> None:
        # given
        client, session = korail
        client.stations.all()

        # when
        client.stations.all(refresh=True)

        # then
        assert len(session.calls) == 2

    def test_returned_list_is_a_copy(self, korail) -> None:
        # given
        client, _ = korail

        # when
        (client.stations.all()).clear()

        # then
        assert len(client.stations.all()) == 3

    def test_find_by_name(self, korail) -> None:
        # given
        client, _ = korail

        # when
        station = client.stations.find("부산")

        # then
        assert station is not None
        assert station.code == "0020"

    def test_find_unknown_returns_none(self, korail) -> None:
        # given
        client, _ = korail

        # when
        station = client.stations.find("짜장")

        # then
        assert station is None

    def test_major_flag_and_coordinates(self, korail) -> None:
        # given
        client, _ = korail

        # when
        seoul = client.stations.find("서울")

        # then
        assert seoul is not None
        assert seoul.is_major
        assert seoul.latitude == pytest.approx(37.55)

    def test_works_without_login(self, korail) -> None:
        """공개 조회라 로그인 전에도 동작해야 합니다."""
        # given
        client, _ = korail

        # when
        stations = client.stations.all()

        # then
        assert not client.is_logged_in
        assert stations


class TestStationValidation:
    def test_unknown_departure_is_rejected_before_search(self, korail) -> None:
        # given
        client, session = korail

        # when
        with pytest.raises(StationNotFoundError) as exc:
            client.trains.search("짜장", "부산")

        # then
        assert exc.value.names == ["짜장"]
        assert session.urls() == [API_ENDPOINTS["stationdata"]], "조회는 아예 보내지 않아야 합니다"

    def test_reports_both_unknown_stations(self, korail) -> None:
        # given
        client, _ = korail

        # when
        with pytest.raises(StationNotFoundError) as exc:
            client.trains.search("짜장", "탕수육")

        # then
        assert exc.value.names == ["짜장", "탕수육"]

    def test_suggests_close_matches(self, make_korail) -> None:
        # given
        payload = {
            "stns": {
                "stn": [
                    {"stn_cd": "0001", "stn_nm": "서울역", "group": "1", "popupType": "0", "popupMessage": ""},
                ]
            }
        }
        client, _ = make_korail({"stationdata": payload})

        # when
        with pytest.raises(StationNotFoundError) as exc:
            client.trains.search("서울", "서울역")

        # then
        assert exc.value.suggestions["서울"] == ["서울역"]

    def test_can_be_disabled(self, make_korail) -> None:
        # given
        client, session = make_korail({"search_schedule": SEARCH_PAYLOAD}, validate_stations=False)

        # when
        client.trains.search("짜장", "부산")

        # then
        assert session.urls() == [API_ENDPOINTS["search_schedule"]]


class TestPastDepartureGuard:
    """서버는 과거 시각에도 빈 결과만 주므로 "떠난 열차"와 "열차 없음"이 구분되지 않습니다."""

    def test_rejects_a_past_departure(self, korail) -> None:
        # given
        client, _ = korail
        long_gone = datetime.now(KST) - timedelta(hours=1)

        # when & then
        with pytest.raises(PastDepartureError):
            client.trains.search("서울", "부산", depart_after=long_gone)

    def test_blocks_before_sending_the_search(self, korail) -> None:
        # given
        client, session = korail
        long_gone = datetime.now(KST) - timedelta(days=1)

        # when
        with pytest.raises(PastDepartureError):
            client.trains.search("서울", "부산", depart_after=long_gone)

        # then
        assert API_ENDPOINTS["search_schedule"] not in session.urls()

    def test_error_carries_both_times(self, korail) -> None:
        # given
        client, _ = korail
        long_gone = datetime.now(KST) - timedelta(hours=2)

        # when
        with pytest.raises(PastDepartureError) as exc:
            client.trains.search("서울", "부산", depart_after=long_gone)

        # then
        assert exc.value.requested == long_gone
        assert exc.value.now > exc.value.requested

    def test_accepts_a_future_departure(self, korail) -> None:
        # given
        client, _ = korail
        later = datetime.now(KST) + timedelta(hours=1)

        # when
        trains = client.trains.search("서울", "부산", depart_after=later)

        # then
        assert trains

    def test_accepts_now(self, korail) -> None:
        """호출자가 `datetime.now()` 를 그대로 넘기는 것이 가장 흔한 형태입니다."""
        # given
        client, _ = korail

        # when
        trains = client.trains.search("서울", "부산", depart_after=datetime.now(KST))

        # then
        assert trains

    def test_accepts_omitted_departure(self, korail) -> None:
        # given
        client, _ = korail

        # when
        trains = client.trains.search("서울", "부산")

        # then
        assert trains

    def test_tolerates_small_clock_skew(self, korail) -> None:
        """연산·왕복 지연으로 몇 초 지난 것까지 막으면 못 씁니다."""
        # given
        client, _ = korail
        just_now = datetime.now(KST) - PAST_TOLERANCE / 2

        # when
        trains = client.trains.search("서울", "부산", depart_after=just_now)

        # then
        assert trains

    def test_naive_past_datetime_is_also_rejected(self, korail) -> None:
        """naive 는 KST 로 해석되므로 과거 판정도 KST 기준입니다."""
        # given
        client, _ = korail
        naive_past = (datetime.now(KST) - timedelta(hours=3)).replace(tzinfo=None)

        # when & then
        with pytest.raises(PastDepartureError):
            client.trains.search("서울", "부산", depart_after=naive_past)

    def test_utc_past_datetime_is_converted_then_rejected(self, korail) -> None:
        # given
        client, _ = korail
        utc_past = datetime.now(UTC) - timedelta(hours=5)

        # when & then
        with pytest.raises(PastDepartureError):
            client.trains.search("서울", "부산", depart_after=utc_past)


class TestTrainSearchPages:
    """조회 결과 이어 받기 — 마지막 열차의 출발 시각부터 다시 조회합니다."""

    def test_single_page_by_default(self, make_korail) -> None:
        # given
        client, session = make_korail(paged_routes(FIRST_PAGE, SECOND_PAGE))

        # when
        trains = client.trains.search("서울", "부산", depart_after=FUTURE)

        # then
        assert [t.train_no for t in trains] == ["101", "103"]
        assert len(session.all_kwargs_for("search_schedule")) == 1, "기본값은 요청 한 번이어야 합니다"

    def test_joins_the_next_page_without_repeating_the_boundary_train(self, make_korail) -> None:
        # given
        client, _ = make_korail(paged_routes(FIRST_PAGE, SECOND_PAGE))

        # when
        trains = client.trains.search("서울", "부산", depart_after=FUTURE, max_pages=2)

        # then
        assert [t.train_no for t in trains] == ["101", "103", "105"]

    def test_next_page_starts_at_the_last_departure(self, make_korail) -> None:
        # given
        client, session = make_korail(paged_routes(FIRST_PAGE, SECOND_PAGE))

        # when
        client.trains.search("서울", "부산", depart_after=FUTURE, max_pages=2)

        # then
        second = session.all_kwargs_for("search_schedule")[1]["params"]
        assert (second["txtGoAbrdDt"], second["txtGoHour"]) == (FUTURE.strftime("%Y%m%d"), "110000")

    def test_next_page_changes_nothing_but_the_departure_moment(self, make_korail) -> None:
        """다음 쪽은 같은 요청입니다 — 다른 필드가 달라지면 서버는 다른 조회로 봅니다."""
        # given
        client, session = make_korail(paged_routes(FIRST_PAGE, SECOND_PAGE))

        # when
        client.trains.search("서울", "부산", depart_after=FUTURE, max_pages=2)

        # then
        first, second = (call["params"] for call in session.all_kwargs_for("search_schedule"))
        changed = {key for key in first if first[key] != second[key]}
        assert changed == {"txtGoHour"}
        assert set(first) == set(second)

    def test_stops_early_when_a_page_brings_nothing_new(self, make_korail) -> None:
        # given
        client, session = make_korail(paged_routes(FIRST_PAGE, NOTHING_NEW_PAGE))

        # when
        trains = client.trains.search("서울", "부산", depart_after=FUTURE, max_pages=5)

        # then
        assert [t.train_no for t in trains] == ["101", "103"]
        assert len(session.all_kwargs_for("search_schedule")) == 2, "새 열차가 없으면 상한 전에 멈춰야 합니다"

    def test_keeps_earlier_pages_when_a_later_page_has_no_results(self, make_korail) -> None:
        # given
        client, _ = make_korail(paged_routes(FIRST_PAGE, NO_RESULTS))

        # when
        trains = client.trains.search("서울", "부산", depart_after=FUTURE, max_pages=3)

        # then
        assert [t.train_no for t in trains] == ["101", "103"]

    def test_no_results_on_the_first_page_still_raises(self, make_korail) -> None:
        # given
        client, session = make_korail(paged_routes(NO_RESULTS, SECOND_PAGE))

        # when & then
        with pytest.raises(NoResultsError):
            client.trains.search("서울", "부산", depart_after=FUTURE, max_pages=3)
        assert len(session.all_kwargs_for("search_schedule")) == 1, "첫 쪽이 비면 더 조회하지 않습니다"

    def test_stops_when_the_last_departure_is_unreadable(self, make_korail) -> None:
        """출발 시각이 비어 오면 어디서부터 이어 받을지 알 수 없습니다."""
        # given
        timeless = train_departing("103", FUTURE, h_dpt_tm="")
        client, session = make_korail(paged_routes(search_page(TRAIN_1000, timeless), SECOND_PAGE))

        # when
        client.trains.search("서울", "부산", depart_after=FUTURE, max_pages=3)

        # then
        assert len(session.all_kwargs_for("search_schedule")) == 1

    def test_seat_filter_applies_to_every_page(self, make_korail) -> None:
        # given
        sold_out = train_departing("105", FUTURE.replace(hour=12, minute=0), h_spe_rsv_cd="00", h_gen_rsv_cd="00")
        client, _ = make_korail(paged_routes(FIRST_PAGE, search_page(TRAIN_1100, sold_out)))

        # when
        trains = client.trains.search("서울", "부산", depart_after=FUTURE, max_pages=2)

        # then
        assert [t.train_no for t in trains] == ["101", "103"]

    def test_the_upper_limit_itself_is_accepted(self, make_korail) -> None:
        # given
        client, _ = make_korail(paged_routes(FIRST_PAGE, NOTHING_NEW_PAGE))

        # when
        trains = client.trains.search("서울", "부산", depart_after=FUTURE, max_pages=MAX_PAGES)

        # then
        assert [t.train_no for t in trains] == ["101", "103"]

    @pytest.mark.parametrize("max_pages", [0, -1, MAX_PAGES + 1, 1000])
    def test_rejects_a_page_limit_out_of_range_before_any_request(self, make_korail, max_pages: int) -> None:
        # given
        client, session = make_korail(paged_routes(FIRST_PAGE))

        # when & then
        with pytest.raises(ValueError, match="max_pages"):
            client.trains.search("서울", "부산", depart_after=FUTURE, max_pages=max_pages)
        assert session.calls == []


class TestTrainSearch:
    def test_filters_out_sold_out_by_default(self, korail) -> None:
        # given
        client, _ = korail

        # when
        trains = client.trains.search("서울", "부산")

        # then
        assert [t.train_no for t in trains] == ["101"]

    def test_include_no_seats_returns_everything(self, korail) -> None:
        # given
        client, _ = korail

        # when
        trains = client.trains.search("서울", "부산", include_no_seats=True)

        # then
        assert [t.train_no for t in trains] == ["101", "103"]

    def test_raises_when_nothing_matches(self, make_korail) -> None:
        # given
        empty = {"strResult": "SUCC", "trn_infos": {"trn_info": []}}
        client, _ = make_korail({"stationdata": STATION_PAYLOAD, "search_schedule": empty})

        # when & then
        with pytest.raises(NoResultsError):
            client.trains.search("서울", "부산")

    @pytest.mark.parametrize("status", [403, 200])
    @pytest.mark.parametrize("code", ["-2000", -2000])
    def test_access_restriction_is_not_reported_as_no_results(self, make_korail, status: int, code: object) -> None:
        """이용제한을 "열차 없음" 으로 바꾸면 대기 루프가 원인을 모른 채 계속 돕니다 (이슈 #27).

        봉투가 HTTP 200 으로 와도 같습니다 — 상태 코드가 아니라 봉투가 거절을 말합니다.
        """
        # given
        restricted = Reply(status, {**ACCESS_RESTRICTED, "code": code})
        client, _ = make_korail({"stationdata": STATION_PAYLOAD, "search_schedule": restricted})

        # when
        with pytest.raises(AccessRestrictedError) as exc:
            client.trains.search("서울", "부산")

        # then
        assert (exc.value.status_code, exc.value.code) == (status, "-2000")

    def test_sends_departure_time_in_kst(self, korail) -> None:
        # given
        client, session = korail

        # when
        client.trains.search("서울", "부산", depart_after=FUTURE)

        # then
        params = session.kwargs_for("search_schedule")["params"]
        assert params["txtGoAbrdDt"] == FUTURE.strftime("%Y%m%d")
        assert params["txtGoHour"] == "093000"

    def test_converts_aware_datetime(self, korail) -> None:
        # given
        client, session = korail

        # when
        client.trains.search("서울", "부산", depart_after=FUTURE_UTC)

        # then
        assert session.kwargs_for("search_schedule")["params"]["txtGoHour"] == "090000"

    def test_passenger_counts_are_grouped(self, korail) -> None:
        # given
        client, session = korail

        # when
        client.trains.search("서울", "부산", passengers=[AdultPassenger(1), ChildPassenger(1), AdultPassenger(2)])

        # then
        params = session.kwargs_for("search_schedule")["params"]
        assert params["txtPsgFlg_1"] == 3
        assert params["txtPsgFlg_2"] == 1

    def test_search_is_signed(self, korail) -> None:
        # given
        client, session = korail

        # when
        client.trains.search("서울", "부산")

        # then
        assert "x-dynapath-m-token" in session.kwargs_for("search_schedule")["headers"]

    def test_search_sends_empty_sid_and_no_key(self, korail) -> None:
        """조회 엔드포인트만 Key 없이 빈 Sid 를 보냅니다 (앱 동작)."""
        # given
        client, session = korail

        # when
        client.trains.search("서울", "부산")

        # then
        params = session.kwargs_for("search_schedule")["params"]
        assert params["Sid"] == ""
        assert "Key" not in params


#: 환승 조회를 돌리는 라우트. 같은 엔드포인트가 여정 종류에 따라 다른 모양을 줍니다.
TRANSFER_ROUTES = {"stationdata": STATION_PAYLOAD, "search_schedule": TRANSFER_SEARCH_PAYLOAD}


def transfer_page(*rows: dict[str, str]) -> dict[str, object]:
    return {"stationdata": STATION_PAYLOAD, "search_schedule": search_page(*rows)}


class TestTransferStations:
    """환승역 — ``qry.chtnStn.do``."""

    def test_lists_the_stations_to_change_at(self, korail) -> None:
        # given
        client, _ = korail

        # when
        stations = client.trains.transfer_stations("서울", "부산")

        # then
        assert [(s.code, s.name, s.english_name) for s in stations] == [
            ("0015", "대전", "Daejeon"),
            ("0001", "서울", ""),
        ]

    def test_sends_exact_form_fields(self, korail) -> None:
        """폼 필드 이름이 바뀌면 서버가 조용히 빈 결과를 줍니다."""
        # given
        client, session = korail

        # when
        client.trains.transfer_stations("서울", "부산")

        # then
        assert set(session.kwargs_for("transfer_stations")["data"]) == {
            "Device",
            "Version",
            "AppVersion",
            "Key",
            "dptRsStnCd",
            "arvRsStnCd",
        }

    def test_sends_station_codes_not_names(self, korail) -> None:
        # given
        client, session = korail

        # when
        client.trains.transfer_stations("서울", "부산")

        # then
        data = session.kwargs_for("transfer_stations")["data"]
        assert (data["dptRsStnCd"], data["arvRsStnCd"]) == ("0001", "0020")

    def test_goes_in_the_form_body_and_unsigned(self, korail) -> None:
        # given
        client, session = korail

        # when
        client.trains.transfer_stations("서울", "부산")

        # then
        kwargs = session.kwargs_for("transfer_stations")
        assert "params" not in kwargs
        assert "x-dynapath-m-token" not in kwargs.get("headers", {})

    def test_unknown_station_is_rejected_before_the_request(self, korail) -> None:
        # given
        client, session = korail

        # when & then
        with pytest.raises(StationNotFoundError):
            client.trains.transfer_stations("서울", "부산역")
        assert API_ENDPOINTS["transfer_stations"] not in session.urls()

    def test_needs_the_station_master_even_when_validation_is_off(self, make_korail) -> None:
        """역을 코드로 보내야 해서, 검증을 꺼도 역 마스터는 봅니다."""
        # given
        routes = {"stationdata": STATION_PAYLOAD, "transfer_stations": TRANSFER_STATIONS_PAYLOAD}
        client, session = make_korail(routes, validate_stations=False)

        # when
        client.trains.transfer_stations("서울", "부산")

        # then
        assert session.urls() == [API_ENDPOINTS["stationdata"], API_ENDPOINTS["transfer_stations"]]

    @pytest.mark.parametrize(
        "body",
        [{"strResult": "SUCC"}, {"strResult": "SUCC", "chtnList": None}, {"strResult": "SUCC", "chtnList": []}],
        ids=["absent", "null", "empty"],
    )
    def test_no_stations_is_an_empty_list(self, make_korail, body: dict[str, object]) -> None:
        # given
        client, _ = make_korail({"stationdata": STATION_PAYLOAD, "transfer_stations": body})

        # when
        stations = client.trains.transfer_stations("서울", "부산")

        # then
        assert stations == []


class TestRunDates:
    """운행 달력 — ``schedule.runDt``."""

    def test_sends_exact_form_fields(self, korail) -> None:
        """폼 필드 이름이 바뀌면 서버가 조용히 다른 달력을 줍니다."""
        # given
        client, session = korail

        # when
        client.trains.run_dates()

        # then
        assert set(session.kwargs_for("run_dates")["data"]) == {
            "Device",
            "Version",
            "AppVersion",
            "Key",
            "timeStamp",
        }

    def test_timestamp_is_the_request_time_in_epoch_milliseconds(self, korail, monkeypatch) -> None:
        # given
        client, session = korail
        monkeypatch.setattr(trains.time, "time_ns", lambda: 1_700_000_000_123_000_000)

        # when
        client.trains.run_dates()

        # then
        assert session.kwargs_for("run_dates")["data"]["timeStamp"] == "1700000000123"

    def test_goes_in_the_form_body_and_unsigned(self, korail) -> None:
        # given
        client, session = korail

        # when
        client.trains.run_dates()

        # then
        kwargs = session.kwargs_for("run_dates")
        assert "params" not in kwargs
        assert "x-dynapath-m-token" not in kwargs.get("headers", {})

    def test_parses_every_field_verbatim(self, korail) -> None:
        # given
        client, _ = korail

        # when
        run_dates = client.trains.run_dates()

        # then
        first = run_dates[0]
        assert (first.run_date, first.biz_dd_stg_cd, first.day_dv_cd) == ("20261016", "1", "6")
        assert (first.hldy_dv_cd, first.sale_dd_dv_cd) == ("", "5")
        assert (first.o_trn_op_flg, first.v_trn_op_flg, first.s_trn_op_flg) == ("Y", "N", "Y")
        assert (first.d_trn_op_flg, first.a_trn_op_flg, first.g_trn_op_flg, first.x_trn_op_flg) == ("N", "N", "N", "N")

    def test_blank_item_keeps_empty_strings(self, korail) -> None:
        """플래그의 세 번째 상태(빈 값)를 불리언으로 접지 않습니다."""
        # given
        client, _ = korail

        # when
        run_dates = client.trains.run_dates()

        # then
        blank = run_dates[2]
        assert (blank.run_date, blank.biz_dd_stg_cd, blank.s_trn_op_flg) == ("", "", "")

    def test_peak_season_flag_is_biz_dd_stg_cd_5(self, korail) -> None:
        # given
        client, _ = korail

        # when
        run_dates = client.trains.run_dates()

        # then
        assert [day.is_peak_season for day in run_dates] == [False, True, False]

    @pytest.mark.parametrize(
        "body",
        [
            {"strResult": "SUCC"},
            {"strResult": "SUCC", "runningCalendar": None},
            {"strResult": "SUCC", "runningCalendar": []},
        ],
        ids=["absent", "null", "empty"],
    )
    def test_no_calendar_is_an_empty_list(self, make_korail, body: dict[str, object]) -> None:
        # given
        client, _ = make_korail({"run_dates": body})

        # when
        run_dates = client.trains.run_dates()

        # then
        assert run_dates == []

    def test_failure_response_raises(self, make_korail) -> None:
        # given
        client, _ = make_korail({"run_dates": NO_RESULTS})

        # when & then
        with pytest.raises(KorailError):
            client.trains.run_dates()


class TestTransferSearch:
    """환승 여정 — 직통 조회와 같은 엔드포인트, 여정 종류만 다릅니다."""

    def test_pairs_the_two_legs_of_an_itinerary(self, make_korail) -> None:
        # given
        client, _ = make_korail(TRANSFER_ROUTES)

        # when
        transfers = client.trains.search_transfers("서울", "부산")

        # then
        assert [(t.first.train_no, t.station_name, t.second.train_no) for t in transfers] == [("101", "대전", "1201")]

    def test_itinerary_with_a_sold_out_leg_is_hidden_by_default(self, make_korail) -> None:
        """한 구간만 좌석이 있어서는 여정을 탈 수 없습니다."""
        # given
        client, _ = make_korail(TRANSFER_ROUTES)

        # when
        transfers = client.trains.search_transfers("서울", "부산")

        # then
        assert [t.second.train_no for t in transfers] == ["1201"]

    def test_include_no_seats_returns_every_itinerary(self, make_korail) -> None:
        # given
        client, _ = make_korail(TRANSFER_ROUTES)

        # when
        transfers = client.trains.search_transfers("서울", "부산", include_no_seats=True)

        # then
        assert [(t.first.train_no, t.second.train_no) for t in transfers] == [("101", "1201"), ("103", "1203")]

    def test_differs_from_a_direct_search_only_in_the_journey_kind(self, make_korail) -> None:
        """같은 요청에 여정 종류만 환승입니다 — 다른 필드가 달라지면 서버는 다른 조회로 봅니다."""
        # given
        client, session = make_korail(TRANSFER_ROUTES)

        # when
        client.trains.search("서울", "부산", depart_after=FUTURE, include_no_seats=True)
        client.trains.search_transfers("서울", "부산", depart_after=FUTURE)

        # then
        direct, transfer = (call["params"] for call in session.all_kwargs_for("search_schedule"))
        changed = {key: (direct[key], transfer[key]) for key in direct if direct[key] != transfer[key]}
        assert changed == {"radJobId": ("1", "2")}
        assert list(direct) == list(transfer)

    def test_is_signed_like_a_direct_search(self, make_korail) -> None:
        # given
        client, session = make_korail(TRANSFER_ROUTES)

        # when
        client.trains.search_transfers("서울", "부산")

        # then
        assert "x-dynapath-m-token" in session.kwargs_for("search_schedule")["headers"]

    @pytest.mark.parametrize(
        "rows",
        [
            (FIRST_LEG_INFO,),
            (FIRST_LEG_INFO, SECOND_LEG_INFO, {**SECOND_LEG_INFO, "h_trn_no": "1205"}),
            ({**FIRST_LEG_INFO, "h_trn_seq": ""}, {**SECOND_LEG_INFO, "h_trn_seq": ""}),
            (TRAIN_INFO, SOLD_OUT_INFO),
        ],
        ids=["lone-leg", "three-legs", "blank-sequence", "no-sequence-field"],
    )
    def test_rows_that_do_not_pair_up_are_not_itineraries(self, make_korail, rows: tuple[dict[str, str], ...]) -> None:
        """무엇과 짝인지 모르는 행을 넘겨짚어 이으면 갈아탈 수 없는 여정이 만들어집니다."""
        # given
        client, _ = make_korail(transfer_page(*rows))

        # when & then
        with pytest.raises(NoResultsError):
            client.trains.search_transfers("서울", "부산", include_no_seats=True)

    def test_server_no_results_propagates(self, make_korail) -> None:
        # given
        client, _ = make_korail({"stationdata": STATION_PAYLOAD, "search_schedule": NO_RESULTS})

        # when & then
        with pytest.raises(NoResultsError):
            client.trains.search_transfers("서울", "부산")

    def test_unknown_station_is_rejected_before_the_search(self, make_korail) -> None:
        # given
        client, session = make_korail(TRANSFER_ROUTES)

        # when & then
        with pytest.raises(StationNotFoundError):
            client.trains.search_transfers("서울역", "부산")
        assert API_ENDPOINTS["search_schedule"] not in session.urls()

    def test_skips_the_station_master_when_validation_is_off(self, make_korail) -> None:
        # given
        client, session = make_korail({"search_schedule": TRANSFER_SEARCH_PAYLOAD}, validate_stations=False)

        # when
        client.trains.search_transfers("서울", "부산")

        # then
        assert session.urls() == [API_ENDPOINTS["search_schedule"]]

    def test_past_departure_is_rejected_before_the_search(self, make_korail) -> None:
        # given
        client, session = make_korail(TRANSFER_ROUTES)
        long_gone = datetime.now(KST) - timedelta(hours=3)

        # when & then
        with pytest.raises(PastDepartureError):
            client.trains.search_transfers("서울", "부산", depart_after=long_gone)
        assert API_ENDPOINTS["search_schedule"] not in session.urls()


#: 운임 조회까지 돌릴 수 있는 라우트. 조회 결과에 좌석 속성이 들어 있습니다.
FARE_ROUTES = {"stationdata": STATION_PAYLOAD, "search_schedule": SEATABLE_SEARCH_PAYLOAD, "fare": FARE_PAYLOAD}

#: 앱이 운임 조회에 싣는 필드 전체, 싣는 순서대로 (PrcFareIn 을 펼친 뒤 열차별 여덟 칸을 넣습니다).
FARE_FORM_FIELDS = [
    "Device",
    "Version",
    "AppVersion",
    "Key",
    "txtMenuId",
    "chtnDvCd",
    "trnCnt",
    "dptRsStnCd",
    "arvRsStnCd",
    "runDt",
    "trnNo",
    "gdNo",
    "rqSeatAttCd",
    "trnGpCd",
    "stlbTrnClsfCd",
]

#: 좌석 속성까지 갖춘 환승 여정 (운임 조회에는 구간마다 좌석 속성이 필요합니다).
FARE_TRANSFER = Transfer.from_response(
    [{**FIRST_LEG_INFO, "h_seat_att_cd": "015"}, {**SECOND_LEG_INFO, "h_seat_att_cd": "015"}]
)


class TestFares:
    """예매 전 운임 — ``trn.prcFare.do``."""

    def test_lists_the_fares_of_a_train(self, make_korail) -> None:
        # given
        client, _ = make_korail(FARE_ROUTES)
        train = (client.trains.search("서울", "부산"))[0]

        # when
        fares = client.trains.fares(train)

        # then
        assert [(fare.seat_class_name, fare.price, fare.charge, fare.total) for fare in fares] == [
            ("일반실", 59800, 0, 59800),
            ("특실", 59800, 23900, 83700),
        ]

    def test_transfer_fares_come_one_row_per_leg_and_class(self, make_korail) -> None:
        """구간별 줄을 여정 번호로 가릅니다. 응답은 객실 순으로 먼저 묶여 옵니다."""
        # given
        client, _ = make_korail({**FARE_ROUTES, "fare": TRANSFER_FARE_PAYLOAD})

        # when
        fares = client.trains.fares(FARE_TRANSFER)

        # then
        assert [(fare.journey_no, fare.train_no, fare.seat_class_name, fare.total) for fare in fares] == [
            ("0001", "101", "일반실", 23700),
            ("0002", "1201", "일반실", 17800),
            ("0001", "101", "특실", 33200),
            ("0002", "1201", "우등실", 23300),
        ]

    def test_sends_exact_form_fields_in_the_apps_order(self, make_korail) -> None:
        """폼 필드 이름이 바뀌면 서버가 조용히 빈 결과를 줍니다."""
        # given
        client, session = make_korail(FARE_ROUTES)
        train = (client.trains.search("서울", "부산"))[0]

        # when
        client.trains.fares(train)

        # then
        assert list(session.kwargs_for("fare")["data"]) == FARE_FORM_FIELDS

    def test_sends_one_train_as_single_values(self, make_korail) -> None:
        # given
        client, session = make_korail(FARE_ROUTES)
        train = (client.trains.search("서울", "부산"))[0]

        # when
        client.trains.fares(train)

        # then
        data = session.kwargs_for("fare")["data"]
        sent = {key: data[key] for key in FARE_FORM_FIELDS[4:]}
        assert sent == {
            "txtMenuId": "11",
            "chtnDvCd": "1",
            "trnCnt": "1",
            "dptRsStnCd": "0001",
            "arvRsStnCd": "0020",
            "runDt": "20260401",
            "trnNo": "101",
            "gdNo": "",
            "rqSeatAttCd": "015",
            "trnGpCd": "300",
            "stlbTrnClsfCd": "00",
        }

    def test_blank_goods_number_is_still_sent(self, make_korail) -> None:
        """앱은 요청 모델을 펼친 뒤에 열차별 칸을 따로 넣어, 빈 상품번호도 그대로 실립니다."""
        # given
        client, session = make_korail(FARE_ROUTES)
        train = (client.trains.search("서울", "부산"))[0]

        # when
        client.trains.fares(train)

        # then
        assert session.kwargs_for("fare")["data"]["gdNo"] == ""

    def test_transfer_joins_each_column_with_commas(self, make_korail) -> None:
        """열차마다 필드를 따로 두지 않고 칸마다 쉼표로 이어 보냅니다."""
        # given
        client, session = make_korail(FARE_ROUTES)

        # when
        client.trains.fares(FARE_TRANSFER)

        # then
        data = session.kwargs_for("fare")["data"]
        sent = {
            key: data[key]
            for key in ("chtnDvCd", "trnCnt", "dptRsStnCd", "arvRsStnCd", "trnNo", "gdNo", "stlbTrnClsfCd")
        }
        assert sent == {
            "chtnDvCd": "2",
            "trnCnt": "2",
            "dptRsStnCd": "0001,0015",
            "arvRsStnCd": "0015,0020",
            "trnNo": "101,1201",
            "gdNo": ",",
            "stlbTrnClsfCd": "00,02",
        }

    def test_transfer_division_is_the_kind_of_journey_not_the_train_count(self, make_korail) -> None:
        """``chtnDvCd`` 는 직통 1 · 환승 2 의 구분입니다. 구간이 셋이어도 3 이 되면 안 됩니다.

        앱은 열차를 둘까지만 보내므로 세 구간 요청이 통하는지는 확인된 바 없습니다. 여기서
        고정하는 것은 구분 코드가 열차 수를 따라가지 않는다는 것뿐입니다.
        """
        # given
        client, session = make_korail(FARE_ROUTES)
        three_legs = dataclasses.replace(FARE_TRANSFER, legs=(*FARE_TRANSFER.legs, FARE_TRANSFER.second))

        # when
        client.trains.fares(three_legs)

        # then
        data = session.kwargs_for("fare")["data"]
        assert (data["chtnDvCd"], data["trnCnt"]) == ("2", "3")

    def test_is_signed_but_carries_no_sid(self, make_korail) -> None:
        # given
        client, session = make_korail(FARE_ROUTES)
        train = (client.trains.search("서울", "부산"))[0]

        # when
        client.trains.fares(train)

        # then
        kwargs = session.kwargs_for("fare")
        assert "x-dynapath-m-token" in kwargs["headers"]
        assert "Sid" not in kwargs["data"]

    def test_goes_in_the_form_body_not_the_query(self, make_korail) -> None:
        # given
        client, session = make_korail(FARE_ROUTES)
        train = (client.trains.search("서울", "부산"))[0]

        # when
        client.trains.fares(train)

        # then
        assert "params" not in session.kwargs_for("fare")

    def test_something_that_is_not_a_journey_is_rejected_before_any_request(self, korail) -> None:
        """예약을 넘기는 실수가 속성 오류로 드러나면 원인을 알기 어렵습니다."""
        # given
        client, session = korail
        reservation = (client.reservations.all())[0]

        # when & then
        with pytest.raises(TypeError, match="Reservation"):
            client.trains.fares(reservation)
        assert API_ENDPOINTS["fare"] not in session.urls()

    def test_train_without_the_needed_values_is_rejected_before_any_request(self, korail) -> None:
        """빈 값을 이어 붙이면 칸 수가 맞지 않는 요청이 됩니다. 넘겨짚지 않고 막습니다."""
        # given
        client, session = korail
        train = (client.trains.search("서울", "부산"))[0]

        # when & then
        with pytest.raises(ValueError, match="seat_attribute"):
            client.trains.fares(train)
        assert API_ENDPOINTS["fare"] not in session.urls()

    @pytest.mark.parametrize(
        "body",
        [{"strResult": "SUCC"}, {"strResult": "SUCC", "prcList": None}, {"strResult": "SUCC", "prcList": []}],
        ids=["absent", "null", "empty"],
    )
    def test_no_fares_is_an_empty_list(self, make_korail, body: dict[str, object]) -> None:
        # given
        client, _ = make_korail({**FARE_ROUTES, "fare": body})
        train = (client.trains.search("서울", "부산"))[0]

        # when
        fares = client.trains.fares(train)

        # then
        assert fares == []

    def test_server_refusal_becomes_an_exception(self, make_korail) -> None:
        # given
        client, _ = make_korail({**FARE_ROUTES, "fare": {"strResult": "FAIL", "h_msg_cd": "P058"}})
        train = (client.trains.search("서울", "부산"))[0]

        # when & then
        with pytest.raises(NeedToLoginError):
            client.trains.fares(train)


class TestSeatCars:
    """호차 목록 — ``research.TrainResearch``."""

    def test_lists_the_cars_of_a_train(self, make_korail) -> None:
        # given
        client, _ = make_korail(SEAT_ROUTES)
        train = (client.trains.search("서울", "부산"))[0]

        # when
        cars = client.trains.cars(train)

        # then
        assert [(car.car_no, car.remaining_seats, car.has_seat()) for car in cars] == [
            ("0003", 19, True),
            ("0004", 0, False),
        ]

    def test_sends_exact_form_fields(self, make_korail) -> None:
        """폼 필드 이름이 바뀌면 서버가 조용히 빈 결과를 줍니다."""
        # given
        client, session = make_korail(SEAT_ROUTES)
        train = (client.trains.search("서울", "부산"))[0]

        # when
        client.trains.cars(train)

        # then
        assert set(session.kwargs_for("seat_cars")["data"]) == CARS_FORM_FIELDS

    def test_sends_the_train_as_the_app_does(self, make_korail) -> None:
        # given
        client, session = make_korail(SEAT_ROUTES)
        train = (client.trains.search("서울", "부산"))[0]

        # when
        client.trains.cars(train)

        # then
        data = session.kwargs_for("seat_cars")["data"]
        sent = {key: data[key] for key in ("AppVersion", "txtMenuId", "txtTrnNo", "txtPsrmClCd", "txtSeatAttCd")}
        assert sent == {
            "AppVersion": "7.0.10",
            "txtMenuId": "11",
            "txtTrnNo": "00101",
            "txtPsrmClCd": "1",
            "txtSeatAttCd": "015",
        }

    def test_sends_the_section_by_run_order(self, make_korail) -> None:
        # given
        client, session = make_korail(SEAT_ROUTES)
        train = (client.trains.search("서울", "부산"))[0]

        # when
        client.trains.cars(train)

        # then
        data = session.kwargs_for("seat_cars")["data"]
        assert (data["txtDptStnRunOrdr"], data["txtArvStnRunOrdr"]) == ("000001", "000019")

    def test_goes_in_the_form_body_not_the_query(self, make_korail) -> None:
        """앱은 이 요청을 폼 본문으로 보냅니다(@FormUrlEncoded)."""
        # given
        client, session = make_korail(SEAT_ROUTES)
        train = (client.trains.search("서울", "부산"))[0]

        # when
        client.trains.cars(train)

        # then
        assert "params" not in session.kwargs_for("seat_cars")

    def test_is_not_signed(self, make_korail) -> None:
        # given
        client, session = make_korail(SEAT_ROUTES)
        train = (client.trains.search("서울", "부산"))[0]

        # when
        client.trains.cars(train)

        # then
        assert "x-dynapath-m-token" not in session.kwargs_for("seat_cars").get("headers", {})

    def test_leaves_out_fields_the_search_did_not_fill(self, korail) -> None:
        """앱은 값이 빈 필드를 싣지 않습니다. 빈 문자열로 보내면 다른 요청이 됩니다."""
        # given
        client, session = korail
        train = (client.trains.search("서울", "부산"))[0]

        # when
        client.trains.cars(train)

        # then
        missing = CARS_FORM_FIELDS - set(session.kwargs_for("seat_cars")["data"])
        assert missing == {"txtSeatAttCd", "txtDptStnRunOrdr", "txtArvStnRunOrdr"}

    def test_special_class_is_sent_as_its_code(self, make_korail) -> None:
        # given
        client, session = make_korail(SEAT_ROUTES)
        train = (client.trains.search("서울", "부산"))[0]

        # when
        client.trains.cars(train, seat_class=SeatClass.SPECIAL)

        # then
        assert session.kwargs_for("seat_cars")["data"]["txtPsrmClCd"] == "2"

    def test_headcount_adds_every_passenger(self, make_korail) -> None:
        # given
        client, session = make_korail(SEAT_ROUTES)
        train = (client.trains.search("서울", "부산"))[0]

        # when
        client.trains.cars(train, passengers=[AdultPassenger(2), ChildPassenger(1)])

        # then
        assert session.kwargs_for("seat_cars")["data"]["txtTotPsgCnt"] == "3"

    @pytest.mark.parametrize(
        "body",
        [{"strResult": "SUCC"}, {"strResult": "SUCC", "srcar_infos": None}],
        ids=["absent", "null"],
    )
    def test_no_cars_is_an_empty_list(self, make_korail, body: dict[str, object]) -> None:
        # given
        client, _ = make_korail({**SEAT_ROUTES, "seat_cars": body})
        train = (client.trains.search("서울", "부산"))[0]

        # when
        cars = client.trains.cars(train)

        # then
        assert cars == []

    def test_server_refusal_becomes_an_exception(self, make_korail) -> None:
        # given
        client, _ = make_korail({**SEAT_ROUTES, "seat_cars": {"strResult": "FAIL", "h_msg_cd": "P058"}})
        train = (client.trains.search("서울", "부산"))[0]

        # when & then
        with pytest.raises(NeedToLoginError):
            client.trains.cars(train)


class TestCarSeats:
    """호차의 좌석 배치 — ``research.TResidualSeatsResearch.do``."""

    def test_lists_the_seats_of_a_car(self, make_korail) -> None:
        # given
        client, _ = make_korail(SEAT_ROUTES)
        train = (client.trains.search("서울", "부산"))[0]
        car = (client.trains.cars(train))[0]

        # when
        seats = client.trains.seats(train, car)

        # then
        assert [(seat.seat_no, seat.label, seat.is_available) for seat in seats] == [
            ("57", "15A", True),
            ("58", "15B", False),
        ]

    def test_seats_know_their_car(self, make_korail) -> None:
        # given
        client, _ = make_korail(SEAT_ROUTES)
        train = (client.trains.search("서울", "부산"))[0]
        car = (client.trains.cars(train))[0]

        # when
        seats = client.trains.seats(train, car)

        # then
        assert {seat.car_no for seat in seats} == {"0003"}

    @pytest.mark.parametrize(
        ("asked", "expected"),
        [(None, "1"), (SeatClass.SPECIAL, "2")],
        ids=["from-the-car", "as-asked"],
    )
    def test_seats_know_the_class_they_were_looked_up_in(self, make_korail, asked: str | None, expected: str) -> None:
        """좌석 응답에는 객실이 없습니다. 좌석 지정 예매가 다시 묻지 않도록 조회 조건을 붙여 둡니다."""
        # given
        client, _ = make_korail(SEAT_ROUTES)
        train = (client.trains.search("서울", "부산"))[0]
        car = (client.trains.cars(train))[0]

        # when
        seats = client.trains.seats(train, car, seat_class=asked)

        # then
        assert {seat.seat_class for seat in seats} == {expected}

    def test_sends_exact_form_fields(self, make_korail) -> None:
        """폼 필드 이름이 바뀌면 서버가 조용히 빈 결과를 줍니다."""
        # given
        client, session = make_korail(SEAT_ROUTES)
        train = (client.trains.search("서울", "부산"))[0]
        car = (client.trains.cars(train))[0]

        # when
        client.trains.seats(train, car)

        # then
        assert set(session.kwargs_for("seat_map")["data"]) == SEATS_FORM_FIELDS

    def test_sends_the_car_and_train_as_the_app_does(self, make_korail) -> None:
        # given
        client, session = make_korail(SEAT_ROUTES)
        train = (client.trains.search("서울", "부산"))[0]
        car = (client.trains.cars(train))[0]

        # when
        client.trains.seats(train, car, passengers=[AdultPassenger(2)])

        # then
        data = session.kwargs_for("seat_map")["data"]
        sent = {key: data[key] for key in ("trnNo", "srcarNo", "psrmClCd", "seatAttCd", "totPsgCnt", "isArrow")}
        assert sent == {
            "trnNo": "00101",
            "srcarNo": "0003",
            "psrmClCd": "1",
            "seatAttCd": "015",
            "totPsgCnt": "2",
            "isArrow": "false",
        }

    def test_car_number_goes_back_exactly_as_the_server_gave_it(self, make_korail) -> None:
        """호차 번호는 "0003" 처럼 0 이 채워져 옵니다. 숫자로 바꿨다 되돌리면 그 모양을 잃습니다."""
        # given
        client, session = make_korail(SEAT_ROUTES)
        train = (client.trains.search("서울", "부산"))[0]
        car = (client.trains.cars(train))[0]

        # when
        client.trains.seats(train, car)

        # then
        assert session.kwargs_for("seat_map")["data"]["srcarNo"] == CAR_INFO["h_srcar_no"]

    def test_seat_class_comes_from_the_car_by_default(self, make_korail) -> None:
        """호차 목록에 넘긴 객실을 다시 넘길 필요가 없어야 합니다."""
        # given
        special_car = {**CAR_INFO, "h_psrm_cl_cd": "2", "h_psrm_cl_nm": "특실"}
        routes = {**SEAT_ROUTES, "seat_cars": {**SEAT_CARS_PAYLOAD, "srcar_infos": {"srcar_info": [special_car]}}}
        client, session = make_korail(routes)
        train = (client.trains.search("서울", "부산"))[0]
        car = (client.trains.cars(train, seat_class=SeatClass.SPECIAL))[0]

        # when
        client.trains.seats(train, car)

        # then
        assert session.kwargs_for("seat_map")["data"]["psrmClCd"] == "2"

    def test_car_without_a_seat_class_is_rejected_before_any_request(self, make_korail) -> None:
        """객실 코드가 비면 psrmClCd 가 요청에서 통째로 빠집니다. 넘겨짚지 않고 막습니다."""
        # given
        classless_car = {**CAR_INFO, "h_psrm_cl_cd": ""}
        routes = {**SEAT_ROUTES, "seat_cars": {**SEAT_CARS_PAYLOAD, "srcar_infos": {"srcar_info": [classless_car]}}}
        client, session = make_korail(routes)
        train = (client.trains.search("서울", "부산"))[0]
        car = (client.trains.cars(train))[0]

        # when & then
        with pytest.raises(ValueError, match="seat_class"):
            client.trains.seats(train, car)
        assert API_ENDPOINTS["seat_map"] not in session.urls()

    def test_explicit_seat_class_rescues_a_car_without_one(self, make_korail) -> None:
        # given
        classless_car = {**CAR_INFO, "h_psrm_cl_cd": ""}
        routes = {**SEAT_ROUTES, "seat_cars": {**SEAT_CARS_PAYLOAD, "srcar_infos": {"srcar_info": [classless_car]}}}
        client, session = make_korail(routes)
        train = (client.trains.search("서울", "부산"))[0]
        car = (client.trains.cars(train))[0]

        # when
        client.trains.seats(train, car, seat_class=SeatClass.GENERAL)

        # then
        assert session.kwargs_for("seat_map")["data"]["psrmClCd"] == "1"

    def test_explicit_seat_class_overrides_the_car(self, make_korail) -> None:
        # given
        client, session = make_korail(SEAT_ROUTES)
        train = (client.trains.search("서울", "부산"))[0]
        car = (client.trains.cars(train))[0]

        # when
        client.trains.seats(train, car, seat_class=SeatClass.SPECIAL)

        # then
        assert session.kwargs_for("seat_map")["data"]["psrmClCd"] == "2"

    def test_goes_in_the_form_body_not_the_query(self, make_korail) -> None:
        # given
        client, session = make_korail(SEAT_ROUTES)
        train = (client.trains.search("서울", "부산"))[0]
        car = (client.trains.cars(train))[0]

        # when
        client.trains.seats(train, car)

        # then
        assert "params" not in session.kwargs_for("seat_map")

    def test_is_not_signed(self, make_korail) -> None:
        # given
        client, session = make_korail(SEAT_ROUTES)
        train = (client.trains.search("서울", "부산"))[0]
        car = (client.trains.cars(train))[0]

        # when
        client.trains.seats(train, car)

        # then
        assert "x-dynapath-m-token" not in session.kwargs_for("seat_map").get("headers", {})

    @pytest.mark.parametrize(
        "body",
        [{"strResult": "SUCC"}, {"strResult": "SUCC", "seatList": None}],
        ids=["absent", "null"],
    )
    def test_no_seats_is_an_empty_list(self, make_korail, body: dict[str, object]) -> None:
        # given
        client, _ = make_korail({**SEAT_ROUTES, "seat_map": body})
        train = (client.trains.search("서울", "부산"))[0]
        car = (client.trains.cars(train))[0]

        # when
        seats = client.trains.seats(train, car)

        # then
        assert seats == []


class TestWithoutBlanks:
    def test_drops_only_empty_strings(self) -> None:
        """0 이나 None 은 값입니다 — 앱의 평탄화기가 빼는 것은 길이 0 인 문자열뿐입니다."""
        # when
        form = without_blanks({"kept": "1", "blank": "", "zero": 0, "none": None})

        # then
        assert form == {"kept": "1", "zero": 0, "none": None}


class TestNearbyStations:
    """인접역 조회 (``adjStnScdlOfrFlg``)."""

    def test_is_off_by_default(self, korail) -> None:
        """켜면 직통편이 밀려날 수 있으므로 기본값은 꺼짐이어야 합니다."""
        # given
        client, session = korail

        # when
        client.trains.search("서울", "부산")

        # then
        assert session.kwargs_for("search_schedule")["params"]["adjStnScdlOfrFlg"] == "N"

    @pytest.mark.parametrize(("include", "expected"), [(False, "N"), (True, "Y")])
    def test_sends_the_flag(self, korail, include: bool, expected: str) -> None:
        """철자나 값이 틀리면 서버는 에러 대신 인접역 없는 결과를 조용히 돌려줍니다."""
        # given
        client, session = korail

        # when
        client.trains.search("서울", "부산", include_nearby_stations=include)

        # then
        assert session.kwargs_for("search_schedule")["params"]["adjStnScdlOfrFlg"] == expected

    def test_does_not_disturb_the_rest_of_the_payload(self, korail) -> None:
        """이 플래그 하나만 달라져야 합니다 — 다른 필드가 흔들리면 로그인·조회가 막힙니다."""
        # given — 출발 시각을 고정합니다. 생략하면 호출마다 now() 를 다시 계산해서
        # 초가 넘어가는 순간 txtGoHour 까지 달라집니다.
        client, session = korail
        client.trains.search("서울", "부산", depart_after=FUTURE)
        before = dict(session.kwargs_for("search_schedule")["params"])

        # when
        client.trains.search("서울", "부산", depart_after=FUTURE, include_nearby_stations=True)

        # then
        after = dict(session.kwargs_for("search_schedule")["params"])
        assert {k: v for k, v in after.items() if k != "adjStnScdlOfrFlg"} == {
            k: v for k, v in before.items() if k != "adjStnScdlOfrFlg"
        }

    def test_returns_trains_from_other_stations(self, make_korail) -> None:
        """인접역 편은 요청한 역이 아닌 출발·도착역으로 내려옵니다."""
        # given
        client, _ = make_korail({"stationdata": STATION_PAYLOAD, "search_schedule": NEARBY_SEARCH_PAYLOAD})

        # when
        trains = client.trains.search("서울", "부산", include_nearby_stations=True)

        # then
        assert [(t.dep_name, t.arr_name) for t in trains] == [("서울", "부산"), ("용산", "서대전")]


class TestReservations:
    def test_list_fills_seats_and_wct_no(self, korail) -> None:
        # given
        client, _ = korail

        # when
        reservations = client.reservations.all()

        # then
        assert len(reservations) == 1
        assert reservations[0].pnr_no == "1234567890"
        assert reservations[0].wct_no == "0143"
        assert [s.seat_no for s in reservations[0].seats] == ["5A"]

    def test_reservation_is_complete_at_construction(self, korail) -> None:
        """좌석이 나중에 주입되지 않고 생성 시점에 이미 채워져 있어야 합니다."""
        # given
        client, _ = korail

        # when
        rsv = (client.reservations.all())[0]

        # then
        assert isinstance(rsv, Reservation)
        assert all(isinstance(seat, Seat) for seat in rsv.seats)

    def test_reservation_references_train(self, korail) -> None:
        # given
        client, _ = korail

        # when
        rsv = (client.reservations.all())[0]

        # then
        assert rsv.train.dep_name == "서울"
        assert not hasattr(rsv, "dep_name"), "예약은 열차를 상속하지 않습니다"

    def test_reservation_dates_come_from_run_date(self, korail) -> None:
        # given
        client, _ = korail

        # when
        rsv = (client.reservations.all())[0]

        # then
        assert rsv.train.dep_date == rsv.train.arr_date == "20260401"

    def test_empty_when_no_results(self, make_korail) -> None:
        # given
        client, _ = make_korail({"myreservationview": NO_RESULTS})

        # when
        reservations = client.reservations.all()

        # then
        assert reservations == []

    def test_find_by_id(self, korail) -> None:
        # given
        client, _ = korail

        # when
        found = client.reservations.find("1234567890")
        missing = client.reservations.find("nope")
        empty = client.reservations.find(None)

        # then
        assert found is not None
        assert missing is None
        assert empty is None

    def test_find_fetches_seats_only_for_the_match(self, make_korail) -> None:
        """예약이 N건이어도 좌석 조회는 1회여야 합니다 — 나머지는 어차피 버립니다."""
        # given
        client, session = make_korail(MANY_RESERVATIONS_ROUTES)

        # when
        found = client.reservations.find("1234567890")

        # then
        assert found is not None
        assert session.urls().count(API_ENDPOINTS["myreservationlist"]) == 1
        assert session.kwargs_for("myreservationlist")["params"]["hidPnrNo"] == "1234567890", (
            "횟수만 세면 엉뚱한 예약의 좌석을 1회 조회해도 통과합니다"
        )

    def test_create_does_not_walk_every_reservation(self, make_korail) -> None:
        """예매 한 번에 남의 예약 좌석까지 긁어 오면 계정 제재로 가는 길입니다."""
        # given
        client, session = make_korail({**MANY_RESERVATIONS_ROUTES, **SEARCHABLE_ROUTES})
        train = (client.trains.search("서울", "부산"))[0]

        # when
        reservation = client.reservations.create(train)

        # then
        assert reservation.pnr_no == "1234567890"
        assert session.urls().count(API_ENDPOINTS["myreservationlist"]) == 1
        assert session.kwargs_for("myreservationlist")["params"]["hidPnrNo"] == "1234567890"
        assert len(session.calls) == 5, "역 마스터 · 조회 · 예매 · 예약목록 · 좌석 각 1회"

    def test_all_still_fills_every_reservation(self, make_korail) -> None:
        """find 와 달리 all 은 전부 채워야 하므로 예약 수만큼 조회하는 게 맞습니다."""
        # given
        client, session = make_korail(MANY_RESERVATIONS_ROUTES)

        # when
        reservations = client.reservations.all()

        # then
        assert [r.pnr_no for r in reservations] == list(MANY_RESERVATION_IDS)
        assert [kw["params"]["hidPnrNo"] for kw in session.all_kwargs_for("myreservationlist")] == list(
            MANY_RESERVATION_IDS
        ), "횟수만 세면 같은 예약을 네 번 조회해도 통과합니다"

    def test_find_missing_id_does_not_fetch_seats(self, make_korail) -> None:
        # given
        client, session = make_korail(MANY_RESERVATIONS_ROUTES)

        # when
        found = client.reservations.find("0000000000")

        # then
        assert found is None
        assert API_ENDPOINTS["myreservationlist"] not in session.urls()

    def test_create_returns_the_reservation(self, korail) -> None:
        # given
        client, _ = korail
        train = (client.trains.search("서울", "부산"))[0]

        # when
        reservation = client.reservations.create(train)

        # then
        assert reservation.pnr_no == "1234567890"

    def test_create_sends_passenger_blocks(self, korail) -> None:
        # given
        client, session = korail
        train = (client.trains.search("서울", "부산"))[0]

        # when
        client.reservations.create(train, passengers=[AdultPassenger(2), ChildPassenger(1)])

        # then
        params = session.kwargs_for("reserve")["params"]
        assert params["txtTotPsgCnt"] == 3
        assert params["txtPsgTpCd1"] == "1"
        assert params["txtPsgTpCd2"] == "3"

    def test_create_raises_when_lookup_fails(self, make_korail) -> None:
        # given
        client, _ = make_korail(
            {
                "stationdata": STATION_PAYLOAD,
                "search_schedule": SEARCH_PAYLOAD,
                "reserve": {"strResult": "SUCC", "h_pnr_no": "9999999999"},
                "myreservationview": NO_RESULTS,
            }
        )
        train = (client.trains.search("서울", "부산"))[0]

        # when & then
        with pytest.raises(KorailError, match="9999999999"):
            client.reservations.create(train)

    def test_cancel_rejects_wrong_type(self, korail) -> None:
        # given
        client, _ = korail

        # when & then
        with pytest.raises(TypeError):
            client.reservations.cancel("1234567890")  # type: ignore[arg-type]

    def test_cancel_sends_journey_identifiers(self, korail) -> None:
        # given
        client, session = korail
        rsv = (client.reservations.all())[0]

        # when
        client.reservations.cancel(rsv)

        # then
        data = session.kwargs_for("cancel")["data"]
        assert data["txtPnrNo"] == "1234567890"
        assert data["txtJrnySqno"] == rsv.journey_no


class TestPayment:
    def test_pay_sends_card_fields(self, korail) -> None:
        # given
        client, session = korail
        rsv = (client.reservations.all())[0]

        # when
        client.reservations.pay(rsv, Card("1234567812345678", "12", "900101", "2812"))

        # then
        data = session.kwargs_for("pay")["data"]
        assert data["hidStlCrCrdNo1"] == "1234567812345678"
        assert data["hidVanPwd1"] == "12"
        assert data["hidAthnVal1"] == "900101"
        assert data["hidCrdVlidTrm1"] == "2812"
        assert data["hidMnsStlAmt1"] == "119600"
        assert data["hidWctNo"] == "0143"

    @pytest.mark.parametrize(
        "detail",
        [{**SEAT_DETAIL_PAYLOAD, "h_wct_no": ""}, NO_RESULTS],
        ids=["blank-window", "no-journeys"],
    )
    def test_missing_window_number_is_sent_as_empty(self, make_korail, detail: dict[str, object]) -> None:
        """발매창구 번호가 없으면 결제 폼에는 빈 문자열이 실립니다 — 요청 모양을 바꾸지 않습니다."""
        # given
        client, session = make_korail(
            {
                "myreservationview": RESERVATION_LIST_PAYLOAD,
                "myreservationlist": detail,
                "pay": OK,
            }
        )
        rsv = (client.reservations.all())[0]

        # when
        client.reservations.pay(rsv, Card("1234567812345678", "12", "900101", "2812"))

        # then
        assert session.kwargs_for("pay")["data"]["hidWctNo"] == ""

    def test_individual_card_is_the_default(self, korail) -> None:
        # given
        client, session = korail
        rsv = (client.reservations.all())[0]

        # when
        client.reservations.pay(rsv, Card("1234", "12", "900101", "2812"))

        # then
        assert session.kwargs_for("pay")["data"]["hidAthnDvCd1"] == "J"

    def test_corporate_card_flag(self, korail) -> None:
        # given
        client, session = korail
        rsv = (client.reservations.all())[0]

        # when
        client.reservations.pay(rsv, Card("1234", "12", "1234567890", "2812", is_corporate=True))

        # then
        assert session.kwargs_for("pay")["data"]["hidAthnDvCd1"] == "S"

    def test_installment_defaults_to_lump_sum(self, korail) -> None:
        # given
        client, session = korail
        rsv = (client.reservations.all())[0]

        # when
        client.reservations.pay(rsv, Card("1234", "12", "900101", "2812"))

        # then
        assert session.kwargs_for("pay")["data"]["hidIsmtMnthNum1"] == 0

    def test_installment_is_forwarded(self, korail) -> None:
        # given
        client, session = korail
        rsv = (client.reservations.all())[0]

        # when
        client.reservations.pay(rsv, Card("1234", "12", "900101", "2812", installment=3))

        # then
        assert session.kwargs_for("pay")["data"]["hidIsmtMnthNum1"] == 3

    def test_rejects_wrong_reservation_type(self, korail) -> None:
        # given
        client, _ = korail

        # when & then
        with pytest.raises(TypeError, match="Reservation"):
            client.reservations.pay("nope", Card("1234", "12", "900101", "2812"))  # type: ignore[arg-type]

    def test_rejects_wrong_card_type(self, korail) -> None:
        # given
        client, _ = korail
        rsv = (client.reservations.all())[0]

        # when & then
        with pytest.raises(TypeError, match="Card"):
            client.reservations.pay(rsv, "1234567812345678")  # type: ignore[arg-type]


class TestTickets:
    def test_list_resolves_real_seat_number(self, korail) -> None:
        """목록의 좌석번호(5A)가 아니라 상세 조회 값(7C)이 들어가야 합니다."""
        # given
        client, _ = korail

        # when
        tickets = client.tickets.all()

        # then
        assert len(tickets) == 1
        assert tickets[0].seat_no == "7C"
        assert tickets[0].seat_no_end is None

    def test_ticket_is_immutable_and_complete(self, korail) -> None:
        # given
        client, _ = korail
        ticket = (client.tickets.all())[0]

        # when & then
        assert isinstance(ticket, Ticket)
        with pytest.raises(AttributeError):
            ticket.seat_no = "1A"  # type: ignore[misc]

    def test_ticket_references_train(self, korail) -> None:
        # given
        client, _ = korail

        # when
        ticket = (client.tickets.all())[0]

        # then
        assert ticket.train.train_no == "101"
        assert not hasattr(ticket, "train_no"), "승차권은 열차를 상속하지 않습니다"

    def test_ticket_no(self, korail) -> None:
        # given
        client, _ = korail

        # when
        ticket_no = (client.tickets.all())[0].ticket_no

        # then
        assert ticket_no == "0000-20260320-0001-1111"

    def test_empty_when_no_results(self, make_korail) -> None:
        # given
        client, _ = make_korail({"myticketlist": NO_RESULTS})

        # when
        tickets = client.tickets.all()

        # then
        assert tickets == []

    def test_empty_seat_detail_keeps_the_ticket(self, make_korail) -> None:
        """상세 조회가 비어도 승차권은 남아야 합니다 — 목록 전체가 사라지면 안 됩니다."""
        # given
        client, _ = make_korail({"myticketlist": TICKET_LIST_PAYLOAD, "myticketseat": NO_RESULTS})

        # when
        tickets = client.tickets.all()

        # then
        assert [t.seat_no for t in tickets] == ["5A"], "상세를 못 받으면 목록 응답 값으로 되돌아갑니다"

    def test_unreadable_entry_is_skipped_not_fatal(self, make_korail) -> None:
        """항목 하나가 비어 있다고 목록 전체가 KeyError 로 죽으면 안 됩니다."""
        # given
        client, _ = make_korail(
            {
                "myticketlist": {
                    "strResult": "SUCC",
                    "reservation_list": [{"ticket_list": []}, *TICKET_LIST_PAYLOAD["reservation_list"]],
                },
                "myticketseat": TICKET_SEAT_PAYLOAD,
            }
        )

        # when
        tickets = client.tickets.all()

        # then
        assert [t.seat_no for t in tickets] == ["7C"], "읽을 수 있는 항목만 남습니다"

    def test_empty_train_info_does_not_become_a_ghost_ticket(self, make_korail) -> None:
        """구조만 있고 내용이 없으면 승차권이 아닙니다 — 빈 승차권을 지어내면 안 됩니다."""
        # given
        client, _ = make_korail(
            {
                "myticketlist": {
                    "strResult": "SUCC",
                    "reservation_list": [
                        {"ticket_list": [{"train_info": [{}]}]},
                        *TICKET_LIST_PAYLOAD["reservation_list"],
                    ],
                },
                "myticketseat": TICKET_SEAT_PAYLOAD,
            }
        )

        # when
        tickets = client.tickets.all()

        # then
        assert [t.ticket_no for t in tickets] == ["0000-20260320-0001-1111"]

    def test_no_seat_lookup_without_original_ticket_ids(self, make_korail) -> None:
        """식별자가 전부 None 인 조회는 서버가 돌려줄 것이 없어 요청만 축냅니다."""
        # given
        listing = {"strResult": "SUCC", "reservation_list": [{"ticket_list": [{"train_info": [{"h_trn_no": "101"}]}]}]}
        client, session = make_korail({"myticketlist": listing})

        # when
        tickets = client.tickets.all()

        # then
        assert len(tickets) == 1, "승차권 자체는 남습니다 — 좌석번호만 포기합니다"
        assert API_ENDPOINTS["myticketseat"] not in session.urls()

    def test_seat_detail_failure_other_than_no_results_propagates(self, make_korail) -> None:
        """세션 만료 같은 진짜 실패까지 빈 목록으로 접어 버리면 안 됩니다."""
        # given
        client, _ = make_korail(
            {"myticketlist": TICKET_LIST_PAYLOAD, "myticketseat": {"strResult": "FAIL", "h_msg_cd": "P058"}}
        )

        # when & then
        with pytest.raises(NeedToLoginError):
            client.tickets.all()

    def test_refund_fee_reads_amounts(self, korail) -> None:
        # given
        client, _ = korail
        ticket = (client.tickets.all())[0]

        # when
        fee = client.tickets.refund_fee(ticket)

        # then
        assert (fee.fee, fee.amount, fee.usable_mileage) == (5600, 53400, 1200)
        assert fee.refundable is True
        assert fee.period_code == "21"

    def test_refund_fee_is_refundable_only_on_y(self, make_korail) -> None:
        # given
        client, _ = make_korail(
            {
                "myticketlist": TICKET_LIST_PAYLOAD,
                "myticketseat": TICKET_SEAT_PAYLOAD,
                "refund_commission": {**REFUND_FEE_PAYLOAD, "prg_psb_flg": ""},
            }
        )
        ticket = (client.tickets.all())[0]

        # when
        fee = client.tickets.refund_fee(ticket)

        # then
        assert fee.refundable is False, "빈 값은 판단 근거가 없으므로 불가로 봅니다"

    @pytest.mark.parametrize(
        ("field", "expected"),
        [
            # refund() 와 철자가 다릅니다. 통일하면 조용한 빈 값이 됩니다.
            ("h_orgtk_ret_sale_dt", "20260320"),
            ("h_orgtk_wct_no", "0000"),
            ("h_orgtk_sale_sqno", "0001"),
            ("h_orgtk_ret_pwd", "1111"),
            # 앱이 기본값으로 빈 문자열을 싣습니다 — 빼면 안 됩니다.
            ("h_comp_nm", ""),
            ("h_comp_cert_no", ""),
            ("ctlDvCd", ""),
            ("lang", ""),
        ],
    )
    def test_refund_fee_form_fields(self, korail, field: str, expected: str) -> None:
        # given
        client, session = korail
        ticket = (client.tickets.all())[0]

        # when
        client.tickets.refund_fee(ticket)

        # then
        assert session.kwargs_for("refund_commission")["data"][field] == expected

    def test_refund_fee_does_not_call_refund(self, korail) -> None:
        # given
        client, session = korail
        ticket = (client.tickets.all())[0]

        # when
        client.tickets.refund_fee(ticket)

        # then
        assert API_ENDPOINTS["refund"] not in session.urls(), "조회일 뿐 환불하면 안 됩니다"

    def test_refund_uses_train_reference(self, korail) -> None:
        # given
        client, session = korail
        ticket = (client.tickets.all())[0]

        # when
        client.tickets.refund(ticket)

        # then
        data = session.kwargs_for("refund")["data"]
        assert data["trnNo"] == "101"
        assert data["h_orgtk_sale_wct_no"] == "0000"


class TestListsThatCameBackAsNull:
    """결과가 없을 때 서버가 ``FAIL`` 대신 목록 자리에 null · 빈 목록을 주는 경우.

    기본값을 주는 ``payload.get(a, {}).get(b, [])`` 는 **키가 없을 때만** 통합니다.
    키는 있고 값이 null 이면 그대로 죽습니다.
    """

    @pytest.mark.parametrize(
        "body",
        [
            {"strResult": "SUCC", "trn_infos": None},
            {"strResult": "SUCC", "trn_infos": {"trn_info": None}},
            {"strResult": "SUCC", "trn_infos": {"trn_info": []}},
        ],
        ids=["null-wrapper", "null-list", "empty-list"],
    )
    def test_search_reports_no_results(self, make_korail, body: dict[str, object]) -> None:
        # given
        client, _ = make_korail({"stationdata": STATION_PAYLOAD, "search_schedule": body})

        # when & then
        with pytest.raises(NoResultsError):
            client.trains.search("서울", "부산")

    @pytest.mark.parametrize(
        "body",
        [
            {"strResult": "SUCC", "jrny_infos": None},
            {"strResult": "SUCC", "jrny_infos": {"jrny_info": None}},
            {"strResult": "SUCC", "jrny_infos": {"jrny_info": [{"train_infos": None}]}},
            {"strResult": "SUCC", "jrny_infos": {"jrny_info": [{"train_infos": {"train_info": None}}]}},
        ],
        ids=["null-journeys", "null-journey-list", "null-trains", "null-train-list"],
    )
    def test_reservation_list_is_empty(self, make_korail, body: dict[str, object]) -> None:
        # given
        client, _ = make_korail({"myreservationview": body})

        # when
        reservations = client.reservations.all()

        # then
        assert reservations == []

    @pytest.mark.parametrize(
        "body",
        [
            {"strResult": "SUCC", "h_wct_no": "0143", "jrny_infos": None},
            {"strResult": "SUCC", "h_wct_no": "0143", "jrny_infos": {"jrny_info": None}},
            {"strResult": "SUCC", "h_wct_no": "0143", "jrny_infos": {"jrny_info": [{"seat_infos": None}]}},
            {
                "strResult": "SUCC",
                "h_wct_no": "0143",
                "jrny_infos": {"jrny_info": [{"seat_infos": {"seat_info": None}}]},
            },
        ],
        ids=["null-journeys", "null-journey-list", "null-seats", "null-seat-list"],
    )
    def test_seat_detail_keeps_the_window_number(self, make_korail, body: dict[str, object]) -> None:
        """좌석을 못 읽어도 발매창구 번호는 결제에 필요합니다."""
        # given
        client, _ = make_korail({"myreservationlist": body})

        # when
        seats, wct_no = client.reservations.seats("1234567890")

        # then
        assert (seats, wct_no) == ([], "0143")

    @pytest.mark.parametrize(
        "body",
        [{"strResult": "SUCC", "reservation_list": None}, {"strResult": "SUCC", "reservation_list": []}],
        ids=["null", "empty"],
    )
    def test_ticket_list_is_empty(self, make_korail, body: dict[str, object]) -> None:
        # given
        client, _ = make_korail({"myticketlist": body})

        # when
        tickets = client.tickets.all()

        # then
        assert tickets == []

    @pytest.mark.parametrize(
        "body",
        [
            {"strResult": "SUCC", "ticket_infos": None},
            {"strResult": "SUCC", "ticket_infos": {"ticket_info": None}},
            {"strResult": "SUCC", "ticket_infos": {"ticket_info": []}},
            {"strResult": "SUCC", "ticket_infos": {"ticket_info": [{"tk_seat_info": None}]}},
            {"strResult": "SUCC", "ticket_infos": {"ticket_info": [{"tk_seat_info": []}]}},
        ],
        ids=["null-tickets", "null-ticket-list", "empty-ticket-list", "null-seats", "empty-seats"],
    )
    def test_unreadable_seat_detail_keeps_the_ticket(self, make_korail, body: dict[str, object]) -> None:
        """좌석 상세 하나를 못 읽는다고 승차권 목록 전체가 죽으면 안 됩니다."""
        # given
        client, _ = make_korail({"myticketlist": TICKET_LIST_PAYLOAD, "myticketseat": body})

        # when
        tickets = client.tickets.all()

        # then
        assert [t.seat_no for t in tickets] == ["5A"], "상세를 못 받으면 목록 응답 값으로 되돌아갑니다"


class TestReservationDays:
    def test_list_takes_the_departure_and_arrival_dates_from_the_journey(self, make_korail) -> None:
        """목록은 운행일만 주므로, 여정 상세가 준 출발·도착 날짜를 예약에 씁니다."""
        # given
        journey = {"h_dpt_dt": "20260401", "h_arv_dt": "20260402", "seat_infos": {"seat_info": [SEAT_INFO]}}
        client, _ = make_korail(
            {
                "myreservationview": RESERVATION_LIST_PAYLOAD,
                "myreservationlist": {"strResult": "SUCC", "jrny_infos": {"jrny_info": [journey]}},
            }
        )

        # when
        reservations = client.reservations.all()

        # then
        assert (reservations[0].train.dep_date, reservations[0].train.arr_date) == ("20260401", "20260402")
