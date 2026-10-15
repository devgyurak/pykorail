"""``AsyncNetFunnelHelper`` 의 동시 호출·중간 취소 안전성.

``tests/_async/test_netfunnel.py`` 와 달리 이 파일은 **손으로 씁니다.** 대기 중에
끼어든 다른 호출과 중간 취소를 ``asyncio`` 프리미티브(``Event`` · ``Task``)로
재현하기 때문입니다 — 생성기에 실리면 그대로 동기판에 복사되어 흔적 검사
(``scripts/unasync.py`` 의 ``\\basyncio\\b``)에 걸립니다.

동기판에는 이 위험이 없습니다(실행이 한 줄기라 대기 중에 다른 호출이 끼어들지
않습니다). 회귀는 ``run()`` 이 통과를 확인하기 전에 공유 캐시 ``self._cached_key`` 를
채우면서 생깁니다 — 대기 중에 들어온 호출이 아직 게이트를 통과하지 않은 키를 받거나,
취소된 실행이 그 키를 캐시에 남깁니다.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from pykorail._async.netfunnel import AsyncNetFunnelHelper

WAIT_K1 = "201:key=K1&nwait=7"
PASS_K2 = "200:key=K2&nwait=0"
COMPLETE_K2 = "200:key=K2"
PASS_K1 = "200:key=K1&nwait=0"
COMPLETE_K1 = "200:key=K1"


class FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeSession:
    """스크립트를 순서대로 돌려주는 세션."""

    def __init__(self, script: list[str]) -> None:
        self.headers: dict[str, str] = {}
        self.script = list(script)
        self.calls: list[dict[str, Any]] = []

    async def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return FakeResponse(self.script.pop(0))

    def opcodes(self) -> list[str]:
        return [call["params"]["opcode"] for call in self.calls]


class GatedSleep:
    """``asyncio.sleep`` 대역 — 게이트가 열릴 때까지 대기를 붙잡아 둡니다."""

    def __init__(self, gate: asyncio.Event) -> None:
        self.waits = 0
        self._gate = gate

    async def __call__(self, _seconds: float) -> None:
        self.waits += 1
        await self._gate.wait()


@pytest.fixture
def make_helper(monkeypatch: pytest.MonkeyPatch):
    def factory(script: list[str]) -> tuple[AsyncNetFunnelHelper, FakeSession]:
        session = FakeSession(script)
        monkeypatch.setattr("pykorail._async.netfunnel.create_async_session", lambda headers: session)
        return AsyncNetFunnelHelper(), session

    return factory


class TestConcurrentCallers:
    async def test_a_queued_caller_does_not_lend_an_unfinished_ticket(self, make_helper, monkeypatch) -> None:
        # given
        real_sleep = asyncio.sleep
        gate = asyncio.Event()
        sleeper = GatedSleep(gate)
        monkeypatch.setattr("pykorail._async.netfunnel.asyncio.sleep", sleeper)
        helper, session = make_helper([WAIT_K1, PASS_K2, COMPLETE_K2, PASS_K1, COMPLETE_K1])

        # when
        queued = asyncio.ensure_future(helper.run())
        await real_sleep(0)
        other = await helper.run()
        gate.set()
        queued_ticket = await queued

        # then
        assert sleeper.waits == 1, "첫 호출이 대기 중이어야 시나리오가 성립합니다"
        assert other == "K2", "대기 중인 호출의 미완성 키를 빌려 오면 안 됩니다"
        assert queued_ticket == "K1"
        assert session.opcodes().count("5004") == 2, "두 호출이 각자 게이트를 통과해야 합니다"


class TestCancellation:
    async def test_a_cancelled_caller_caches_nothing(self, make_helper) -> None:
        # given
        helper, session = make_helper([WAIT_K1, PASS_K1, COMPLETE_K1])

        # when
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(helper.run(), timeout=0.05)

        # then
        assert helper._cached_key is None, "통과하지 못한 키를 캐시에 남기면 안 됩니다"
        assert helper._last_fetch_time == 0.0
        assert session.opcodes() == ["5101"], "대기 중에 끊겼으니 완료(5004)는 나가지 않습니다"
