"""세션 래퍼 — 두 번 닫아도 안전한 ``close()`` 를 한 곳에서 제공합니다.

``ApiClient`` 와 ``NetFunnelHelper`` 가 각자 들고 있던 ``_closed`` 플래그를 이
클래스로 내립니다. 세션을 직접 다루는 곳이 늘어도 가드를 복사할 필요가 없고, 한쪽에만
빠뜨려 그 경로에서만 터지는 일도 없어집니다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from pykorail.transport import AsyncHttpSession, AsyncResponse


class AsyncIdempotentSession:
    """``AsyncHttpSession`` 을 감싸 ``close()`` 를 멱등하게 만듭니다.

    나머지 표면(``get`` · ``post`` · ``headers``)은 안쪽 세션에 그대로 넘깁니다.
    """

    def __init__(self, session: AsyncHttpSession) -> None:
        self._session = session
        self._closed = False
        # 프로토콜이 ``headers`` 를 가변 속성으로 선언합니다. 읽기 전용 프로퍼티로 두면
        # ``AsyncHttpSession`` 자리에 넣을 수 없어 ``ty`` 가 거절합니다.
        self.headers: MutableMapping[str, str] = session.headers

    async def get(self, url: str, **kwargs: Any) -> AsyncResponse:
        return await self._session.get(url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> AsyncResponse:
        return await self._session.post(url, **kwargs)

    async def close(self) -> None:
        """연결을 닫습니다. 두 번째 호출은 아무 일도 하지 않습니다.

        curl_cffi 의 코루틴 세션은 두 번째 ``close()`` 에서 ``TypeError`` 를 냅니다 —
        ``async with`` 블록 안에서 직접 ``close()`` 를 부르면 ``__aexit__`` 이 한 번 더
        닫으므로 가드가 필요합니다. 동기 세션은 두 번 닫아도 괜찮습니다.
        """
        # ``_closed`` 를 안쪽 close 호출 전에 세웁니다. 그래야 동시에 들어온 두 번째
        # 호출이 안쪽 close 를 다시 부르지 않습니다. 그 대가로, 닫는 도중 취소되면
        # 세션이 정리되지 않은 채 남습니다(별도 이슈).
        if self._closed:
            return
        self._closed = True
        await self._session.close()
