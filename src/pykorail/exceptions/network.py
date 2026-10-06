"""전송 계층·대기열(NetFunnel) 관련 예외."""

from __future__ import annotations

from pykorail.exceptions.base import PykorailError


class NetFunnelError(PykorailError):
    """NetFunnel 대기열 티켓을 얻지 못했습니다.

    코레일 응답이 아니라 대기열 게이트(``nf.letskorail.com``) 유래이므로
    :class:`~pykorail.exceptions.base.KorailError` 가 아닌 형제 타입입니다.
    """

    def __init__(self, msg: str) -> None:
        self.msg = msg
        super().__init__(msg)

    def __str__(self) -> str:
        return self.msg


class TransportError(PykorailError):
    """HTTP 세션을 만들 수 없거나 응답이 JSON 이 아닙니다."""


class HttpStatusError(TransportError):
    """코레일이 요청을 거절했고, 본문이 코레일 응답 형식이 아닙니다 (HTTP 4xx·5xx 또는 이용제한 봉투).

    서버나 앞단이 요청 자체를 거절한 것이라 자격증명·조회 결과와는 무관합니다.
    실행 환경 검증에 걸리면 HTTP 403 과 함께 ``code=-2000`` 이용제한 안내가 옵니다
    (이슈 #27). 이를 비밀번호 오류나 결과 없음으로 바꾸면 사용자가 원인을 알 수
    없으므로, 상태 코드와 서버가 준 ``code``·``message`` 를 그대로 실어 따로 올립니다.

    이용제한 봉투(``code=-2000``)는 상태 코드와 무관하게 하위 타입
    :class:`AccessRestrictedError` 로 올라옵니다.

    본문에 ``strResult`` 가 있으면 상태 코드와 무관하게 기존처럼
    :class:`~pykorail.exceptions.base.KorailError` 코드 매핑을 탑니다.
    """

    def __init__(self, status_code: int, msg: str | None = None, code: str | None = None) -> None:
        self.status_code = status_code
        self.msg = msg
        self.code = code
        super().__init__(status_code, msg, code)

    def __str__(self) -> str:
        return f"HTTP {self.status_code}: {self.msg or '응답 본문 없음'} ({self.code})"


class AccessRestrictedError(HttpStatusError):
    """실행 환경 검증에 걸려 이용이 제한됐습니다 (``code=-2000``, 이슈 #27).

    **같은 요청을 곧바로 반복하지 마세요** — 막힌 채로 두드리면 제한이 길어집니다.
    대기 루프는 이 타입만 따로 잡아 멈추면 됩니다. :class:`HttpStatusError` 의 하위
    타입이라 기존 ``except HttpStatusError`` 도 그대로 잡습니다.

    관측된 이용제한 응답은 HTTP 403 입니다. 같은 봉투가 다른 상태(200 등)로 오는 캡처는
    없지만, 그때도 "결과 없음"·"비밀번호 오류" 로 흘러가지 않도록 상태와 무관하게 이
    타입으로 올립니다. ``status_code`` 에는 실제 상태가 담깁니다.
    """

    def __str__(self) -> str:
        # 상태 코드보다 원인을 앞에 둡니다 — 200 으로 왔을 때 "HTTP 200" 으로 시작하면
        # 로그만 봐서는 성공한 응답처럼 읽힙니다.
        return f"이용제한: {self.msg or '안내 없음'} (HTTP {self.status_code}, {self.code})"
