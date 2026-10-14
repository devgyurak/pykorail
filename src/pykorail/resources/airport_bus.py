"""동기 공개 경로 재수출 shim. 실제 구현은 :mod:`pykorail._sync.resources.airport_bus` 에 있습니다."""

from __future__ import annotations

from pykorail._sync.resources import airport_bus as _impl

AirportBusResource = _impl.AirportBusResource

__all__ = ["AirportBusResource"]


def __getattr__(name: str) -> object:
    """``_impl`` 이 노출하는 나머지 이름을 위임합니다 (하위 호환)."""
    return getattr(_impl, name)
