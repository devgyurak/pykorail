"""기기 프로파일 카탈로그의 정합성."""

from __future__ import annotations

import random
import re
from dataclasses import asdict, replace
from unittest.mock import Mock

import pytest

from pykorail.device import (
    BUILD_ID,
    CATALOG_SIZE,
    DEVICE_PROFILES,
    DeviceProfile,
    dalvik_user_agent,
    generate_android_id,
    profile_by_id,
    random_profile,
)

#: 안드로이드 버전 → 빌드ID 첫 글자. 어긋나면 실재하지 않는 조합입니다.
BUILD_PREFIX = {13: "T", 14: "U", 15: "A", 16: "B"}


class TestAndroidId:
    def test_matches_android14_hmac_vector(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # given: 추출한 APK 인증서와 별도 PyCryptodome HMAC 계산으로 확인한 벡터입니다.
        entropy = Mock(return_value=bytes(range(32)))
        monkeypatch.setattr("pykorail.device.android_id._token_bytes", entropy)

        # when
        android_id = generate_android_id()

        # then
        assert android_id == "1d3e4cc39288a9b6"
        entropy.assert_called_once_with(32)

    def test_saved_profile_restores_without_new_entropy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # given
        profile = DEVICE_PROFILES[0]
        saved = asdict(profile)
        entropy = Mock(side_effect=AssertionError("복원 시 ID를 새로 생성하면 안 됩니다"))
        monkeypatch.setattr("pykorail.device.android_id._token_bytes", entropy)

        # when
        restored = DeviceProfile(**saved)

        # then
        assert restored == profile
        assert restored.android_id == saved["android_id"]
        assert restored.android_id not in repr(restored)
        entropy.assert_not_called()

    @pytest.mark.parametrize("value", ["", "abcd", "g" * 16, "A" * 16, "1" * 17])
    def test_rejects_malformed_saved_id(self, value: str) -> None:
        # when & then
        with pytest.raises(ValueError, match="android_id"):
            profile_by_id(DEVICE_PROFILES[0].id, android_id=value)


class TestCatalog:
    def test_has_expected_size(self) -> None:
        # when
        size = len(DEVICE_PROFILES)

        # then
        assert size == CATALOG_SIZE

    def test_ids_are_unique(self) -> None:
        # when
        ids = [profile.id for profile in DEVICE_PROFILES]

        # then
        assert len(set(ids)) == len(ids)

    def test_build_id_matches_android_version(self) -> None:
        # when
        mismatched = [
            f"{p.id}={p.build_id}" for p in DEVICE_PROFILES if not p.build_id.startswith(BUILD_PREFIX[int(p.android)])
        ]

        # then
        assert mismatched == []

    def test_build_id_comes_from_the_table(self) -> None:
        # when
        off_table = [p.id for p in DEVICE_PROFILES if p.build_id != BUILD_ID[int(p.android)]]

        # then
        assert off_table == []

    def test_only_korean_unlocked_models(self) -> None:
        """통신사 전용(S/K/L)이나 아이폰이 섞이면 TLS 지문과 어긋납니다."""
        # when
        foreign = [p.model for p in DEVICE_PROFILES if not re.fullmatch(r"SM-[A-Z]\d{3}N", p.model)]

        # then
        assert foreign == []

    def test_every_model_is_represented(self) -> None:
        # when
        models = {profile.model for profile in DEVICE_PROFILES}

        # then
        assert len(models) == 38, "라운드로빈이라 모든 모델이 최소 1개씩 나와야 합니다"

    def test_catalog_model_definitions_are_deterministic(self) -> None:
        # given
        from pykorail.device.catalog import _build_catalog

        # when
        rebuilt = _build_catalog()

        # then
        assert [(p.id, p.marketing, p.model, p.android, p.build_id) for p in rebuilt] == [
            (p.id, p.marketing, p.model, p.android, p.build_id) for p in DEVICE_PROFILES
        ]

    def test_android_ids_are_distinct_and_valid(self) -> None:
        # when
        ids = [profile.android_id for profile in DEVICE_PROFILES]

        # then
        assert len(set(ids)) == CATALOG_SIZE
        assert [value for value in ids if re.fullmatch(r"[0-9a-f]{16}", value) is None] == []


class TestLookup:
    def test_android_id_participates_in_device_identity(self) -> None:
        # given
        original = replace(DEVICE_PROFILES[0], android_id="0123456789abcdef")

        # when
        another_device = replace(original, android_id="fedcba9876543210")

        # then
        assert original != another_device
        assert len({original, another_device}) == 2

    def test_restores_android_id_without_mutating_catalog(self) -> None:
        # given
        original = DEVICE_PROFILES[0]
        original_id = original.android_id

        # when
        restored = profile_by_id(original.id, android_id="0123456789abcdef")

        # then
        assert restored is not None
        assert restored.android_id == "0123456789abcdef"
        assert restored.model == original.model
        assert original.android_id == original_id
        assert profile_by_id(original.id) is original

    def test_finds_by_id(self) -> None:
        # given
        target = DEVICE_PROFILES[0]

        # when
        found = profile_by_id(target.id)

        # then
        assert found is target

    def test_unknown_id_returns_none(self) -> None:
        # when
        found = profile_by_id("nope-a99")

        # then
        assert found is None

    def test_none_returns_none(self) -> None:
        # when
        found = profile_by_id(None)

        # then
        assert found is None


class TestRandomProfile:
    def test_returns_a_catalog_member(self) -> None:
        # when
        profile = random_profile()

        # then
        assert profile in DEVICE_PROFILES

    def test_seeded_rng_is_reproducible(self) -> None:
        # when
        first = random_profile(random.Random(42))
        second = random_profile(random.Random(42))

        # then
        assert first == second


class TestUserAgent:
    def test_renders_all_three_fields(self) -> None:
        # given
        profile = DeviceProfile(
            id="s24u-a14",
            marketing="Galaxy S24 Ultra",
            model="SM-S928N",
            android="14",
            build_id="UP1A.231005.007",
        )

        # when
        agent = dalvik_user_agent(profile)

        # then
        assert agent == "Dalvik/2.1.0 (Linux; U; Android 14; SM-S928N Build/UP1A.231005.007)"

    @pytest.mark.parametrize("profile", DEVICE_PROFILES[:10])
    def test_catalog_profiles_render(self, profile: DeviceProfile) -> None:
        # when
        agent = dalvik_user_agent(profile)

        # then
        assert agent.startswith("Dalvik/2.1.0 (Linux; U; Android ")
        assert profile.model in agent
        assert profile.build_id in agent

    def test_accepts_any_structurally_compatible_object(self) -> None:
        """DeviceProfileLike 는 프로토콜이라 외부 프로파일도 그대로 받습니다."""

        # given
        class ForeignProfile:
            model = "SM-S921N"
            android = "15"
            build_id = "AP3A.240905.015.A2"
            chrome = "131.0.6778.85"  # KTX 에는 쓰이지 않는 여분 필드

        # when
        agent = dalvik_user_agent(ForeignProfile())

        # then
        assert "SM-S921N" in agent
