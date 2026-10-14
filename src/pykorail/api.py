"""동기 공개 경로 재수출 shim.

실제 구현은 :mod:`pykorail._sync.api` 에 있습니다. 로거 이름은 동기 호출이
``pykorail.api``, 비동기 호출이 그 하위인 ``pykorail.api.async`` 입니다 — ``pykorail.api``
에 핸들러를 걸어 두면 propagate 로 동기·비동기 로그를 함께 받습니다. ``AsyncApiClient`` 는
:mod:`pykorail._async.api` 의 짝으로, 타입 힌트에 쓸 수 있게 여기서도 내보냅니다.
"""

from __future__ import annotations

from pykorail._async.api import AsyncApiClient
from pykorail._shared.response import ACCESS_RESTRICTED_CODE as ACCESS_RESTRICTED_CODE
from pykorail._sync import api as _impl

# :func:`~pykorail._shared.parse_response` 로 판정 로직을 옮기면서 ``_impl`` 이 더는
# 이 이름들을 import 하지 않습니다. 그래도 한때 이 모듈의 속성이었으므로(하위 호환),
# ``as`` 자기 자신으로 재수출해 옛 import 경로를 유지합니다. 원래도 import 부산물로
# 우연히 노출되던 이름이라 새 공개 표면으로 만들지 않도록 ``__all__`` 에는 넣지 않습니다.
from pykorail.exceptions import AccessRestrictedError as AccessRestrictedError
from pykorail.exceptions import HttpStatusError as HttpStatusError
from pykorail.exceptions import TransportError as TransportError
from pykorail.models.parsing import text as text

Account = _impl.Account
ApiClient = _impl.ApiClient
logger = _impl.logger

__all__ = ["ACCESS_RESTRICTED_CODE", "Account", "ApiClient", "AsyncApiClient", "logger"]


def __getattr__(name: str) -> object:
    """``_impl`` 이 노출하는 나머지 이름을 위임합니다 (하위 호환)."""
    return getattr(_impl, name)
