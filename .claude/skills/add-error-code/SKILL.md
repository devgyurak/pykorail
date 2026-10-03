---
name: add-error-code
description: 새 코레일 응답 코드(h_msg_cd)를 pykorail 예외 계층에 매핑하는 절차. "이 에러 코드 처리해줘", "P0xx 코드가 뜨는데", "예외 추가" 같은 요청에 사용하세요. 자동 등록 방식과 KorailError / PykorailError 중 어디에 붙일지 판단 기준을 담고 있습니다.
---

# 응답 코드를 예외로 매핑

## 먼저 판단: 어느 갈래인가

```
PykorailError
├── KorailError            ← 서버가 strResult=FAIL 로 응답한 경우
│   ├── NeedToLoginError
│   ├── NoResultsError
│   ├── SoldOutError
│   └── LoginFailedError
├── NetFunnelError         ← 대기열 게이트 실패
├── StationNotFoundError   ← 요청을 보내기 **전** 클라이언트가 잡은 입력 오류
└── TransportError         ← 세션 생성 실패 / 비 JSON 응답
    └── HttpStatusError    ← 코레일 형식(strResult)이 아닌 HTTP 4xx·5xx (403 이용제한 등)
```

- **서버가 `h_msg_cd` 로 알려준 실패** → `KorailError` 하위. 아래 절차대로.
- **요청을 보내기 전에 우리가 막는 입력 오류** → `KorailError` 가 아니라
  `PykorailError` 의 형제로 만드세요 (`exceptions/validation.py`).
  서버 응답이 아닌 것을 `KorailError` 로 두면 `except KorailError` 의 의미가 흐려집니다.

## 코레일 응답 코드 추가하기

`src/pykorail/exceptions/api.py` 에 클래스를 추가하는 것으로 **끝입니다.**
등록 테이블이 없습니다 — `error_for_code()` 가 `KorailError.__subclasses__()` 를
훑어 `codes` 가 비어 있지 않은 하위 타입을 찾아갑니다.

```python
class TooManyReservationsError(KorailError):
    """1인당 예약 한도를 넘었습니다."""

    codes = frozenset({"ERR211072"})
    default_msg = "Too many reservations"
```

지켜야 할 것:

- **`__init__` 을 덮어쓰지 마세요.** 생성자 시그니처가 계층 전체에서 같아야
  `error_for_code(code, msg)` 가 균일하게 조립합니다. `codes` 와 `default_msg`
  클래스 속성만 채우세요.
- `codes` 는 `frozenset` 입니다.
- 코드를 여러 개 묶어도 됩니다 (`NoResultsError` 가 4개를 묶습니다). **호출자가
  같은 방식으로 대응할 코드끼리** 묶으세요. 대응이 다르면 타입을 나누세요.
- `default_msg` 는 짧은 영문 식별 문구. 사용자에게 보일 한국어 메시지는 서버가
  `h_msg_txt` 로 주고, 매칭 안 된 코드는 그 메시지가 그대로 실립니다.
- `exceptions/__init__.py` 의 import 와 `__all__` 에 추가하고, 공개할 만하면
  `pykorail/__init__.py` 에도 추가하세요.

## 새 갈래(클라이언트 측 검증)를 만들 때

`src/pykorail/exceptions/validation.py` 에 `PykorailError` 를 상속해 만듭니다.
사용자가 고칠 수 있도록 **무엇이 왜 잘못됐는지** 를 담으세요 —
`StationNotFoundError` 가 오타 후보까지 알려주는 것처럼.

```python
class SeatUnavailableError(PykorailError):
    def __init__(self, requested: str, available: Sequence[str]) -> None:
        self.requested = requested
        self.available = list(available)
        super().__init__(f"{requested!r} 좌석을 쓸 수 없습니다. 가능: {', '.join(self.available)}")
```

## 테스트

`tests/test_exceptions.py` 에 추가합니다. 기존 파라미터 표에 코드를 얹으면 됩니다:

```python
@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("P058", NeedToLoginError),
        ("ERR211072", TooManyReservationsError),  # ← 추가
    ],
)
def test_known_codes_promote_to_specific_types(self, code, expected) -> None:
    # when
    error = error_for_code(code, "서버 메시지")

    # then
    assert type(error) is expected
    assert error.code == code
```

계층 테스트(`test_everything_is_a_pykorail_error`)의 파라미터 목록에도 새 타입을
넣어, 새 예외가 `PykorailError` 아래에 있다는 것을 고정하세요.

## 마무리

```bash
uv run ruff format && uv run ruff check --fix && uv run ty check && uv run pytest
```

README 의 예외 계층 다이어그램도 갱신하세요.
