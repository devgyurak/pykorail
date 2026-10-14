"""동기 공개 경로 재수출 shim.

실제 구현은 :mod:`pykorail._sync.client` 에 있습니다. develop 의 ``pykorail.client``
는 자기 import(``create_session`` · 상수 · 예외 등)까지 모듈 속성으로 노출했으므로,
그 이름들도 옛 경로로 계속 접근되게 합니다.
"""

from __future__ import annotations

from pykorail._sync import client as _impl
from pykorail.transport import create_session

Korail = _impl.Korail

__all__ = ["Korail", "create_session"]


def __getattr__(name: str) -> object:
    """``_impl`` 이 노출하는 나머지 이름을 위임합니다 (하위 호환)."""
    return getattr(_impl, name)
