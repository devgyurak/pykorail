"""응답 dict → 파이썬 값으로 옮길 때 쓰는 관용 파서.

코레일 응답은 필드를 통째로 빼먹거나 빈 문자열로 채워 보내는 경우가 있습니다.
모델 생성이 그런 이유로 죽으면 안 되므로, 여기서 전부 흡수합니다.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pykorail._shared.clock import KST


def text(data: dict[str, Any], key: str, default: str = "") -> str:
    """문자열 필드를 읽습니다. 없거나 ``None`` 이면 ``default``."""
    value = data.get(key)
    return default if value is None else str(value)


def optional_text(data: dict[str, Any], key: str) -> str | None:
    """문자열 필드를 읽되, 없거나 빈 값이면 ``None`` 입니다.

    "값이 없음" 을 ``None`` 하나로 통일합니다. 빈 문자열을 그대로 두면 ``str | None``
    선언이 거짓이 되고, 호출부가 ``""`` 와 ``None`` 을 따로 처리하게 됩니다.
    """
    return text(data, key) or None


def integer(data: dict[str, Any], key: str, default: int = 0) -> int:
    """정수 필드를 읽습니다. 없거나 숫자로 못 읽으면 ``default``."""
    return _to_int(data.get(key), default)


def amount(data: dict[str, Any], key: str, default: int = 0) -> int:
    """금액·포인트 필드를 읽습니다. 표시용 문자열(``"48,000원"``)도 읽고, ``"-"`` 는 0 입니다.

    운임 조회는 금액을 화면에 찍을 모양 그대로 줍니다 — 자릿수 쉼표와 ``원`` 이 붙고,
    해당 없는 칸은 ``"-"`` 입니다 (2026-10-13 실서버 확인). 마일리지 잔액도 앱이 더하기
    전에 한 글자를 지우고 숫자로 바꾸는 값이라(코레일+ 7.0.8 ``StringExKt.safeToLong``)
    쉼표가 올 수 있습니다. :func:`integer` 로 읽으면 이런 값이 오류 없이 ``default`` 가
    되어, 운임이나 잔액이 조용히 0 으로 보입니다.
    """
    value = data.get(key)
    if isinstance(value, str):
        value = value.strip().replace(",", "").removesuffix("원").strip()
        if value == "-":
            return 0
    return _to_int(value, default)


def floating(data: dict[str, Any], key: str, default: float | None = None) -> float | None:
    """실수 필드를 읽습니다. 없거나 숫자로 못 읽으면 ``default``."""
    value = data.get(key)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def records(data: dict[str, Any], *path: str) -> list[dict[str, Any]]:
    """``path`` 를 따라 들어간 곳의 목록을 읽습니다. 없으면 빈 목록.

    코레일은 목록을 ``{"x_infos": {"x_info": [...]}}`` 처럼 한 겹 싸서 주고, 결과가
    없으면 키를 빼거나 ``null`` 을 넣거나 목록 자리에 다른 것을 보냅니다. 어느 쪽이든
    빈 목록으로 읽고, 목록 안에서도 dict 가 아닌 항목은 건너뜁니다.
    """
    node: Any = data
    for key in path:
        if not isinstance(node, dict):
            return []
        node = node.get(key)
    if not isinstance(node, list):
        return []
    return [item for item in node if isinstance(item, dict)]


def _to_int(value: Any, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def kst_date(value: str) -> date | None:
    """``YYYYMMDD`` 를 날짜로. 길이가 다르거나 없는 날짜(``20261340``)면 ``None``.

    자릿수가 모자란 값을 ``strptime`` 에 맡기면 ``2026110`` 같은 것도 말없이 읽힙니다.
    그래서 길이와 숫자 여부를 먼저 봅니다.
    """
    if len(value) != 8 or not value.isdigit():
        return None
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        return None


def kst_datetime(day: str, clock: str) -> datetime | None:
    """``YYYYMMDD`` 와 ``HHMMSS`` 를 KST 일시로. 둘 중 하나라도 틀리면 ``None``.

    날짜만 있고 시각이 빈 응답(예약대기 등)을 ``00:00`` 으로 꾸미지 않으려고 시각도 같은
    기준으로 막습니다.
    """
    moment = kst_date(day)
    if moment is None or len(clock) != 6 or not clock.isdigit():
        return None
    try:
        return datetime(
            moment.year,
            moment.month,
            moment.day,
            int(clock[:2]),
            int(clock[2:4]),
            int(clock[4:6]),
            tzinfo=KST,
        )
    except ValueError:
        return None


def hhmm(value: str) -> str:
    """``HHMMSS`` → ``HH:MM``. 형식이 안 맞으면 원본을 그대로 돌려줍니다."""
    if len(value) < 4 or not value[:4].isdigit():
        return value
    return f"{value[:2]}:{value[2:4]}"


def mmdd(value: str, separator: str = "/") -> str:
    """``YYYYMMDD`` → ``MM/DD``. 형식이 안 맞으면 원본을 그대로 돌려줍니다."""
    if len(value) < 8 or not value.isdigit():
        return value
    return f"{int(value[4:6]):02d}{separator}{int(value[6:8]):02d}"
