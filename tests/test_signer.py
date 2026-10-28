"""실제 전송 없이 서명 경로 배선과 기기 ID 보관을 검증합니다."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from pykorail.auth.signer import _DEFAULT_OP_ID, RequestSigner, _op_id_for
from pykorail.constants import API_ENDPOINTS, DYNAPATH_LOGIN_OP, TOKEN_PREFIX
from pykorail.crypto import encrypt_sid
from pykorail.device import DEVICE_PROFILES, profile_by_id

INIT_MS = 1_700_000_000_000
SYNTHETIC_SID_KEY = b"0123456789abcdef"
#: 기본 선언 엔진은 device_id(android_id) 문자열을 ASCII 16바이트로 인코딩해 ``iid`` 로 씁니다 —
#: 테스트 픽스처도 실제 계약대로 16자리 소문자 16진수를 씁니다.
FIXTURE_DEVICE_ID = "0123456789abcdef"


def test_sid_can_be_omitted_without_encrypting(monkeypatch: pytest.MonkeyPatch) -> None:
    # given
    encrypt = Mock(side_effect=AssertionError("Sid가 필요 없는 요청입니다"))
    monkeypatch.setattr("pykorail.auth.signer.encrypt_sid", encrypt)
    signer = RequestSigner(device_id=FIXTURE_DEVICE_ID)

    # when
    headers, sid = signer.sign(API_ENDPOINTS["login"], include_sid=False)

    # then
    assert "x-dynapath-m-token" in headers
    assert sid is None
    encrypt.assert_not_called()


def test_login_path_carries_a_dynapath_header() -> None:
    # given
    signer = RequestSigner(device_id=FIXTURE_DEVICE_ID)

    # when
    headers, _ = signer.sign(API_ENDPOINTS["login"], include_sid=False)

    # then
    assert headers["x-dynapath-m-token"].startswith(TOKEN_PREFIX)


def test_unsigned_path_returns_no_material() -> None:
    # given
    signer = RequestSigner(device_id=FIXTURE_DEVICE_ID)

    # when & then
    assert signer.sign(API_ENDPOINTS["stationdata"]) == ({}, None)


@pytest.mark.parametrize("endpoint", ["login", "search_schedule"])
def test_signed_endpoints_emit_a_prefixed_token(endpoint: str) -> None:
    """로그인·조회 모두 DynaPath 경로라 ``201`` 프리픽스 선언 토큰을 싣습니다."""
    # given
    signer = RequestSigner(device_id=FIXTURE_DEVICE_ID)

    # when
    headers, _ = signer.sign(API_ENDPOINTS[endpoint], include_sid=False)

    # then
    assert headers["x-dynapath-m-token"].startswith(TOKEN_PREFIX)


def test_sid_uses_the_token_timestamp(monkeypatch: pytest.MonkeyPatch) -> None:
    # given
    monkeypatch.setattr("pykorail.auth.dynapath.time.time", lambda: INIT_MS / 1000)
    signer = RequestSigner(device_id=FIXTURE_DEVICE_ID, sid_key=SYNTHETIC_SID_KEY)

    # when
    _, sid = signer.sign(API_ENDPOINTS["search_schedule"])

    # then
    assert sid == encrypt_sid("AD", INIT_MS, SYNTHETIC_SID_KEY)


def test_repeated_signing_varies_the_token() -> None:
    # given
    signer = RequestSigner(device_id=FIXTURE_DEVICE_ID)

    # when
    first, _ = signer.sign(API_ENDPOINTS["search_schedule"])
    second, _ = signer.sign(API_ENDPOINTS["search_schedule"])

    # then
    assert first["x-dynapath-m-token"] != second["x-dynapath-m-token"]


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        ("login", DYNAPATH_LOGIN_OP),
        ("search_schedule", _DEFAULT_OP_ID),
        ("reserve", _DEFAULT_OP_ID),
    ],
)
def test_op_id_is_chosen_by_endpoint(endpoint: str, expected: int) -> None:
    # when
    op_id = _op_id_for(API_ENDPOINTS[endpoint])

    # then
    assert op_id == expected


def test_profile_id_is_reused_across_signers() -> None:
    # given
    profile = profile_by_id(DEVICE_PROFILES[0].id, android_id="0123456789abcdef")

    # when
    ids = [RequestSigner(profile).android_id for _ in range(2)]

    # then
    assert ids == ["0123456789abcdef", "0123456789abcdef"]


def test_different_profiles_keep_different_ids() -> None:
    # given
    profiles = DEVICE_PROFILES[:2]

    # when
    ids = [RequestSigner(profile).android_id for profile in profiles]

    # then
    assert ids == [profile.android_id for profile in profiles]
    assert len(set(ids)) == 2


def test_explicit_signer_id_overrides_profile_id() -> None:
    # when
    signer = RequestSigner(DEVICE_PROFILES[0], device_id="ffffffffffffffff")

    # then
    assert signer.android_id == "ffffffffffffffff"


def test_invalid_explicit_device_id_is_rejected_early() -> None:
    """잘못된 device_id 는 sign() 이 아니라 생성 시점에 명확히 걸립니다."""
    # when & then
    with pytest.raises(ValueError, match="android_id"):
        RequestSigner(device_id="not-hex")


def test_legacy_foreign_profile_gets_one_id_per_signer(monkeypatch: pytest.MonkeyPatch) -> None:
    # given
    class ForeignProfile:
        model = "SM-S921N"
        android = "15"
        build_id = "AP3A.240905.015.A2"

    generate = Mock(return_value="0123456789abcdef")
    monkeypatch.setattr("pykorail.auth.signer.generate_android_id", generate)

    # when
    signer = RequestSigner(ForeignProfile())
    signer.sign(API_ENDPOINTS["login"])
    signer.sign(API_ENDPOINTS["login"])

    # then
    generate.assert_called_once_with()
    assert signer.android_id == "0123456789abcdef"


def test_default_signer_generates_id_once(monkeypatch: pytest.MonkeyPatch) -> None:
    # given
    generate = Mock(return_value="0123456789abcdef")
    monkeypatch.setattr("pykorail.auth.signer.generate_android_id", generate)

    # when
    signer = RequestSigner()

    # then
    assert signer.android_id == "0123456789abcdef"
    generate.assert_called_once_with()


class _FixedEngine:
    """토큰을 고정값으로 돌려주는 주입용 엔진(DynaPathEngine 계약)."""

    def generate_token_with_timestamp(self, *, request_bound: bool, op_id: int, device_id: str) -> tuple[str, int]:
        return "201-INJECTED", 0


class _RecordingEngine:
    """서명기가 어떤 인자로 엔진을 호출하는지 기록합니다."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate_token_with_timestamp(self, *, request_bound: bool, op_id: int, device_id: str) -> tuple[str, int]:
        self.calls.append({"request_bound": request_bound, "op_id": op_id, "device_id": device_id})
        return "201x", 0


def test_injected_engine_replaces_the_default() -> None:
    # given
    signer = RequestSigner(device_id=FIXTURE_DEVICE_ID, engine=_FixedEngine())

    # when
    headers, _ = signer.sign(API_ENDPOINTS["search_schedule"], include_sid=False)

    # then
    assert headers["x-dynapath-m-token"] == "201-INJECTED"


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        ("login", {"request_bound": True, "op_id": DYNAPATH_LOGIN_OP, "device_id": FIXTURE_DEVICE_ID}),
        ("search_schedule", {"request_bound": False, "op_id": _DEFAULT_OP_ID, "device_id": FIXTURE_DEVICE_ID}),
    ],
)
def test_engine_receives_endpoint_binding_op_id_and_device_id(endpoint: str, expected: dict[str, object]) -> None:
    """주입 엔진은 봉투를 채우는 데 필요한 op_id·device_id·요청바인딩을 받습니다."""
    # given
    engine = _RecordingEngine()
    signer = RequestSigner(device_id=FIXTURE_DEVICE_ID, engine=engine)

    # when
    signer.sign(API_ENDPOINTS[endpoint], include_sid=False)

    # then
    assert engine.calls == [expected]
