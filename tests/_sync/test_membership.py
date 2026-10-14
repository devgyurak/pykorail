# 이 파일은 생성물입니다 — 직접 고치지 마세요.
# 원본: tests/_async/test_membership.py
# 다시 만들려면: uv run python scripts/unasync.py
"""멤버십 리소스(``korail.membership``)와 그 모델 — 마일리지 · 할인쿠폰."""

from __future__ import annotations

import dataclasses
from datetime import UTC, date, datetime

import pytest

from pykorail._shared.clock import KST, to_kst
from pykorail._sync.resources import membership as membership_module
from pykorail.exceptions import KorailError, NeedToLoginError
from pykorail.models import Coupon, Mileage, MileageEntry
from pykorail.options import MileageInquiry, MileageType
from tests.payloads import (
    COUPON_INFO,
    COUPONS_PAYLOAD,
    MILEAGE_ENTRY_INFO,
    MILEAGE_PAYLOAD,
    NO_COUPONS_PAYLOAD,
    NO_RESULTS,
)

MEMBERSHIP_ROUTES = {"mileage": MILEAGE_PAYLOAD, "coupons": COUPONS_PAYLOAD}

NEED_LOGIN = {"strResult": "FAIL", "h_msg_cd": "P058", "h_msg_txt": "로그인이 필요합니다"}

#: 앱 공통 필드 넷 + ``AmtSpecIn`` 의 필드. ``mbCrdNo`` 는 앱이 비워 두어 실리지 않습니다.
MILEAGE_FORM_FIELDS = {
    "Device",
    "Version",
    "AppVersion",
    "Key",
    "pontTpVal",
    "qryDvVal",
    "qryStDt",
    "qryClsDt",
    "pgPrCnt",
    "nowPgNo",
}

#: 앱 공통 필드 넷 + ``CouponIn`` 의 쪽 번호. ``pnrNo`` 는 쿠폰함에서 비어 있어 실리지 않습니다.
COUPONS_FORM_FIELDS = {"Device", "Version", "AppVersion", "Key", "txtSelPage"}


class TestMileage:
    """마일리지 잔액과 내역 — ``mlg.amtSpec.do``."""

    def test_reads_the_balances(self, make_korail) -> None:
        # given
        client, _ = make_korail(MEMBERSHIP_ROUTES)

        # when
        mileage = client.membership.mileage()

        # then
        assert (mileage.ktx, mileage.samsung_card, mileage.rail_point, mileage.expiring) == (12340, 660, 500, 120)

    def test_reads_one_page_of_history(self, make_korail) -> None:
        # given
        client, _ = make_korail(MEMBERSHIP_ROUTES)

        # when
        mileage = client.membership.mileage()

        # then
        assert [(entry.date, entry.movement, entry.amount) for entry in mileage.entries] == [
            ("20261003", "적립", 2990),
            ("20260921", "사용", -1000),
        ]
        assert mileage.page_count == 3

    def test_sends_exact_form_fields(self, make_korail) -> None:
        """폼 필드 이름이 바뀌면 서버가 조용히 빈 결과를 줍니다."""
        # given
        client, session = make_korail(MEMBERSHIP_ROUTES)

        # when
        client.membership.mileage()

        # then
        assert set(session.kwargs_for("mileage")["data"]) == MILEAGE_FORM_FIELDS

    def test_asks_for_every_ktx_mileage_entry_by_default(self, make_korail) -> None:
        """구분 코드는 앱의 ``MileageType`` · ``MileageInquiryType`` 이 보내는 값입니다."""
        # given
        client, session = make_korail(MEMBERSHIP_ROUTES)

        # when
        client.membership.mileage()

        # then
        data = session.kwargs_for("mileage")["data"]
        sent = {key: data[key] for key in ("AppVersion", "pontTpVal", "qryDvVal", "pgPrCnt", "nowPgNo")}
        assert sent == {"AppVersion": "7.0.8", "pontTpVal": "1", "qryDvVal": "0", "pgPrCnt": "20", "nowPgNo": "1"}

    @pytest.mark.parametrize(
        ("kind", "inquiry", "expected"),
        [
            (MileageType.KTX, MileageInquiry.SAVE, ("1", "1")),
            (MileageType.KTX, MileageInquiry.USE, ("1", "2")),
            (MileageType.RAIL_POINT, MileageInquiry.ALL, ("2", "0")),
        ],
        ids=["ktx-save", "ktx-use", "rail-point-all"],
    )
    def test_sends_the_chosen_ledger_and_inquiry(
        self, make_korail, kind: str, inquiry: str, expected: tuple[str, str]
    ) -> None:
        # given
        client, session = make_korail(MEMBERSHIP_ROUTES)

        # when
        client.membership.mileage(kind=kind, inquiry=inquiry)

        # then
        data = session.kwargs_for("mileage")["data"]
        assert (data["pontTpVal"], data["qryDvVal"]) == expected

    def test_sends_the_period_as_eight_digit_dates(self, make_korail) -> None:
        # given
        client, session = make_korail(MEMBERSHIP_ROUTES)

        # when
        client.membership.mileage(since=date(2026, 7, 1), until=date(2026, 9, 30))

        # then
        data = session.kwargs_for("mileage")["data"]
        assert (data["qryStDt"], data["qryClsDt"]) == ("20260701", "20260930")

    def test_period_defaults_to_the_last_thirty_days_in_kst(self, make_korail, monkeypatch) -> None:
        """실행 머신의 시간대가 아니라 KST 의 오늘이 기준입니다."""
        # given
        client, session = make_korail(MEMBERSHIP_ROUTES)
        today = datetime(2026, 10, 12, 0, 30, tzinfo=KST)
        monkeypatch.setattr(membership_module, "to_kst", lambda moment: today)

        # when
        client.membership.mileage()

        # then
        data = session.kwargs_for("mileage")["data"]
        assert (data["qryStDt"], data["qryClsDt"]) == ("20260912", "20261012")

    def test_since_alone_runs_up_to_today(self, make_korail, monkeypatch) -> None:
        # given
        client, session = make_korail(MEMBERSHIP_ROUTES)
        today = datetime(2026, 10, 12, 9, 0, tzinfo=KST)
        monkeypatch.setattr(membership_module, "to_kst", lambda moment: today)

        # when
        client.membership.mileage(since=date(2026, 4, 1))

        # then
        data = session.kwargs_for("mileage")["data"]
        assert (data["qryStDt"], data["qryClsDt"]) == ("20260401", "20261012")

    def test_until_alone_looks_back_thirty_days_from_it(self, make_korail) -> None:
        # given
        client, session = make_korail(MEMBERSHIP_ROUTES)

        # when
        client.membership.mileage(until=date(2026, 3, 31))

        # then
        data = session.kwargs_for("mileage")["data"]
        assert (data["qryStDt"], data["qryClsDt"]) == ("20260301", "20260331")

    def test_datetime_since_does_not_break_the_period_check(self, make_korail, monkeypatch) -> None:
        """``datetime`` 은 ``date`` 의 하위 타입이라 타입 검사를 통과하지만 ``date`` 와 비교되지 않습니다.

        ``until`` 을 생략하면 한쪽만 ``datetime`` 이 되어 ``TypeError`` 가 났습니다.
        """
        # given
        client, session = make_korail(MEMBERSHIP_ROUTES)
        today = datetime(2026, 10, 12, 9, 0, tzinfo=KST)
        # 오늘만 고정하고, 넘겨받은 시각은 진짜 변환을 그대로 탑니다.
        monkeypatch.setattr(membership_module, "to_kst", lambda moment: to_kst(moment) if moment else today)

        # when
        client.membership.mileage(since=datetime(2026, 9, 1, 15, 30))

        # then
        data = session.kwargs_for("mileage")["data"]
        assert (data["qryStDt"], data["qryClsDt"]) == ("20260901", "20261012")

    @pytest.mark.parametrize(
        ("since", "until", "expected"),
        [
            (datetime(2026, 7, 1, 8, 0), datetime(2026, 9, 30, 23, 59), ("20260701", "20260930")),
            (date(2026, 7, 1), datetime(2026, 9, 30, 12, 0), ("20260701", "20260930")),
            (datetime(2026, 7, 1, 12, 0), date(2026, 9, 30), ("20260701", "20260930")),
        ],
        ids=["both-datetime", "date-then-datetime", "datetime-then-date"],
    )
    def test_accepts_datetimes_for_the_period(
        self, make_korail, since: date, until: date, expected: tuple[str, str]
    ) -> None:
        # given
        client, session = make_korail(MEMBERSHIP_ROUTES)

        # when
        client.membership.mileage(since=since, until=until)

        # then
        data = session.kwargs_for("mileage")["data"]
        assert (data["qryStDt"], data["qryClsDt"]) == expected

    def test_aware_datetime_is_read_as_its_kst_date(self, make_korail) -> None:
        """UTC 15:00 은 KST 로 다음 날 0시입니다. 조회(``trains.search``)와 같은 해석입니다."""
        # given
        client, session = make_korail(MEMBERSHIP_ROUTES)
        late_utc = datetime(2026, 9, 30, 15, 0, tzinfo=UTC)

        # when
        client.membership.mileage(since=date(2026, 9, 1), until=late_utc)

        # then
        assert session.kwargs_for("mileage")["data"]["qryClsDt"] == "20261001"

    def test_sends_the_page_number(self, make_korail) -> None:
        # given
        client, session = make_korail(MEMBERSHIP_ROUTES)

        # when
        client.membership.mileage(page=3)

        # then
        assert session.kwargs_for("mileage")["data"]["nowPgNo"] == "3"

    def test_rejects_a_period_that_ends_before_it_starts(self, make_korail) -> None:
        # given
        client, session = make_korail(MEMBERSHIP_ROUTES)

        # when
        with pytest.raises(ValueError, match="since"):
            client.membership.mileage(since=date(2026, 10, 2), until=date(2026, 10, 1))

        # then
        assert session.calls == [], "틀린 기간은 요청 전에 걸러야 합니다"

    @pytest.mark.parametrize("page", [0, -1])
    def test_rejects_a_page_below_one(self, make_korail, page: int) -> None:
        # given
        client, session = make_korail(MEMBERSHIP_ROUTES)

        # when
        with pytest.raises(ValueError, match="page"):
            client.membership.mileage(page=page)

        # then
        assert session.calls == []

    def test_goes_in_the_form_body_not_the_query(self, make_korail) -> None:
        """앱은 이 요청을 폼 본문으로 보냅니다(@FormUrlEncoded)."""
        # given
        client, session = make_korail(MEMBERSHIP_ROUTES)

        # when
        client.membership.mileage()

        # then
        assert "params" not in session.kwargs_for("mileage")

    def test_is_not_signed(self, make_korail) -> None:
        # given
        client, session = make_korail(MEMBERSHIP_ROUTES)

        # when
        client.membership.mileage()

        # then
        assert "x-dynapath-m-token" not in session.kwargs_for("mileage").get("headers", {})

    @pytest.mark.parametrize(
        "body",
        [
            {key: value for key, value in MILEAGE_PAYLOAD.items() if key != "specList"},
            {**MILEAGE_PAYLOAD, "specList": None},
            {**MILEAGE_PAYLOAD, "specList": []},
        ],
        ids=["absent", "null", "empty"],
    )
    def test_no_history_still_carries_the_balances(self, make_korail, body: dict[str, object]) -> None:
        # given
        client, _ = make_korail({"mileage": body})

        # when
        mileage = client.membership.mileage()

        # then
        assert (mileage.entries, mileage.ktx) == ((), 12340)

    def test_not_logged_in_is_an_exception(self, make_korail) -> None:
        # given
        client, _ = make_korail({"mileage": NEED_LOGIN})

        # when & then
        with pytest.raises(NeedToLoginError):
            client.membership.mileage()


class TestCoupons:
    """할인쿠폰 목록 — ``passCard.CouponView``."""

    def test_lists_the_coupons(self, make_korail) -> None:
        # given
        client, _ = make_korail(MEMBERSHIP_ROUTES)

        # when
        coupons = client.membership.coupons()

        # then
        assert [(coupon.title, coupon.valid_until) for coupon in coupons] == [("KTX 10% 할인쿠폰", "20261231")]

    def test_sends_exact_form_fields(self, make_korail) -> None:
        """폼 필드 이름이 바뀌면 서버가 조용히 빈 결과를 줍니다."""
        # given
        client, session = make_korail(MEMBERSHIP_ROUTES)

        # when
        client.membership.coupons()

        # then
        assert set(session.kwargs_for("coupons")["data"]) == COUPONS_FORM_FIELDS

    @pytest.mark.parametrize(("page", "sent"), [(1, "1"), (2, "2")])
    def test_sends_the_page_number(self, make_korail, page: int, sent: str) -> None:
        # given
        client, session = make_korail(MEMBERSHIP_ROUTES)

        # when
        client.membership.coupons(page)

        # then
        data = session.kwargs_for("coupons")["data"]
        assert (data["AppVersion"], data["txtSelPage"]) == ("7.0.8", sent)

    @pytest.mark.parametrize(
        "body",
        [
            NO_COUPONS_PAYLOAD,
            NO_RESULTS,
            {**COUPONS_PAYLOAD, "coupon_infos": None},
            {**COUPONS_PAYLOAD, "coupon_infos": {"coupon_info": []}},
        ],
        ids=["success-without-a-list", "no-results-refusal", "null", "empty"],
    )
    def test_no_coupons_is_an_empty_list(self, make_korail, body: dict[str, object]) -> None:
        # given
        client, _ = make_korail({"coupons": body})

        # when
        coupons = client.membership.coupons()

        # then
        assert coupons == []

    @pytest.mark.parametrize("page", [0, -1])
    def test_rejects_a_page_below_one(self, make_korail, page: int) -> None:
        # given
        client, session = make_korail(MEMBERSHIP_ROUTES)

        # when
        with pytest.raises(ValueError, match="page"):
            client.membership.coupons(page)

        # then
        assert session.calls == []

    def test_goes_in_the_form_body_not_the_query(self, make_korail) -> None:
        # given
        client, session = make_korail(MEMBERSHIP_ROUTES)

        # when
        client.membership.coupons()

        # then
        assert "params" not in session.kwargs_for("coupons")

    def test_is_not_signed(self, make_korail) -> None:
        # given
        client, session = make_korail(MEMBERSHIP_ROUTES)

        # when
        client.membership.coupons()

        # then
        assert "x-dynapath-m-token" not in session.kwargs_for("coupons").get("headers", {})

    def test_other_refusals_are_not_swallowed(self, make_korail) -> None:
        """빈 리스트로 접는 것은 "결과 없음" 뿐입니다. 로그인 만료까지 삼키면 쿠폰이 없는 것으로 보입니다."""
        # given
        client, _ = make_korail({"coupons": NEED_LOGIN})

        # when & then
        with pytest.raises(NeedToLoginError):
            client.membership.coupons()

    def test_unknown_refusal_is_a_korail_error(self, make_korail) -> None:
        # given
        client, _ = make_korail({"coupons": {"strResult": "FAIL", "h_msg_cd": "ERR999999", "h_msg_txt": "오류"}})

        # when & then
        with pytest.raises(KorailError):
            client.membership.coupons()


class TestMileageModel:
    def test_total_adds_the_samsung_card_mileage(self) -> None:
        """앱이 "KTX 마일리지" 로 보여 주는 숫자는 두 잔액의 합입니다."""
        # when
        total = Mileage.from_response(MILEAGE_PAYLOAD).total

        # then
        assert total == 13000

    def test_total_leaves_out_rail_points(self) -> None:
        # when
        mileage = Mileage.from_response({"totAvlRailPontValNum": "100", "totAvlAfltPontValNum": "9000"})

        # then
        assert (mileage.total, mileage.rail_point) == (100, 9000)

    def test_reads_balances_with_thousands_separators(self) -> None:
        """실서버는 쉼표 없이 주지만, 앱이 한 글자를 떼고 읽는 값이라 쉼표가 와도 읽습니다."""
        # when
        mileage = Mileage.from_response({"totAvlRailPontValNum": "12,340", "delPontValNum": "1,200"})

        # then
        assert (mileage.ktx, mileage.expiring) == (12340, 1200)

    def test_missing_fields_do_not_break_the_model(self) -> None:
        # when
        mileage = Mileage.from_response({})

        # then
        assert mileage == Mileage(ktx=0, samsung_card=0, rail_point=0, expiring=0, info="", page_count=0)

    def test_reads_an_entry(self) -> None:
        # when
        entry = MileageEntry.from_response(MILEAGE_ENTRY_INFO)

        # then
        assert entry == MileageEntry(
            date="20261003",
            kind_name="KTX 마일리지",
            movement="적립",
            detail="마일리지 적립 (열차이용)",
            amount=2990,
        )

    @pytest.mark.parametrize(
        ("printed", "expected"),
        [("+2,990", 2990), ("+990", 990), ("-1,000", -1000), ("-500", -500)],
        ids=["earned", "earned-small", "used", "used-small"],
    )
    def test_entry_amount_keeps_its_sign(self, printed: str, expected: int) -> None:
        """서버는 증감을 부호와 쉼표가 붙은 문자열로 줍니다. 사용은 음수로 읽혀야 합니다."""
        # when
        entry = MileageEntry.from_response({**MILEAGE_ENTRY_INFO, "pontAmt": printed})

        # then
        assert entry.amount == expected

    def test_reads_zero_padded_balances(self) -> None:
        """실서버는 잔액을 0 을 채운 고정 폭 숫자로 줍니다."""
        # when
        mileage = Mileage.from_response(
            {"totAvlRailPontValNum": "000012340", "delPontValNum": "00000000120", "pgCnt": "00003"}
        )

        # then
        assert (mileage.ktx, mileage.expiring, mileage.page_count) == (12340, 120, 3)

    def test_entry_with_nothing_is_blank(self) -> None:
        # when
        entry = MileageEntry.from_response({})

        # then
        assert entry == MileageEntry(date="", kind_name="", movement="", detail="", amount=0)


class TestCouponModel:
    def test_reads_what_the_app_shows(self) -> None:
        # when
        coupon = Coupon.from_response(COUPON_INFO)

        # then
        assert coupon == Coupon(
            coupon_no="C202610120001234",
            title="KTX 10% 할인쿠폰",
            description="주중 · 주말 모두 사용 가능",
            tag="KTX",
            valid_from="20261001",
            valid_until="20261231",
            guide="한 번에 한 장만 쓸 수 있습니다.",
        )

    def test_missing_fields_do_not_break_the_model(self) -> None:
        # when
        coupon = Coupon.from_response({})

        # then
        assert (coupon.coupon_no, coupon.title, coupon.valid_until) == ("", "", "")

    def test_repr_masks_the_coupon_number(self) -> None:
        """쿠폰번호는 다른 계정에 등록할 수 있는 값이라 로그에 통째로 남으면 안 됩니다."""
        # when
        shown = repr(Coupon.from_response(COUPON_INFO))

        # then
        assert "C20261012000" not in shown
        assert "****1234" in shown

    @pytest.mark.parametrize("number", ["", "123"])
    def test_repr_hides_short_numbers_entirely(self, number: str) -> None:
        # when
        shown = repr(Coupon.from_response({**COUPON_INFO, "h_cpn_no": number}))

        # then
        assert "coupon_no='****'" in shown


class TestMembershipModelsAreFrozen:
    @pytest.mark.parametrize(
        ("model", "field"),
        [
            (Mileage.from_response(MILEAGE_PAYLOAD), "ktx"),
            (MileageEntry.from_response(MILEAGE_ENTRY_INFO), "amount"),
            (Coupon.from_response(COUPON_INFO), "coupon_no"),
        ],
        ids=["mileage", "entry", "coupon"],
    )
    def test_models_are_frozen(self, model: object, field: str) -> None:
        # when & then
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(model, field, "changed")
