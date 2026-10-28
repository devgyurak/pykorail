"""DynaPath v2 선언 토큰(:class:`DeclarationDynaPathEngine`) 회귀 테스트.

세 종류의 기준점이 있습니다(근거: ``docs/protocol-evidence-7.0.10.json``):
- ``_NATIVE_RECORDED``: 기록된 ``.so`` 에뮬 출력 r0(nonce=0)·r1(nonce=5)을 패키지 코덱이
  **바이트 동일로 재인코딩**하는지 — 키스트림 ``LE32(nonce)‖BE32(block)`` 을 못박습니다
  (r1 의 nonce=5 가 엔디언을 고정). 원본 캡처 토큰은 저장소 정책상 넣지 않습니다.
- ``_GOLDEN_ENGINE_SNAPSHOT``/``_GOLDEN_APK_SHAPE``: 엔진 출력 회귀 스냅샷(자체 생성).
나머지는 프리픽스·문자셋·요청별 변화·기기 사실 반영을 검증합니다.
"""

from __future__ import annotations

import hashlib

import pytest

from pykorail.auth.dynapath import (
    _V2_ALPHABET,
    _V2_SECRET_HEX,
    DeclarationDynaPathEngine,
    _sdk_for,
    _v2_b62_word,
    _v2_keystream,
    _v2_width,
)
from pykorail.constants import TOKEN_PREFIX
from pykorail.device import DeviceProfile

INIT_MS = 1_700_000_000_000

#: 기록된 네이티브 ``.so`` 에뮬레이터 출력(``cipher_capture.json`` r0·r1). **같은 평문 봉투**를
#: nonce=0 과 **nonce=5** 로 돌린 두 토큰이라, 키스트림의 ``LE32(nonce)‖BE32(block)`` 카운터를
#: 유일하게 검증 가능한 방식으로 못박는다(옛 ``BE_u64(nonce+i)`` 는 r1 에서 깨진다). 튜플: (nonce, 평문, 토큰).
_NATIVE_RECORDED = [
    (
        0,
        "!v=2&es=533034890897565508&ts=1700000000000&st=Android&sv=2.0.1&ai=korailplus&os=UkVM&dm=TU9ERUxBQUFB&iid=AAAAAAAAAAAAAAAAAAAAAA&mf=TUZS&bd=QkQ&sl=34&sb=1&kl=990094375841594426&ec=978212327729758430",
        "201TTTTTTTMTySkTo5b6SF5Wbj6OdDzSReArGZDTYBNd4TTemDJufGckCFrEPrHOONjqHOVSbHVThY2hcTW1YypeNt6naetn4MouFBF2GeMPUjWeQHWBLuwLZ2wOqdSqduC6SYNuCD0ANu1iiVFTQoFZbeQwAqjFSSYr9en194iOih5PheHPfoNFJDuUETK8mBEe8DONDFhk1tkeXjhLXepVii4OwEZ60FS13HMTZCRNqOJqjilOUdf9eTTus3OOPoiTEOqQ5xyFRJ5GhOa56pDe2vbedebeu4AeI9xP6TPxA1te7kWwdec",
    ),
    (
        5,
        "!v=2&es=533034890897565508&ts=1700000000000&st=Android&sv=2.0.1&ai=korailplus&os=UkVM&dm=TU9ERUxBQUFB&iid=AAAAAAAAAAAAAAAAAAAAAA&mf=TUZS&bd=QkQ&sl=34&sb=1&kl=990094375841594426&ec=978212327729758430",
        "201TQWIimOZGMLEF7YQycum3XezTPMASAuOv0WVuWNaECejOWsZFWdUpZFP26avTXYrVSFo4R44TKOr8tOjGkgOTSzeanOeeVIST8Jo3HFzzvS1OzTn6gegPgAjTYLUsVeQ90YrFLaFbduUIbJ5eC7TyhuYbDSYTfOsisOWXiLWuQeGQITzpW1QT60QgcFl3rWxTOYk91uwoygCOwqhu3ewFBfxev3qLUeb9SQdT9Lm4KTUrpOeOAp4nIFL3FoDFSJ7PGTtJpRAF6bN4zOmYNH6eAjgvgujLobOFdbhZHFROebKe1GVLLFR",
    ),
]


def _encode(nonce: int, plaintext: bytes) -> str:
    """패키지 코덱으로 평문 봉투를 토큰으로 인코딩(_build 의 암호화 단계와 동일) — 키스트림을 실제로 탄다."""
    eor = bytes(p ^ k for p, k in zip(plaintext, _v2_keystream(len(plaintext), nonce), strict=True))
    mac3 = hashlib.sha256(_V2_SECRET_HEX + nonce.to_bytes(4, "little") + eor).digest()[:3]
    buffer = nonce.to_bytes(4, "little") + mac3 + eor
    words = [buffer[i : i + 4] for i in range(0, len(buffer), 4)]
    return TOKEN_PREFIX + "".join(_v2_b62_word(int.from_bytes(w, "big"), _v2_width(len(w))) for w in words)


@pytest.mark.parametrize(("nonce", "plaintext", "token"), _NATIVE_RECORDED)
def test_codec_matches_native_recorded(nonce: int, plaintext: str, token: str) -> None:
    """기록된 .so 에뮬 출력(r0 nonce=0 / r1 nonce=5)을 패키지 코덱이 바이트 동일로 재현한다."""
    # when
    encoded = _encode(nonce, plaintext.encode("latin1"))

    # then
    assert encoded == token


def _declaration_engine(nonce: int | None = 0) -> DeclarationDynaPathEngine:
    """테스트용 기본 선언 엔진(공통 기기 사실 + 고정 nonce)."""
    return DeclarationDynaPathEngine(
        release=b"REL", model=b"MODELAAAA", manufacturer=b"MFR", board=b"BD", sdk_int=34, strongbox=1, nonce=nonce
    )


#: **엔진 출력 스냅샷(자체 생성, 네이티브 미기록).** 엔진이 주어진 입력에 같은 토큰을 내는지
#: 회귀로 고정한다. 코덱의 네이티브 정합성은 ``_NATIVE_RECORDED``(기록된 .so 에뮬 출력 r0·r1,
#: nonce 0·5)가 못박고, 이 목록 자체는 그 코덱으로 생성한 값이라 네이티브 근거가 아니다.
#: 튜플: (엔진, op_id, device_id, ts_ms, 기대 토큰).
_GOLDEN_ENGINE_SNAPSHOT = [
    (
        DeclarationDynaPathEngine(
            release=b"REL",
            model=b"MODELAAAA",
            manufacturer=b"MFR",
            board=b"BD",
            sdk_int=34,
            strongbox=1,
            android_id=bytes(16),
            nonce=0,
        ),
        288904575606514493,
        "",
        1_700_000_000_000,
        "201TTTTTTecNsflTo5b6SF5Wbj4OXY5BleAXmQ8TcFFv5TxI8SEuAeiW1FrEPrHOONjqHOVSbHVThY2hcTW1YypeNt6naetn4MouFBF2GeMPUjWeQHWBLuwLZ2wOqdSqduC6SYNuCD0ANu1iiVFTQoFZbeQwAqjFSSYr9en194iOih5PheHPfoNFJDuUETK8mBEe8DONDFhk1tkeXjhLXepVii4OwEZ60FS13HMTZCRNqOJqjilOUdf9eTTus3OOPoiTEOqQ5xyFRJ5GhOa56pDe2vbedebeu4AeI9xP6TPxA1te7kWwdec",
    ),
    (
        DeclarationDynaPathEngine(
            release=b"14",
            model=b"Pixel 7",
            manufacturer=b"Google",
            board=b"panther",
            sdk_int=34,
            strongbox=0,
            android_id=bytes(range(1, 17)),
            nonce=0,
        ),
        288904575606514493,
        "",
        1_733_999_999_999,
        "201TTTTTTu3OoETTo5b6SF5Wbj4OXY5BleAXmQ8TcFFv5TxI8SEuAeiW1FrEPrqOFzWczOXSOEDT2SCihTW1YypeNt6naetn4MouFBF2GeMPUjWeQHWBLuwLZ2wOqdSqduC6SYNum2gkhFPGn0zTCjLleejLS9JehK5tQTZvUqbOwnvhvecWTdyOpwVFneqql31eBaZbYuyvHCyeNth3Rew1LcouAMmRqF1MmS3TgotIkFgJyjwuCOeNST5OtFTOPDqBpOOYv9RFqVvgsOVpa0tTHCw4peZdFKbeQl2GwTPqHF0egfEGOedL5a2OVLxVHuu",
    ),
    (
        DeclarationDynaPathEngine(
            release=b"13",
            model=b"SM-S911N",
            manufacturer=b"samsung",
            board=b"kalama",
            sdk_int=33,
            strongbox=1,
            android_id=b"\xaa" * 16,
            nonce=0,
        ),
        288904575606514493,
        "",
        42,
        "201TTTTTTOW01JPTo5b6SF5Wbj4OXY5BleAXmQ8TcFFv5TxI8SEuAeiW1Fr2NI8uU48PjFh0WIvFUnO7hTGvqNUTeXh9ieccFSIFiK9XzTdVLUiTiDTcDOu6pKyuizlGsF3U7TquC2dMbFtLHIreO7UwLTCY0cNe0aX6yeqNKhBF5yNSkFB31byOU7js8TZbVTueCqKQZFbGRk4ThkryaFUYvGcFfb7oETP1x0HF1cS6KF9WT71uLWDpYTu9zvYO6FEhAFMd9nTFYMsDmObRdJVTjJEFberWjO5eIgevOexLZ4gTvKmQ",
    ),
]

#: **APK 모양 회귀 스냅샷(자체 생성, 네이티브 미대조).** 실제 서명 경로 모양(device_id 16자리
#: 16진수 → ``iid`` ASCII 16바이트, es=288904575606514493 소프트웨어 선언 op)을 고정합니다.
#: 위 _GOLDEN_ENGINE_SNAPSHOT 가 코덱을 네이티브에 못박았으므로, 이쪽은 **입력→토큰 매핑이 production
#: 모양대로 유지되는지**만 지킵니다(이 특정 입력으로 .so 를 돌린 기록은 없음). 3번째는 코덱이
#: 다른 선언 op(674926635053674478)도 싣는지 확인용입니다.
#: 튜플: (엔진, op_id, device_id(16자리 16진수), ts_ms, 기대 토큰).
_GOLDEN_APK_SHAPE = [
    (
        _declaration_engine(nonce=0),
        288904575606514493,
        "0123456789abcdef",
        1_700_000_000_000,
        "201TTTTTTOm4UruTo5b6SF5Wbj4OXY5BleAXmQ8TcFFv5TxI8SEuAeiW1FrEPrHOONjqHOVSbHVThY2hcTW1YypeNt6naetn4MouFBF2GeMPUjWeQHWBLuwLZ2wOqdSqduC6SYNuCD0ANu1iiVFTQoFZbeQwAqjFSSYr9en194iOiWbYfFKcTiSu3NKWVFU6Y46eZrmkVOT1zKDeXjhLXepVii4OwEZ60FS13HMTZCRNqOJqjilOUdf9eTTus3OOPoiTEOqQ5xyFRJ5GhOa56pDe2vbedebeu4AeI9xP6TPxA1te7kWwdec",
    ),
    (
        DeclarationDynaPathEngine(
            release=b"14", model=b"SM-S911N", manufacturer=b"samsung", board=b"kalama", sdk_int=35, strongbox=1, nonce=0
        ),
        288904575606514493,
        "fedcba9876543210",
        1_733_999_999_999,
        "201TTTTTTFMG4OjTo5b6SF5Wbj4OXY5BleAXmQ8TcFFv5TxI8SEuAeiW1FrEPrqOFzWczOXSOEDT2SCihTW1YypeNt6naetn4MouFBF2GeMPUjWeQHWBLuwLZ2wOqdSqduC6SYNum2gkhFPGn0zeEVYCtT8hTBSFwJ7erT7pnu1F7O35tTJWwAyFt0toPTGbfNAFBkAEhFidgZZeu9zA5FTOg57OuWzqRFRkRXKFjg94EOTKGWiu8ctwvT11lYSOMIITNuoyliuFqZPYzOrn6rbTkVYvgeZdcQBFUhsktexL4WAe9GCUkedA1u9Od7orBye2",
    ),
    (
        DeclarationDynaPathEngine(
            release=b"15",
            model=b"SM-S928N",
            manufacturer=b"samsung",
            board=b"pineapple",
            sdk_int=35,
            strongbox=0,
            nonce=7,
        ),
        674926635053674478,
        "00112233445566ff",
        42,
        "201TxPEgbeIYspYuKnUGtu3EUtUTPAKzBFAiWcITZ9DrWuS480nuvFjH1OPmkptT4MuGRT9asRQTSAtLNOYxa5LOTBSpjOfvtWPedJiEHFCvYC5edTvlHToOBNLOtGcIiFfDhWtuFJMxdOai50zeNMHRwO7WZqYFd4e6WFYKuTLe3bItNOfE8PheJsNx8FuX5J0uAqOQmT6nYE6F6qf5TORGGT8TM5LmeFbadGpOn8vFLuAmIDxuyuKH9OnNPhEOIV7GHeOhC2pFGu9rnFZuZGRTNGxSUFITFgYewysdGO4vn9aecLPBdTzEpO",
    ),
]


@pytest.mark.parametrize(("engine", "op_id", "device_id", "ts_ms", "expected"), _GOLDEN_ENGINE_SNAPSHOT)
def test_declaration_engine_output_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    engine: DeclarationDynaPathEngine,
    op_id: int,
    device_id: str,
    ts_ms: int,
    expected: str,
) -> None:
    """엔진이 같은 입력에 같은 토큰을 내는지(자체 스냅샷) 고정합니다 — 네이티브 근거는 _NATIVE_RECORDED."""
    # given
    monkeypatch.setattr("pykorail.auth.dynapath.time.time", lambda: ts_ms / 1000)

    # when
    token = engine.generate_token(op_id=op_id, device_id=device_id)

    # then
    assert token == expected


@pytest.mark.parametrize(("engine", "op_id", "device_id", "ts_ms", "expected"), _GOLDEN_APK_SHAPE)
def test_declaration_engine_apk_shape_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    engine: DeclarationDynaPathEngine,
    op_id: int,
    device_id: str,
    ts_ms: int,
    expected: str,
) -> None:
    """실제 서명 경로 모양(iid=ASCII16, es=선언 op)의 입력→토큰 매핑을 고정합니다(자체 스냅샷)."""
    # given
    monkeypatch.setattr("pykorail.auth.dynapath.time.time", lambda: ts_ms / 1000)

    # when
    token = engine.generate_token(op_id=op_id, device_id=device_id)

    # then
    assert token == expected


def test_declaration_token_has_version_prefix() -> None:
    # when
    token = _declaration_engine().generate_token(op_id=288904575606514493, device_id="0123456789abcdef")

    # then
    assert token.startswith(TOKEN_PREFIX)


def test_declaration_body_uses_native_base62_alphabet() -> None:
    # when
    token = _declaration_engine().generate_token(op_id=288904575606514493, device_id="0123456789abcdef")

    # then
    assert set(token) <= set(_V2_ALPHABET)


def test_fixed_nonce_is_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    # given
    monkeypatch.setattr("pykorail.auth.dynapath.time.time", lambda: INIT_MS / 1000)
    engine = _declaration_engine(nonce=0)

    # when
    first = engine.generate_token(op_id=288904575606514493, device_id="0123456789abcdef")
    second = engine.generate_token(op_id=288904575606514493, device_id="0123456789abcdef")

    # then
    assert first == second


def test_random_nonce_varies_between_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """nonce=None 이면 시각이 같아도 요청마다 토큰이 달라집니다(실제 앱 동작)."""
    # given
    monkeypatch.setattr("pykorail.auth.dynapath.time.time", lambda: INIT_MS / 1000)
    engine = _declaration_engine(nonce=None)

    # when
    first = engine.generate_token(op_id=288904575606514493, device_id="0123456789abcdef")
    second = engine.generate_token(op_id=288904575606514493, device_id="0123456789abcdef")

    # then
    assert first != second


def test_device_id_flows_into_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """device_id(android_id)가 iid 로 들려 토큰이 달라집니다 — 기본 엔진과 달리 기기 신원이 실립니다."""
    # given
    monkeypatch.setattr("pykorail.auth.dynapath.time.time", lambda: INIT_MS / 1000)
    engine = _declaration_engine(nonce=0)

    # when
    one = engine.generate_token(op_id=288904575606514493, device_id="0123456789abcdef")
    other = engine.generate_token(op_id=288904575606514493, device_id="ffeeddccbbaa9988")

    # then
    assert one != other


def test_declaration_token_with_timestamp_returns_sampled_time(monkeypatch: pytest.MonkeyPatch) -> None:
    # given
    monkeypatch.setattr("pykorail.auth.dynapath.time.time", lambda: (INIT_MS + 1234) / 1000)

    # when
    token, timestamp = _declaration_engine().generate_token_with_timestamp(
        op_id=288904575606514493, device_id="0123456789abcdef"
    )

    # then
    assert timestamp == INIT_MS + 1234
    assert token.startswith(TOKEN_PREFIX)


def test_default_engine_constructs_without_args(monkeypatch: pytest.MonkeyPatch) -> None:
    """인자 없이도 현행 플래그십 기본값으로 선언 토큰을 냅니다(프로파일 없는 Korail 경로)."""
    # given
    monkeypatch.setattr("pykorail.auth.dynapath.time.time", lambda: INIT_MS / 1000)
    engine = DeclarationDynaPathEngine(nonce=0)

    # when
    token = engine.generate_token(op_id=288904575606514493, device_id="0123456789abcdef")

    # then
    assert token.startswith(TOKEN_PREFIX)
    assert set(token) <= set(_V2_ALPHABET)


def test_from_profile_pulls_model_release_and_sdk() -> None:
    # given
    profile = DeviceProfile(
        id="x",
        marketing="Galaxy S24",
        model="SM-S921N",
        android="14",
        build_id="UP1A.231005.007",
        android_id="0123456789abcdef",
    )

    # when
    engine = DeclarationDynaPathEngine.from_profile(profile)

    # then
    assert (engine.model, engine.release, engine.sdk_int) == (b"SM-S921N", b"14", 34)


@pytest.mark.parametrize(
    ("android", "expected"),
    [("13", 33), ("16", 36), ("17", 37), ("12", 31), ("10", 29), ("9", 35), ("foo", 35)],
)
def test_sdk_for_maps_known_extrapolates_13plus_and_falls_back(android: str, expected: int) -> None:
    """알려진 버전은 표로, 13+ 미지 버전은 +20 외삽, 그 밖은 현행 기본값(35)."""
    # when & then
    assert _sdk_for(android) == expected


def test_rejects_out_of_range_nonce() -> None:
    # when & then
    with pytest.raises(ValueError, match="nonce"):
        DeclarationDynaPathEngine(nonce=2**32)
