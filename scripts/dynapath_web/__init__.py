"""웹 DynaPath(_qdb) 보호 스크립트를 정적으로 해제하고 드리프트를 감지합니다.

``www.korail.com`` 의 로그인·조회·예약은 서버가 세션마다 내려주는 JScrambler
바이트코드 VM(``dyna/<token>.js``)으로 만든 ``_qdb`` 지문을 함께 제출합니다.
이 패키지는 그 자산을 **네트워크 없이**(이미 받아 둔 파일만으로) 해제해
알고리즘 스펙을 만들고, 고정된 baseline 과 비교해 배포 회전(JScrambler 재난독화)을
조기에 드러냅니다.

바이트코드를 파이썬 재현으로 옮기는 것은 이 패키지의 일이 아닙니다 — 여기서는
디코딩과 시그니처까지만 다룹니다. 자세한 근거와 한계는
``docs/protocol-evidence-web-20261022.json`` 을 참고하세요.
"""

from __future__ import annotations
