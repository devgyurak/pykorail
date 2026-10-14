"""로그인 세션 상태 — 동기·비동기가 같은 클래스를 씁니다.

I/O 가 없는 데이터라 한쪽 계층에 두면 다른 쪽이 그쪽을 import 하게 됩니다. 여기
모아 두면 어느 쪽도 다른 쪽을 보지 않습니다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Account:
    """로그인 세션 상태.

    여러 리소스가 읽고(``mbCrdNo``) 로그인만 쓰기 때문에, 클라이언트와 리소스가
    같은 인스턴스를 공유합니다.

    로그인·로그아웃이 값을 바꾸므로 ``frozen`` 으로 두지 않습니다. 응답 모델의 불변
    규칙(AGENTS.md §2-3)은 서버 응답을 해석한 결과에만 적용됩니다.
    """

    logined: bool = False
    membership_number: str | None = None
    name: str | None = None
    email: str | None = None
    phone_number: str | None = None

    def clear(self) -> None:
        self.logined = False
        self.membership_number = None
        self.name = None
        self.email = None
        self.phone_number = None
