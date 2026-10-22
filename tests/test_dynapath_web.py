"""웹 DynaPath 정적 해제·드리프트 하네스 회귀 테스트.

기대값은 전부 **실제 JS 구현**(``dynaPath.do`` 의 커스텀 base64+RC4, ``_vbee`` 의
XOR)으로 계산한 값입니다 — 파이썬끼리 맞춰 보는 순환 검증이 아닙니다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.dynapath_web.__main__ import main
from scripts.dynapath_web.codec import base64_decode, rc4, unescape_js_string, xor_decode
from scripts.dynapath_web.disasm import disassemble, opcode_name
from scripts.dynapath_web.drift import compare, report_markdown
from scripts.dynapath_web.loader import decode_loader_strings, extract_string_array
from scripts.dynapath_web.pepperpowder import hash_cyper, rot_schedule, rotate_right
from scripts.dynapath_web.spec import build_spec, filter_spec
from scripts.dynapath_web.vm import decode_blocks, extract_decode_params, extract_literal_blobs

FIXTURES = Path(__file__).parent / "_web"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _assets() -> dict[str, str]:
    return {"loader": _fixture("loader.js"), "vm": _fixture("vm.js")}


class TestCodecMatchesJavaScript:
    """코덱의 기대값은 실제 JS 로 계산한 골든 벡터입니다."""

    def test_base64_decode_matches_js(self) -> None:
        # when
        decoded = base64_decode("pidCb5BoZ3I=")

        # then
        assert decoded.hex() == "3c80dc0796cecf78c0"

    def test_rc4_matches_js(self) -> None:
        # when
        decoded = rc4(b"plaintext here", "keyZ")

        # then
        assert decoded.hex() == "58de506ee3a0b6e275214e54b921"

    def test_xor_decode_matches_js(self) -> None:
        # when
        decoded = xor_decode("Hello, DynaPath!", 0xBB93, 0x60B3)

        # then
        assert decoded.hex() == "5e06dcf98d035c25d795297d1bb37cb8"

    @pytest.mark.parametrize(
        ("literal", "expected"),
        [
            (r"AB\x00\u0041", "AB\0A"),
            (r"a\'b\"c", "a'b\"c"),
            (r"\x7b\x22l\x22\x7d", '{"l"}'),
            (r"plain", "plain"),
        ],
        ids=["hex-and-unicode", "quotes", "json-escaped", "no-escape"],
    )
    def test_unescape_js_string(self, literal: str, expected: str) -> None:
        # when
        decoded = unescape_js_string(literal)

        # then
        assert decoded == expected


class TestLoaderDecoding:
    def test_string_array_is_fully_extracted(self) -> None:
        # when
        items = extract_string_array(_fixture("loader.js"))

        # then
        assert len(items) == 55

    def test_loader_value_matches_js(self) -> None:
        """``idx = num + DELTA - BASE`` 와 RC4+커스텀 base64 가 JS 와 같아야 합니다."""
        # when
        decoded = decode_loader_strings(_fixture("loader.js"))
        value = decoded[0]["value"]

        # then
        assert [(entry["key"], entry["index"]) for entry in decoded] == [("ab", 40)]
        assert isinstance(value, str)
        assert value.encode("latin-1").hex() == "f38e32744c1ee0d60ffe1462"

    def test_out_of_range_index_yields_none(self) -> None:
        # given
        source = "(function(){var g0=['a'];});y('zz',-0x1);"

        # when
        decoded = decode_loader_strings(source)

        # then
        assert decoded[0]["value"] is None


class TestVmDecoding:
    def test_literal_blob_is_unescaped(self) -> None:
        # when
        blobs = extract_literal_blobs(_fixture("vm.js"))

        # then
        assert set(blobs) == {"XyZ"}

    def test_decode_params_are_collected(self) -> None:
        # when
        params = extract_decode_params(_fixture("vm.js"))

        # then
        assert (0x1234, 0xABCD) in params

    def test_blocks_recover_the_vm_json(self) -> None:
        # given
        expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))["vm_json"]

        # when
        blocks = decode_blocks(_fixture("vm.js"))

        # then
        assert len(blocks) == 1
        assert blocks[0]["blob"] == "XyZ"
        assert blocks[0]["params"] == [0x1234, 0xABCD]
        assert [function["name"] for function in blocks[0]["functions"]] == ["_vftestfn"]
        assert blocks[0]["constants"] == json.loads(expected)["constants"]

    def test_nonmutated_source_yields_no_blocks(self) -> None:
        # when
        blocks = decode_blocks("(function(){var a=1;})();")

        # then
        assert blocks == []


class TestSpec:
    def test_same_assets_give_the_same_signature(self) -> None:
        # when
        first = build_spec(_assets())
        second = build_spec(_assets())

        # then
        assert first["signature"] == second["signature"]

    def test_changed_asset_changes_the_signature(self) -> None:
        # given
        baseline = build_spec(_assets())
        mutated = {**_assets(), "vm": _fixture("vm.js") + "\n// rotated"}

        # when
        current = build_spec(mutated)

        # then
        assert current["signature"] != baseline["signature"]

    def test_filter_spec_drops_other_assets(self) -> None:
        # given
        spec = build_spec({**_assets(), "helper": "bootstrap"})

        # when
        filtered = filter_spec(spec, {"helper"})

        # then
        assert set(filtered["assets"]) == {"helper"}
        assert filtered["vm_functions"] == []


class TestDrift:
    def test_identical_specs_do_not_drift(self) -> None:
        # when
        diff = compare(build_spec(_assets()), build_spec(_assets()))

        # then
        assert diff["drifted"] is False

    def test_changed_asset_is_reported(self) -> None:
        # given
        baseline = build_spec(_assets())

        # when
        diff = compare(baseline, build_spec({**_assets(), "helper": "new"}))

        # then
        assert diff["drifted"] is True
        assert diff["assets_added"] == ["helper"]

    def test_report_marks_drift(self) -> None:
        # given
        baseline = build_spec(_assets())
        current = build_spec({**_assets(), "loader": _fixture("loader.js") + "\n// x"})

        # when
        report = report_markdown(baseline, current, compare(baseline, current))

        # then
        assert "드리프트 감지" in report
        assert "`loader`" in report

    def test_report_marks_no_drift(self) -> None:
        # given
        spec = build_spec(_assets())

        # when
        report = report_markdown(spec, spec, compare(spec, spec))

        # then
        assert "변화 없음" in report


class TestDisassembly:
    def test_known_opcode_is_named(self) -> None:
        # when & then
        assert opcode_name(0x6A) == "ADD"

    def test_unknown_opcode_is_marked(self) -> None:
        # when & then
        assert opcode_name(0x00) == "OP_0x00"

    def test_disassemble_yields_one_line_per_instruction(self) -> None:
        # when
        lines = disassemble("6a")

        # then
        assert lines == ["0000: ADD"]


class TestCli:
    def test_exit_zero_without_baseline(self, tmp_path: Path) -> None:
        # given
        out = tmp_path / "art"

        # when
        code = main(["--asset", f"vm={FIXTURES / 'vm.js'}", "--out", str(out)])

        # then
        assert code == 0
        assert (out / "algorithm-spec.json").is_file()

    def test_exit_one_on_drift(self, tmp_path: Path) -> None:
        # given
        baseline = tmp_path / "baseline.json"
        baseline.write_text(json.dumps(build_spec(_assets())), encoding="utf-8")
        rotated = tmp_path / "loader.js"
        rotated.write_text(_fixture("loader.js") + "\n// rotated", encoding="utf-8")

        # when
        code = main(
            [
                "--asset",
                f"loader={rotated}",
                "--only",
                "loader",
                "--baseline",
                str(baseline),
                "--fail-on-drift",
            ]
        )

        # then
        assert code == 1

    def test_exit_zero_without_drift(self, tmp_path: Path) -> None:
        # given
        baseline = tmp_path / "baseline.json"
        baseline.write_text(json.dumps(build_spec(_assets())), encoding="utf-8")

        # when
        code = main(
            [
                "--asset",
                f"loader={FIXTURES / 'loader.js'}",
                "--asset",
                f"vm={FIXTURES / 'vm.js'}",
                "--only",
                "loader,vm",
                "--baseline",
                str(baseline),
                "--fail-on-drift",
            ]
        )

        # then
        assert code == 0


def _pepperpowder_vectors() -> list[dict]:
    return json.loads((FIXTURES / "pepperpowder_oracle.json").read_text(encoding="utf-8"))["vectors"]


class TestPepperPowder:
    """런타임 후킹 오라클(raw plain · key · rot · seed)로 해시 코어 바이트일치를 확인합니다."""

    @pytest.mark.parametrize("vector", _pepperpowder_vectors(), ids=lambda v: v["label"])
    def test_rot_schedule_comes_from_key_nibbles(self, vector: dict) -> None:
        # when
        schedule = rot_schedule(vector["key_int32"])

        # then
        assert schedule == vector["rot"]

    @pytest.mark.parametrize("vector", _pepperpowder_vectors(), ids=lambda v: v["label"])
    def test_cyper_matches_the_oracle(self, vector: dict) -> None:
        # given
        plain = bytes.fromhex(vector["plain_hex"])

        # when
        cyper = hash_cyper(plain, vector["key_int32"], vector["seed"])

        # then
        assert cyper.hex() == vector["cyper_hex"]

    def test_rotate_right_is_a_32bit_rotation(self) -> None:
        # when
        rotated = rotate_right(0x00000001, 8)

        # then
        assert rotated == 0x01000000

    def test_rotate_right_by_zero_is_identity(self) -> None:
        # when
        rotated = rotate_right(0xDEADBEEF, 0)

        # then
        assert rotated == 0xDEADBEEF
