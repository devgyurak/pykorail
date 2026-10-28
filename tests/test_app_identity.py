"""앱 신원값(``Version`` · ``AppVersion`` · ``Key``)이 7.1.0 근거와 어긋나지 않는지 지킵니다.

``docs/protocol-evidence-7.1.0.json`` 의 ``app_identity`` 를 두 방향에서 봅니다.

1. **캡처** — ``constants.py`` 의 값이 7.1.0 앱 캡처에서 본 폼 값과 같은지.
2. **APK 암호문** — 그 값을 만드는 AlienGuard 암호문이 같은 평문으로 4바이트 반복 XOR 에
   정합하는지. 키를 평문 앞 4바이트에서 뽑으므로 검증되는 것은 5번째 바이트부터입니다
   (근거 파일의 ``guard_limit``).

이 값들은 서버가 앱 버전 게이트로 보는 값이라, 근거 없이 바뀌면 로그인이 조용히 막힙니다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pykorail import constants

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = json.loads((ROOT / "docs" / "protocol-evidence-7.1.0.json").read_text(encoding="utf-8"))
FIELDS: list[dict[str, Any]] = EVIDENCE["app_identity"]["fields"]
CIPHERTEXTS: list[tuple[dict[str, Any], dict[str, Any]]] = [
    (field, entry) for field in FIELDS for entry in field["ciphertexts"]
]


def _decode(ciphertext: list[int], plaintext: str) -> str:
    """평문 앞 4바이트로 키를 뽑아 4바이트 반복 XOR 을 풉니다."""
    key = [byte ^ known for byte, known in zip(ciphertext[:4], plaintext.encode()[:4], strict=True)]
    return bytes(byte ^ key[index % 4] for index, byte in enumerate(ciphertext)).decode("ascii")


@pytest.mark.parametrize("field", FIELDS, ids=lambda field: field["form"])
def test_constant_matches_the_captured_form_value(field: dict[str, Any]) -> None:
    # when
    value = getattr(constants, field["pykorail"].split(".", 1)[1])

    # then
    assert value == field["captured"], f"{field['pykorail']} 가 7.1.0 캡처의 {field['form']} 와 다릅니다"


@pytest.mark.parametrize(("field", "entry"), CIPHERTEXTS, ids=lambda item: item.get("apk", item.get("form")))
def test_apk_ciphertext_decodes_to_the_captured_value(field: dict[str, Any], entry: dict[str, Any]) -> None:
    # when
    decoded = _decode(entry["ciphertext"], field["captured"])

    # then
    assert decoded == field["captured"], f"{entry['apk']} 암호문이 {field['form']} 값과 정합하지 않습니다"
