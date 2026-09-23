"""실제 전송 없이 서명 시각과 동시 호출 이력을 검증합니다."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qsl

import pytest

from pykorail.auth.signer import RequestSigner
from pykorail.constants import API_ENDPOINTS
from pykorail.crypto import encrypt_sid
from tests.dynapath_decoder import decode_token
from tests.signing_support import ReverseFirstTwoLock

INIT_MS = 1_700_000_000_000
SYNTHETIC_SID_KEY = b"0123456789abcdef"


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
