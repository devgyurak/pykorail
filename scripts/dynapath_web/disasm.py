"""해제한 JScrambler 바이트코드를 의사코드로 펼칩니다.

opcode→의미 표는 인터프리터 디스패치에서 옮긴 **잠정** 매핑입니다. 피연산자 폭이
확정되지 않은 opcode 가 남아 있어 출력에 ``OP_xx`` 가 섞입니다 — 그대로 사실대로
남깁니다. 이 표를 알고리즘의 정본으로 쓰지 마세요. 스펙·드리프트 판정은 바이트
해시(:mod:`scripts.dynapath_web.spec`)로 하고, 이 모듈은 사람이 읽는 보조물입니다.
"""

from __future__ import annotations

from typing import Any

#: 산술·논리 opcode. 같은 의미에 여러 opcode 가 매핑된다(인터프리터의 별칭).
ARITHMETIC = {
    0x6A: "ADD",
    0x78: "ADD",
    0x80: "ADD",
    0xC8: "SUB",
    0xCF: "SUB",
    0xED: "SUB",
    0x06: "MUL",
    0x2C: "MUL",
    0xD3: "MUL",
    0x1A: "DIV",
    0x94: "DIV",
    0xE4: "DIV",
    0x3B: "MOD",
    0x8E: "MOD",
    0xE1: "MOD",
    0x1E: "POW",
    0x44: "POW",
    0xAC: "POW",
    0xCC: "SHL",
    0xAB: "SHL",
    0xD9: "SHL",
    0x33: "SAR",
    0x65: "SAR",
    0x73: "SAR",
    0xBB: "USHR",
    0x12: "USHR",
    0x91: "USHR",
    0x55: "OR",
    0x4E: "OR",
    0xD4: "OR",
    0x37: "AND",
    0x48: "AND",
    0x69: "AND",
    0x05: "XOR",
    0x38: "XOR",
    0x7F: "XOR",
    0x13: "EQ",
    0x30: "EQ",
    0xC4: "EQ",
    0xC2: "NE",
    0xDD: "NE",
    0xF0: "NE",
    0x4B: "SEQ",
    0x9B: "SEQ",
    0xA4: "SEQ",
    0x8A: "SNE",
    0x90: "SNE",
    0xCD: "SNE",
    0x52: "LT",
    0x77: "LT",
    0x8D: "LT",
    0x08: "GT",
    0x5E: "GT",
    0x7A: "GT",
    0x3E: "LE",
    0xAA: "LE",
    0xBD: "LE",
    0x83: "GE",
    0x9E: "GE",
    0xD2: "GE",
    0x8F: "IN",
    0xC5: "IN",
    0xD0: "IN",
}

#: 메모리·스택 opcode.
MEMORY = {
    0xAE: "LOAD_CONST",
    0x0F: "LOAD_CONST",
    0xC7: "LOAD_CONST",
    0xF1: "LOAD_VAR",
    0x63: "LOAD_VAR",
    0x18: "LOAD_VAR",
    0x32: "STORE_VAR",
    0x0A: "STORE_VAR",
    0x0E: "STORE_VAR",
    0xBC: "PUSH_IMM",
    0x7B: "RETURN",
    0xC1: "POP",
    0x4D: "DUP2",
    0x5D: "DUP2",
    0xE8: "DUP2",
    0x50: "PUSH",
    0x5B: "PUSH",
    0x45: "INC",
    0x81: "INC",
    0x75: "DEC",
    0xEC: "DEC",
    0xD6: "GET_PROP",
    0x99: "GET_PROP",
    0xE9: "GET_PROP",
    0x35: "SET_PROP",
    0xA2: "SET_PROP",
    0xBE: "SET_PROP",
}

#: 제어 흐름·호출 opcode.
CONTROL = {
    0x04: "CALL",
    0xD1: "CALL",
    0x98: "CALL3",
    0xA6: "CALL3",
    0x71: "CALL1",
    0x7D: "CALL1",
    0x16: "CALL_VMF",
    0xFA: "CALL_VMF",
    0x20: "JMP_FALSE",
    0x3A: "JMP_FALSE",
    0xFB: "JMP_FALSE",
    0xA3: "JMP_TRUE",
    0xB6: "JMP_TRUE",
    0xFD: "JMP_TRUE",
    0x43: "JMP_LT",
    0xE7: "JMP_LT",
    0x9C: "TRY",
    0xF4: "TRY",
}

#: 2바이트 피연산자(상수·변수 인덱스, 점프 대상)를 갖는 의미.
_WORD_OPERANDS = frozenset({"LOAD_CONST", "LOAD_VAR", "STORE_VAR", "JMP_FALSE", "JMP_TRUE", "JMP_LT", "TRY"})


def opcode_name(op: int) -> str:
    """opcode 바이트를 의미 이름으로 옮깁니다. 모르면 ``OP_xx`` 로 남깁니다."""
    for table in (ARITHMETIC, MEMORY, CONTROL):
        name = table.get(op)
        if name is not None:
            return name
    return f"OP_0x{op:02x}"


def disassemble(bytecode_hex: str, constants: list[Any] | None = None) -> list[str]:
    """16진 바이트코드를 한 줄씩 의사코드로 펼칩니다.

    피연산자 폭이 확정되지 않은 면이 있으므로, 결과는 사람이 읽는 데까지만
    쓰고 프로그램 판정에 쓰지 마세요.
    """
    code = bytes.fromhex(bytecode_hex)
    consts = constants or []
    lines: list[str] = []
    pc = 0
    while pc < len(code):
        op = code[pc]
        name = opcode_name(op)
        if name in _WORD_OPERANDS and pc + 2 < len(code):
            operand = (code[pc + 1] << 8) | code[pc + 2]
            if name == "LOAD_CONST" and operand < len(consts):
                lines.append(f"{pc:04d}: {name} #{operand} ({_format_const(consts[operand])})")
            else:
                lines.append(f"{pc:04d}: {name} #{operand}")
            pc += 3
        elif name == "PUSH_IMM" and pc + 1 < len(code):
            lines.append(f"{pc:04d}: {name} {code[pc + 1] - 0x80}")
            pc += 2
        else:
            lines.append(f"{pc:04d}: {name}")
            pc += 1
    return lines


def _format_const(value: Any) -> str:
    text = str(value)
    return text if len(text) < 30 else text[:28] + ".."
