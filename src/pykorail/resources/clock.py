"""동기 코드 경로를 위한 재수출. 실제 구현은 :mod:`pykorail._shared.clock` 에 있습니다."""

from __future__ import annotations

from pykorail._shared.clock import KST, to_kst

__all__ = ["KST", "to_kst"]
