"""역 마스터.

응답 모양(2026-09 실측)::

    {
        "stns": {
            "stn": [
                {
                    "stn_cd": "0115",
                    "stn_nm": "강릉",
                    "longitude": "128.898851",
                    "latitude": "37.764108",
                    "group": "1",
                    "major": "28",
                    "popupType": "0",
                    "popupMessage": "",
                },
                ...,
            ]
        }
    }

281개 역이 내려오고, 그중 45개에만 ``major`` 가 붙습니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pykorail.models.parsing import floating, text

if TYPE_CHECKING:
    from typing import Self

#: 역 목록이 들어 있는 응답 경로.
STATIONS_PATH = ("stns", "stn")


@dataclass(frozen=True)
class Station:
    """역 하나.

    조회 API 는 역 **이름**을 받으므로(``txtGoStart``), 보통은 :attr:`name` 을
    그대로 넘깁니다. 나머지는 부가 정보입니다.
    """

    code: str
    name: str
    latitude: float | None
    longitude: float | None
    #: 노선 그룹 코드. 같은 값이면 같은 노선군입니다.
    group: str
    #: 주요역 정렬 순번. 주요역이 아니면 빈 문자열입니다.
    major: str
    #: 역 선택 시 앱이 띄우는 안내 종류. ``"0"`` 이면 안내 없음.
    popup_type: str
    popup_message: str

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> Self:
        return cls(
            code=text(data, "stn_cd"),
            name=text(data, "stn_nm"),
            latitude=floating(data, "latitude"),
            longitude=floating(data, "longitude"),
            group=text(data, "group"),
            major=text(data, "major"),
            popup_type=text(data, "popupType"),
            popup_message=text(data, "popupMessage"),
        )

    @property
    def is_major(self) -> bool:
        """주요역(앱 상단에 먼저 노출되는 역)인지."""
        return bool(self.major)

    @property
    def major_rank(self) -> int | None:
        """주요역 정렬 순번을 정수로. 주요역이 아니면 ``None``."""
        return int(self.major) if self.major.isdigit() else None

    def __repr__(self) -> str:
        return f"{self.name}({self.code})"


def parse_stations(payload: dict[str, Any]) -> list[Station]:
    """``stationdata`` 응답에서 역 목록을 뽑습니다."""
    node: Any = payload
    for key in STATIONS_PATH:
        node = node.get(key, {}) if isinstance(node, dict) else {}
    return [Station.from_response(entry) for entry in node] if isinstance(node, list) else []
