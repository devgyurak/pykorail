"""동기 공개 경로 재수출 shim. 실제 구현은 :mod:`pykorail._shared.clock` 에 있습니다."""

from __future__ import annotations

from pykorail._shared.clock import KST, to_kst
from pykorail.constants import KST_OFFSET_HOURS

__all__ = ["KST", "KST_OFFSET_HOURS", "to_kst"]
