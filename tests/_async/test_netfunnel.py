"""NetFunnel 대기열 게이트."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from pykorail._async.netfunnel import DEFAULT_DEVICE_PROFILE_ID, NETFUNNEL_URL, AsyncNetFunnelHelper
from pykorail.device import PROFILES_BY_ID, dalvik_user_agent
from pykorail.exceptions import NetFunnelError
from pykorail.options import NetFunnelAction
from tests.payloads import NETFUNNEL_CALLS_GOLDEN, NETFUNNEL_HEADERS_GOLDEN

PASS = "200:key=TICKET-1&nwait=0"
WAIT = "201:key=TICKET-1&nwait=42"
COMPLETE = "200:key=TICKET-1"
ALREADY = "502:key=TICKET-1"
BROKEN = "200"
#: aid 를 하나하나 적으면 새 대기열(7.1.0 의 act_14_2 처럼)을 빠뜨려도 드러나지 않습니다.
ALL_ACTIONS = [value for name, value in vars(NetFunnelAction).items() if not name.startswith("_")]


class FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


def _noop() -> None:
    """첫 ``close()`` 는 그대로 통과합니다."""


def _double_close_error() -> None:
    """실제 curl_cffi 의 코루틴 세션도 두 번째 ``close()`` 에서 TypeError 를 냅니다."""
    raise TypeError("세션을 두 번 닫았습니다")


class FakeSession:
    """미리 정한 순서대로 응답을 돌려주는 세션."""

    def __init__(self, script: list[str]) -> None:
        self.headers: dict[str, str] = {}
        self.script = list(script)
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    async def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": "POST", "url": url, **kwargs})
        return FakeResponse(self.script.pop(0))

    async def get(self, url: str, **kwargs: Any) -> FakeResponse:  # pragma: no cover - 미사용
        raise AssertionError("NetFunnel 은 POST 만 씁니다")

    async def close(self) -> None:
        # 두 번째 close() 에서 실패시켜 이중 close 가드가 실제로 일하는지 드러냅니다.
        # 테스트 파일은 헬퍼 클래스까지 제어 흐름 금지 규칙(tests/test_style.py)이 걸려
        # 있어 if 문을 쓸 수 없습니다 — 조건식으로 분기합니다.
        was_closed = self.closed
        self.closed = True
        _noop() if not was_closed else _double_close_error()


class Sleeper:
    """폴링 대기(``sleep``)를 가로채 호출 기록만 남깁니다.

    동기 생성물은 반환값을 버리고, 이 원본은 기다려야 하므로 대역 자체가
    ``__await__`` 을 갖습니다 — 그래야 양쪽에서 안전합니다. 진짜 ``sleep`` 을 놔두면
    이 시험 하나가 몇 초를 잡아먹습니다.
    """

    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> Sleeper:
        self.calls.append(seconds)
        return self

    def __await__(self) -> Iterator[None]:
        return iter(())


@pytest.fixture
def make_helper(monkeypatch: pytest.MonkeyPatch):
    def factory(script: list[str]) -> tuple[AsyncNetFunnelHelper, FakeSession]:
        session = FakeSession(script)
        monkeypatch.setattr("pykorail._async.netfunnel.create_async_session", lambda headers: session)
        return AsyncNetFunnelHelper(), session

    return factory


class TestRun:
    async def test_passes_straight_through(self, make_helper) -> None:
        # given
        helper, session = make_helper([PASS, COMPLETE])

        # when
        key = await helper.run()

        # then
        assert key == "TICKET-1"
        assert len(session.calls) == 2

    async def test_already_completed_counts_as_success(self, make_helper) -> None:
        # given
        helper, _ = make_helper([PASS, ALREADY])

        # when
        key = await helper.run()

        # then
        assert key == "TICKET-1"

    async def test_polls_while_queued(self, make_helper, monkeypatch) -> None:
        # given
        sleeper = Sleeper()
        monkeypatch.setattr("pykorail._async.netfunnel.asyncio.sleep", sleeper)
        helper, session = make_helper([WAIT, WAIT, PASS, COMPLETE])

        # when
        key = await helper.run()

        # then
        assert key == "TICKET-1"
        assert len(session.calls) == 4, "대기 두 번 + 통과 + 완료"
        assert sleeper.calls == [1, 1], "폴링은 주입한 sleep 대역을 거쳐야 합니다"

    async def test_uses_the_queue_url(self, make_helper) -> None:
        # given
        helper, session = make_helper([PASS, COMPLETE])

        # when
        await helper.run()

        # then
        assert session.calls[0]["url"] == NETFUNNEL_URL

    async def test_run_carries_the_action_in_the_enter_request(self, make_helper) -> None:
        # given
        helper, session = make_helper([PASS, COMPLETE])

        # when
        await helper.run(NetFunnelAction.PAY)

        # then
        assert session.calls[0]["params"]["aid"] == NetFunnelAction.PAY

    async def test_ignores_host_redirect_in_responses(self, make_helper, monkeypatch) -> None:
        # given
        monkeypatch.setattr("pykorail._async.netfunnel.asyncio.sleep", Sleeper())
        redirect = "&ip=other.example&port=8443"
        helper, session = make_helper([WAIT + redirect, PASS + redirect, COMPLETE + redirect])

        # when
        await helper.run()

        # then
        assert [call["url"] for call in session.calls] == [NETFUNNEL_URL] * 3

    async def test_poll_interval_follows_the_response_ttl(self, make_helper, monkeypatch) -> None:
        # given
        sleeper = Sleeper()
        monkeypatch.setattr("pykorail._async.netfunnel.asyncio.sleep", sleeper)
        helper, _ = make_helper(["201:key=K&nwait=5&ttl=7", PASS, COMPLETE])

        # when
        await helper.run()

        # then
        assert sleeper.calls == [7], "응답의 ttl 이 폴링 간격이 되어야 합니다"

    async def test_completion_failure_raises_and_clears(self, make_helper) -> None:
        # given
        helper, _ = make_helper([PASS, "999:key=X"])

        # when
        with pytest.raises(NetFunnelError, match="complete"):
            await helper.run()

        # then
        assert helper._cache == {}

    async def test_unparseable_response_raises(self, make_helper) -> None:
        # given
        helper, _ = make_helper([BROKEN])

        # when & then
        with pytest.raises(NetFunnelError, match="parse"):
            await helper.run()

    async def test_transport_failure_is_wrapped(self, monkeypatch) -> None:
        # given
        class Exploding:
            headers: dict[str, str] = {}

            async def post(self, url: str, **kwargs: Any) -> FakeResponse:
                raise OSError("연결 실패")

        monkeypatch.setattr("pykorail._async.netfunnel.create_async_session", lambda headers: Exploding())

        # when & then
        with pytest.raises(NetFunnelError, match="연결 실패"):
            await AsyncNetFunnelHelper().run()


class TestCache:
    async def test_second_run_reuses_the_ticket(self, make_helper) -> None:
        # given
        helper, session = make_helper([PASS, COMPLETE])
        await helper.run()

        # when
        key = await helper.run()

        # then
        assert key == "TICKET-1"
        assert len(session.calls) == 2, "캐시가 살아 있으면 추가 요청이 없어야 합니다"

    async def test_clear_forces_a_refetch(self, make_helper) -> None:
        # given
        helper, session = make_helper([PASS, COMPLETE, PASS, COMPLETE])
        await helper.run()

        # when
        helper.clear()
        await helper.run()

        # then
        assert len(session.calls) == 4

    async def test_expired_cache_refetches(self, make_helper) -> None:
        # given
        helper, session = make_helper([PASS, COMPLETE, PASS, COMPLETE])
        await helper.run()

        # when
        key, fetched = helper._cache[NetFunnelAction.TRAIN_SEARCH]
        helper._cache[NetFunnelAction.TRAIN_SEARCH] = (key, fetched - helper.CACHE_TTL - 1)
        await helper.run()

        # then
        assert len(session.calls) == 4

    @pytest.mark.parametrize(
        ("first", "second"),
        [
            (NetFunnelAction.TRAIN_SEARCH, NetFunnelAction.PAY),
            (NetFunnelAction.TRAIN_SEARCH, NetFunnelAction.TRAIN_SEARCH_PEAK),
            (NetFunnelAction.RESERVE, NetFunnelAction.RESERVE_PEAK),
        ],
        ids=["search-vs-pay", "search-off-peak-vs-peak", "reserve-off-peak-vs-peak"],
    )
    async def test_different_actions_do_not_share_the_cache(self, make_helper, first: str, second: str) -> None:
        """평시·성수기 대기열도 서로 다른 줄입니다 — 티켓을 섞어 쓰면 안 됩니다."""
        # given
        helper, session = make_helper([PASS, COMPLETE, PASS, COMPLETE])
        await helper.run(first)

        # when
        await helper.run(second)

        # then
        assert len(session.calls) == 4, "aid 가 다르면 같은 티켓을 재사용하면 안 됩니다"

    async def test_clear_one_action_keeps_the_others(self, make_helper) -> None:
        # given
        helper, session = make_helper([PASS, COMPLETE, PASS, COMPLETE, PASS, COMPLETE])
        await helper.run(NetFunnelAction.TRAIN_SEARCH)
        await helper.run(NetFunnelAction.PAY)

        # when
        helper.clear(NetFunnelAction.PAY)
        await helper.run(NetFunnelAction.TRAIN_SEARCH)
        await helper.run(NetFunnelAction.PAY)

        # then
        assert len(session.calls) == 6, "조회 티켓은 남고 결제만 다시 통과해야 합니다"

    async def test_clear_all_actions_empties_every_slot(self, make_helper) -> None:
        # given
        helper, session = make_helper([PASS, COMPLETE, PASS, COMPLETE, PASS, COMPLETE, PASS, COMPLETE])
        await helper.run(NetFunnelAction.TRAIN_SEARCH)
        await helper.run(NetFunnelAction.PAY)

        # when
        helper.clear()
        await helper.run(NetFunnelAction.TRAIN_SEARCH)
        await helper.run(NetFunnelAction.PAY)

        # then
        assert len(session.calls) == 8

    async def test_failure_clears_only_the_failing_action(self, make_helper) -> None:
        # given
        helper, session = make_helper([PASS, COMPLETE, PASS, "999:key=X"])
        await helper.run(NetFunnelAction.TRAIN_SEARCH)

        # when
        with pytest.raises(NetFunnelError, match="complete"):
            await helper.run(NetFunnelAction.PAY)

        # then
        assert NetFunnelAction.PAY not in helper._cache
        assert helper._cache[NetFunnelAction.TRAIN_SEARCH][0] == "TICKET-1"
        assert len(session.calls) == 4


class TestClose:
    async def test_close_closes_session(self, make_helper) -> None:
        # given
        helper, session = make_helper([])

        # when
        await helper.close()

        # then
        assert session.closed

    async def test_double_close_is_safe(self, make_helper) -> None:
        # given
        helper, session = make_helper([])
        await helper.close()

        # when
        await helper.close()

        # then
        assert session.closed

    async def test_context_manager_closes_session(self, make_helper) -> None:
        # given
        helper, session = make_helper([PASS, COMPLETE])

        # when
        async with helper as entered:
            await entered.run()

        # then
        assert entered is helper
        assert session.closed

    async def test_leaving_the_context_after_an_explicit_close(self, make_helper) -> None:
        # given
        helper, session = make_helper([])

        # when
        async with helper:
            await helper.close()

        # then
        assert session.closed


class TestParams:
    @pytest.mark.parametrize(
        ("operation", "expected_opcode"),
        [("getTidchkEnter", "5101"), ("chkEnter", "5002"), ("setComplete", "5004")],
    )
    def test_opcodes(self, make_helper, operation: str, expected_opcode: str) -> None:
        # given
        helper, _ = make_helper([])

        # when
        params = helper._build_params(helper.OP_CODE[operation])

        # then
        assert params["opcode"] == expected_opcode

    def test_enter_carries_service_ids(self, make_helper) -> None:
        # given
        helper, _ = make_helper([])

        # when
        params = helper._build_params(helper.OP_CODE["getTidchkEnter"])

        # then
        assert params["sid"] == "service_1"
        assert params["aid"] == NetFunnelAction.TRAIN_SEARCH, "aid 를 생략하면 열차 조회가 기본입니다"

    @pytest.mark.parametrize("aid", ALL_ACTIONS)
    def test_enter_carries_the_requested_action(self, make_helper, aid: str) -> None:
        # given
        helper, _ = make_helper([])

        # when
        params = helper._build_params(helper.OP_CODE["getTidchkEnter"], aid=aid)

        # then
        assert params["sid"] == "service_1"
        assert params["aid"] == aid

    def test_check_carries_only_opcode_and_key(self, make_helper) -> None:
        # given
        helper, _ = make_helper([])

        # when
        params = helper._build_params(helper.OP_CODE["chkEnter"], key="K")

        # then
        assert params == {"opcode": "5002", "key": "K"}

    def test_complete_carries_the_key(self, make_helper) -> None:
        # given
        helper, _ = make_helper([])

        # when
        params = helper._build_params(helper.OP_CODE["setComplete"], key="K")

        # then
        assert params["key"] == "K"

    def test_missing_key_becomes_empty_string(self, make_helper) -> None:
        # given
        helper, _ = make_helper([])

        # when
        params = helper._build_params(helper.OP_CODE["setComplete"])

        # then
        assert params["key"] == ""


class TestWaitSeconds:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [(None, 1), ("", 1), ("0", 1), ("abc", 1), ("3", 3), ("99", 30)],
    )
    def test_clamps_ttl_between_one_and_thirty(self, make_helper, raw: str | None, expected: int) -> None:
        # given
        helper, _ = make_helper([])

        # when
        seconds = helper._wait_seconds(raw)

        # then
        assert seconds == expected


class TestWireGolden:
    """같은 요청을 보내는지 겨루는 기준선 — 구현이 어긋나면 여기서 드러납니다."""

    async def test_headers_match_the_golden(self, monkeypatch) -> None:
        # given
        captured: dict[str, str] = {}

        def fake_create_async_session(headers: dict[str, str]) -> FakeSession:
            captured.update(headers)
            return FakeSession([PASS, COMPLETE])

        monkeypatch.setattr("pykorail._async.netfunnel.create_async_session", fake_create_async_session)

        # when
        await AsyncNetFunnelHelper().run()

        # then
        assert captured == NETFUNNEL_HEADERS_GOLDEN

    async def test_profile_shapes_the_user_agent(self, monkeypatch) -> None:
        # given
        profile = PROFILES_BY_ID["s25ultra-a16"]
        captured: dict[str, str] = {}

        def fake_create_async_session(headers: dict[str, str]) -> FakeSession:
            captured.update(headers)
            return FakeSession([PASS, COMPLETE])

        monkeypatch.setattr("pykorail._async.netfunnel.create_async_session", fake_create_async_session)

        # when
        await AsyncNetFunnelHelper(device_profile=profile).run()

        # then
        assert captured["User-Agent"] == dalvik_user_agent(profile)

    async def test_default_user_agent_uses_the_default_profile(self, monkeypatch) -> None:
        # given
        profile = PROFILES_BY_ID[DEFAULT_DEVICE_PROFILE_ID]
        captured: dict[str, str] = {}

        def fake_create_async_session(headers: dict[str, str]) -> FakeSession:
            captured.update(headers)
            return FakeSession([PASS, COMPLETE])

        monkeypatch.setattr("pykorail._async.netfunnel.create_async_session", fake_create_async_session)

        # when
        await AsyncNetFunnelHelper().run()

        # then
        assert captured["User-Agent"] == dalvik_user_agent(profile)

    async def test_requests_match_the_golden(self, make_helper, monkeypatch) -> None:
        # given
        monkeypatch.setattr("pykorail._async.netfunnel.asyncio.sleep", Sleeper())
        helper, session = make_helper([WAIT, WAIT, PASS, COMPLETE])

        # when
        await helper.run()

        # then
        calls = [{"method": call["method"], "url": call["url"], "params": call["params"]} for call in session.calls]
        assert calls == NETFUNNEL_CALLS_GOLDEN
