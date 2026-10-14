"""코레일 응답 본문 해석 — 동기·비동기가 같은 판정을 씁니다.

상태 코드와 본문만 보는 순수 로직이라 I/O 계층 어느 쪽에 두면 다른 쪽이 그쪽을
import 하게 됩니다. 응답 객체 대신 원시값을 받으므로 :class:`~pykorail.transport.Response`
와 그 비동기 짝 어느 프로토콜에도 묶이지 않습니다.
"""

from __future__ import annotations

import json
from typing import Any, Final

from pykorail.exceptions import AccessRestrictedError, HttpStatusError, TransportError
from pykorail.models.parsing import text

#: 실행 환경 검증에 걸렸을 때 오는 이용제한 봉투의 ``code`` (이슈 #27).
ACCESS_RESTRICTED_CODE: Final = "-2000"


def parse_response(status: int, body: str) -> dict[str, Any]:
    """코레일 응답 본문을 해석합니다. 거절이면 예외를 던집니다."""
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        if status >= 400:
            raise HttpStatusError(status, body[:200] or None) from exc
        raise TransportError(f"코레일 응답을 JSON 으로 읽지 못했습니다: {body[:200]!r}") from exc
    # 4xx·5xx 라도 코레일 형식(strResult)이면 h_msg_cd 매핑을 그대로 탑니다.
    # 그 밖의 거절 본문(403 이용제한의 code·message 등)을 통과시키면 호출부가
    # strResult 부재를 "비밀번호 오류"·"결과 없음" 으로 읽어 원인이 사라집니다.
    korail_shaped = isinstance(parsed, dict) and "strResult" in parsed
    # 이용제한 봉투(code=-2000)는 상태 코드와 무관하게 거절로 봅니다. 관측된 것은 HTTP 403
    # 응답뿐이고(#27) 200 으로 온 캡처는 없습니다 — 방어적 처리입니다. 같은 봉투가 200 으로
    # 왔을 때 그대로 돌려주면 호출부가 strResult 부재를 "결과 없음"·"비밀번호 오류" 로 읽고,
    # 막힌 채로 같은 요청을 반복하게 됩니다.
    restricted = isinstance(parsed, dict) and not korail_shaped and text(parsed, "code") == ACCESS_RESTRICTED_CODE
    if (status >= 400 and not korail_shaped) or restricted:
        body_dict = parsed if isinstance(parsed, dict) else {}
        error_type = AccessRestrictedError if restricted else HttpStatusError
        # ``id`` 는 요청 추적값일 수 있어 예외 메시지에 싣지 않습니다.
        raise error_type(status, text(body_dict, "message") or None, text(body_dict, "code") or None)
    if not isinstance(parsed, dict):
        raise TransportError(f"코레일 응답이 객체가 아닙니다: {type(parsed).__name__}")
    return parsed
