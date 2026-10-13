"""리소스가 공유하는 KST 시각 기준.

코레일 서버가 주고받는 날짜·시각은 전부 KST 라, 해석 기준을 한 곳에 모읍니다. 조회 ·
멤버십 · 공항버스 셋이 쓰게 되어 형제 리소스(``trains``)에서 빼냈습니다.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pykorail.constants import KST_OFFSET_HOURS

#: 코레일 서버가 시각을 주고받는 기준 시간대. 실행 머신의 로컬 타임존과 무관합니다.
KST = timezone(timedelta(hours=KST_OFFSET_HOURS))


def to_kst(moment: datetime | None) -> datetime:
    """KST 기준 시각으로 정규화합니다.

    ``None`` 이면 지금, naive 면 이미 KST 인 것으로 보고 tz 만 붙이고, aware 면
    KST 로 변환합니다. 서버가 보내 주는 날짜·시각이 전부 KST 라 기준을 여기 하나로
    모읍니다 — 실행 머신의 로컬 타임존에 결과가 흔들리면 안 됩니다.
    """
    if moment is None:
        return datetime.now(KST)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=KST)
    return moment.astimezone(KST)
