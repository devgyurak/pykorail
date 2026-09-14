"""pykorail 예외 계층.

::

    PykorailError
    ├── KorailError            코레일이 strResult=FAIL 로 응답
    │   ├── NeedToLoginError   P058
    │   ├── NoResultsError     P100, WRG000000, WRD000061, WRT300005
    │   ├── SoldOutError       IRT010110, ERR211161
    │   └── LoginFailedError   로그인 실패 전부 (코드 매핑 없음 — 클라이언트가 직접 던짐)
    ├── NetFunnelError         대기열 게이트 실패
    ├── StationNotFoundError   요청 전 클라이언트 검증 실패
    ├── PastDepartureError     이미 지난 시각으로 조회
    └── TransportError         세션 생성 실패 / 비 JSON 응답
"""

from __future__ import annotations

from pykorail.exceptions.api import (
    LoginFailedError,
    NeedToLoginError,
    NoResultsError,
    SoldOutError,
    error_for_code,
)
from pykorail.exceptions.base import KorailError, PykorailError
from pykorail.exceptions.network import NetFunnelError, TransportError
from pykorail.exceptions.validation import PastDepartureError, StationNotFoundError

__all__ = [
    "KorailError",
    "LoginFailedError",
    "NeedToLoginError",
    "NetFunnelError",
    "NoResultsError",
    "PastDepartureError",
    "PykorailError",
    "SoldOutError",
    "StationNotFoundError",
    "TransportError",
    "error_for_code",
]
