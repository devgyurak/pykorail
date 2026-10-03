"""기기 프로파일 — DynaPath의 ID·모델·OS를 지정하며 User-Agent는 바꾸지 않습니다.

::

    from pykorail import Korail
    from pykorail.device import profile_by_id, random_profile

    profile = profile_by_id(saved_id, android_id=saved_android_id) or random_profile()
    # profile.id와 profile.android_id를 함께 저장합니다.
    korail = Korail(device_profile=profile)
"""

from __future__ import annotations

from pykorail.device.android_id import generate_android_id
from pykorail.device.catalog import (
    BUILD_ID,
    CATALOG_SIZE,
    DEVICE_PROFILES,
    PROFILES_BY_ID,
    profile_by_id,
    random_profile,
)
from pykorail.device.profile import DeviceProfile, DeviceProfileLike, dalvik_user_agent

__all__ = [
    "BUILD_ID",
    "CATALOG_SIZE",
    "DEVICE_PROFILES",
    "PROFILES_BY_ID",
    "DeviceProfile",
    "DeviceProfileLike",
    "dalvik_user_agent",
    "generate_android_id",
    "profile_by_id",
    "random_profile",
]
