# 이 파일은 생성물입니다 — 직접 고치지 마세요.
# 원본: src/pykorail/_async/resources/base.py
# 다시 만들려면: uv run python scripts/unasync.py
"""리소스 공통 기반."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pykorail._sync.api import ApiClient


class Resource:
    """엔드포인트 묶음 하나.

    리소스는 상태를 거의 갖지 않고 :class:`~pykorail.api.ApiClient` 를 통해서만
    통신합니다. 클라이언트 하나가 만든 리소스들은 세션·서명·로그인 상태를 공유합니다.
    """

    def __init__(self, api: ApiClient) -> None:
        self._api = api
