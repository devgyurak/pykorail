"""기기 프로파일 카탈로그.

**한 프로파일 = 폰 한 대.** 개별 User-Agent 문자열을 나열하는 대신, 아래 정합성
제약을 만족하는 (모델 × 안드로이드 버전) 조합을 결정적으로 전개합니다.

정합성 제약:
  1. 안드로이드 버전 ↔ 빌드ID 프리픽스 (13→T, 14→U, 15→A, 16→B) — :data:`BUILD_ID` 로 강제
  2. 모델 ↔ 유효 버전 범위 (출시 OS ~ 검증된 최대 지원)        — :data:`_MODELS` 로 강제

모든 모델은 소스로 확인된 **한국 자급제(SM-…N)** 만 씁니다. curl_cffi 임퍼소네이션이
안드로이드 크롬 계열(``chrome131_android``)이라 TLS 지문과도 일치합니다 — 아이폰·
통신사 전용(S/K/L 접미사) 모델을 넣지 마세요.

모델·OS 조합과 프로파일 ``id`` 는 결정적이며 ``android_id`` 는 생성 시 임의 값입니다.
무작위로 하나 뽑고 싶으면
:func:`random_profile` 을 쓰되, **한 번 뽑은 프로파일은 계속 재사용하세요** —
실행마다 다른 폰인 척하는 것이 오히려 부자연스럽습니다.
"""

from __future__ import annotations

import random
from dataclasses import replace

from pykorail.device.profile import DeviceProfile

#: 카탈로그에 전개할 프로파일 수.
CATALOG_SIZE = 100

#: 안드로이드 버전 → 구글 정식 릴리스 빌드ID. 삼성폰도 ``ro.build.id`` 로 이 값을
#: 그대로 씁니다. 랜덤 날짜/증분을 굴리면 오히려 비현실적이라 버전당 하나로 고정합니다.
BUILD_ID: dict[int, str] = {
    13: "TP1A.220624.014",
    14: "UP1A.231005.007",
    15: "AP3A.240905.015.A2",
    16: "BP2A.250605.031",
}

# (마케팅명, 모델, 유효 안드로이드 버전). 전부 소스 검증된 한국 자급제 N 모델.
# 최고버전 신뢰가 낮은 경우는 보수적으로 뺐습니다 (A33→14, A15 LTE→15).
_MODELS: tuple[tuple[str, str, tuple[int, ...]], ...] = (
    ("Galaxy S20", "SM-G981N", (13,)),
    ("Galaxy S20+", "SM-G986N", (13,)),
    ("Galaxy S20 Ultra", "SM-G988N", (13,)),
    ("Galaxy S20 FE 5G", "SM-G781N", (13,)),
    ("Galaxy S21", "SM-G991N", (13, 14, 15)),
    ("Galaxy S21+", "SM-G996N", (13, 14, 15)),
    ("Galaxy S21 Ultra", "SM-G998N", (13, 14, 15)),
    ("Galaxy S22", "SM-S901N", (13, 14, 15, 16)),
    ("Galaxy S22+", "SM-S906N", (13, 14, 15, 16)),
    ("Galaxy S22 Ultra", "SM-S908N", (13, 14, 15, 16)),
    ("Galaxy S23", "SM-S911N", (13, 14, 15, 16)),
    ("Galaxy S23+", "SM-S916N", (13, 14, 15, 16)),
    ("Galaxy S23 Ultra", "SM-S918N", (13, 14, 15, 16)),
    ("Galaxy S24", "SM-S921N", (14, 15, 16)),
    ("Galaxy S24+", "SM-S926N", (14, 15, 16)),
    ("Galaxy S24 Ultra", "SM-S928N", (14, 15, 16)),
    ("Galaxy S25", "SM-S931N", (15, 16)),
    ("Galaxy S25+", "SM-S936N", (15, 16)),
    ("Galaxy S25 Ultra", "SM-S938N", (15, 16)),
    ("Galaxy Note20", "SM-N981N", (13,)),
    ("Galaxy Note20 Ultra", "SM-N986N", (13,)),
    ("Galaxy Z Fold3", "SM-F926N", (13, 14, 15)),
    ("Galaxy Z Fold4", "SM-F936N", (13, 14, 15, 16)),
    ("Galaxy Z Fold5", "SM-F946N", (13, 14, 15, 16)),
    ("Galaxy Z Fold6", "SM-F956N", (14, 15, 16)),
    ("Galaxy Z Flip3", "SM-F711N", (13, 14, 15)),
    ("Galaxy Z Flip4", "SM-F721N", (13, 14, 15, 16)),
    ("Galaxy Z Flip5", "SM-F731N", (13, 14, 15, 16)),
    ("Galaxy Z Flip6", "SM-F741N", (14, 15, 16)),
    ("Galaxy A52s 5G", "SM-A528N", (13, 14)),
    ("Galaxy A53 5G", "SM-A536N", (13, 14, 15)),
    ("Galaxy A33 5G", "SM-A336N", (13, 14)),
    ("Galaxy A34 5G", "SM-A346N", (13, 14, 15, 16)),
    ("Galaxy A35 5G", "SM-A356N", (14, 15, 16)),
    ("Galaxy A55 5G", "SM-A556N", (14, 15, 16)),
    ("Galaxy A24", "SM-A245N", (13, 14, 15, 16)),
    ("Galaxy A25 5G", "SM-A256N", (14, 15, 16)),
    ("Galaxy A15 LTE", "SM-A155N", (14, 15)),
)


def _slug(marketing: str) -> str:
    return (
        marketing.lower()
        .replace("galaxy ", "")
        .replace(" 5g", "5g")
        .replace(" lte", "lte")
        .replace(" ", "")
        .replace("+", "plus")
    )


def _select_devices() -> list[tuple[str, str, int]]:
    """모델 간 라운드로빈으로 최대 :data:`CATALOG_SIZE` 개의 (모델, 버전) 조합을 고릅니다.

    각 모델의 최신 OS 부터 한 개씩 순회하므로 모든 모델이 최소 1개씩 대표되고,
    잘려 나가는 것은 버전이 많은 모델의 구형 OS 조합뿐이라 다양성이 유지됩니다.
    """
    pools = [[(mk, md, v) for v in sorted(vs, reverse=True)] for mk, md, vs in _MODELS]
    selected: list[tuple[str, str, int]] = []
    depth = 0
    while len(selected) < CATALOG_SIZE and any(depth < len(pool) for pool in pools):
        for pool in pools:
            if depth < len(pool):
                selected.append(pool[depth])
                if len(selected) == CATALOG_SIZE:
                    break
        depth += 1
    return selected


def _build_catalog() -> tuple[DeviceProfile, ...]:
    return tuple(
        DeviceProfile(
            id=f"{_slug(marketing)}-a{version}",
            marketing=marketing,
            model=model,
            android=str(version),
            build_id=BUILD_ID[version],
        )
        for marketing, model, version in _select_devices()
    )


#: 전개된 카탈로그. 순서는 실행 간 안정적입니다.
DEVICE_PROFILES: tuple[DeviceProfile, ...] = _build_catalog()

#: ``id`` 로 찾기 위한 인덱스.
PROFILES_BY_ID: dict[str, DeviceProfile] = {profile.id: profile for profile in DEVICE_PROFILES}


def profile_by_id(profile_id: str | None, *, android_id: str | None = None) -> DeviceProfile | None:
    """프로파일을 찾고, 저장된 ``android_id`` 가 있으면 카탈로그를 바꾸지 않고 복원합니다.

    프로파일이 없으면 ``None`` 입니다. ID를 생략하면 이번 프로세스에서 생성된
    카탈로그 객체를 반환하므로 실행 간 유지하려면 두 ID를 함께 저장하세요.

    Raises:
        ValueError: 찾은 프로파일에 복원할 android_id의 형식이 잘못됐습니다.
    """
    if profile_id is None:
        return None
    profile = PROFILES_BY_ID.get(profile_id)
    if profile is not None and android_id is not None:
        return replace(profile, android_id=android_id)
    return profile


def random_profile(rng: random.Random | None = None) -> DeviceProfile:
    """카탈로그에서 프로파일 하나를 무작위로 뽑습니다.

    최초 1회만 뽑아 ``profile.id`` 와 ``profile.android_id`` 를 함께 저장하고,
    :func:`profile_by_id` 로 복원해 쓰세요. ``rng`` 를 넘기면
    재현 가능한 선택이 됩니다(테스트용).
    """
    return (rng or random).choice(DEVICE_PROFILES)
