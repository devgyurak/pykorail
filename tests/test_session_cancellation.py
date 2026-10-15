"""``AsyncIdempotentSession.close()`` 가 도중에 취소돼도 정리를 끝내는지 확인합니다.

``tests/_async/test_session.py`` 와 달리 이 파일은 **손으로 씁니다.** 취소가 끼어든
``close()`` 를 ``asyncio`` 프리미티브(``Event`` · ``Task``)로 재현하기 때문입니다 —
생성기에 실리면 그대로 동기판에 복사되어 흔적 검사(``scripts/unasync.py`` 의
``\\basyncio\\b``)에 걸립니다. 동기판에는 취소가 없어 이 위험이 없습니다.

``curl_cffi`` 처럼 취소를 삼키는 안쪽 세션(``SwallowingSession``)까지 재현합니다. 래퍼가
``shield`` 로 감싸지 않으면 그 삼킴이 그대로 호출자에게 새어 나가 타임아웃이 만료를
감지하지 못하므로, 이 파일이 그 회귀를 잡습니다.
"""

from __future__ import annotations

import asyncio

# ``MutableMapping`` 은 주석에만 쓰지만 ``if TYPE_CHECKING`` 로 감쌀 수 없습니다 — 테스트
# 파일은 제어 흐름 금지 검사(tests/test_style.py)가 **파일 전체**를 훑기 때문입니다.
from collections.abc import MutableMapping
from contextlib import suppress
from typing import Any

import pytest

from pykorail._async.session import AsyncIdempotentSession


class FakeResponse:
    """``status_code`` · ``text`` 만 갖는 최소 응답."""

    def __init__(self) -> None:
        self.status_code = 200
        self.text = "ok"


class GatedSession:
    """``close()`` 가 ``release`` 를 기다렸다가 끝나는 세션 — 취소 창을 엽니다."""

    def __init__(self) -> None:
        self.headers: MutableMapping[str, str] = {"User-Agent": "pykorail-test"}
        self.closes = 0
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.finished = asyncio.Event()

    async def get(self, url: str, **kwargs: Any) -> FakeResponse:
        return FakeResponse()

    async def post(self, url: str, **kwargs: Any) -> FakeResponse:
        return FakeResponse()

    async def close(self) -> None:
        self.closes += 1
        self.started.set()
        await self.release.wait()
        self.finished.set()


class SwallowingSession(GatedSession):
    """``curl_cffi`` 처럼 대기 중 들어온 취소를 삼키는 세션.

    실제 ``AsyncCurl.close()`` 는 정리 대기를 ``suppress`` 로 감싸므로, 래퍼가 막아
    주지 않으면 호출자의 타임아웃이 만료를 감지하지 못합니다.
    """

    async def close(self) -> None:
        self.closes += 1
        self.started.set()
        with suppress(asyncio.CancelledError):
            await self.release.wait()
        self.finished.set()


async def _start_cancelled_close(session: AsyncIdempotentSession, inner: GatedSession) -> asyncio.Task[None]:
    """``close()`` 를 띄우고 안쪽 정리가 시작된 뒤 취소합니다. 취소 창을 결정론적으로 엽니다."""
    closing = asyncio.create_task(session.close())
    await inner.started.wait()
    closing.cancel()
    inner.release.set()
    return closing


class TestCancellation:
    async def test_cancelled_close_still_finishes_inner_cleanup(self) -> None:
        # given
        inner = GatedSession()
        session = AsyncIdempotentSession(inner)

        # when
        closing = await _start_cancelled_close(session, inner)
        with pytest.raises(asyncio.CancelledError):
            await closing

        # then
        await asyncio.wait_for(inner.finished.wait(), timeout=1)
        assert inner.closes == 1
        assert inner.finished.is_set(), "호출자가 취소돼도 안쪽 정리는 끝까지 돌아야 합니다"

    async def test_cancelled_close_propagates_cancellation(self) -> None:
        # given
        inner = GatedSession()
        session = AsyncIdempotentSession(inner)

        # when
        closing = await _start_cancelled_close(session, inner)
        with pytest.raises(asyncio.CancelledError):
            await closing

        # then
        assert closing.cancelled(), "취소는 shield 가 삼키지 않고 호출자에게 올라가야 합니다"

    async def test_second_close_after_cancel_does_not_reach_the_inner_session(self) -> None:
        # given
        inner = GatedSession()
        session = AsyncIdempotentSession(inner)
        closing = await _start_cancelled_close(session, inner)
        with pytest.raises(asyncio.CancelledError):
            await closing
        await asyncio.wait_for(inner.finished.wait(), timeout=1)

        # when
        await session.close()

        # then
        assert inner.closes == 1, "취소가 가드를 무력화해 안쪽 close 를 다시 부르면 안 됩니다"

    async def test_timeout_during_close_raises_timeout_error(self) -> None:
        # given
        inner = SwallowingSession()
        session = AsyncIdempotentSession(inner)

        # when
        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.05):
                await session.close()
        # shield 로 살아남은 안쪽 정리를 끝까지 돌려 태스크를 정리합니다.
        inner.release.set()
        await asyncio.wait_for(inner.finished.wait(), timeout=1)

        # then
        assert inner.closes == 1
        assert inner.finished.is_set()
