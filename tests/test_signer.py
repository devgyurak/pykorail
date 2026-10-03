"""실제 전송 없이 서명 시각과 동시 호출 이력을 검증합니다."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
from urllib.parse import parse_qsl

import pytest

from pykorail.auth.signer import RequestSigner
from pykorail.constants import API_ENDPOINTS
from pykorail.crypto import encrypt_sid
from pykorail.device import DEVICE_PROFILES, profile_by_id
from tests.dynapath_decoder import decode_token
from tests.signing_support import ReverseFirstTwoLock

INIT_MS = 1_700_000_000_000
SYNTHETIC_SID_KEY = b"0123456789abcdef"


def test_sid_can_be_omitted_without_encrypting(monkeypatch: pytest.MonkeyPatch) -> None:
    # given
    encrypt = Mock(side_effect=AssertionError("Sid가 필요 없는 요청입니다"))
    monkeypatch.setattr("pykorail.auth.signer.encrypt_sid", encrypt)
    signer = RequestSigner(device_id="fixture-device")

    # when
    headers, sid = signer.sign(API_ENDPOINTS["login"], include_sid=False)

    # then
    assert "x-dynapath-m-token" in headers
    assert sid is None
    encrypt.assert_not_called()


def test_profile_id_is_reused_across_signers_and_requests() -> None:
    # given
    profile = profile_by_id(DEVICE_PROFILES[0].id, android_id="0123456789abcdef")
    signers = [RequestSigner(profile), RequestSigner(profile)]

    # when
    headers = [signer.sign(API_ENDPOINTS["login"])[0] for signer in signers for _ in range(2)]

    # then
    ids = [dict(parse_qsl(decode_token(h["x-dynapath-m-token"])[1]))["di"] for h in headers]
    assert ids == ["0123456789abcdef"] * 4


def test_different_profiles_sign_with_different_ids() -> None:
    # given
    profiles = DEVICE_PROFILES[:2]

    # when
    headers = [RequestSigner(profile).sign(API_ENDPOINTS["login"])[0] for profile in profiles]

    # then
    ids = [dict(parse_qsl(decode_token(h["x-dynapath-m-token"])[1]))["di"] for h in headers]
    assert ids == [p.android_id for p in profiles]
    assert len(set(ids)) == 2


def test_explicit_signer_id_overrides_profile_id() -> None:
    # given
    signer = RequestSigner(DEVICE_PROFILES[0], device_id="fixture-override")

    # when
    headers, _ = signer.sign(API_ENDPOINTS["login"])

    # then
    assert dict(parse_qsl(decode_token(headers["x-dynapath-m-token"])[1]))["di"] == "fixture-override"


def test_legacy_foreign_profile_gets_one_id_per_signer(monkeypatch: pytest.MonkeyPatch) -> None:
    # given
    class ForeignProfile:
        model = "SM-S921N"
        android = "15"
        build_id = "AP3A.240905.015.A2"

    generate = Mock(return_value="0123456789abcdef")
    monkeypatch.setattr("pykorail.auth.signer.generate_android_id", generate)
    signer = RequestSigner(ForeignProfile())

    # when
    headers = [signer.sign(API_ENDPOINTS["login"])[0] for _ in range(2)]

    # then
    generate.assert_called_once_with()
    assert [dict(parse_qsl(decode_token(h["x-dynapath-m-token"])[1]))["di"] for h in headers] == [
        "0123456789abcdef",
        "0123456789abcdef",
    ]


def test_default_signer_generates_id_once(monkeypatch: pytest.MonkeyPatch) -> None:
    # given
    generate = Mock(return_value="0123456789abcdef")
    monkeypatch.setattr("pykorail.auth.signer.generate_android_id", generate)

    # when
    signer = RequestSigner()

    # then
    assert signer._device_id == "0123456789abcdef"
    generate.assert_called_once_with()


def test_nonce_uses_apk_alphabet_and_keeps_lowercase(monkeypatch: pytest.MonkeyPatch) -> None:
    # given
    signer = RequestSigner(device_id="fixture-device", sid_key=SYNTHETIC_SID_KEY)
    choose = Mock(return_value=list("aZ09"))
    monkeypatch.setattr("pykorail.auth.signer.random.choices", choose)

    # when
    headers, _ = signer.sign(API_ENDPOINTS["login"])

    # then
    choose.assert_called_once_with("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=4)
    key, _ = decode_token(headers["x-dynapath-m-token"])
    assert key.split("+")[1] == "aZ09"


def test_reversed_lock_entry_preserves_timestamp_history_and_sid(monkeypatch: pytest.MonkeyPatch) -> None:
    # given
    monkeypatch.setattr("pykorail.auth.dynapath.time.time", lambda: INIT_MS / 1000)
    signer = RequestSigner(device_id="fixture-device", sid_key=SYNTHETIC_SID_KEY)
    gate = ReverseFirstTwoLock()
    monkeypatch.setattr(signer._engine, "_lock", gate)
    clock = iter([INIT_MS + 1000, INIT_MS + 1005, INIT_MS + 1010])
    monkeypatch.setattr("pykorail.auth.dynapath.time.time", lambda: next(clock) / 1000)

    # when
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(signer.sign, API_ENDPOINTS["login"])
        assert gate.first_waiting.wait(2), "첫 호출이 잠금 대기에 도달하지 않았습니다"
        second = pool.submit(signer.sign, API_ENDPOINTS["login"])
        second_result = second.result(timeout=2)
        first_result = first.result(timeout=2)
    third_result = signer.sign(API_ENDPOINTS["login"])

    # then: 잠금 획득 순서대로 시각을 채취하고 각 요청의 Sid에도 같은 시각을 씁니다.
    results = [second_result, first_result, third_result]
    fields = [parse_qsl(decode_token(headers["x-dynapath-m-token"])[1]) for headers, _ in results]
    timestamps = [int(dict(pairs)["ts"]) for pairs in fields]
    assert timestamps == [INIT_MS + 1000, INIT_MS + 1005, INIT_MS + 1010]
    assert [[value for key, value in pairs if key == "rt"] for pairs in fields] == [
        ["1000"],
        ["1000", "5"],
        ["1000", "5", "5"],
    ]
    assert [sid for _, sid in results] == [encrypt_sid("AD", ts, SYNTHETIC_SID_KEY) for ts in timestamps]


def test_unsigned_path_does_not_advance_token_history(monkeypatch: pytest.MonkeyPatch) -> None:
    # given
    clock = iter([INIT_MS, INIT_MS + 500])
    monkeypatch.setattr("pykorail.auth.dynapath.time.time", lambda: next(clock) / 1000)
    signer = RequestSigner(device_id="fixture-device", sid_key=SYNTHETIC_SID_KEY)

    # when
    unsigned = signer.sign(API_ENDPOINTS["stationdata"])
    headers, _ = signer.sign(API_ENDPOINTS["login"])

    # then
    assert unsigned == ({}, None)
    fields = parse_qsl(decode_token(headers["x-dynapath-m-token"])[1])
    assert [value for key, value in fields if key == "rt"] == ["500"]
