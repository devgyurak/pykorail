"""이름을 바꾼 속성의 폐기 예고.

옛 이름은 같은 값을 돌려주는 속성으로 남겨 두고, 읽을 때마다 :class:`DeprecationWarning`
을 냅니다. ``from_response`` 로만 만든 객체는 옛 이름을 읽던 코드가 그대로 돌아가고,
다음 릴리스에서 이 속성을 지웁니다.
"""

from __future__ import annotations

import warnings
from typing import Any


def renamed(old: str, new: str) -> property:
    """``old`` 를 읽으면 ``new`` 의 값을 주고 폐기 예고를 냅니다.

    ``stacklevel=2`` 로 경고를 호출한 코드의 줄에 붙습니다 — 라이브러리 안을 가리키면
    사용자가 어디를 고칠지 알 수 없습니다.
    """

    def getter(self: Any) -> Any:
        warnings.warn(
            f"{type(self).__name__}.{old} 는 폐기 예정입니다. {new} 를 쓰세요.",
            DeprecationWarning,
            stacklevel=2,
        )
        return getattr(self, new)

    return property(getter, doc=f"폐기 예정. :attr:`{new}` 를 쓰세요.")
