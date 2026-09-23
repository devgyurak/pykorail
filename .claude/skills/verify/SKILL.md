---
name: verify
description: pykorail 의 전체 품질 게이트를 순서대로 실행하고 실패를 진단합니다. 작업을 끝내기 전, 커밋 전, 또는 "검증해줘"·"게이트 돌려줘"·"통과하는지 봐줘" 라고 할 때 사용하세요. 포맷 → 린트 → 타입 검사 → 테스트+커버리지 순서로 돌리고 각 실패의 흔한 원인을 알려줍니다.
---

# 게이트 실행

**네 개를 전부 통과해야 작업이 끝난 것입니다.** 순서가 중요합니다 — 포매터가 먼저
돌아야 린터가 포맷 문제를 중복 보고하지 않습니다.

```bash
uv run ruff format
uv run ruff check --fix
uv run ty check
uv run pytest
```

한 번에 돌리려면:

```bash
uv run ruff format && uv run ruff check --fix && uv run ty check && uv run pytest
```

실패하면 **거기서 멈추고 고친 뒤 처음부터 다시** 돌리세요. 앞 단계의 수정이 뒤
단계 결과를 바꿉니다.

## 실패 진단

### `ruff check` 실패

- `RUF012 Mutable default value for class attribute` — 소스라면 `ClassVar` 를 붙이거나
  `__init__` 으로 옮기세요. 테스트라면 이미 `per-file-ignores` 로 면제돼 있습니다.
- `SIM108` (삼항 권유) — 두 분기가 각각 여러 값을 대입하도록 바꾸는 게 대개 더
  읽기 좋습니다. 억지로 긴 삼항으로 만들지 마세요.
- `I001` (import 정렬) — `--fix` 가 처리합니다.
- 규칙을 통째로 끄지 마세요. 정말 필요하면 `pyproject.toml` 의 `per-file-ignores`
  에 이유와 함께 추가하세요.

### `ty check` 실패

- `Invalid subscript of object of type 'def list(...)'` — 클래스 안에 빌트인 이름의
  메서드(`list`)가 있어 같은 클래스의 `-> list[X]` 어노테이션을 가린 것입니다.
  메서드 이름을 바꾸세요 (리소스가 `all()` 인 이유).
- 테스트에서 **일부러** 잘못된 타입을 넘길 때 나는 오류 — `dict[str, Any]` 헬퍼나
  `cast` 로 의도를 명시하세요 (`tests/test_card.py` 의 `card_with` 참고).
  런타임 가드 테스트를 지우지 마세요.
- `unresolved-import` (curl_cffi / requests) — 배포 스텁이 없어서이고
  `pyproject.toml` 에서 `warn` 으로 낮춰 뒀습니다. 에러로 뜨면 설정이 바뀐 것입니다.

### `pytest` 실패

- `Required test coverage of 90% not reached` — **게이트를 낮추지 말고 테스트를
  쓰세요.** `Missing` 열이 안 덮인 줄을 알려 줍니다. `test-author` 서브에이전트가
  있다면 위임하세요.
- `test_every_test_follows_given_when_then[...]` — 테스트에 `# when` 또는 `# then`
  주석이 없습니다. 준비 코드가 있으면 `# given` 도 필요합니다. 예외 검증처럼 실행과
  검증이 한 덩어리면 `# when & then` 으로 묶으세요.
- `test_no_control_flow_statements[...]` — 테스트에 `if`/`for`/`while` **문**이
  들어갔습니다. `@pytest.mark.parametrize` 로 펼치거나, 컴프리헨션으로 위반 목록을
  만들어 `== []` 와 비교하세요. 이 규칙은 `tests/test_style.py` 가 강제합니다.
- `test_first_token_matches_v1_0_3_golden` — 새 엔진의 첫 토큰이 고정된 회귀
  기준과 달라졌습니다. APK 근거·직렬화·시간 초기화를 확인하세요. 실패만으로 서버
  거부를 단정하거나, 테스트를 통과시키려고 골든을 자동 갱신하지 마세요.
  `test_fresh_engines_match_for_same_inputs`와 역디코더 검증도 함께 확인합니다.
  같은 엔진의 재호출은 `rt` 이력이 바뀌므로 서로 다른 토큰이 나올 수 있습니다.
- `예상하지 못한 요청: <url>` — `FakeSession` 에 라우트가 없습니다. 픽스처의
  `routes` dict 에 해당 엔드포인트를 추가하세요.

## 커버리지 자세히 보기

```bash
uv run pytest --cov-report=html && open htmlcov/index.html
```

특정 파일만:

```bash
uv run pytest --cov=pykorail.resources.trains --cov-report=term-missing
```

## 마지막

게이트가 통과했다면 무엇을 돌렸고 결과가 무엇인지 사실대로 보고하세요.
**통과하지 않았는데 통과했다고 하지 마세요.** 일부만 돌렸으면 일부만 돌렸다고
말하세요.
