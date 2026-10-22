"""드리프트 검사용 자산을 네트워크에서 받아옵니다.

세션 VM(``dyna/<token>.js``)의 파일 이름은 서버가 세션마다 발급하므로 저장소가
알 수 없습니다. 그래서 고정 URL 이 확인된 부트스트랩(``dp.helper.js``)만 기본값으로
두고, 나머지는 ``이름=URL`` 로 주입받습니다.
"""

from __future__ import annotations

import urllib.request

#: 자산 요청에 쓰는 User-Agent. 실제 브라우저가 아니므로 앱 신원과 무관하다.
USER_AGENT = "pykorail-dynapath-drift-check"

#: 고정 URL 이 확인된 부트스트랩. 로더·세션 VM 은 여기서 이어지지만 이름이
#: 회전하므로 자동으로는 받지 않는다.
BOOTSTRAP_URL = "https://cdn.korail.com/dyna/dp.helper.js"


def fetch_text(url: str, timeout: float = 30.0) -> str:
    """``url`` 을 내려받아 UTF-8 로 풉니다."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")
