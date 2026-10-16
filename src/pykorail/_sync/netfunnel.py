# 이 파일은 생성물입니다 — 직접 고치지 마세요.
# 원본: src/pykorail/_async/netfunnel.py
# 다시 만들려면: uv run python scripts/unasync.py
"""NetFunnel 대기열 게이트 (``nf.letskorail.com``).

접속 폭주 때 코레일 앞단에 서는 대기열입니다. 통과 티켓(key)을 받아 두면
잠깐 재사용할 수 있어 동작(``aid``)별로 캐시합니다.

**클라이언트는 이 모듈을 쓰지 않습니다 — 의도된 것입니다.** 코레일톡+ 앱은 열차 조회 ·
예약 · 내 예약 조회 · 결제 전에 대기열을 통과하지만(``docs/reference.md`` 의 대응표),
지금까지 본 캡처에서 통과 키가 스마트 요청(``smart.letskorail.com``) 어디에도 실린 적이
없습니다 — 서버가 통과 여부를 검사한다는 근거가 없습니다. 명절 예매처럼 대기열이
실제로 붙는 상황을 만나면 직접 꺼내 쓸 수 있도록 공개 유틸리티로 남겨 둡니다::

    from pykorail import NetFunnelHelper, NetFunnelAction

    with NetFunnelHelper() as nf:
        key = nf.run(NetFunnelAction.PAY)  # 동작별 aid

``Korail`` 과 함께 쓸 때는 ``korail.device_profile`` 을 넘겨 같은 가상 기기로 보이게
합니다.

:class:`~pykorail.Korail` 에 자동으로 엮지 않은 이유는, 필요 없는 상황에서
매 요청마다 외부 게이트를 때리는 비용과 실패 지점이 생기기 때문입니다.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, ClassVar, Final

from pykorail._sync.session import IdempotentSession
from pykorail.device import PROFILES_BY_ID, dalvik_user_agent
from pykorail.exceptions import NetFunnelError
from pykorail.options import NetFunnelAction
from pykorail.transport import create_session

if TYPE_CHECKING:
    from types import TracebackType
    from typing import Self

    from pykorail.device import DeviceProfileLike
    from pykorail.options import NetFunnelActionCode

#: 로거 이름은 ``__name__`` 대신 문자열로 고정합니다. ``scripts/unasync.py`` 가 이
#: 리터럴만 동기 이름으로 바꿔, 예전 ``pykorail.auth.netfunnel`` 핸들러가 두 모듈의
#: 로그를 함께 받습니다.
logger = logging.getLogger("pykorail.auth.netfunnel")

NETFUNNEL_URL: Final = "https://nf.letskorail.com/ts.wseq"

#: ``device_profile`` 을 넘기지 않았을 때 쓸 카탈로그 프로파일. DynaPath 기본
#: 기기(``SM-S928N`` · Android 14)와 같은 모델 · OS 라, 앱이 쓰는 기본 UA 와 맞습니다.
DEFAULT_DEVICE_PROFILE_ID: Final = "s24ultra-a14"

#: 고정 헤더. ``Host`` 는 넣지 않습니다 — 앱도 직접 넣지 않고 클라이언트가 URL 에서
#: 붙입니다. ``Context_Type`` 의 밑줄과 ``charset=UTF-8`` 은 앱 SDK(com.netfunnel.api
#: 1.7.18)의 오타 그대로입니다. 서버가 이 헤더를 보는지는 확인하지 않았습니다.
NETFUNNEL_HEADERS: Final[dict[str, str]] = {
    "Accept-Charset": "UTF-8",
    "Context_Type": "application/x-www-form-urlencoded;charset=UTF-8",
    "Content-Type": "application/x-www-form-urlencoded",
    "Connection": "Keep-Alive",
    "Accept-Encoding": "gzip",
}


class NetFunnelHelper:
    """대기열을 통과해 티켓(key)을 얻습니다.

    :meth:`run` 이 유일한 진입점입니다. 대기 줄이 있으면 통과할 때까지 응답이 준
    ``ttl``(1–30초, 없거나 잘못되면 1초) 간격으로 폴링합니다. ``run`` 은 동작별
    ``aid``(기본값 열차 조회)를 받고, 캐시도 ``aid`` 별로 나눕니다.
    """

    WAIT_STATUS_PASS: ClassVar[str] = "200"
    WAIT_STATUS_FAIL: ClassVar[str] = "201"
    ALREADY_COMPLETED: ClassVar[str] = "502"

    OP_CODE: ClassVar[dict[str, str]] = {
        "getTidchkEnter": "5101",
        "chkEnter": "5002",
        "setComplete": "5004",
    }

    #: 폴링 간격(초)의 하한 · 상한. SDK 의 ``getTTL(max_ttl=30, min=1)`` 과 같습니다.
    MIN_WAIT_SECONDS: ClassVar[int] = 1
    MAX_WAIT_SECONDS: ClassVar[int] = 30

    #: 티켓 재사용 시간(초). 서버 만료보다 짧게 잡아 아슬아슬한 재사용을 피합니다.
    CACHE_TTL: ClassVar[float] = 50.0

    def __init__(self, device_profile: DeviceProfileLike | None = None) -> None:
        """``device_profile`` 은 UA 의 모델 · OS · 빌드를 정합니다.

        넘기지 않으면 DynaPath 기본값과 같은 카탈로그 프로파일을 씁니다. :class:`Korail`
        과 함께 쓸 때는 ``korail.device_profile`` 을 넘겨 같은 가상 기기로 보이게 합니다.
        """
        profile = device_profile if device_profile is not None else PROFILES_BY_ID[DEFAULT_DEVICE_PROFILE_ID]
        headers = {**NETFUNNEL_HEADERS, "User-Agent": dalvik_user_agent(profile)}
        self._session = IdempotentSession(create_session(headers))
        # 동작(``aid``)별 통과 티켓과 획득 시각. ``aid`` 가 다르면 다른 대기열이라
        # 티켓을 섞어 쓸 수 없어 칸을 나눕니다.
        self._cache: dict[NetFunnelActionCode, tuple[str, float]] = {}

    def run(self, aid: NetFunnelActionCode = NetFunnelAction.TRAIN_SEARCH) -> str | None:
        """``aid`` 대기열의 통과 티켓을 돌려줍니다. 그 칸의 캐시가 살아 있으면 재사용합니다.

        키는 끝까지 지역 변수로 들고 다니고, **통과를 확인한 뒤에만** 캐시에 씁니다.
        통과 전에 공유 캐시(``self._cache``)를 채우면, 아직 게이트를 통과하지 않은
        키가 대기 중에 들어온 다른 호출에 새어 나가거나, 중간에 중단된 실행이 그 키를
        캐시에 남깁니다.

        ``aid`` 는 :data:`~pykorail.options.NetFunnelActionCode` 로 정적으로 검사할 뿐
        런타임 검증은 하지 않습니다.

        Raises:
            NetFunnelError: 대기열 통과에 실패했습니다. 실패한 ``aid`` 칸만 비웁니다.
        """
        now = time.time()
        cached = self._cached_ticket(aid, now)
        if cached is not None:
            return cached

        try:
            status, key, nwait, ttl = self._start(aid)

            while status == self.WAIT_STATUS_FAIL:
                logger.debug("현재 %s명 대기중", nwait)
                time.sleep(self._wait_seconds(ttl))
                status, key, nwait, ttl = self._check(key)

            status, _, _, _ = self._complete(key)
            if status in (self.WAIT_STATUS_PASS, self.ALREADY_COMPLETED):
                self._cache[aid] = (key or "", now)
                return key

            self.clear(aid)
            raise NetFunnelError("Failed to complete NetFunnel")

        except NetFunnelError:
            self.clear(aid)
            raise
        except Exception as exc:
            self.clear(aid)
            raise NetFunnelError(str(exc)) from exc

    def clear(self, aid: NetFunnelActionCode | None = None) -> None:
        """캐시된 티켓을 버립니다. ``aid`` 를 주면 그 칸만, 생략하면 전부 비웁니다.

        연결은 그대로 둡니다 — 정리는 :meth:`close` 가 맡습니다. 동작 하나가
        실패했다고 다른 동작의 티켓까지 버리면, 결제 대기열 실패가 조회 티켓을
        날립니다.
        """
        if aid is None:
            self._cache.clear()
        else:
            self._cache.pop(aid, None)

    # ------------------------------------------------------------- 컨텍스트 관리
    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """연 HTTP 세션을 닫습니다. 캐시(:meth:`clear`)와는 별개입니다."""
        # 이중 close 가드는 세션 래퍼가 집니다.
        self._session.close()

    # ------------------------------------------------------------------- 내부
    def _start(self, aid: NetFunnelActionCode) -> tuple[str | None, str | None, str | None, str | None]:
        return self._make_request("getTidchkEnter", aid=aid)

    def _check(self, key: str | None) -> tuple[str | None, str | None, str | None, str | None]:
        return self._make_request("chkEnter", key)

    def _complete(self, key: str | None) -> tuple[str | None, str | None, str | None, str | None]:
        return self._make_request("setComplete", key)

    def _make_request(
        self,
        operation: str,
        key: str | None = None,
        aid: NetFunnelActionCode = NetFunnelAction.TRAIN_SEARCH,
    ) -> tuple[str | None, str | None, str | None, str | None]:
        params = self._build_params(self.OP_CODE[operation], key, aid)
        # 앱은 값을 query 에 실어 보내고 본문은 비웁니다. ``post`` 에 ``params`` 를 주면
        # curl_cffi 가 URL 뒤에 붙이고 ``Content-Length: 0`` 을 씁니다.
        #
        # 응답의 ``ip`` · ``port`` 는 일부러 따르지 않습니다. SDK 의 ``makeURL`` 은
        # ``host_notmodify=false`` 일 때만 그 값으로 호스트를 바꾸는데, 앱은 기본값
        # ``true`` 를 바꾸지 않습니다. 근거는 docs/protocol-evidence-7.0.8.json 의
        # netfunnel.host_redirect.
        response = self._session.post(NETFUNNEL_URL, params=params)
        parsed = self._parse(response.text)
        return parsed.get("status"), parsed.get("key"), parsed.get("nwait"), parsed.get("ttl")

    def _build_params(
        self,
        opcode: str,
        key: str | None = None,
        aid: NetFunnelActionCode = NetFunnelAction.TRAIN_SEARCH,
    ) -> dict[str, str]:
        """``key`` 는 호출자가 넘긴 값만 씁니다. 캐시를 되읽으면 다른 실행이 덮어쓴
        키나 만료된 옛 키가 응답에 실려 나갑니다.
        """
        params: dict[str, str] = {"opcode": opcode}

        if opcode == self.OP_CODE["getTidchkEnter"]:
            params.update({"sid": "service_1", "aid": aid})
        elif opcode in (self.OP_CODE["chkEnter"], self.OP_CODE["setComplete"]):
            # 5002 는 앱도 ``opcode`` · ``key`` 만 보냅니다. sid · aid · ttl 을 되붙이면
            # 대기 상태에서 앱과 다른 모양이 됩니다.
            params["key"] = key or ""

        return params

    def _wait_seconds(self, raw: str | None) -> int:
        """응답의 ``ttl``(초)을 1–30초로 자릅니다. 정수가 아니거나 없으면 1초입니다.

        SDK 의 ``getTTL(max_ttl=30, min=1)`` 과 같은 규칙입니다. 앱은 이 상한을 원격
        설정에서 불러오지 않으므로 30 이 고정입니다.
        """
        if raw is None:
            return self.MIN_WAIT_SECONDS
        try:
            ttl = int(raw)
        except ValueError:
            return self.MIN_WAIT_SECONDS
        return min(self.MAX_WAIT_SECONDS, max(self.MIN_WAIT_SECONDS, ttl))

    @staticmethod
    def _parse(response: str) -> dict[str, str]:
        status, _, params_str = response.partition(":")
        if not params_str:
            raise NetFunnelError("Failed to parse NetFunnel response")

        parsed = dict(param.split("=", 1) for param in params_str.split("&") if "=" in param)
        parsed["status"] = status
        return parsed

    def _cached_ticket(self, aid: NetFunnelActionCode, now: float) -> str | None:
        """``aid`` 칸의 캐시가 아직 살아 있으면 그 키를, 아니면 ``None`` 을 돌려줍니다.

        빈 키는 캐시로 보지 않습니다 — 통과 응답에 키가 없었던 경우입니다.
        """
        cached = self._cache.get(aid)
        if cached is None:
            return None
        key, fetched = cached
        return key if key and (now - fetched) < self.CACHE_TTL else None
