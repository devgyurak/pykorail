"""동기 공개 경로 재수출 shim.

실제 구현은 :mod:`pykorail._sync.api` 에 있습니다. 로거 이름은 동기 호출이
``pykorail.api``, 비동기 호출이 ``pykorail._async.api`` 입니다 — ``verbose`` 로그를
``pykorail.api`` 에 걸어 둔 사용자는 동기 로그를 계속 받습니다. ``AsyncApiClient`` 는
:mod:`pykorail._async.api` 의 짝으로, 타입 힌트에 쓸 수 있게 여기서도 내보냅니다.
"""

from __future__ import annotations

from pykorail._async.api import AsyncApiClient
from pykorail._sync import api as _impl

ACCESS_RESTRICTED_CODE = _impl.ACCESS_RESTRICTED_CODE
Account = _impl.Account
ApiClient = _impl.ApiClient
logger = _impl.logger

__all__ = ["ACCESS_RESTRICTED_CODE", "Account", "ApiClient", "AsyncApiClient", "logger"]


def __getattr__(name: str) -> object:
    """``_impl`` 이 노출하는 나머지 이름을 위임합니다 (하위 호환)."""
    return getattr(_impl, name)
