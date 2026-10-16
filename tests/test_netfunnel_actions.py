"""NetFunnel 동작별 ``aid`` 가 APK 근거와 어긋나지 않는지 지킵니다.

``docs/protocol-evidence-7.0.8.json`` 의 ``netfunnel.actions`` 를 세 방향에서 봅니다.

1. **XOR 방식 자체** — 평문을 아는 값(``https`` · ``nf.letskorail.com`` · ``service_1``
   등)이 4바이트 반복 키로 풀리는지. 4바이트를 넘는 값의 꼬리까지 맞아야 하므로
   "키가 4바이트마다 반복된다" 가 검증됩니다.
2. **상수** — ``NetworkConstants$Netfunnel`` 암호문이 :class:`NetFunnelAction` 상수와
   같은 값으로 풀리는지.
3. **호출 지점** — 각 화면이 자기 자리에서 직접 넣는 암호문이 같은 aid 로 풀리는지.
   동작↔aid 대응의 실제 근거는 상수 정의가 아니라 이 바이트들입니다.
   마지막으로 상수 집합과 :data:`NetFunnelActionCode` 리터럴이 일치하는지 봅니다.

비밀번호 골든 벡터와 같은 방식입니다 — 근거 파일이 바뀌거나 상수를 잘못 옮기면 여기서
드러납니다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, get_args

import pytest

from pykorail.options import NetFunnelAction, NetFunnelActionCode

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = json.loads((ROOT / "docs" / "protocol-evidence-7.0.8.json").read_text(encoding="utf-8"))
ACTIONS: dict[str, Any] = EVIDENCE["netfunnel"]["actions"]
KNOWN_PLAINTEXTS: list[dict[str, Any]] = ACTIONS["known_plaintexts"]
CONSTANTS: list[dict[str, Any]] = ACTIONS["constants"]
CALL_SITES: list[dict[str, Any]] = ACTIONS["call_sites"]
PREFIX = b"act_"


def _decode(ciphertext: list[int], prefix: bytes = PREFIX) -> str:
    """4바이트 반복 XOR 을 풉니다. 키는 이미 아는 접두 4바이트에서 뽑습니다.

    ``ciphertext`` 가 4바이트보다 길면 키가 반복돼야 나머지가 맞습니다 — 그래서 긴
    평문을 넣으면 "키가 4바이트마다 반복된다" 가 함께 검증됩니다.
    """
    key = [byte ^ known for byte, known in zip(ciphertext[:4], prefix[:4], strict=True)]
    return bytes(byte ^ key[index % 4] for index, byte in enumerate(ciphertext)).decode("ascii")


def _attribute(reference: str) -> str:
    return reference.split(".", 1)[1]


class TestXorAlgorithm:
    @pytest.mark.parametrize("entry", KNOWN_PLAINTEXTS, ids=lambda entry: entry["constant"])
    def test_known_plaintext_decodes_with_a_repeating_key(self, entry: dict[str, Any]) -> None:
        # when
        decoded = _decode(entry["ciphertext"], entry["plaintext"][:4].encode())

        # then
        assert decoded == entry["plaintext"], f"{entry['constant']} — 키가 4바이트마다 반복되지 않습니다"


class TestActionConstants:
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

    def test_action_code_literal_matches_the_constants(self) -> None:
        """상수만 늘리고 Literal 을 빠뜨리면 타입 검사가 그 aid 를 모릅니다."""
        # when
        declared = {value for name, value in vars(NetFunnelAction).items() if not name.startswith("_")}

        # then
        assert set(get_args(NetFunnelActionCode)) == declared


class TestCallSites:
    @pytest.mark.parametrize("entry", CALL_SITES, ids=lambda entry: entry["where"])
    def test_call_site_ciphertext_decodes_to_the_action(self, entry: dict[str, Any]) -> None:
        # when
        decoded = _decode(entry["ciphertext"])
        constant = getattr(NetFunnelAction, _attribute(entry["pykorail"]))

        # then
        assert decoded == entry["aid"], f"{entry['where']} 복호 결과가 aid 와 다릅니다"
        assert constant == entry["aid"]

    def test_every_action_has_a_call_site(self) -> None:
        """근거 행만 있고 실제 호출 지점이 없으면 aid 대응이 허공에 뜹니다."""
        # given
        documented = {entry["aid"] for entry in CONSTANTS}

        # when
        reached = {entry["aid"] for entry in CALL_SITES}

        # then
        assert documented <= reached
