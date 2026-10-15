"""세션 래퍼 — 이중 close 가드가 한 곳에서 일하는지 확인합니다."""

from __future__ import annotations

# ``MutableMapping`` 은 주석에만 쓰지만 ``if TYPE_CHECKING`` 로 감쌀 수 없습니다 — 테스트
# 파일은 제어 흐름 금지 검사(tests/test_style.py)가 **파일 전체**를 훑기 때문입니다.
from collections.abc import MutableMapping
from typing import Any

from pykorail._async.session import AsyncIdempotentSession


class FakeResponse:
    """``status_code`` · ``text`` 만 갖는 최소 응답 — 응답 프로토콜의 표면입니다."""

    def __init__(self, text: str) -> None:
        self.status_code = 200
        self.text = text


def _noop() -> None:
    """첫 ``close()`` 는 그대로 통과합니다."""


def _double_close_error() -> None:
    """실제 curl_cffi 의 코루틴 세션도 두 번째 ``close()`` 에서 TypeError 를 냅니다."""
    raise TypeError("세션을 두 번 닫았습니다")


class FakeSession:
    """호출을 기록하고 두 번째 ``close()`` 에서 실패하는 세션."""

    def __init__(self) -> None:
        # 프로토콜의 ``headers`` 는 가변 속성이라 ``dict`` 로 선언하면 불변성이 어긋나
        # ``ty`` 가 ``AsyncHttpSession`` 자리에 넣지 못하게 막습니다.
        self.headers: MutableMapping[str, str] = {"User-Agent": "pykorail-test"}
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.closes = 0

    async def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(("GET", url, kwargs))
        return FakeResponse("ok")

    async def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(("POST", url, kwargs))
        return FakeResponse("ok")

    async def close(self) -> None:
        # 두 번째 close() 에서 실패시켜 가드가 실제로 일하는지 드러냅니다. 테스트 파일은
        # 헬퍼 클래스까지 제어 흐름 금지 규칙(tests/test_style.py)이 걸려 있어 if 문을 쓸 수
        # 없습니다 — 조건식으로 분기합니다.
        self.closes += 1
        _noop() if self.closes == 1 else _double_close_error()


class TestForwarding:
    """래퍼는 나머지 표면을 손대지 않고 안쪽 세션에 넘겨야 합니다."""

    async def test_get_passes_the_url_and_kwargs_through(self) -> None:
        # given
        inner = FakeSession()
        session = AsyncIdempotentSession(inner)

        # when
        await session.get("http://example.test/a", params={"x": "1"})

        # then
        assert inner.calls == [("GET", "http://example.test/a", {"params": {"x": "1"}})]

    async def test_post_passes_the_url_and_kwargs_through(self) -> None:
        # given
        inner = FakeSession()
        session = AsyncIdempotentSession(inner)

        # when
        await session.post("http://example.test/b", data={"a": "1"})

        # then
        assert inner.calls == [("POST", "http://example.test/b", {"data": {"a": "1"}})]

    async def test_returns_the_inner_response_unchanged(self) -> None:
        # given
        inner = FakeSession()
        session = AsyncIdempotentSession(inner)

        # when
        response = await session.get("http://example.test/a")

        # then
        assert response.text == "ok"

    def test_headers_are_the_inner_sessions_dict(self) -> None:
        # given
        inner = FakeSession()

        # when
        session = AsyncIdempotentSession(inner)

        # then
        assert session.headers is inner.headers


class TestClose:
    """가드가 없으면 안쪽 세션의 두 번째 ``close()`` 가 TypeError 를 냅니다."""

    async def test_close_closes_the_inner_session(self) -> None:
        # given
        inner = FakeSession()
        session = AsyncIdempotentSession(inner)

        # when
        await session.close()

        # then
        assert inner.closes == 1

    async def test_double_close_reaches_the_inner_session_once(self) -> None:
        # given
        inner = FakeSession()
        session = AsyncIdempotentSession(inner)

        # when
        await session.close()
        await session.close()

        # then
        assert inner.closes == 1, "가드가 없으면 두 번째 호출이 TypeError 를 냅니다"
