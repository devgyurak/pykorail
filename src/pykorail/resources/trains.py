"""동기 공개 경로 재수출 shim. 실제 구현은 :mod:`pykorail._sync.resources.trains` 에 있습니다."""

from __future__ import annotations

from pykorail._sync.resources import trains as _impl

MAX_PAGES = _impl.MAX_PAGES
PAST_TOLERANCE = _impl.PAST_TOLERANCE
TrainResource = _impl.TrainResource

__all__ = ["MAX_PAGES", "PAST_TOLERANCE", "TrainResource"]


def __getattr__(name: str) -> object:
    """``KST`` · ``to_kst`` 등 develop 이 노출하던 나머지 이름을 위임합니다 (하위 호환)."""
    return getattr(_impl, name)
