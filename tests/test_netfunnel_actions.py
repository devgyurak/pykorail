"""NetFunnel 동작별 ``aid`` 가 APK 근거와 어긋나지 않는지 지킵니다.

``docs/protocol-evidence-7.0.8.json`` 의 ``netfunnel.actions.constants`` 에 적어 둔
AlienGuard 암호문을 4바이트 반복 XOR 로 풀어 :class:`~pykorail.options.NetFunnelAction`
상수와 대조합니다. 비밀번호 골든 벡터와 같은 방식입니다 — 근거 파일이 바뀌거나 상수를
잘못 옮기면 여기서 드러납니다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pykorail.options import NetFunnelAction

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = json.loads((ROOT / "docs" / "protocol-evidence-7.0.8.json").read_text(encoding="utf-8"))
CONSTANTS: list[dict[str, Any]] = EVIDENCE["netfunnel"]["actions"]["constants"]
PREFIX = b"act_"


def _decode(ciphertext: list[int]) -> str:
    """4바이트 반복 XOR 을 풉니다. 키는 이미 아는 접두 ``act_`` 에서 뽑습니다."""
    key = [byte ^ known for byte, known in zip(ciphertext[:4], PREFIX, strict=True)]
    return bytes(byte ^ key[index % 4] for index, byte in enumerate(ciphertext)).decode("ascii")


def _attribute(reference: str) -> str:
    return reference.split(".", 1)[1]


class TestActionEvidence:
    @pytest.mark.parametrize("entry", CONSTANTS, ids=lambda entry: entry["apk"])
    def test_constant_matches_the_apk_ciphertext(self, entry: dict[str, Any]) -> None:
        # when
        decoded = _decode(entry["ciphertext"])
        constant = getattr(NetFunnelAction, _attribute(entry["pykorail"]))

        # then
        assert decoded == entry["aid"], f"{entry['apk']} 복호 결과가 aid 와 다릅니다"
        assert constant == entry["aid"]

    def test_every_action_constant_has_an_evidence_row(self) -> None:
        """상수를 늘렸는데 근거 행을 빠뜨리면 여기서 걸립니다."""
        # given
        documented = {_attribute(entry["pykorail"]) for entry in CONSTANTS}

        # when
        declared = {name for name in vars(NetFunnelAction) if not name.startswith("_")}

        # then
        assert declared == documented
