"""AOSP Android 14 인코더와 Java AES로 생성한 비밀번호 와이어 기준값입니다."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pykorail.crypto import encrypt_password

VECTORS = json.loads(Path(__file__).with_name("password_vectors.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("vector", VECTORS, ids=[f"utf8-{len(v['password'].encode('utf-8'))}" for v in VECTORS])
def test_password_matches_android_encoder(vector: dict[str, str]) -> None:
    # when
    encrypted = encrypt_password(vector["password"], vector["key"])

    # then
    assert encrypted == vector["expected"]
