"""HTTP 세션 생성 — curl_cffi 우선, requests 폴백.

코레일 서버는 TLS 지문을 봅니다. curl_cffi 의 안드로이드 크롬 임퍼소네이션이
기본이고, 그걸 못 쓰는 환경(주로 Windows 의 libcurl DLL 로드 실패)에서만
requests 로 내려앉습니다 — 이때는 python-requests 지문이 나가 로그인이 거부될 수
있으므로 경고를 남깁니다.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

from pykorail.constants import IMPERSONATE
from pykorail.exceptions import TransportError

if TYPE_CHECKING:
    from collections.abc import Mapping, MutableMapping

logger = logging.getLogger(__name__)

try:
    import curl_cffi
except ImportError as exc:  # pragma: no cover - 환경 의존
    curl_cffi = None  # type: ignore[assignment]
    CURL_CFFI_IMPORT_ERROR: BaseException | None = exc
else:
    CURL_CFFI_IMPORT_ERROR = None

#: curl_cffi 를 쓸 수 있는지. False 면 requests 폴백이 동작합니다.
HAS_CURL_CFFI: bool = curl_cffi is not None


class Response(Protocol):
    """curl_cffi 와 requests 응답 객체의 공통 최소 표면."""

    @property
    def status_code(self) -> int: ...

    @property
    def text(self) -> str: ...


class HttpSession(Protocol):
    """curl_cffi ``Session`` 과 requests ``Session`` 의 공통 최소 표면.

    두 라이브러리 모두 배포 스텁이 없어 실제 타입을 그대로 쓰면 클라이언트 전체가
    ``Any`` 로 물듭니다. 이 프로토콜로 좁혀 두면 클라이언트 코드는 정적으로 검사되고,
    라이브러리 차이는 :func:`create_session` 안에 갇힙니다.
    """

    headers: MutableMapping[str, str]

    def get(self, url: str, **kwargs: Any) -> Response: ...

    def post(self, url: str, **kwargs: Any) -> Response: ...

    def close(self) -> None: ...


def resolve_ca_bundle() -> str | None:
    """존재가 확인된 CA 번들 경로, 없으면 ``None``.

    PyInstaller 로 얼린 앱에서는 certifi 가 번들에서 빠지거나 ``certifi.where()`` 가
    없는 경로를 가리킬 수 있습니다. 그런 경로를 curl 에 넘기면 모든 HTTPS 요청이
    실패하므로, 조용히 죽는 대신 curl 기본 CA 저장소로 넘기고 크게 경고합니다.
    """
    try:
        import certifi
    except ImportError:
        logger.warning("certifi 를 불러오지 못했습니다 — 기본 CA 저장소로 HTTPS 검증을 시도합니다")
        return None

    ca_path = certifi.where()
    if not Path(ca_path).is_file():
        logger.warning("certifi CA 번들이 없습니다(%s) — 기본 CA 저장소로 HTTPS 검증을 시도합니다", ca_path)
        return None
    return ca_path


def _create_fallback_session() -> HttpSession:
    logger.warning(
        "curl_cffi 를 사용할 수 없어 requests 로 폴백합니다 — TLS 지문이 달라져 서버가 로그인을 거부할 수 있습니다: %s",
        CURL_CFFI_IMPORT_ERROR,
    )
    try:
        import requests
    except ImportError as exc:  # pragma: no cover - 환경 의존
        raise TransportError(
            "curl_cffi 와 requests 를 모두 사용할 수 없습니다. "
            "`pip install curl_cffi` 또는 `pip install pykorail[fallback]` 을 실행하세요."
        ) from exc
    return cast("HttpSession", requests.Session())


def create_session(headers: Mapping[str, str] | None = None, impersonate: str = IMPERSONATE) -> HttpSession:
    """기본 헤더가 적용된 HTTP 세션을 만듭니다.

    ``headers`` 는 복사해서 적용하므로 호출자의 dict 를 오염시키지 않습니다.
    """
    session: HttpSession
    if curl_cffi is not None:
        ca_bundle = resolve_ca_bundle()
        # 앱의 UA만 덮어쓰면 Chrome 탐색용 Sec-Fetch/Client-Hint 헤더가 섞입니다.
        # TLS 설정과 별개로 HTTP 헤더는 호출자가 지정한 앱 헤더만 사용합니다.
        kwargs: dict[str, Any] = {"impersonate": impersonate, "default_headers": False}
        if ca_bundle:
            kwargs["verify"] = ca_bundle
        session = cast("HttpSession", curl_cffi.Session(**kwargs))
    else:  # pragma: no cover - 환경 의존
        session = _create_fallback_session()

    if headers:
        session.headers.update(dict(headers))
    return session
