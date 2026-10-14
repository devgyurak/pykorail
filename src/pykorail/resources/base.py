"""동기 공개 경로 재수출 shim.

``Resource`` 는 :mod:`pykorail._sync.resources.base`(생성물)의 원본이고,
``without_blanks`` 는 두 계층이 함께 쓰는 순수 헬퍼라 :mod:`pykorail._shared` 에
있습니다. 두 이름 다 옛 경로로도 계속 import 됩니다.
"""

from __future__ import annotations

from pykorail._shared.blank import without_blanks
from pykorail._sync.resources import base as _impl

Resource = _impl.Resource

__all__ = ["Resource", "without_blanks"]


def __getattr__(name: str) -> object:
    """``_impl`` 이 노출하는 나머지 이름을 위임합니다 (하위 호환)."""
    return getattr(_impl, name)
