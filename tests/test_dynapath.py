"""DynaPath 서명 회귀 테스트.

고정 토큰 전체와 독립 역디코더로 합성 입력의 필드·순서·시간 이력을 확인합니다.
원본 Android SDK 실행 결과나 실서버 수용 여부를 검증하는 테스트는 아닙니다.
"""

from __future__ import annotations

from urllib.parse import parse_qsl

import pytest

from pykorail.auth.dynapath import _TABLE, DynaPathMasterEngine, _url_encode
from pykorail.device import DeviceProfile
from tests.dynapath_decoder import decode_token

INIT_MS = 1_700_000_000_000


@pytest.fixture
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pykorail.auth.dynapath.time.time", lambda: INIT_MS / 1000)


@pytest.fixture
def engine(fixed_clock: None) -> DynaPathMasterEngine:
    return DynaPathMasterEngine()


def test_first_token_matches_v1_0_3_golden(engine: DynaPathMasterEngine) -> None:
    """APK 분석을 반영한 Python 구현의 회귀 기준이며 SDK 실행 산출물은 아닙니다."""
    # when
    token = engine.generate_token("fixture-device", INIT_MS + 1234, "aB12")

    # then: 2026-09-23 합성 입력의 전체 출력. 디코더와 별개로 바이트 변경을 검출합니다.
    assert token == (
        "bEeEPLYj144a44lDf3CMM4Pv4ff4GR4GR4GR4GDK3FFmwPy4agG13F3YG19wPyG4RgvdGYCkKFfvEf3KMwJMqMfuEfaqMkdwjgkKCgGk"
        "kg34vK3umfDyDanwjwDCYwdRfaaw5YfuM3ykF1mw5nwm9DEqwjffuFDEMkKdg1mf3GGYYfuDw1mfPjf3GGYYfuDfCgg1mf3GGYYfuDf"
        "MM4adwPCggEkKYgjwFjjFGkFGkFGkFGkFGkFfJgJ431aDJdFGkFGkFGkFjGDCYkKlgjwFjGDCYkKGgGkFjgkKFGwaPmaFRF3nw3u"
        "RkKdgjw4l9faPG1kwKmgMu4qDFj9FGRqM"
    )


def test_fresh_engines_match_for_same_inputs(engine: DynaPathMasterEngine) -> None:
    # given
    fresh = DynaPathMasterEngine()

    # when
    first = engine.generate_token("fixture-device", INIT_MS + 1234, "aB12")
    second = fresh.generate_token("fixture-device", INIT_MS + 1234, "aB12")

    # then
    assert first == second
    assert decode_token(first) == (
        f"v1.0.3+aB12+{INIT_MS + 1234}",
        "ai=com.korail.talk&di=fixture-device&as=%5B38ff229cb34c7dda8e28220a2d750cce%5D&"
        f"su=false&dbg=false&emu=false&hk=false&it={INIT_MS}&ts={INIT_MS + 1234}&rt=1234&"
        "os=13&dm=SM-S928N&st=Android&sv=v1.0.3",
    )


def test_repeated_input_updates_same_engine_history(engine: DynaPathMasterEngine) -> None:
    # given
    first = engine.generate_token("fixture-device", INIT_MS + 1234, "aB12")

    # when
    second = engine.generate_token("fixture-device", INIT_MS + 1234, "aB12")

    # then
    assert second != first
    assert [value for key, value in parse_qsl(decode_token(second)[1]) if key == "rt"] == ["1234", "0"]


def test_clock_sampled_token_matches_explicit_timestamp(
    engine: DynaPathMasterEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    # given
    fresh = DynaPathMasterEngine()
    expected = engine.generate_token("fixture-device", INIT_MS + 1234, "aB12")
    monkeypatch.setattr("pykorail.auth.dynapath.time.time", lambda: (INIT_MS + 1234) / 1000)

    # when
    token, timestamp = fresh.generate_token_with_timestamp("fixture-device", "aB12")

    # then
    assert timestamp == INIT_MS + 1234
    assert token == expected


@pytest.mark.parametrize("nonce", ["\0ABC", "A\0BC", "ABC\0"])
def test_decoder_handles_nul_key_reset(engine: DynaPathMasterEngine, nonce: str) -> None:
    """일반 논스에는 없는 NUL로 역디코더의 원시연산 경계를 확인합니다."""
    # when
    token = engine.generate_token("fixture-device", INIT_MS + 1234, nonce)

    # then
    key, payload = decode_token(token)
    assert key == f"v1.0.3+{nonce}+{INIT_MS + 1234}"
    assert dict(parse_qsl(payload))["di"] == "fixture-device"


@pytest.mark.parametrize(
    ("offsets", "expected"),
    [
        ([1234], ["1234"]),
        ([1234, 1234], ["1234", "0"]),
        ([1000, 900], ["1000", "-100"]),
        ([100, 300, 600, 1000, 1500], ["100", "200", "300", "400", "500"]),
        ([100, 300, 600, 1000, 1500, 2100, 2800], ["300", "400", "500", "600", "700"]),
    ],
)
def test_recent_intervals_follow_generation_history(
    engine: DynaPathMasterEngine, offsets: list[int], expected: list[str]
) -> None:
    # when
    tokens = [engine.generate_token("fixture-device", INIT_MS + offset, "aB12") for offset in offsets]

    # then
    fields = parse_qsl(decode_token(tokens[-1])[1])
    assert [value for key, value in fields if key == "rt"] == expected
    assert dict(fields)["ts"] == str(INIT_MS + offsets[-1])


def test_new_engine_resets_history(engine: DynaPathMasterEngine, monkeypatch: pytest.MonkeyPatch) -> None:
    # given
    engine.generate_token("fixture-device", INIT_MS + 1000, "aB12")
    monkeypatch.setattr("pykorail.auth.dynapath.time.time", lambda: (INIT_MS + 2000) / 1000)
    fresh = DynaPathMasterEngine()

    # when
    token = fresh.generate_token("fixture-device", INIT_MS + 2500, "aB12")

    # then
    fields = parse_qsl(decode_token(token)[1])
    assert dict(fields)["it"] == str(INIT_MS + 2000)
    assert [value for key, value in fields if key == "rt"] == ["500"]


def test_java_form_encoding_preserves_field_boundaries(fixed_clock: None) -> None:
    # given
    engine = DynaPathMasterEngine(device_model="fixture 한글/~*", os_version="14+test")

    # when
    token = engine.generate_token("device &di=+%~*", INIT_MS + 100, "aB12")

    # then
    payload = decode_token(token)[1]
    assert "di=device+%26di%3D%2B%25%7E*&" in payload
    assert "os=14%2Btest&dm=fixture+%ED%95%9C%EA%B8%80%2F%7E*&" in payload
    assert [value for key, value in parse_qsl(payload) if key == "di"] == ["device &di=+%~*"]
    assert "%255B" not in payload


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("\ud800", "%3F"),
        ("\udfff", "%3F"),
        ("\ufffd", "%EF%BF%BD"),
        ("\U0001f600", "%F0%9F%98%80"),
        ("한글 /~*", "%ED%95%9C%EA%B8%80+%2F%7E*"),
    ],
)
def test_url_encoding_matches_java_boundary_values(value: str, expected: str) -> None:
    """기대값은 로컬 Java URLEncoder.encode(UTF_8)로 확인했습니다."""
    # when
    encoded = _url_encode(value)

    # then
    assert encoded == expected


def test_token_prefix_and_length_marker(engine: DynaPathMasterEngine) -> None:
    """토큰은 ``bEeEP`` + 키 길이를 나타내는 테이블 문자로 시작합니다."""
    # when
    token = engine.generate_token("558a4f02041657ea", 1700000001234, "AB12")

    # then
    assert token.startswith("bEeEP")
    length_marker = token[5]
    assert length_marker in _TABLE
    # 마커가 가리키는 길이만큼이 키 파트, 나머지가 본문 파트입니다.
    assert len(token) > 6 + _TABLE.index(length_marker)


def test_nonce_changes_the_token(engine: DynaPathMasterEngine) -> None:
    # given
    fresh = DynaPathMasterEngine()

    # when
    first = engine.generate_token("dev", 1700000001234, "AAAA")
    second = fresh.generate_token("dev", 1700000001234, "BBBB")

    # then
    assert first != second


def test_timestamp_changes_the_token(engine: DynaPathMasterEngine) -> None:
    # when
    first = engine.generate_token("dev", 1700000001234, "AAAA")
    second = engine.generate_token("dev", 1700000009999, "AAAA")

    # then
    assert first != second


def test_default_engine_signs_as_the_documented_device() -> None:
    # when
    engine = DynaPathMasterEngine()

    # then
    assert engine.device_model == "SM-S928N"
    assert engine.os_version == "13"


def test_profile_drives_the_signature() -> None:
    # given
    profile = DeviceProfile(
        id="s21-a15",
        marketing="Galaxy S21",
        model="SM-G991N",
        android="15",
        build_id="AP3A.240905.015.A2",
    )

    # when
    engine = DynaPathMasterEngine.from_profile(profile)

    # then
    assert engine.device_model == "SM-G991N"
    assert engine.os_version == "15"


def test_from_profile_without_profile_matches_defaults(fixed_clock: None) -> None:
    """프로파일 미주입 시 서명은 기본 엔진과 동일해야 합니다."""
    # given
    injected = DynaPathMasterEngine.from_profile(None)
    default = DynaPathMasterEngine()

    # when
    from_injected = injected.generate_token("dev", 1700000001234, "AAAA")
    from_default = default.generate_token("dev", 1700000001234, "AAAA")

    # then
    assert from_injected == from_default


def test_encode_handles_empty_input() -> None:
    # when
    encoded = DynaPathMasterEngine._encode("", _TABLE)

    # then
    assert encoded == ""


def test_encode_handles_multibyte_input() -> None:
    """한글은 3바이트 경로를 타므로 인코딩이 죽지 않는지 확인합니다."""
    # when
    encoded = DynaPathMasterEngine._encode("서울역", _TABLE)

    # then
    assert encoded


def test_build_table_produces_a_permutation() -> None:
    # when
    table = DynaPathMasterEngine._build_table(123456789, 30, _TABLE)

    # then
    assert len(table) == 30
    assert len(set(table)) == 30, "커스텀 테이블에 중복 문자가 있으면 디코딩이 깨집니다"
    assert set(table) <= set(_TABLE)
