"""리소스별 동작 — 조회·예매·결제·승차권."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from pykorail.constants import API_ENDPOINTS
from pykorail.exceptions import (
    KorailError,
    NeedToLoginError,
    NoResultsError,
    PastDepartureError,
    StationNotFoundError,
)
from pykorail.models import AdultPassenger, Card, ChildPassenger, Reservation, Seat, Ticket
from pykorail.resources.trains import KST, PAST_TOLERANCE, to_kst
from tests.payloads import (
    NEARBY_SEARCH_PAYLOAD,
    NO_RESULTS,
    REFUND_FEE_PAYLOAD,
    SEARCH_PAYLOAD,
    STATION_PAYLOAD,
    TICKET_LIST_PAYLOAD,
    TICKET_SEAT_PAYLOAD,
)

#: 과거 조회 가드에 걸리지 않도록 넉넉히 미래인 기준 시각. 초까지 고정해야
#: 전송값을 정확히 단언할 수 있습니다.
FUTURE = (datetime.now(KST) + timedelta(days=30)).replace(hour=9, minute=30, second=0, microsecond=0)
FUTURE_UTC = (datetime.now(timezone.utc) + timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)


class TestToKst:
    def test_naive_is_treated_as_kst(self) -> None:
        # when
        result = to_kst(datetime(2026, 4, 1, 9, 0))

        # then
        assert result.tzinfo == KST
        assert result.hour == 9

    def test_aware_is_converted(self) -> None:
        # given
        utc_midnight = datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc)

        # when
        result = to_kst(utc_midnight)

        # then
        assert result.hour == 9

    def test_none_is_now_in_kst(self) -> None:
        # when
        result = to_kst(None)

        # then
        assert result.tzinfo == KST


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
        client.stations.all().clear()

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
        assert not client.logined
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
        utc_past = datetime.now(timezone.utc) - timedelta(hours=5)

        # when & then
        with pytest.raises(PastDepartureError):
            client.trains.search("서울", "부산", depart_after=utc_past)


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
        assert reservations[0].rsv_id == "1234567890"
        assert reservations[0].wct_no == "0143"
        assert [s.seat for s in reservations[0].seats] == ["5A"]

    def test_reservation_is_complete_at_construction(self, korail) -> None:
        """좌석이 나중에 주입되지 않고 생성 시점에 이미 채워져 있어야 합니다."""
        # given
        client, _ = korail

        # when
        rsv = client.reservations.all()[0]

        # then
        assert isinstance(rsv, Reservation)
        assert all(isinstance(seat, Seat) for seat in rsv.seats)

    def test_reservation_references_train(self, korail) -> None:
        # given
        client, _ = korail

        # when
        rsv = client.reservations.all()[0]

        # then
        assert rsv.train.dep_name == "서울"
        assert not hasattr(rsv, "dep_name"), "예약은 열차를 상속하지 않습니다"

    def test_reservation_dates_come_from_run_date(self, korail) -> None:
        # given
        client, _ = korail

        # when
        rsv = client.reservations.all()[0]

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

    def test_create_returns_the_reservation(self, korail) -> None:
        # given
        client, _ = korail
        train = client.trains.search("서울", "부산")[0]

        # when
        reservation = client.reservations.create(train)

        # then
        assert reservation.rsv_id == "1234567890"

    def test_create_sends_passenger_blocks(self, korail) -> None:
        # given
        client, session = korail
        train = client.trains.search("서울", "부산")[0]

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
        train = client.trains.search("서울", "부산")[0]

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
        rsv = client.reservations.all()[0]

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
        rsv = client.reservations.all()[0]

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

    def test_individual_card_is_the_default(self, korail) -> None:
        # given
        client, session = korail
        rsv = client.reservations.all()[0]

        # when
        client.reservations.pay(rsv, Card("1234", "12", "900101", "2812"))

        # then
        assert session.kwargs_for("pay")["data"]["hidAthnDvCd1"] == "J"

    def test_corporate_card_flag(self, korail) -> None:
        # given
        client, session = korail
        rsv = client.reservations.all()[0]

        # when
        client.reservations.pay(rsv, Card("1234", "12", "1234567890", "2812", is_corporate=True))

        # then
        assert session.kwargs_for("pay")["data"]["hidAthnDvCd1"] == "S"

    def test_installment_defaults_to_lump_sum(self, korail) -> None:
        # given
        client, session = korail
        rsv = client.reservations.all()[0]

        # when
        client.reservations.pay(rsv, Card("1234", "12", "900101", "2812"))

        # then
        assert session.kwargs_for("pay")["data"]["hidIsmtMnthNum1"] == 0

    def test_installment_is_forwarded(self, korail) -> None:
        # given
        client, session = korail
        rsv = client.reservations.all()[0]

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
        rsv = client.reservations.all()[0]

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
        ticket = client.tickets.all()[0]

        # when & then
        assert isinstance(ticket, Ticket)
        with pytest.raises(AttributeError):
            ticket.seat_no = "1A"  # type: ignore[misc]

    def test_ticket_references_train(self, korail) -> None:
        # given
        client, _ = korail

        # when
        ticket = client.tickets.all()[0]

        # then
        assert ticket.train.train_no == "101"
        assert not hasattr(ticket, "train_no"), "승차권은 열차를 상속하지 않습니다"

    def test_ticket_no(self, korail) -> None:
        # given
        client, _ = korail

        # when
        ticket_no = client.tickets.all()[0].ticket_no

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
        ticket = client.tickets.all()[0]

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
        ticket = client.tickets.all()[0]

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
        ticket = client.tickets.all()[0]

        # when
        client.tickets.refund_fee(ticket)

        # then
        assert session.kwargs_for("refund_commission")["data"][field] == expected

    def test_refund_fee_does_not_call_refund(self, korail) -> None:
        # given
        client, session = korail
        ticket = client.tickets.all()[0]

        # when
        client.tickets.refund_fee(ticket)

        # then
        assert API_ENDPOINTS["refund"] not in session.urls(), "조회일 뿐 환불하면 안 됩니다"

    def test_refund_uses_train_reference(self, korail) -> None:
        # given
        client, session = korail
        ticket = client.tickets.all()[0]

        # when
        client.tickets.refund(ticket)

        # then
        data = session.kwargs_for("refund")["data"]
        assert data["trnNo"] == "101"
        assert data["h_orgtk_sale_wct_no"] == "0000"
