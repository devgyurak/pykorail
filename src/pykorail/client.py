"""동기 코드 경로를 위한 재수출. 실제 구현은 :mod:`pykorail._sync.client` 에 있습니다."""

from __future__ import annotations

from pykorail._sync.client import Korail

__all__ = ["Korail"]
