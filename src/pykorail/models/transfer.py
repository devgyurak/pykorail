"""환승 — 갈아탈 수 있는 역과, 두 열차를 이어 붙인 환승 여정."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pykorail.models.parsing import integer, text
from pykorail.models.schedule import Train

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Self

logger = logging.getLogger(__name__)

#: 여정 하나의 구간 수. 실서버에서 본 환승 여정은 전부 두 구간이었습니다.
_LEGS = 2


@dataclass(frozen=True)
class TransferStation:
    """두 역 사이에서 갈아탈 수 있는 역."""

    code: str
    name: str
    english_name: str

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> Self:
        return cls(
            code=text(data, "chtnRsStnCd"),
            name=text(data, "chtnRsStnNm"),
            english_name=text(data, "chtnRsStnEngNm"),
        )


@dataclass(frozen=True)
class Transfer:
    """열차를 갈아타는 여정 하나.

    열차를 상속하지 않고 **참조**합니다 — 여정은 열차가 아니라 열차들의 묶음입니다.

    구간은 ``legs`` 에 타는 순서대로 담깁니다. 지금 만드는 여정은 전부 두 구간이지만
    자료형에는 그 수를 박아 두지 않았습니다 — 두 번 갈아타는 여정을 다루게 되는 날
    필드를 뒤집지 않아도 되게 하기 위해서입니다.
    """

    legs: tuple[Train, ...]

    def __post_init__(self) -> None:
        # 갈아타는 여정은 구간이 둘은 있어야 합니다. 하나짜리를 받아 두면 만들 때는 조용하다가
        # second 를 읽는 순간에야 IndexError 로 터집니다.
        if len(self.legs) < _LEGS:
            raise ValueError(f"환승 여정에는 구간이 {_LEGS}개 이상 필요합니다: {len(self.legs)}개")

    @classmethod
    def from_response(cls, rows: Sequence[dict[str, Any]]) -> Self:
        """한 여정으로 묶인 행들에서 만듭니다. 타는 순서대로 넘기세요 — 묶고 줄 세우는 일은
        :func:`parse_transfers` 가 합니다."""
        return cls(legs=tuple(Train.from_response(row) for row in rows))

    @property
    def first(self) -> Train:
        """처음 타는 열차."""
        return self.legs[0]

    @property
    def second(self) -> Train:
        """갈아탄 뒤의 열차."""
        return self.legs[1]

    @property
    def station_name(self) -> str | None:
        """갈아타는 역 이름. 첫 열차의 도착역과 둘째 열차의 출발역이 다르면 ``None``.

        두 역이 다르다는 것은 역 사이를 따로 이동해야 한다는 뜻이라, 한쪽 이름을
        환승역이라고 넘겨짚지 않습니다. ``first.arr_name`` 과 ``second.dep_name`` 을 보세요.
        """
        return self.first.arr_name if self.first.arr_name == self.second.dep_name else None

    def has_seat(self) -> bool:
        """모든 구간에 좌석이 있는지. 한 구간만 있어서는 여정을 탈 수 없습니다."""
        return all(leg.has_seat() for leg in self.legs)


def parse_transfers(rows: Sequence[dict[str, Any]]) -> list[Transfer]:
    """환승 조회의 열차 행들을 여정 단위로 묶습니다.

    서버는 여정을 중첩하지 않고 열차 행을 한 줄로 늘어놓은 채, 같은 여정의 행에 같은
    ``h_trn_seq`` 를(``"000"``, ``"001"`` …), 여정 안의 타는 순서에 ``h_chg_trn_seq``
    를(``"1"``, ``"2"``) 붙여 줍니다. 여정 번호가 같은 행을 묶고 타는 순서대로 놓습니다.

    **두 구간으로 묶이지 않는 것은 여정으로 만들지 않습니다** — 번호가 비어 있는 행, 한
    줄만 있는 번호, 셋 이상인 번호. 무엇과 짝인지 알 수 없는 행을 넘겨짚어 이으면
    실제로는 갈아탈 수 없는 여정이 만들어집니다.

    버린 행이 있으면 경고를 남깁니다. 서버가 여정 번호의 모양을 바꾸거나 세 구간 여정을
    섞어 주기 시작하면 결과가 통째로 비어 "여정 없음" 으로만 보이는데, 그때 원인을 알
    단서가 이 로그뿐입니다.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(text(row, "h_trn_seq"), []).append(row)

    # 타는 순서는 응답의 줄 순서가 아니라 서버가 붙인 번호를 따릅니다. 번호가 없으면 0 으로
    # 읽혀 줄 순서가 그대로 남습니다 (sorted 는 안정 정렬입니다).
    paired = [sorted(group, key=_leg_order) for sequence, group in groups.items() if sequence and len(group) == _LEGS]

    dropped = len(rows) - _LEGS * len(paired)
    if dropped:
        logger.warning(
            "환승 조회 행 %d개 중 %d개가 두 구간 여정으로 묶이지 않아 버렸습니다 (여정 번호별 행 수: %s)",
            len(rows),
            dropped,
            {sequence: len(group) for sequence, group in groups.items()},
        )
    return [Transfer.from_response(group) for group in paired]


def _leg_order(row: dict[str, Any]) -> int:
    return integer(row, "h_chg_trn_seq")
