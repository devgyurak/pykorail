"""NetFunnel 대기열 재수출 shim.

실제 구현은 :mod:`pykorail._sync.netfunnel`(동기)과 :mod:`pykorail._async.netfunnel`
(비동기) 에 있습니다. ``pykorail.auth.netfunnel`` 을 직접 import 하던 코드가 옛 이름을
계속 찾을 수 있도록, develop 이 모듈 속성으로 노출하던 이름을 그대로 다시 실어 둡니다.
빠진 이름은 :func:`__getattr__` 이 ``_impl`` 에서 위임합니다.
"""

from __future__ import annotations

from pykorail._async.netfunnel import AsyncNetFunnelHelper
from pykorail._sync import netfunnel as _impl

NETFUNNEL_HEADERS = _impl.NETFUNNEL_HEADERS
NETFUNNEL_URL = _impl.NETFUNNEL_URL
NetFunnelError = _impl.NetFunnelError
NetFunnelHelper = _impl.NetFunnelHelper
create_session = _impl.create_session
logger = _impl.logger

__all__ = [
    "NETFUNNEL_HEADERS",
    "NETFUNNEL_URL",
    "AsyncNetFunnelHelper",
    "NetFunnelError",
    "NetFunnelHelper",
    "create_session",
    "logger",
]


def __getattr__(name: str) -> object:
    """``_impl`` 이 노출하는 나머지 이름을 위임합니다 (하위 호환)."""
    return getattr(_impl, name)
