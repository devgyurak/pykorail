"""동기 코드 경로를 위한 재수출. 실제 구현은 :mod:`pykorail._sync.resources.trains` 에 있습니다."""

from __future__ import annotations

from pykorail._shared.clock import KST, to_kst
from pykorail._sync.resources.trains import MAX_PAGES, PAST_TOLERANCE, TrainResource

__all__ = ["KST", "MAX_PAGES", "PAST_TOLERANCE", "TrainResource", "to_kst"]
