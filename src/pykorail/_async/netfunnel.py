"""NetFunnel 대기열 게이트 (``nf.letskorail.com``).

접속 폭주 때 코레일 앞단에 서는 대기열입니다. 통과 티켓(key)을 받아 두면
잠깐 재사용할 수 있어 캐시합니다.

**클라이언트는 이 모듈을 쓰지 않습니다 — 의도된 것입니다.** 대기열은 코레일 웹
프런트가 통과하는 관문이고, 이 패키지가 쓰는 스마트 앱 엔드포인트
(``smart.letskorail.com``)는 대기열 뒤에 있지 않습니다. 명절 예매처럼 앱 경로에도
대기열이 붙는 상황을 만나면 직접 꺼내 쓸 수 있도록 공개 유틸리티로 남겨 둡니다::

    from pykorail import AsyncNetFunnelHelper

    async with AsyncNetFunnelHelper() as nf:
        key = await nf.run()

:class:`~pykorail.AsyncKorail` 에 자동으로 엮지 않은 이유는, 필요 없는 상황에서
매 요청마다 외부 게이트를 때리는 비용과 실패 지점이 생기기 때문입니다.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, ClassVar, Final

from pykorail.exceptions import NetFunnelError
from pykorail.transport import create_async_session

if TYPE_CHECKING:
    from types import TracebackType
    from typing import Self

#: 로거 이름은 ``__name__`` 대신 문자열로 고정합니다. ``scripts/unasync.py`` 가 이
#: 리터럴만 동기 이름으로 바꿔, 예전 ``pykorail.auth.netfunnel`` 핸들러가 두 모듈의
#: 로그를 함께 받습니다.
logger = logging.getLogger("pykorail.auth.netfunnel.async")

NETFUNNEL_URL: Final = "http://nf.letskorail.com/ts.wseq"

NETFUNNEL_HEADERS: Final[dict[str, str]] = {
    "Host": "nf.letskorail.com",
    "Connection": "Keep-Alive",
    "User-Agent": "Apache-HttpClient/UNAVAILABLE (java 1.4)",
}


class AsyncNetFunnelHelper:
    """대기열을 통과해 티켓(key)을 얻습니다.

    :meth:`run` 이 유일한 진입점입니다. 대기 줄이 있으면 통과할 때까지 1초 간격으로
    폴링합니다.
    """

    WAIT_STATUS_PASS: ClassVar[str] = "200"
    WAIT_STATUS_FAIL: ClassVar[str] = "201"
    ALREADY_COMPLETED: ClassVar[str] = "502"

    OP_CODE: ClassVar[dict[str, str]] = {
        "getTidchkEnter": "5101",
        "chkEnter": "5002",
        "setComplete": "5004",
    }

    #: 티켓 재사용 시간(초). 서버 만료보다 짧게 잡아 아슬아슬한 재사용을 피합니다.
    CACHE_TTL: ClassVar[float] = 50.0

    def __init__(self) -> None:
        self._session = create_async_session(NETFUNNEL_HEADERS)
        self._cached_key: str | None = None
        self._last_fetch_time = 0.0
        self._closed = False

    async def run(self) -> str | None:
        """통과 티켓을 돌려줍니다. 캐시가 살아 있으면 재사용합니다.

        키는 끝까지 지역 변수로 들고 다니고, **통과를 확인한 뒤에만** 캐시에 씁니다.
        통과 전에 공유 캐시(``self._cached_key``)를 채우면, 아직 게이트를 통과하지 않은
        키가 대기 중에 들어온 다른 호출에 새어 나가거나, 중간에 중단된 실행이 그 키를
        캐시에 남깁니다.

        Raises:
            NetFunnelError: 대기열 통과에 실패했습니다. 캐시는 비워집니다.
        """
        now = time.time()
        if self._is_cache_valid(now):
            return self._cached_key

        try:
            status, key, nwait = await self._start()

            while status == self.WAIT_STATUS_FAIL:
                logger.debug("현재 %s명 대기중", nwait)
                await asyncio.sleep(1)
                status, key, nwait = await self._check(key)

            status, _, _ = await self._complete(key)
            if status in (self.WAIT_STATUS_PASS, self.ALREADY_COMPLETED):
                self._cached_key = key
                self._last_fetch_time = now
                return key

            self.clear()
            raise NetFunnelError("Failed to complete NetFunnel")

        except NetFunnelError:
            self.clear()
            raise
        except Exception as exc:
            self.clear()
            raise NetFunnelError(str(exc)) from exc

    def clear(self) -> None:
        """캐시된 티켓을 버립니다. 연결은 그대로 둡니다 — 정리는 :meth:`close` 가 맡습니다."""
        self._cached_key = None
        self._last_fetch_time = 0.0

    # ------------------------------------------------------------- 컨텍스트 관리
    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        """연 HTTP 세션을 닫습니다. 캐시(:meth:`clear`)와는 별개입니다."""
        # close() 를 두 번 불러도 안전하게 합니다. ``async with`` 블록 안에서 직접
        # close() 를 부르면 블록을 나갈 때 __aexit__ 이 한 번 더 닫는데, curl_cffi 의
        # 코루틴 세션은 그때 TypeError 를 냅니다(동기 세션은 두 번 닫아도 괜찮습니다).
        if self._closed:
            return
        self._closed = True
        await self._session.close()

    # ------------------------------------------------------------------- 내부
    async def _start(self) -> tuple[str | None, str | None, str | None]:
        return await self._make_request("getTidchkEnter")

    async def _check(self, key: str | None) -> tuple[str | None, str | None, str | None]:
        return await self._make_request("chkEnter", key)

    async def _complete(self, key: str | None) -> tuple[str | None, str | None, str | None]:
        return await self._make_request("setComplete", key)

    async def _make_request(self, operation: str, key: str | None = None) -> tuple[str | None, str | None, str | None]:
        params = self._build_params(self.OP_CODE[operation], key)
        response = await self._session.get(NETFUNNEL_URL, params=params)
        parsed = self._parse(response.text)
        return parsed.get("status"), parsed.get("key"), parsed.get("nwait")

    def _build_params(self, opcode: str, key: str | None = None) -> dict[str, str]:
        """``key`` 는 호출자가 넘긴 값만 씁니다. 캐시를 되읽으면 다른 실행이 덮어쓴
        키나 만료된 옛 키가 응답에 실려 나갑니다.
        """
        params: dict[str, str] = {"opcode": opcode}

        if opcode in (self.OP_CODE["getTidchkEnter"], self.OP_CODE["chkEnter"]):
            params.update({"sid": "service_1", "aid": "act_8"})
            if opcode == self.OP_CODE["chkEnter"]:
                params.update({"key": key or "", "ttl": "1"})
        elif opcode == self.OP_CODE["setComplete"]:
            params["key"] = key or ""

        return params

    @staticmethod
    def _parse(response: str) -> dict[str, str]:
        status, _, params_str = response.partition(":")
        if not params_str:
            raise NetFunnelError("Failed to parse NetFunnel response")

        parsed = dict(param.split("=", 1) for param in params_str.split("&") if "=" in param)
        parsed["status"] = status
        return parsed

    def _is_cache_valid(self, now: float) -> bool:
        return bool(self._cached_key) and (now - self._last_fetch_time) < self.CACHE_TTL
