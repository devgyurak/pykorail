"""DynaPath 기기 신원과 기존 Dalvik 문자열 렌더 유틸리티."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from pykorail.device.android_id import generate_android_id, validate_android_id


class DeviceProfileLike(Protocol):
    """:class:`DeviceProfile` 이 아니어도 이 세 필드만 있으면 클라이언트에 주입할 수 있습니다.

    읽기 전용 프로퍼티로 선언해 뒀으므로 ``frozen=True`` 데이터클래스도 그대로
    만족합니다. 이미 자기 앱에서 기기 카탈로그를 굴리고 있다면(예: KTX·SRT 를 같이
    다루느라 Chrome 버전까지 들고 있는 프로파일) 그 객체를 변환 없이 넘기면 됩니다.
    선택적으로 ``android_id`` 를 제공하면 해당 ID를 재사용합니다. 없으면
    클라이언트마다 ID를 새로 생성하므로 실행 간 유지하려면 함께 저장하세요.
    """

    @property
    def model(self) -> str:
        """기기 모델명 (예: ``SM-S928N``)."""
        ...

    @property
    def android(self) -> str:
        """안드로이드 메이저 버전 문자열 (예: ``"14"``)."""
        ...

    @property
    def build_id(self) -> str:
        """``ro.build.id`` 값 (예: ``UP1A.231005.007``)."""
        ...


@dataclass(frozen=True, slots=True)
class DeviceProfile:
    """이 패키지가 기본 제공하는 기기 프로파일 구현.

    :mod:`pykorail.device.catalog` 가 정합성 제약(버전 ↔ 빌드ID 프리픽스, 모델 ↔
    유효 버전 범위)을 만족하는 조합만 조립해 둡니다. 직접 만들어 써도 되지만,
    실재하지 않는 조합은 그 자체가 탐지 신호가 될 수 있습니다.

    ``android_id`` 도 동등성·해시에 포함됩니다. 같은 모델·OS여도 ID가 다르면
    다른 가상 기기이며, 카탈로그의 모델 정의와 기기 신원을 구분합니다.

    Raises:
        ValueError: android_id가 16자리 소문자 16진수 문자열이 아닙니다.
    """

    id: str
    marketing: str
    model: str
    android: str
    build_id: str
    android_id: str = field(default_factory=generate_android_id, repr=False)

    def __post_init__(self) -> None:
        validate_android_id(self.android_id)


def dalvik_user_agent(profile: DeviceProfileLike) -> str:
    """기존 호출자 호환용 Dalvik 문자열을 렌더합니다.

    Korail 클라이언트의 요청에는 사용하지 않습니다. 스마트 앱 API는
    프로파일과 무관하게 ``korailtalk`` User-Agent를 사용합니다.
    """
    return f"Dalvik/2.1.0 (Linux; U; Android {profile.android}; {profile.model} Build/{profile.build_id})"
