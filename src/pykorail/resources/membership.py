"""멤버십 리소스 — 마일리지 · 할인쿠폰."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from pykorail.constants import API_ENDPOINTS
from pykorail.exceptions import NoResultsError
from pykorail.models.membership import Coupon, Mileage
from pykorail.models.parsing import records
from pykorail.options import MileageInquiry, MileageType
from pykorail.resources.base import Resource
from pykorail.resources.clock import to_kst

if TYPE_CHECKING:
    from pykorail.options import MileageInquiryCode, MileageTypeCode

#: 기간을 주지 않았을 때 거슬러 올라가는 날수. 앱의 가장 짧은 선택지("1개월")에 맞췄습니다.
DEFAULT_PERIOD = timedelta(days=30)

#: 내역 한 쪽의 건수 (``pgPrCnt``). 앱의 값은 보호돼 있어 두 자리 숫자라는 것까지만
#: 읽힙니다. 20 은 7.0.8 실서버에서 성공이 기록된 값입니다
#: (``docs/protocol-evidence-7.0.8.json``).
_PAGE_SIZE = "20"


class MembershipResource(Resource):
    """``korail.membership`` — 마일리지 · 레일포인트 · 할인쿠폰 조회. 전부 **로그인이 필요합니다.**"""

    def mileage(
        self,
        since: date | None = None,
        until: date | None = None,
        *,
        kind: MileageTypeCode = MileageType.KTX,
        inquiry: MileageInquiryCode = MileageInquiry.ALL,
        page: int = 1,
    ) -> Mileage:
        """마일리지 잔액과 적립 · 사용 내역 한 쪽을 조회합니다.

        잔액(KTX 마일리지 · 레일포인트 · 소멸 예정)은 조건과 무관하게 함께 옵니다.
        요청 필드는 코레일+ 7.0.8 의 ``AmtSpecIn`` 에서, 구분 코드의 값은 앱의
        ``MileageType`` · ``MileageInquiryType`` 에서 확인했습니다.

        Args:
            since: 내역을 볼 첫날. 생략하면 ``until`` 의 30일 전.
            until: 내역을 볼 마지막 날. 생략하면 오늘(KST). 둘 다 ``datetime`` 을 넘겨도
                되고, 그때는 KST 기준 날짜만 씁니다.
            kind: 어느 장부의 내역인지 — :class:`~pykorail.options.MileageType`. 기본은 KTX 마일리지.
            inquiry: 적립 · 사용 구분 — :class:`~pykorail.options.MileageInquiry`. 기본은 전체.
            page: 내역의 쪽 번호. 1 부터. 전체 쪽 수는 결과의 ``page_count`` 입니다.

        Raises:
            ValueError: ``since`` 가 ``until`` 보다 늦거나 ``page`` 가 1 보다 작습니다.
            NeedToLoginError: 로그인하지 않았습니다.
        """
        page_no = self._page_number(page)
        last = self._day(until) or to_kst(None).date()
        first = self._day(since) or last - DEFAULT_PERIOD
        if first > last:
            raise ValueError(f"since 가 until 보다 늦습니다: {first:%Y-%m-%d} > {last:%Y-%m-%d}")

        url = API_ENDPOINTS["mileage"]
        headers, _ = self._api.sign(url)
        # 요청 모델에는 mbCrdNo 도 있지만 앱이 비워 두고, 빈 필드는 폼에 실리지 않습니다.
        form = {
            **self._api.common_payload(),
            "pontTpVal": kind,
            "qryDvVal": inquiry,
            "qryStDt": f"{first:%Y%m%d}",
            "qryClsDt": f"{last:%Y%m%d}",
            "pgPrCnt": _PAGE_SIZE,
            "nowPgNo": page_no,
        }

        payload = self._api.post(url, data=form, headers=headers)
        self._api.check(payload)

        return Mileage.from_response(payload)

    def coupons(self, page: int = 1) -> list[Coupon]:
        """가진 할인쿠폰을 조회합니다. 없으면 빈 리스트.

        요청 필드는 코레일+ 7.0.8 의 ``CouponIn`` 에서 확인했습니다. 앱의 쿠폰함은
        쪽 번호만 싣고, 예약번호(``pnrNo``)는 결제 화면에서만 채웁니다.

        Args:
            page: 쪽 번호. 1 부터. 전체 쪽 수는 돌려주지 않습니다 — 쿠폰이 실린 응답을
                확인하지 못해 쪽 정보를 싣지 않았습니다. 다음 쪽이 비면 끝입니다.

        Raises:
            ValueError: ``page`` 가 1 보다 작습니다.
            NeedToLoginError: 로그인하지 않았습니다.
        """
        page_no = self._page_number(page)

        url = API_ENDPOINTS["coupons"]
        headers, _ = self._api.sign(url)
        form = {**self._api.common_payload(), "txtSelPage": page_no}

        payload = self._api.post(url, data=form, headers=headers)
        try:
            self._api.check(payload)
        except NoResultsError:
            return []

        return [Coupon.from_response(info) for info in records(payload, "coupon_infos", "coupon_info")]

    @staticmethod
    def _day(value: date | None) -> date | None:
        """``datetime`` 이 오면 KST 날짜로 줄입니다.

        ``datetime`` 은 ``date`` 의 하위 타입이라 타입 검사를 통과하지만 ``date`` 와는
        비교가 되지 않습니다 — 한쪽만 ``datetime`` 이면 기간 검사에서 ``TypeError`` 가 납니다.
        ``trains.search`` 에 ``datetime`` 을 넘기던 사람이 여기에도 그대로 넘길 수 있으므로
        입구에서 받습니다. 시각대 해석은 조회와 같습니다(tz 없으면 KST, 있으면 KST 로 변환).
        """
        return to_kst(value).date() if isinstance(value, datetime) else value

    @staticmethod
    def _page_number(page: int) -> str:
        if page < 1:
            raise ValueError(f"page 는 1 이상이어야 합니다: {page}")
        return str(page)
