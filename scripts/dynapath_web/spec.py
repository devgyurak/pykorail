"""해제한 자산을 비교 가능한 알고리즘 스펙(시그니처)으로 정규화합니다.

스펙은 자산 원문 해시, 로더 문자열 목록, VM 블록의 함수·상수·바이트코드 해시를
담습니다. 이 값들이 배포마다 같은지 비교해 드리프트를 판정합니다.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .loader import decode_loader_strings
from .vm import decode_blocks

#: 스펙 형식 버전. 스펙 구조를 바꾸면 올려 baseline 과 어긋나게 만든다.
SPEC_VERSION = 1


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical(payload: Any) -> str:
    """키 순서·공백에 흔들리지 않는 정규 JSON 문자열."""
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def build_spec(assets: dict[str, str]) -> dict[str, Any]:
    """자산 원문 ``{논리 이름: 소스}`` 로 스펙을 만듭니다.

    ``loader`` 는 로더(``dynaPath.do``), ``vm`` 은 세션 VM(``dyna/<token>.js``)
    입니다. 없는 자산은 빈 문자열로 취급합니다.
    """
    loader_values = decode_loader_strings(assets.get("loader", ""))
    blocks = decode_blocks(assets.get("vm", ""))

    functions = sorted({fn.get("name", "<anonymous>") for block in blocks for fn in block.get("functions", [])})
    constants = sorted({str(value) for block in blocks for value in block.get("constants", [])})

    spec: dict[str, Any] = {
        "version": SPEC_VERSION,
        "assets": {name: _sha256_text(text) for name, text in sorted(assets.items())},
        "loader_values": sorted({str(entry["value"]) for entry in loader_values if entry["value"] is not None}),
        "vm_blocks": [
            {
                "blob": block["blob"],
                "params": list(block["params"]),
                "functions": [
                    {
                        "name": fn.get("name", "<anonymous>"),
                        "bytecode_sha256": _sha256_text(fn["bytecode"])
                        if isinstance(fn.get("bytecode"), str)
                        else None,
                    }
                    for fn in block.get("functions", [])
                ],
                "constants": [str(value) for value in block.get("constants", [])],
            }
            for block in blocks
        ],
        "vm_functions": functions,
        "vm_constants": constants,
    }
    spec["signature"] = _sha256_text(_canonical({key: value for key, value in spec.items() if key != "signature"}))
    return spec


def filter_spec(spec: dict[str, Any], names: set[str]) -> dict[str, Any]:
    """스펙을 ``names`` 자산만 남기고 접습니다.

    일부 자산만 내려받는 CI 실행에서, 확보한 자산끼리만 비교하려고 씁니다.
    버린 자산에 딸린 파생 필드(로더 문자열·VM 블록)도 함께 비웁니다.
    """
    filtered: dict[str, Any] = {
        "version": spec.get("version", SPEC_VERSION),
        "assets": {name: digest for name, digest in spec.get("assets", {}).items() if name in names},
        "loader_values": list(spec.get("loader_values", [])) if "loader" in names else [],
        "vm_blocks": list(spec.get("vm_blocks", [])) if "vm" in names else [],
        "vm_functions": list(spec.get("vm_functions", [])) if "vm" in names else [],
        "vm_constants": list(spec.get("vm_constants", [])) if "vm" in names else [],
    }
    filtered["signature"] = _sha256_text(_canonical(filtered))
    return filtered


__all__ = ["SPEC_VERSION", "build_spec", "filter_spec"]
