# AGENTS.md — pykorail

코레일(KTX) 스마트 예매 비공식 Python 클라이언트. PyPI 배포 패키지입니다.

이 문서가 **모든 코딩 에이전트의 단일 규범**입니다. Codex · Claude Code · Pi ·
Cursor · OpenCode 가 각자의 진입점에서 이 파일로 수렴합니다 (`.agents/README.md` 참조).

---

## 1. 명령

`uv` 로만 실행합니다. `pip` 이나 맨몸 `python` 을 쓰지 마세요.

```bash
uv sync --all-extras     # 환경 구성
uv run ruff format       # 포매팅 (검사 전에 먼저)
uv run ruff check --fix  # 린트
uv run ty check          # 타입 검사
uv run pytest            # 테스트 + 커버리지 게이트
uv build                 # 배포 아티팩트
```

**작업을 끝내기 전에 반드시 네 개를 전부 통과시키세요.** 하나라도 실패하면 끝난 게
아닙니다. 실패를 우회(`# noqa`, `# type: ignore`, `--no-cov`)하지 말고 원인을 고치세요.
정말 우회가 맞다면 **왜** 인지 같은 줄에 적으세요.

---

## 2. 아키텍처 — 절대 어기지 말 것

계층은 **한 방향으로만** 의존합니다. 화살표를 거스르는 import 를 추가하지 마세요.

```
client.py  (Korail — 로그인/로그아웃/연결 수명만)
   │
   ├── resources/   stations · trains · reservations · tickets   ← 엔드포인트는 전부 여기
   │      │
   │      └── api.py (ApiClient) ── auth/ (signer · dynapath) ── crypto.py
   │             │                       └── transport.py
   │             └── models/  (불변 응답 모델)
   │
   └── exceptions/ · constants.py · options.py · device/   ← 누구나 의존 가능, 아무에게도 의존 안 함
```

### 지켜야 할 규칙

1. **엔드포인트는 리소스에만.** `Korail` 본체에 새 API 메서드를 붙이지 마세요.
   `korail.trains.search()` 처럼 리소스에 넣고, 클라이언트에는 `login`/`logout`/
   `close` 와 리소스 배선만 둡니다. 리소스가 늘면 `Korail.__init__` 에 한 줄 추가.

2. **HTTP 는 `ApiClient` 를 통해서만.** 리소스가 `self._session` 을 직접 만지거나
   `requests`/`curl_cffi` 를 import 하면 안 됩니다. `self._api.get/post/sign/check/
   base_payload` 만 씁니다.

3. **응답 모델은 불변 + 완성 상태.** 전부 `@dataclass(frozen=True)` 이고
   `from_response()` 클래스메서드로만 만듭니다. 생성자는 값 조립, 응답 dict 해석은
   `from_response` — 이 경계를 섞지 마세요.
   객체를 만든 뒤 필드를 채우는 코드(`obj.x = ...`)는 **금지**입니다. 부속 데이터가
   필요하면 **먼저 조회해서 생성자에 넘기세요** (`Reservation.from_response(data,
   seats=..., wct_no=...)`). 반쯤 채워진 객체가 돌아다니면 안 됩니다.

4. **상속이 아니라 합성.** `Ticket`·`Reservation` 은 `Train` 을 **참조**합니다
   (`ticket.train.dep_name`). 예약에 `has_seat()` 이 딸려오는 건 말이 안 됩니다.
   새 모델도 "A는 B다"가 참일 때만 상속하세요.

5. **파싱 관용성은 `models/parsing.py` 에.** 코레일은 필드를 빼먹거나 빈 문자열로
   보냅니다. `data.get(...)` 을 날로 쓰지 말고 `text`/`integer`/`floating` 을 쓰세요.
   모델 생성이 응답 누락으로 죽으면 안 됩니다.

6. **예외는 계층 안에서.** 새 코레일 응답 코드는 `KorailError` 를 상속하고 `codes`·
   `default_msg` 만 채우면 `error_for_code()` 가 자동으로 찾아갑니다. 등록 테이블을
   만들지 마세요. 클라이언트 측 입력 오류는 `KorailError` 가 아니라
   `PykorailError` 의 형제로 (`StationNotFoundError` 참고).

7. **상태 변경 메서드는 `None` 을 반환하고 실패 시 예외.** `create`/`pay`/`cancel`/
   `refund`. 성공 여부를 불리언으로 돌려주지 마세요.

8. **생성자에서 I/O 금지.** `Korail()` 은 네트워크를 치지 않습니다. 한 줄 편의가
   필요하면 `Korail.logged_in()` 같은 팩토리를 쓰세요.

---

## 3. 외부 API 불변식 — 가장 위험한 부분

### 새 엔드포인트는 APK 검증이 선행 조건입니다

**공식 코레일톡+(`com.korail.talk`) APK 를 디컴파일해 경로·폼 필드·서명 대상 여부를
확인하기 전에는 엔드포인트를 추가하지 마세요.** 추측한 필드 이름은 에러가 아니라
**조용한 빈 값**이 되어, 테스트는 통과하고 사용자만 실패합니다. 절차는
`add-endpoint` 스킬(`.claude/skills/add-endpoint/SKILL.md`)에 있습니다.

확인할 수 없으면 **거기서 멈추고 그 사실을 보고하세요.** "아마 이럴 것 같다" 로
코드를 넣는 것이 이 저장소에서 가장 비싼 실수입니다.

### 그 밖의 불변식

이 패키지는 **문서 없는 사설 API** 를 상대합니다. 서버가 앱 버전·기기 문자열·TLS
지문·서명을 교차 검증하므로, 아래를 건드리면 조용히 로그인이 막힙니다.

- **작동하는 값을 근거 없이 바꾸지 마세요**: `constants.py` 의 `USER_AGENT`,
  `APP_VERSION`, `API_KEY`, `SID_KEY`, `DEVICE_ID`, `IMPERSONATE`, 그리고
  `auth/dynapath.py` 의 인코딩 테이블·상수(`_TABLE`, `_RADIX`, `_MODULUS`, `_CHUNK`).
- **폼 필드를 정리하지 마세요.** 빈 문자열로 보내는 필드(`txtChgFlg2` 등)나 조회
  엔드포인트만 `Key` 없이 빈 `Sid` 를 보내는 것은 앱 동작을 그대로 옮긴 것입니다.
  "안 쓰는 것 같으니 지운다" 는 회귀입니다.
- **UA 와 서명은 같은 기기를 가리켜야 합니다.** `device_profile` 이 User-Agent 와
  DynaPath 서명(`os=`·`dm=`)을 함께 바꿉니다. 한쪽만 바꾸면 그 불일치가 탐지 신호입니다.
- **암호화 형태를 "고치지" 마세요.** 이중 base64, `Sid` 끝의 개행, 키를 IV 로 재사용
  하는 AES-CBC — 전부 서버가 그 모양을 기대합니다.

리팩터링으로 이 영역을 건드렸다면, **요청 페이로드가 그대로인지 증명**하세요.
가짜 세션으로 요청 kwargs 를 캡처해 변경 전후를 dict 단위로 비교하는 테스트를 쓰면 됩니다
(`tests/test_resources.py` 의 폼 필드 단언 참고).

---

## 4. Python 규약

- **최소 버전 3.10.** `pyproject.toml` 의 `requires-python` 과 `_compat.py` 런타임
  가드가 함께 막습니다. 3.10 에 없는 문법(`type` 문, 3.12 제네릭 등)을 쓰지 마세요.
- **모든 모듈은 `from __future__ import annotations` 로 시작.** 어노테이션이 지연
  평가돼야 순환 import 없이 타입을 쓸 수 있습니다.
- **공개 함수·메서드에는 전부 타입 힌트.** `Any` 는 경계(응답 dict, `**kwargs`)에만.
- **런타임에 필요 없는 import 는 `if TYPE_CHECKING:` 블록으로.**
- **`Enum` 대신 `Final` 문자열 상수 + `Literal` 별칭.** 이 값들은 폼에 그대로 실려
  나가는데 `str` 혼합 `Enum` 은 파이썬 버전에 따라 `str()` 이 `"TrainType.KTX"` 로
  나와 전송 값이 조용히 깨집니다. `options.py` 의 패턴을 따르세요.
- **가변 기본 인자 금지.** 불변 모델의 컬렉션 필드는 `tuple` 기본값 `()` 을 쓰세요.
- **텍스트 파일 I/O 는 `encoding="utf-8"` 을 명시.** `open()`·`read_text()`·
  `write_text()` 전부입니다. 파이썬 기본 인코딩은 플랫폼 로케일을 따라가서
  Windows 에서는 UTF-8 이 아니고(cp1252 · cp949), 한국어가 든 이 저장소의 파일은
  **그 환경에서만** 깨집니다. CI 는 우분투에서만 도니 실행으로는 안 잡힙니다 —
  `tests/test_style.py` 가 AST 로 강제합니다.
- **`dict.get()` 연쇄 대신 파싱 헬퍼.**
- **주석은 "무엇"이 아니라 "왜".** 특히 이상해 보이는 코드(앱 동작 재현, 서버 요구
  사항)에는 이유를 남기세요 — 다음 사람이 "정리"하려 들기 때문입니다.
- **문서화 문자열은 한국어**, 코드 식별자는 영어. 기존 파일의 밀도와 어조를 맞추세요.
- **비밀은 `__repr__` 에서 마스킹.** `Card.__repr__` 이 카드번호 뒤 4자리만 남기는
  것처럼, 민감한 값을 담는 모델은 로그·트레이스백에 새지 않게 하세요.

### ruff / ty

- 설정은 `pyproject.toml` 안에만. 별도 `.ruff.toml` 을 만들지 마세요.
- 줄 길이 120. 포매터가 결정하게 두고 손으로 줄바꿈하지 마세요.
- `ruff format` → `ruff check --fix` → `ty check` 순서로 돌립니다.
- 규칙을 통째로 끄지 말고 파일 단위 예외(`per-file-ignores`)를 쓰세요.
- `ty` 는 아직 젊은 검사기입니다. 오탐이라 확신하면 코드를 좁혀 주는 쪽(`cast`,
  명시적 지역 변수)을 먼저 시도하고, 그래도 안 되면 이유를 적고 억제하세요.
- 클래스 안에 `list`/`dict`/`type` 같은 빌트인 이름의 메서드를 만들지 마세요 —
  같은 클래스의 어노테이션(`-> list[X]`)을 가려 검사기가 깨집니다. 리소스가
  `all()` 인 이유입니다.

---

## 5. 테스트 — 강제 규약

### 5.1 제어 흐름 금지

**테스트 함수 안에 `if` / `for` / `while` 문을 쓰지 마세요.** `tests/test_style.py`
가 AST 를 훑어 이 규칙을 자동으로 강제합니다 — 어기면 테스트가 빨갛게 실패합니다.

- 케이스가 여러 개면 → `@pytest.mark.parametrize`
- 반복 검증이 필요하면 → 컴프리헨션으로 **위반 목록을 만들어 빈 리스트와 비교**

```python
# 나쁨 — 어떤 프로파일에서 깨졌는지 알 수 없고, 첫 실패에서 멈춤
def test_build_ids():
    for profile in DEVICE_PROFILES:
        assert profile.build_id.startswith(...)


# 좋음 — 위반 전부가 한 번에 드러남
def test_build_ids():
    bad = [p.id for p in DEVICE_PROFILES if not p.build_id.startswith(...)]
    assert bad == []
```

컴프리헨션은 값을 뽑는 **식**이라 허용합니다. 금지 대상은 제어 흐름 **문**입니다.
`pytest.raises`, `pytest.approx`, `monkeypatch`, 픽스처 등 pytest 기능을 최대한 쓰세요.

### 5.2 Given–When–Then

**모든 테스트는 준비·실행·검증 경계를 주석으로 드러냅니다.** `tests/test_style.py`
가 AST 로 강제합니다.

- `# when` 과 `# then` 은 **필수**입니다.
- `# given` 은 실행 전에 준비할 코드가 있을 때만 씁니다 — 준비가 없는데 빈 Given 을
  두면 잡음일 뿐입니다.
- 예외 검증처럼 실행과 검증이 한 덩어리면 `# when & then` 으로 묶습니다.
- 순서는 given → when → then. `# then` 이 `# when` 보다 앞에 오면 실패합니다.

```python
def test_corporate_card_flag(self, korail) -> None:
    # given
    client, session = korail
    rsv = client.reservations.all()[0]

    # when
    client.reservations.pay(rsv, Card("1234", "12", "1234567890", "2812", is_corporate=True))

    # then
    assert session.kwargs_for("pay")["data"]["hidAthnDvCd1"] == "S"


def test_rejects_negative_installment(self) -> None:
    # when & then
    with pytest.raises(ValueError, match="installment"):
        card_with(installment=-1)


def test_individual_by_default(self) -> None:
    # when
    auth_type = card_with().auth_type

    # then
    assert auth_type == "J"
```

**when 은 "무엇을 실행했는지" 한 가지만** 담으세요. when 블록이 여러 줄이면 대개
테스트 하나가 두 가지를 검증하고 있다는 신호입니다.

### 5.3 커버리지 90% 하한

`pytest` 가 `--cov-fail-under=90` 으로 돌아갑니다. **미달이면 실패입니다.**
현재 96%. 게이트를 낮추거나 `--no-cov` 로 우회하지 마세요 — 테스트를 쓰세요.

### 5.4 그 밖의 규약

- **네트워크 금지.** 테스트는 절대 실제 요청을 보내지 않습니다. `conftest.py` 의
  `FakeSession` 과 `make_korail`/`korail` 픽스처를 쓰세요.
- **응답 샘플은 `tests/payloads.py` 에.** 필드 이름은 실제 응답에서 온 것이니
  지어내지 마세요. 새 페이로드가 필요하면 여기에 추가하고 공유합니다.
- **테스트 하나에 개념 하나.** 이름은 검증하는 **행동**을 말해야 합니다
  (`test_missing_wait_flag_is_not_applicable`, `test_logout_clears_account_but_keeps_connection`).
- **경계 동작을 테스트하세요**: 필드 누락, 빈 문자열, 자정을 넘기는 시각, 매진,
  예약대기, 로그인 실패. 이 코드베이스의 버그는 대부분 거기서 나왔습니다.
- 단언에 이유가 필요하면 메시지를 붙이세요:
  `assert len(session.calls) == 1, "두 번째 호출은 캐시를 써야 합니다"`.

---

## 6. CI/CD

- **CI** (`.github/workflows/ci.yml`) — 린트·타입 검사, Python **3.10–3.14** 테스트,
  빌드·설치 확인, Trivy 스캔. **전부 우분투에서만 돕니다** — `src/` 에 플랫폼 분기가
  없고, Windows 러너가 실제로 잡아주던 인코딩 기본값 문제는 `tests/test_style.py`
  의 `test_text_io_declares_encoding` 이 AST 로 대신합니다.
- **CodeRabbit 리뷰** (`.coderabbit.yaml`) — main 으로 가는 PR 에 리뷰 코멘트를
  답니다. GitHub App 이라 워크플로가 아니고, **필수 체크가 아닙니다**
  (`request_changes_workflow: false`). 설정에 경로별 리뷰 지침이 들어 있고,
  `knowledge_base.code_guidelines` 로 이 파일과 `CONTRIBUTING.md`·스킬을 리뷰
  기준으로 읽습니다 — **규범을 고치면 리뷰 기준도 함께 바뀝니다.**
- **Dependabot** (`.github/dependabot.yml`) — 액션과 `uv` 의존성을 주 1회(월요일)
  범프합니다. 워크플로가 아니라 GitHub 기능이고, **여기서 오는 PR 도 `ci-ok` 를
  통과해야 머지됩니다.**
- **Release** (`.github/workflows/release.yml`) — `v*` 태그에서 동작. 태그와 패키지
  버전을 대조하고, 전 버전 게이트를 다시 돌린 뒤 PyPI(Trusted Publishing)에 올리고
  릴리스 노트를 자동 생성합니다.

에이전트가 알아야 할 것:

- **버전은 git 태그가 유일한 출처입니다** (hatch-vcs). `pyproject.toml` 에도
  `__init__.py` 에도 숫자가 없습니다 — **어디에도 버전을 하드코딩하지 마세요.**
  `git tag v0.2.0` 이 곧 0.2.0 릴리스입니다. `tests/test_packaging.py` 가 하드코딩
  부활과 얕은 체크아웃(`fetch-depth`)을 막습니다.
- **지원 버전을 바꾸면 세 곳을 맞추세요**: `requires-python`, `_compat.MIN_PYTHON`,
  `pyproject.toml` 의 classifier, 그리고 두 워크플로의 매트릭스.
  `tests/test_packaging.py` 가 앞의 셋을 강제합니다.
- **워크플로를 수정했으면 `actionlint` 로 검증하세요** (shellcheck 도 함께 돕니다):
  ```bash
  uv run actionlint .github/workflows/*.yml
  ```
  `uvx` 로 즉석 실행하지 않고 dev 의존성으로 잠가 둔 것은 의도입니다 — 필수 체크가
  걸리는 도구의 버전이 안 잠겨 있으면 서드파티의 새 릴리스가 무관한 PR 을 빨갛게
  만듭니다. CI 의 린트 잡이 같은 명령을 돌리므로 빠뜨려도 PR 에서 걸립니다.
  `release.yml` 은 태그에서만 돌아 CI 가 실행으로는 못 잡으니, 이 정적 검사가
  그쪽의 유일한 그물입니다.
- **Trivy 가 HIGH/CRITICAL 에서 빌드를 막습니다.** 취약점이 뜨면 의존성을 올리세요.
  무시가 정당하면 `.trivyignore` 에 **만료일과 이유**를 함께 적으세요.
- **Dependabot PR 이 빨간 것은 대개 정상 신호입니다.** `ruff` 범프는 새 포맷·린트
  규칙을 들고 오고, `ty` 는 아직 0.x 베타라 범프마다 진단이 늘어납니다. 게이트를 낮추거나
  범프를 되돌리지 말고 **그 PR 안에서 코드를 고치세요** — 그게 이 PR 의 목적입니다.
- **런타임 의존성의 하한을 손으로 올리지 마세요.** 라이브러리라
  `versioning-strategy: increase-if-necessary` 로 고정해 뒀습니다 — 평소에는
  `uv.lock` 만 움직이고 `pyproject.toml` 의 `>=` 는 그대로입니다. 하한을 올리는
  것은 사용자 환경을 좁히는 결정이라 근거(실제 필요한 최소 버전)가 있을 때만.
- 커버리지 게이트를 CI 에서만 끄는 식의 우회를 만들지 마세요.

---

## 7. 작업 흐름

1. 고치기 전에 **읽으세요.** 이 코드베이스에는 이유 있는 이상한 코드가 많습니다.
2. 요청받은 범위만 하세요. 지나가다 본 것을 같이 "정리"하지 마세요.
3. 외부 API 동작을 바꿨다면 페이로드 불변을 증명하세요.
4. `ruff format` → `ruff check` → `ty check` → `pytest` 전부 통과.
5. 무엇을 바꿨고 무엇을 검증했는지 사실대로 보고하세요. 실패는 실패라고 말하세요.

### 커밋 · PR · 브랜치 이름

커밋 요약 줄 · PR 제목 · 브랜치 이름이 **같은 접두사 하나**를 씁니다. 형식은
`<PREFIX>: <요약>` 이고 본문에는 **왜** 를 적습니다.

`ADD:` 새로 넣음 · `FIX:` 버그 수정 · `REF:` 구조 리팩터링(동작 그대로) ·
`DEL:` 제거 · `DOCS:` 문서만 · `UPT:` 의존 패키지 버전 업데이트

`ADD:`·`DEL:` 은 **코드와 의존성**에 대한 것입니다. 문서와 에이전트 설정
(`.claude/` · `.agents/` · `.cursor/` · `.opencode/`)은 추가·수정·삭제 모두
`DOCS:` 입니다. `.github/workflows/` 는 실행되므로 코드로 봅니다.

브랜치는 `<접두사 소문자>/<요약-kebab>` (`fix/midnight-arrival`).

경계가 헷갈리는 경우, 릴리스 노트 라벨 대응, 커밋 전 점검 목록은 **`commit`
스킬**(`.claude/skills/commit/SKILL.md`)에 있습니다. 커밋하거나 PR 을 열기 전에
읽으세요.

### 하지 말 것


- 코레일 서버에 실제 요청 보내기 (역 마스터 같은 공개 조회를 **의도적으로** 확인할
  때만, 그것도 명시적 동의 아래).
- 자격증명·카드번호를 코드·테스트·로그에 넣기.
- 커버리지 게이트나 린트 규칙 낮추기.
- 검증 없이 "고쳤습니다" 라고 보고하기.
