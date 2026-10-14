"""동기 코드 경로를 위한 재수출. 실제 구현은 :mod:`pykorail._sync.resources.tickets` 에 있습니다."""

from __future__ import annotations

from pykorail._sync.resources.tickets import TicketResource

__all__ = ["TicketResource"]
