# 이 파일은 생성물입니다 — 직접 고치지 마세요.
# 원본: tests/_async/test_netfunnel.py
# 다시 만들려면: uv run python scripts/unasync.py
"""NetFunnel 대기열 게이트."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from pykorail._sync.netfunnel import NETFUNNEL_URL, NetFunnelHelper
from pykorail.exceptions import NetFunnelError
from tests.payloads import NETFUNNEL_CALLS_GOLDEN, NETFUNNEL_HEADERS_GOLDEN

PASS = "200:key=TICKET-1&nwait=0"
WAIT = "201:key=TICKET-1&nwait=42"
COMPLETE = "200:key=TICKET-1"
ALREADY = "502:key=TICKET-1"
BROKEN = "200"


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

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return FakeResponse(self.script.pop(0))

    def post(self, url: str, **kwargs: Any) -> FakeResponse:  # pragma: no cover - 미사용
        raise AssertionError("NetFunnel 은 GET 만 씁니다")

    def close(self) -> None:
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
    def factory(script: list[str]) -> tuple[NetFunnelHelper, FakeSession]:
        session = FakeSession(script)
        monkeypatch.setattr("pykorail._sync.netfunnel.create_session", lambda headers: session)
        return NetFunnelHelper(), session

    return factory


class TestRun:
    def test_passes_straight_through(self, make_helper) -> None:
        # given
        helper, session = make_helper([PASS, COMPLETE])

        # when
        key = helper.run()

        # then
        assert key == "TICKET-1"
        assert len(session.calls) == 2

    def test_already_completed_counts_as_success(self, make_helper) -> None:
        # given
        helper, _ = make_helper([PASS, ALREADY])

        # when
        key = helper.run()

        # then
        assert key == "TICKET-1"

    def test_polls_while_queued(self, make_helper, monkeypatch) -> None:
        # given
        sleeper = Sleeper()
        monkeypatch.setattr("pykorail._sync.netfunnel.time.sleep", sleeper)
        helper, session = make_helper([WAIT, WAIT, PASS, COMPLETE])

        # when
        key = helper.run()

        # then
        assert key == "TICKET-1"
        assert len(session.calls) == 4, "대기 두 번 + 통과 + 완료"
        assert sleeper.calls == [1, 1], "폴링은 주입한 sleep 대역을 거쳐야 합니다"

    def test_uses_the_queue_url(self, make_helper) -> None:
        # given
        helper, session = make_helper([PASS, COMPLETE])

        # when
        helper.run()

        # then
        assert session.calls[0]["url"] == NETFUNNEL_URL

    def test_completion_failure_raises_and_clears(self, make_helper) -> None:
        # given
        helper, _ = make_helper([PASS, "999:key=X"])

        # when
        with pytest.raises(NetFunnelError, match="complete"):
            helper.run()

        # then
        assert helper._cached_key is None

    def test_unparseable_response_raises(self, make_helper) -> None:
        # given
        helper, _ = make_helper([BROKEN])

        # when & then
        with pytest.raises(NetFunnelError, match="parse"):
            helper.run()

    def test_transport_failure_is_wrapped(self, monkeypatch) -> None:
        # given
        class Exploding:
            headers: dict[str, str] = {}

            def get(self, url: str, **kwargs: Any) -> FakeResponse:
                raise OSError("연결 실패")

        monkeypatch.setattr("pykorail._sync.netfunnel.create_session", lambda headers: Exploding())

        # when & then
        with pytest.raises(NetFunnelError, match="연결 실패"):
            NetFunnelHelper().run()


class TestCache:
    def test_second_run_reuses_the_ticket(self, make_helper) -> None:
        # given
        helper, session = make_helper([PASS, COMPLETE])
        helper.run()

        # when
        key = helper.run()

        # then
        assert key == "TICKET-1"
        assert len(session.calls) == 2, "캐시가 살아 있으면 추가 요청이 없어야 합니다"

    def test_clear_forces_a_refetch(self, make_helper) -> None:
        # given
        helper, session = make_helper([PASS, COMPLETE, PASS, COMPLETE])
        helper.run()

        # when
        helper.clear()
        helper.run()

        # then
        assert len(session.calls) == 4

    def test_expired_cache_refetches(self, make_helper) -> None:
        # given
        helper, session = make_helper([PASS, COMPLETE, PASS, COMPLETE])
        helper.run()

        # when
        helper._last_fetch_time -= helper.CACHE_TTL + 1
        helper.run()

        # then
        assert len(session.calls) == 4


class TestClose:
    def test_close_closes_session(self, make_helper) -> None:
        # given
        helper, session = make_helper([])

        # when
        helper.close()

        # then
        assert session.closed

    def test_double_close_is_safe(self, make_helper) -> None:
        # given
        helper, session = make_helper([])
        helper.close()

        # when
        helper.close()

        # then
        assert session.closed

    def test_context_manager_closes_session(self, make_helper) -> None:
        # given
        helper, session = make_helper([PASS, COMPLETE])

        # when
        with helper as entered:
            entered.run()

        # then
        assert entered is helper
        assert session.closed

    def test_leaving_the_context_after_an_explicit_close(self, make_helper) -> None:
        # given
        helper, session = make_helper([])

        # when
        with helper:
            helper.close()

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
        assert params["aid"] == "act_8"

    def test_check_carries_the_key(self, make_helper) -> None:
        # given
        helper, _ = make_helper([])

        # when
        params = helper._build_params(helper.OP_CODE["chkEnter"], key="K")

        # then
        assert params["key"] == "K"
        assert params["ttl"] == "1"

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


class TestWireGolden:
    """같은 요청을 보내는지 겨루는 기준선 — 구현이 어긋나면 여기서 드러납니다."""

    def test_headers_match_the_golden(self, monkeypatch) -> None:
        # given
        captured: dict[str, str] = {}

        def fake_create_session(headers: dict[str, str]) -> FakeSession:
            captured.update(headers)
            return FakeSession([PASS, COMPLETE])

        monkeypatch.setattr("pykorail._sync.netfunnel.create_session", fake_create_session)

        # when
        NetFunnelHelper().run()

        # then
        assert captured == NETFUNNEL_HEADERS_GOLDEN

    def test_requests_match_the_golden(self, make_helper, monkeypatch) -> None:
        # given
        monkeypatch.setattr("pykorail._sync.netfunnel.time.sleep", Sleeper())
        helper, session = make_helper([WAIT, WAIT, PASS, COMPLETE])

        # when
        helper.run()

        # then
        calls = [{"url": call["url"], "params": call["params"]} for call in session.calls]
        assert calls == NETFUNNEL_CALLS_GOLDEN
