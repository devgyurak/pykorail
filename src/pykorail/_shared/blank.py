"""빈 폼 필드를 다루는 순수 헬퍼."""

from __future__ import annotations

from typing import Any


def without_blanks(form: dict[str, Any]) -> dict[str, Any]:
    """빈 문자열 필드를 뺀 폼.

    앱은 요청 모델을 폼으로 펼칠 때 값이 빈 필드를 싣지 않습니다(코레일+ 7.0.8
    ``NetworkService`` 의 평탄화: 길이가 0 보다 클 때만 넣습니다). 7.0.8 에서 새로
    확인한 엔드포인트는 이 규칙을 따릅니다.

    **기존 엔드포인트에는 쓰지 마세요.** 조회의 빈 ``Sid`` 처럼 빈 값을 그대로 보내야
    하는 폼이 있고(AGENTS.md §3), 그것들은 실제 동작으로 검증된 모양입니다.
    """
    return {key: value for key, value in form.items() if value != ""}
