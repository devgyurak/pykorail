"""DynaPath 요청 서명 (``x-dynapath-m-token``) — 코레일톡+ 7.0.10 (SDK 2.0.1).

7.0.10 의 토큰은 네이티브 ``libdp_ffi_android.so`` 가 만듭니다. 2026-10-28 알고리즘을 **완전히
역분석**했고, 실기기(에뮬레이터) 앱이 보낸 **캡처 토큰 2개를 복호→재인코딩해 바이트 동일**함을
확인했습니다(근거: ``docs/protocol-evidence-7.0.10.json`` ``v2-codec-byte-exact``). 구조:
``201`` + (``LE32(nonce)`` ‖ ``MAC3`` ‖ ``eor``)를 4바이트 워드별 커스텀 base62 로 인코딩한 것이고,
``MAC3 = SHA256(SECRET ‖ LE32(nonce) ‖ eor)[:3]``, ``eor = 평문봉투 XOR 키스트림``,
**키스트림 = SHA256(SECRET ‖ LE32(nonce) ‖ BE32(block_index))** (블록 카운터는 빅엔디언 u32 —
네이티브 ``sub_35f84`` 의 ``rev`` + 4바이트 append). 기본 엔진 :class:`DeclarationDynaPathEngine`
가 이 형식으로 ``201…`` 토큰을 만들며 ``.so`` 는 실행 시 필요 없습니다. 2026-10-28 실서버 전체
흐름(로그인→조회→예약→취소→로그아웃)에서 수용됨을 확인했습니다.

(이력: 예전엔 키스트림 카운터를 ``BE_u64(nonce+i)`` 로 뒀는데, 모든 에뮬레이터 캡처가 nonce=0 이라
BE/LE 를 구분할 수 없어 틀렸습니다. nonce≠0 인 실측 캡처로 ``LE32(nonce)‖BE32(block)`` 임을
확정해 바로잡았고, 그 결과 실기기 토큰과 평문까지 일치합니다.)

남는 입력-수준 변수(알고리즘이 아니라 operation/상태에 달림): ``es``(op)와 봉투 필드 집합이
요청 종류마다 다릅니다. 캡처된 실기기 토큰 둘(로그인 324자·데이터 222자)은 **모두 선언 토큰**이고
같은 ``es=893617653734745139`` 를 썼는데, 로그인은 ``…&kl`` 까지, 데이터는 ``…&iid`` 까지만 담깁니다
(짧은 쪽도 Flow-2 가 아니라 필드가 적은 선언 토큰 — 캡처 기기는 ``sb=0`` 미enroll 에뮬레이터).
이 엔진 기본은 ``es=288904575606514493`` + ``ec`` 포함(실서버 수용 확인)이라 캡처와 op·필드 구성이
다릅니다 — 맞추려면 wire 변경 결정이 필요합니다. ``kl=990094375841594426`` 은 캡처로 실측 확인된
상수입니다. **enroll 된 실기기**가 per-request 하드웨어 서명(Flow-2: beginRequest→clientDataHash→
StrongBox/TEE 서명→finishRequest)을 쓰는 경로는 별개이며 오프디바이스 재현 불가입니다 — 서버가 그걸
강제하면 어느 엔진으로도 동작하지 않습니다.

토큰 엔진은 :class:`DynaPathEngine` 계약으로 **교체 가능**합니다 —
``Korail(dynapath_engine=...)`` 로 실기기 값(정확한 ``board``·``kl``/``ec`` 등)을 담은
엔진을 주입할 수 있습니다. 네이티브 바이너리(``.so``)는 저작권·속도상 패키지에 번들하지
않습니다.
"""

from __future__ import annotations

import base64
import hashlib
import math
import secrets
import struct
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Protocol

from pykorail.constants import DYNAPATH_APP_ID, DYNAPATH_SDK_VERSION, TOKEN_PREFIX

if TYPE_CHECKING:
    from pykorail.device import DeviceProfileLike

#: 빌드 내장 상수(64 ASCII-hex). .so init 에서 추출.
_V2_SECRET_HEX: Final = b"9a330fd663b62c5f888a7ce76ac7202d93f646b4e0bd605cd4183278ca4ca888"
#: base62 커스텀 알파벳. div 루프(.so 0x35dd8)에서 캡처한 치환열이며 표준 base62 가 아닙니다.
_V2_ALPHABET: Final = "TeFOuQBxj1qRUHwKkymSY8l3psvCzAL5tofNcihg9WDG072EZ4bVad6rJnPXIM"
#: ``kl``/``ec`` 는 keystore/attestation 경로에서 나오는 값으로, 에뮬레이터(게이트 강제)
#: 에서는 요청 입력과 무관하게 고정입니다. 실제 기기의 attestation 값과 다를 수 있으나
#: 2026-10-28 실서버 로그인에서 이 값으로 수용됨을 확인했습니다 — 실기기 값이 있으면
#: 생성자에서 덮어쓰세요.
_V2_KL_DEFAULT: Final = "990094375841594426"
_V2_EC_DEFAULT: Final = "978212327729758430"

#: 프로파일에 없는 기기 사실의 기본값. 카탈로그는 전부 삼성 자급제(SM-…N)라 ``manufacturer``
#: 는 삼성으로 고정됩니다. ``board``(SoC 코드네임)는 프로파일에 없어 서버가 검증하지 않는
#: placeholder 입니다. 프로파일이 아예 없을 때 쓰는 model/release 는 **board 와 정합한**
#: 한 대의 기기(Galaxy S23, SM-S911N · Snapdragon ``kalama`` · Android 15)로 맞췄습니다.
#: 주의: ``from_profile`` 은 프로파일의 model/release 를 쓰되 board 는 이 placeholder 를
#: 그대로 보내므로, 서버가 model↔board 를 대조하기 시작하면 어긋납니다 — 그때는 실기기
#: board 를 담은 커스텀 엔진을 주입하세요(``docs/protocol-evidence-7.0.10.json`` 참조).
_DEFAULT_RELEASE: Final = b"15"
_DEFAULT_MODEL: Final = b"SM-S911N"
_DEFAULT_BOARD: Final = b"kalama"
_DEFAULT_MANUFACTURER: Final = b"samsung"
_DEFAULT_SDK_INT: Final = 35
_DEFAULT_STRONGBOX: Final = 1
#: 안드로이드 메이저 버전 → ``Build.VERSION.SDK_INT``.
_SDK_BY_ANDROID: Final[dict[str, int]] = {"13": 33, "14": 34, "15": 35, "16": 36}


class DynaPathEngine(Protocol):
    """``x-dynapath-m-token`` 생성기 계약.

    기본 구현은 :class:`DeclarationDynaPathEngine`(순수 파이썬 선언 토큰 코덱)이고,
    이 계약을 만족하는 다른 엔진을 ``Korail(dynapath_engine=...)`` 로 주입해 교체할
    수 있습니다 — 예컨대 실기기 ``board``·attestation 값을 담은 엔진. 엔진은 ``op_id``
    와 ``device_id`` 로 선언 봉투를 채웁니다.
    """

    def generate_token_with_timestamp(self, *, request_bound: bool, op_id: int, device_id: str) -> tuple[str, int]:
        """토큰과 ``Sid`` 에 쓸 생성 시각(ms)을 함께 돌려줍니다."""
        ...


def _v2_b64(raw: bytes) -> str:
    """Android ``Base64.URL_SAFE | NO_PADDING | NO_WRAP`` — 봉투의 os/dm/iid/mf/bd 인코딩."""
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _v2_keystream(nbytes: int, nonce: int) -> bytes:
    """``SHA256(SECRET_HEX || LE_u32(nonce) || BE_u32(블록인덱스))`` 를 32바이트 블록으로 이어 붙인 키스트림.

    블록 카운터는 **빅엔디언 u32** 입니다(네이티브 ``sub_35f84`` 의 ``rev w8, w20`` → 4바이트 append).
    실측 캡처 토큰 2개를 바이트 단위로 복호·재현해 검증했습니다(근거 문서 ``v2-codec-byte-exact``).
    """
    blocks = math.ceil(nbytes / 32)
    nonce_le = struct.pack("<I", nonce)
    chunks = [hashlib.sha256(_V2_SECRET_HEX + nonce_le + struct.pack(">I", block)).digest() for block in range(blocks)]
    return b"".join(chunks)[:nbytes]


def _v2_width(nbytes: int) -> int:
    """``nbytes`` 바이트 워드를 담는 고정 base62 자릿수(4B→6, 1B→2)."""
    return math.ceil(nbytes * 8 / math.log2(62))


def _v2_b62_word(value: int, width: int) -> str:
    """정수 하나를 고정폭 base62 로 인코딩(MSB 우선, 앞자리는 알파벳[0] 로 채움)."""
    out = [_V2_ALPHABET[0]] * width
    for i in range(width - 1, -1, -1):
        out[i] = _V2_ALPHABET[value % 62]
        value //= 62
    return "".join(out)


def _sdk_for(android: str) -> int:
    """안드로이드 메이저 버전 문자열 → SDK_INT.

    카탈로그 밖 버전은 안드로이드 13+ 의 규칙(API = 버전 + 20)으로 외삽하고, 숫자가
    아니거나 13 미만이면(매핑이 모호함) 현행 기본값을 씁니다.
    """
    if android in _SDK_BY_ANDROID:
        return _SDK_BY_ANDROID[android]
    return int(android) + 20 if android.isdigit() and int(android) >= 13 else _DEFAULT_SDK_INT


@dataclass(frozen=True)
class DeclarationDynaPathEngine:
    """DynaPath 선언 토큰 생성기(기본 엔진). :class:`DynaPathEngine` 계약 만족.

    네이티브 ``declarationToken`` 의 **Flow-1 선언 토큰**을 바이트 단위로 재현합니다(모듈
    설명 참조). ``.so`` 는 실행 시 필요하지 않습니다. 상태가 없어(frozen) 어디서든 같은
    규칙으로 동작하며, nonce 를 고정하지 않으면 요청마다 토큰이 달라집니다(실제 앱과 동일).

    한계(서버가 ``201`` 프리픽스만 보는 동안은 무해하지만 기록해 둡니다):

    * **Flow-1 전용.** request-binding 로그인 토큰(Flow-2 하드웨어 서명)은 재현 불가 —
      이 엔진은 어떤 op 든 Flow-1 선언 토큰을 냅니다.
    * **``kl``/``ec`` 는 게이트 강제 상수**(실서버 로그인에서 수용 확인). 실기기 값이
      있으면 덮어쓰세요.
    * **``board`` 와 비로그인 op_id, 기기 사실의 Java→네이티브 바이트 마셜링은 APK
      미확인**입니다. 코덱은 넘겨받은 바이트를 바이트 동일로 인코딩하지만, 실기기 토큰과의
      일치를 보장하지는 않습니다.

    Args:
        release: ``Build.VERSION.RELEASE`` 바이트(봉투 ``os``).
        model: ``Build.MODEL`` 바이트(``dm``).
        manufacturer: ``Build.MANUFACTURER`` 바이트(``mf``).
        board: ``Build.BOARD`` 바이트(``bd``).
        sdk_int: ``Build.VERSION.SDK_INT``(``sl``).
        strongbox: StrongBox 지원 플래그(``sb``).
        android_id: ``device_id`` 가 비었을 때 쓸 ``iid`` 바이트. 보통은 서명기가 넘기는
            ``device_id``(16진수)가 우선합니다.
        nonce: 고정 nonce. ``None`` 이면 요청마다 난수를 뽑아 실제 앱처럼 매번 달라집니다.
        kl, ec: attestation 파생 선언 값(기본은 실서버 수용이 확인된 게이트 강제 상수).
    """

    release: bytes = _DEFAULT_RELEASE
    model: bytes = _DEFAULT_MODEL
    manufacturer: bytes = _DEFAULT_MANUFACTURER
    board: bytes = _DEFAULT_BOARD
    sdk_int: int = _DEFAULT_SDK_INT
    strongbox: int = _DEFAULT_STRONGBOX
    android_id: bytes | None = None
    nonce: int | None = None
    kl: str = _V2_KL_DEFAULT
    ec: str = _V2_EC_DEFAULT

    def __post_init__(self) -> None:
        # nonce 는 봉투와 버퍼에 LE_u32 로 실리므로 32비트를 벗어나면 생성 시점에 막습니다
        # (아니면 요청 때 struct.pack 에서 늦게 터집니다).
        if self.nonce is not None and not 0 <= self.nonce < 2**32:
            raise ValueError("nonce는 0 이상 2**32 미만이어야 합니다")

    @classmethod
    def from_profile(cls, profile: DeviceProfileLike) -> DeclarationDynaPathEngine:
        """기기 프로파일에서 ``model``·``release``·``sdk_int`` 를 끌어와 엔진을 만듭니다.

        ``manufacturer``·``board``·``strongbox`` 는 프로파일에 없어 기본값을 씁니다
        (카탈로그가 전부 삼성이라 ``manufacturer`` 는 정확; ``board`` 는 서버 미검증
        placeholder). ``android_id`` 는 서명기가 ``device_id`` 로 매 호출에 넘깁니다.
        """
        return cls(
            release=profile.android.encode("ascii"),
            model=profile.model.encode("utf-8"),
            sdk_int=_sdk_for(profile.android),
        )

    def _plaintext(self, op_id: int, ts_ms: int, android_id: bytes) -> bytes:
        """암호화 직전의 선언 봉투를 조립합니다(앞의 ``!`` 포함)."""
        envelope = (
            f"!v=2&es={op_id}&ts={ts_ms}&st=Android&sv={DYNAPATH_SDK_VERSION}&ai={DYNAPATH_APP_ID}"
            f"&os={_v2_b64(self.release)}&dm={_v2_b64(self.model)}&iid={_v2_b64(android_id)}"
            f"&mf={_v2_b64(self.manufacturer)}&bd={_v2_b64(self.board)}"
            f"&sl={self.sdk_int}&sb={self.strongbox}&kl={self.kl}&ec={self.ec}"
        )
        return envelope.encode("latin1")

    def _build(self, op_id: int, device_id: str, ts_ms: int, nonce: int) -> str:
        """봉투 → SHA256-CTR XOR → MAC[0:3] → 워드별 base62 로 토큰을 만듭니다."""
        # iid 는 android_id **문자열의 UTF-8 바이트**입니다(16자리 16진수 → 16바이트). 앱의
        # C3907n.b() 가 Settings.Secure "android_id" 문자열을 getBytes(UTF_8) 하는 것을 그대로
        # 옮긴 것이라 16진수로 디코드(8바이트)하면 안 됩니다 — APK 7.0.10 에서 확인.
        android_id = device_id.encode("ascii") if device_id else (self.android_id or b"")
        plaintext = self._plaintext(op_id, ts_ms, android_id)
        keystream = _v2_keystream(len(plaintext), nonce)
        eor = bytes(p ^ k for p, k in zip(plaintext, keystream, strict=True))
        # 태그 = SHA256(SECRET || LE_u32(nonce) || eor) 의 앞 3바이트(네이티브는 ldurh+ldurb 로 3바이트만 읽음).
        mac3 = hashlib.sha256(_V2_SECRET_HEX + struct.pack("<I", nonce) + eor).digest()[:3]
        buffer = struct.pack("<I", nonce) + mac3 + eor
        body = [
            _v2_b62_word(int.from_bytes(buffer[i : i + 4], "big"), _v2_width(len(buffer[i : i + 4])))
            for i in range(0, len(buffer), 4)
        ]
        return TOKEN_PREFIX + "".join(body)

    def generate_token(self, *, request_bound: bool = False, op_id: int = 0, device_id: str = "") -> str:
        """``x-dynapath-m-token`` 값을 만듭니다(현재 시각 기준).

        Args:
            request_bound: 계약상 인자. 이 엔진은 Flow-1 선언 토큰만 내므로 영향이 없습니다
                (Flow-2 로그인 토큰은 하드웨어 서명이라 재현 불가 — 클래스 설명 참조).
            op_id: 엔드포인트의 DynaPath op id. 봉투 ``es`` 로 들어갑니다.
            device_id: 기기 android_id(16진수). ``iid`` 로 들어갑니다.
        """
        return self.generate_token_with_timestamp(request_bound=request_bound, op_id=op_id, device_id=device_id)[0]

    def generate_token_with_timestamp(
        self, *, request_bound: bool = False, op_id: int = 0, device_id: str = ""
    ) -> tuple[str, int]:
        """토큰과 ``Sid`` 에 쓸 생성 시각(ms)을 같은 시각으로 함께 돌려줍니다."""
        ts_ms = int(time.time() * 1000)
        return self._build(op_id, device_id, ts_ms, self._resolve_nonce()), ts_ms

    def _resolve_nonce(self) -> int:
        """고정 nonce 가 없으면 요청마다 32비트 난수를 뽑습니다(실제 앱처럼 매번 달라지도록)."""
        return self.nonce if self.nonce is not None else secrets.randbits(32)
