"""마일리지와 할인쿠폰 — 회원이 가진 것들의 조회 결과.

필드 이름은 코레일+ 7.0.8 의 응답 모델(``AmtSpecOut`` · ``CouponOutInfo``)에서,
각 값의 뜻은 앱이 그 값을 화면의 어느 자리에 놓는지에서 가져왔습니다. 마일리지는
값의 모양까지 실서버로 확인했습니다 (2026-10-13). 뜻을 확인하지 못한 필드는 싣지
않았습니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pykorail.models.parsing import amount, integer, records, text

if TYPE_CHECKING:
    from typing import Self


@dataclass(frozen=True)
class MileageEntry:
    """마일리지 적립 · 사용 내역 한 줄."""

    #: 날짜 ``YYYYMMDD`` (``dptDt``).
    date: str
    #: 어느 마일리지인지 (``pontDvNm``, ``"KTX 마일리지"``). 앱은 이 값과 :attr:`movement` 를
    #: 이어 제목으로 씁니다.
    kind_name: str
    #: 적립인지 사용인지 (``rcpDvNm``, ``"적립"`` · ``"사용"``).
    movement: str
    #: 서버가 붙인 설명 (``mlgAcmDvCdNm``). 적립은 ``"마일리지 적립 (열차이용)"``, 사용은
    #: ``"코레일"`` 처럼 옵니다.
    detail: str
    #: 증감 (``pontAmt``). 적립은 양수, 사용은 음수입니다 — 서버가 부호와 쉼표를 붙여
    #: ``"+2,990"`` · ``"-1,000"`` 으로 줍니다.
    amount: int

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> Self:
        return cls(
            date=text(data, "dptDt"),
            kind_name=text(data, "pontDvNm"),
            movement=text(data, "rcpDvNm"),
            detail=text(data, "mlgAcmDvCdNm"),
            amount=amount(data, "pontAmt"),
        )


@dataclass(frozen=True)
class Mileage:
    """마일리지 잔액과 내역 한 쪽.

    잔액은 조회 조건과 무관하게 함께 옵니다. 내역은 조건에 맞는 것 가운데 한 쪽이고,
    전체 쪽 수가 :attr:`page_count` 입니다.
    """

    #: KTX 마일리지 (``totAvlRailPontValNum``).
    ktx: int
    #: KTX 삼성카드로 쌓은 마일리지 (``totAvlRailPontValNum1``).
    samsung_card: int
    #: 레일포인트 (``totAvlAfltPontValNum``).
    rail_point: int
    #: 이번 달 소멸 예정 (``delPontValNum``).
    expiring: int
    #: 마일리지 안내 문구 (``ktxMlgInfo``).
    info: str
    #: 조건에 맞는 내역의 전체 쪽 수 (``pgCnt``).
    page_count: int
    entries: tuple[MileageEntry, ...] = ()

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> Self:
        return cls(
            ktx=amount(data, "totAvlRailPontValNum"),
            samsung_card=amount(data, "totAvlRailPontValNum1"),
            rail_point=amount(data, "totAvlAfltPontValNum"),
            expiring=amount(data, "delPontValNum"),
            info=text(data, "ktxMlgInfo"),
            page_count=integer(data, "pgCnt"),
            entries=tuple(MileageEntry.from_response(info) for info in records(data, "specList")),
        )

    @property
    def total(self) -> int:
        """쓸 수 있는 KTX 마일리지 — :attr:`ktx` 와 :attr:`samsung_card` 의 합.

        앱이 화면에 "KTX 마일리지" 로 보여 주는 숫자입니다. 레일포인트는 따로 셉니다.
        """
        return self.ktx + self.samsung_card


@dataclass(frozen=True)
class Coupon:
    """할인쿠폰 한 장.

    할인율 · 할인액 필드는 싣지 않았습니다. 응답 모델에 이름은 있지만
    (``h_inwk_prc_disc_rt_amt`` 등) 값의 형식과 구분 코드의 뜻을 확인하지 못했습니다.
    무슨 쿠폰인지는 :attr:`title` 로 읽으세요.
    """

    #: 쿠폰번호 (``h_cpn_no``). 번호만 알면 다른 계정에 등록할 수 있는 값이라 ``repr`` 에서 가립니다.
    coupon_no: str
    #: 쿠폰 이름 (``h_rmk_1_cont``).
    title: str
    #: 덧붙는 설명 (``h_rmk_2_cont``).
    description: str
    #: 앱이 꼬리표로 보여 주는 짧은 구분 (``h_rmk_3_cont``).
    tag: str
    #: 쓸 수 있는 첫날 ``YYYYMMDD`` (``h_fdcert_mg_st_dt``).
    valid_from: str
    #: 쓸 수 있는 마지막 날 ``YYYYMMDD`` (``h_fdcert_mg_cls_dt``). **승차일** 기준입니다.
    valid_until: str
    #: 이용 안내 (``guide``).
    guide: str

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> Self:
        return cls(
            coupon_no=text(data, "h_cpn_no"),
            title=text(data, "h_rmk_1_cont"),
            description=text(data, "h_rmk_2_cont"),
            tag=text(data, "h_rmk_3_cont"),
            valid_from=text(data, "h_fdcert_mg_st_dt"),
            valid_until=text(data, "h_fdcert_mg_cls_dt"),
            guide=text(data, "guide"),
        )

    def __repr__(self) -> str:
        """쿠폰번호는 뒤 4자리만 남깁니다 — 로그·트레이스백에 전체가 찍히면 안 됩니다."""
        masked = f"****{self.coupon_no[-4:]}" if len(self.coupon_no) >= 4 else "****"
        return f"Coupon(coupon_no={masked!r}, title={self.title!r}, valid_until={self.valid_until!r})"
