"""승객 유형과 할인 구분.

승객은 "유형 + 할인 + 등록카드"가 같으면 하나로 합쳐 보냅니다 — 코레일 폼이
승객 블록을 인덱스로 받기 때문에, 같은 조건을 두 블록으로 쪼개 보낼 이유가
없습니다. :meth:`Passenger.reduce` 가 그 합치기를 합니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import reduce as _reduce
from itertools import groupby
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True, init=False, repr=False)
class Passenger:
    """승객 묶음 한 종류. 직접 쓰지 말고 하위 타입을 쓰세요.

    하위 타입은 ``TYPE_CODE`` 와 ``DEFAULT_DISCOUNT`` 만 채웁니다 — 생성자
    시그니처가 계층 전체에서 같아야 :meth:`reduce` 가 합칠 때 같은 방식으로
    다시 만들 수 있습니다.

    불변입니다. 인원을 바꾸려면 새 승객을 만드세요 (``a + b`` 가 그렇게 합칩니다).
    동등 비교는 같은 유형과 같은 값끼리 참입니다. ``repr`` 은 카드번호와 비밀번호를
    찍지 않도록 직접 씁니다 — 데이터클래스 기본 ``repr`` 을 쓰면 그 값이 로그에 나갑니다.
    """

    #: 코레일 승객 유형 코드 (``txtPsgTpCd``). 1=어른, 3=어린이 계열.
    TYPE_CODE: ClassVar[str] = "1"
    #: 유형별 기본 할인 코드 (``txtDiscKndCd``).
    DEFAULT_DISCOUNT: ClassVar[str] = "000"

    count: int
    discount_type: str
    card: str
    card_no: str
    card_pw: str

    def __init__(
        self,
        count: int = 1,
        discount_type: str | None = None,
        card: str = "",
        card_no: str = "",
        card_pw: str = "",
    ) -> None:
        # 음수 인원은 합치기에서 조용히 버려지던 값입니다. 0 은 reduce 가 버리는 것이 기존
        # 동작이라 그대로 두고, 음수만 생성 시점에 막습니다.
        if count < 0:
            raise ValueError(f"passenger count must not be negative, got {count}")
        # 불변 객체라 대입은 object.__setattr__ 로 합니다.
        object.__setattr__(self, "count", count)
        object.__setattr__(self, "discount_type", self.DEFAULT_DISCOUNT if discount_type is None else discount_type)
        object.__setattr__(self, "card", card)
        object.__setattr__(self, "card_no", card_no)
        object.__setattr__(self, "card_pw", card_pw)

    @property
    def typecode(self) -> str:
        return self.TYPE_CODE

    def group_key(self) -> str:
        """합칠 수 있는 승객끼리 같아지는 키."""
        return f"{self.typecode}_{self.discount_type}_{self.card}_{self.card_no}_{self.card_pw}"

    @staticmethod
    def reduce(passengers: Sequence[Passenger]) -> list[Passenger]:
        """같은 조건의 승객을 합치고, 인원이 0 인 항목은 버립니다. 음수 인원은 생성 시점에 막힙니다.

        ``itertools.groupby`` 는 **연속된** 같은 키만 묶으므로 먼저 키로 정렬합니다 —
        정렬 없이는 ``[어른, 어린이, 어른]`` 이 어른 블록 두 개로 나가 버립니다.

        ``list`` 가 아니라 ``Sequence`` 를 받는 것은 의도적입니다. ``list`` 는 불변
        (invariant)이라 ``[AdultPassenger(2)]`` 처럼 한 종류만 담은 리스트를 넘기면
        타입 검사에서 걸립니다 — 가장 흔한 호출 형태가 막히면 안 됩니다.
        """
        if not all(isinstance(passenger, Passenger) for passenger in passengers):
            raise TypeError("Passengers must be based on Passenger")

        merged = [
            _reduce(lambda a, b: a + b, group)
            for _, group in groupby(sorted(passengers, key=lambda p: p.group_key()), key=lambda p: p.group_key())
        ]
        return [passenger for passenger in merged if passenger.count > 0]

    def __add__(self, other: Passenger) -> Passenger:
        if not isinstance(other, self.__class__):
            raise TypeError("Cannot add different passenger types")
        if self.group_key() != other.group_key():
            # 그룹 키에는 카드번호·비밀번호가 들어 있어 메시지에 싣지 않습니다.
            raise TypeError(
                f"Cannot add passengers with different group keys: "
                f"type {self.typecode!r} discount {self.discount_type!r} vs discount {other.discount_type!r}"
            )
        return self.__class__(
            count=self.count + other.count,
            discount_type=self.discount_type,
            card=self.card,
            card_no=self.card_no,
            card_pw=self.card_pw,
        )

    def get_dict(self, index: int) -> dict[str, Any]:
        """예매 폼에 실을 인덱스별 승객 필드."""
        return {
            f"txtPsgTpCd{index}": self.typecode,
            f"txtDiscKndCd{index}": self.discount_type,
            f"txtCompaCnt{index}": self.count,
            f"txtCardCode_{index}": self.card,
            f"txtCardNo_{index}": self.card_no,
            f"txtCardPw_{index}": self.card_pw,
        }

    def __repr__(self) -> str:
        return f"{type(self).__name__}(count={self.count}, discount_type={self.discount_type!r})"


class AdultPassenger(Passenger):
    """어른."""

    TYPE_CODE = "1"
    DEFAULT_DISCOUNT = "000"


class ChildPassenger(Passenger):
    """어린이."""

    TYPE_CODE = "3"
    DEFAULT_DISCOUNT = "000"


class ToddlerPassenger(Passenger):
    """유아."""

    TYPE_CODE = "3"
    DEFAULT_DISCOUNT = "321"


class SeniorPassenger(Passenger):
    """경로."""

    TYPE_CODE = "1"
    DEFAULT_DISCOUNT = "131"


class Disability1To3Passenger(Passenger):
    """중증 장애인 (1~3급)."""

    TYPE_CODE = "1"
    DEFAULT_DISCOUNT = "111"


class Disability4To6Passenger(Passenger):
    """경증 장애인 (4~6급)."""

    TYPE_CODE = "1"
    DEFAULT_DISCOUNT = "112"


class GuideDogPassenger(Passenger):
    """안내견 동반 승객 (시각장애인).

    유형 코드가 어른과 같은 ``1`` 이지만 **:class:`AdultPassenger` 의 하위가 아닙니다** —
    예매 폼에서는 할인 코드가 달라 별도 블록으로 나가고, 조회 폼에서는 어른 칸
    (``txtPsgFlg_1``)에 더해집니다. 어른과 합치는 것은 :func:`Passenger.reduce` 의 몫이
    아니라 :meth:`TrainResource.search <pykorail.resources.trains.TrainResource.search>` 가
    조회 폼을 만들 때 합니다 (코레일톡+ 7.0.8 ``TrainScheduleViewModel`` 의 인원 칸 합산).

    앱의 인원 선택기는 안내견 수가 중증 · 경증 장애인 합계를 넘지 못하게 막지만,
    pykorail 은 그 제약을 걸지 않고 서버 거절에 맡깁니다. 인원 제약을 클라이언트에서
    흉내 내면 앱이 나중에 조건을 바꿀 때 우리만 막는 요청이 생깁니다.

    .. warning::
        :attr:`DEFAULT_DISCOUNT` (``173``)는 외부 비공식 클라이언트 기록에 근거한
        값이고 **실서버로 확인되지 않았습니다.** 2026-10-16 중증 1 + 안내견 1 예약이
        서버에서 ``ERR299943``("예약할인이 지원되지 않습니다")로 거절됐지만, 같은
        열차의 중증 단독 예약도 할인이 적용되지 않아(적용 코드 ``000``) 이 거절이
        ``173`` 때문인지 계정 자격 때문인지 가리지 못했습니다. 그래서 이 승객으로
        :meth:`ReservationResource.create <pykorail.resources.reservations.ReservationResource.create>`
        가 실패할 수 있습니다 — 자세한 것은 ``docs/protocol-evidence-7.0.8.json``.
    """

    TYPE_CODE = "1"
    # 외부 비공식 클라이언트에서 온 값. APK 에서는 보호 문자열이라 읽히지 않았고
    # 실서버 예약도 거절되어 아직 확인되지 않았다 (위 경고 · protocol-evidence).
    DEFAULT_DISCOUNT = "173"
