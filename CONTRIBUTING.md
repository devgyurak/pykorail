# 기여 가이드

pykorail 에 관심 가져 주셔서 고맙습니다. 버그 신고 한 줄부터 오타 수정까지 전부
환영합니다.

이 프로젝트는 **문서 없는 사설 API** 를 상대합니다. 그래서 다른 라이브러리와 규칙이
조금 다른 부분이 있는데, 아래에 이유와 함께 적어 뒀습니다.

---

## 먼저 알아두면 좋은 것

**코레일이 바꾸면 우리가 깨집니다.** 이 패키지는 코레일톡+ 앱이 쓰는 비공개
엔드포인트를 흉내 냅니다. 어제까지 되던 코드가 오늘 안 되는 일이 실제로 일어나고,
그건 대개 우리 버그가 아니라 서버 변경입니다. 그래서 **"어제까지 되던 게 안 돼요"
전용 이슈 템플릿**이 따로 있습니다.

**동작하는 값은 함부로 바꾸지 않습니다.** `USER_AGENT` · `APP_VERSION` · 서명
알고리즘 · 빈 문자열로 보내는 폼 필드 — 이상해 보여도 앱이 그렇게 하기 때문에
그대로 둔 것입니다. "정리" 하면 조용히 로그인이 막힙니다.

**추측한 필드 이름은 에러가 아니라 빈 값이 됩니다.** 그래서 새 엔드포인트는
**공식 APK 를 디컴파일해 확인한 뒤에만** 추가합니다 ([아래](#새-엔드포인트-추가) 참조).

---

## 어떻게 기여할 수 있나요

코드만 기여가 아닙니다. 아래 순서대로 **문턱이 낮습니다.**

### 🐛 버그 신고

[버그 신고 템플릿](https://github.com/devgyurak/pykorail/issues/new?template=bug_report.yml)

> [!CAUTION]
> **아이디·비밀번호·카드번호를 붙여넣지 마세요.** 로그와 응답 본문에는 이름·이메일·
> 전화번호·예약번호가 섞여 있습니다. 올리기 전에 `***` 로 가려 주세요.

### 🚄 코레일 API 변경 제보

**가장 도움이 되는 기여입니다.** 서버가 바뀌면 저희가 먼저 알기 어렵습니다.

[API 변경 템플릿](https://github.com/devgyurak/pykorail/issues/new?template=external_api_change.yml)

공식 앱에서는 되는데 라이브러리에서만 안 된다면, 응답 원문(개인정보 가린 것)과
마지막으로 정상 동작한 날짜를 알려 주시면 원인을 크게 좁힐 수 있습니다.

### 📝 문서

오타·잘못된 설명·부족한 예제 전부 환영합니다. `README.md` 는 처음 오는 사람용,
[`docs/reference.md`](docs/reference.md) 는 전체 API 레퍼런스입니다.

> 문서는 테스트가 지킵니다. `tests/test_readme.py` 가 메서드·필드·코드값이 실제
> 코드와 일치하는지 대조하므로, 코드를 바꾸면 문서도 함께 고쳐야 통과합니다.

### ✨ 기능 제안

[기능 제안 템플릿](https://github.com/devgyurak/pykorail/issues/new?template=feature_request.yml)

**해결책보다 문제를 먼저** 적어 주세요. 지금 어떻게 우회하고 있는지 알려 주시면
더 나은 설계를 찾는 데 도움이 됩니다.

### 💻 코드

큰 변경이라면 **먼저 이슈로 상의해 주세요.** 방향이 어긋난 채로 시간을 쓰는 것보다
낫습니다. 작은 수정은 바로 PR 보내셔도 됩니다.

---

## 개발 환경 설정

[uv](https://docs.astral.sh/uv/) 로만 돌립니다. `pip` 이나 맨몸 `python` 은 쓰지
마세요 — 잠긴 의존성과 어긋납니다.

```bash
git clone https://github.com/devgyurak/pykorail
cd pykorail
uv sync --all-extras
```

파이썬은 uv 가 알아서 받습니다. 지원 범위는 **3.10 – 3.14** 입니다.

### 품질 게이트

작업을 끝내기 전에 **네 개를 전부** 통과시켜 주세요.

```bash
uv run ruff format     # 포매팅 (검사 전에 먼저)
uv run ruff check      # 린트
uv run ty check        # 타입 검사
uv run pytest          # 테스트 + 커버리지
```

한 줄로:

```bash
uv run ruff format && uv run ruff check --fix && uv run ty check && uv run pytest
```

실패를 `# noqa` · `# type: ignore` · `--no-cov` 로 우회하지 말고 원인을 고쳐 주세요.
정말 우회가 맞다면 **왜** 인지 같은 줄에 적어 주세요.

---

## 프로젝트 구조

```
pykorail/
├── client.py       Korail — 로그인·로그아웃·연결 (엔드포인트는 여기 없습니다)
├── api.py          ApiClient — 요청/응답/서명/에러 변환
├── resources/      stations · trains · reservations · tickets  ← 엔드포인트는 전부 여기
├── models/         불변 응답 모델 + 승객·카드 파라미터 객체
├── exceptions/     base · api(코드매핑) · network · validation
├── device/         기기 프로파일 + 카탈로그 100개
├── auth/           dynapath(서명) · signer · netfunnel
├── transport.py    curl_cffi 우선 / requests 폴백
└── crypto.py       AES 원시연산
```

지켜야 할 계층 규칙과 그 이유는 [`AGENTS.md`](AGENTS.md) 에 정리돼 있습니다.
요약하면:

- **엔드포인트는 리소스에만.** `Korail` 본체에 API 메서드를 붙이지 마세요.
- **HTTP 는 `ApiClient` 를 통해서만.** `_session` 을 직접 만지지 마세요.
- **응답 모델은 불변** (`@dataclass(frozen=True)` + `from_response()`).
  객체를 만든 뒤 필드를 채우지 마세요.
- **상속이 아니라 합성.** `Ticket`·`Reservation` 은 `Train` 을 참조합니다.
- **상태 변경 메서드는 `None` 반환, 실패 시 예외.**

---

## 테스트

### Given–When–Then (자동 강제)

모든 테스트는 준비·실행·검증 경계를 주석으로 드러냅니다.

```python
def test_corporate_card_flag(self, korail) -> None:
    # given
    client, session = korail
    rsv = client.reservations.all()[0]

    # when
    client.reservations.pay(rsv, Card("1234", "12", "1234567890", "2812", is_corporate=True))

    # then
    assert session.kwargs_for("pay")["data"]["hidAthnDvCd1"] == "S"
```

- `# when` · `# then` **필수**, `# given` 은 준비 코드가 있을 때만
- 예외 검증처럼 실행·검증이 한 덩어리면 `# when & then`

### `if` / `for` / `while` 금지 (자동 강제)

테스트에 분기·반복이 들어가면 통과해도 **무엇을 통과한 건지** 알 수 없습니다.

```python
# 나쁨 — 어디서 깨졌는지 모르고 첫 실패에서 멈춤
for profile in DEVICE_PROFILES:
    assert profile.build_id.startswith(...)

# 좋음 — 위반 전부가 한 번에 드러남
bad = [p.id for p in DEVICE_PROFILES if not p.build_id.startswith(...)]
assert bad == []
```

케이스가 여러 개면 `@pytest.mark.parametrize` 로 펼치세요. 컴프리헨션은 값을 뽑는
**식**이라 허용됩니다.

두 규칙 모두 `tests/test_style.py` 가 AST 로 검사하므로, 어기면 바로 빨갛게 됩니다.

### 커버리지 90%

`pytest` 가 `--cov-fail-under=90` 으로 돌아갑니다 (현재 96%). 게이트를 낮추지
말고 테스트를 써 주세요.

### 네트워크 금지

테스트는 **절대 실제 요청을 보내지 않습니다.** `tests/conftest.py` 의 `FakeSession`
과 `korail` / `make_korail` 픽스처를 쓰세요. 응답 샘플은 `tests/payloads.py` 에
모읍니다 — **필드 이름을 지어내지 마세요.**

### 특히 잘 깨지는 곳

이 코드베이스의 버그는 대부분 여기서 나왔습니다. 새 코드에도 함께 봐 주세요.

- 응답 필드 누락 · 빈 문자열
- 자정을 넘기는 운행 시간
- 타임존 (naive = KST, aware = 변환)
- 매진 · 예약대기 분기
- 승객 합치기 (정렬 안 된 입력)
- 로그인 실패 경로

---

## 새 엔드포인트 추가

> [!IMPORTANT]
> **APK 검증이 선행 조건입니다.** 추측한 필드 이름은 에러가 아니라 조용한 빈 값이
> 되어, 테스트는 통과하고 사용자만 실패합니다.

공식 코레일톡+(`com.korail.talk`) APK 를 디컴파일해 아래를 확인해 주세요.

1. 엔드포인트 경로 (`com.korail.mobile.…`)
2. **요청 폼 필드의 정확한 철자와 대소문자**
3. `Device` · `Version` · `Key` · `Sid` 중 무엇을 싣는지 (엔드포인트마다 다릅니다)
4. 응답 필드 이름과 중첩 구조
5. DynaPath 서명 대상인지 여부

확인한 내용을 PR 본문에 적어 주세요:

```
APK: com.korail.talk versionName 7.0.1 (2026-08 추출)
경로: com.korail.mobile.transfer.TransferView
요청: Device, Version, Key, txtTrnNo, txtDptDt
응답: {"trsf_infos": {"trsf_info": [{"h_trsf_stn_nm", "h_trsf_wait_tm"}]}}
서명: DynaPath 대상 아님
```

**확인할 수 없다면 그 사실을 이슈로 알려 주세요.** 추측으로 채운 PR 보다 "여기까지
확인했고 이건 모르겠다" 가 훨씬 도움이 됩니다.

자세한 절차는 [`.claude/skills/add-endpoint/SKILL.md`](.claude/skills/add-endpoint/SKILL.md)
에 단계별로 있습니다.

---

## PR 보내기

### 1. 접두사 하나 고르기

커밋 요약 줄 · PR 제목 · 브랜치 이름이 **같은 접두사**를 씁니다. 한 PR 에 한 가지
변경만 담으므로 접두사도 하나로 정해집니다.

| 접두사 | 쓰는 때 |
| ------- | ------------------------------------------------------- |
| `ADD:`  | 없던 것을 새로 넣을 때 — 기능 · 엔드포인트 · 테스트 · 의존성 추가 |
| `FIX:`  | 버그 수정 — 의도한 동작과 실제가 달랐던 것 |
| `REF:`  | 코드 구조 리팩터링 — **겉보기 동작은 그대로** |
| `DEL:`  | 제거 — 기능 · 파일 · 죽은 코드 |
| `DOCS:` | 문서만 — README · 독스트링 |
| `UPT:`  | 의존 패키지 **버전 업데이트** |

헷갈리기 쉬운 경계 세 가지만 미리:

- **동작이 바뀌면 `REF:` 가 아닙니다.** 새 동작이면 `ADD:`, 잘못된 동작을 바로잡은
  것이면 `FIX:`.
- **코레일이 API 를 바꿔 대응한 것은 `FIX:`** 입니다 (`external-api` 라벨도 함께).
- **의존성을 새로 넣으면 `ADD:`, 버전만 올리면 `UPT:`**.

문서·에이전트 설정은 **추가해도 `DOCS:`** 입니다 — `ADD:`·`DEL:` 은 코드와 의존성에
대한 것입니다. (`.github/workflows/` 는 실행되므로 코드로 봅니다.)

나머지 경계와 커밋 전 점검 목록은
[`.claude/skills/commit/SKILL.md`](.claude/skills/commit/SKILL.md) 에 있습니다.
코딩 에이전트를 쓰신다면 커밋할 때 이 스킬을 열어 보게 돼 있습니다.

### 2. 브랜치

`<접두사 소문자>/<요약-kebab>`

```bash
git switch -c fix/past-departure-guard
```

### 3. 커밋 메시지

```
FIX: 과거 시각 조회를 요청 전에 차단

서버가 과거 시각에도 빈 결과만 주기 때문에 "떠난 열차"와
"열차 없음"이 구분되지 않았습니다.
```

요약 줄은 한국어 명사형 종결로, 마침표 없이 50자 안팎. 본문에는 **왜** 를 적어
주세요 — **무엇**은 diff 가 이미 말합니다. 이 저장소에는 이유 있는 이상한 코드가
많아서, 다음 사람이 "정리"하려 들지 않게 하려면 이유가 남아 있어야 합니다.

형식이 틀렸다고 PR 을 돌려보내지는 않습니다. 저희가 고쳐 드릴 테니 내용에
집중하세요.

### 4. PR 제목

커밋과 같습니다 — `FIX: 과거 시각 조회를 요청 전에 차단`.

`main` 은 squash 머지가 가능해서 PR 제목이 그대로 히스토리에 남습니다. 그래서
커밋과 같은 형식을 씁니다.

### 5. 라벨 → 릴리스 노트

릴리스 노트는 **PR 라벨**로 자동 분류됩니다 ([`.github/release.yml`](.github/release.yml)).
맞는 것을 하나 붙여 주세요. 권한이 없으면 저희가 붙이겠습니다.

| 라벨 | 분류 |
| --- | --- |
| `breaking` | 💥 호환성이 깨지는 변경 |
| `feature` · `enhancement` | ✨ 새 기능 |
| `bug` · `fix` | 🐛 버그 수정 |
| `security` | 🔐 보안 |
| `external-api` | 🚄 코레일 API 대응 |
| `dependencies` | 📦 의존성 |
| `documentation` | 📝 문서 |
| `refactor` · `chore` · `test` · `ci` | 🧹 내부 정리 |

### 6. 체크리스트

PR 템플릿에 들어 있습니다. 특히:

- [ ] 네 개 게이트 전부 통과
- [ ] 테스트에 `if`/`for`/`while` **문** 없음, GWT 주석 있음
- [ ] 공개 API 를 바꿨다면 `docs/reference.md` 갱신
- [ ] **외부 API 를 건드렸다면 요청 페이로드가 그대로임을 확인**

### 7. CI

PR 을 열면 자동으로 돕니다 — 린트 · 타입 검사 · 워크플로 린트(actionlint) ·
Python 3.10–3.14 테스트 · 빌드 · Trivy 보안 스캔. 전부 우분투에서 돕니다.

여기에 더해 **main 으로 가는 PR** 에는 **CodeRabbit** 이 리뷰 코멘트를 답니다
(설정은 [`.coderabbit.yaml`](.coderabbit.yaml)). 초안(draft) PR 은 건너뜁니다.
필수 통과 항목이 아니니 지적에 동의하지 않으시면 그렇게 답해 주세요 — 사람이
판단합니다. PR 에서 `@coderabbitai` 로 말을 걸 수도 있습니다.

> 다만 **리뷰 스레드는 전부 resolve 해야 머지됩니다** (아래 8번). 반영하든 안
> 하든 답글을 달고 해결 처리해 주세요.

빨간불이 떠도 괜찮습니다. 어디서 막혔는지 말씀해 주시면 같이 봅니다.

### 8. 머지

`main` 은 보호돼 있습니다. **@devgyurak 의 승인**과 **CI(`ci-ok`) 통과** 후에만
머지되고, 리뷰 코멘트가 남아 있으면 머지 버튼이 잠깁니다. 새 커밋을 올리면 기존
승인이 무효화되니, 리뷰 반영 후 다시 승인을 요청해 주세요.

---

## 리뷰

- 작은 PR 일수록 빨리 머지됩니다. 한 PR 에 한 가지 변경을 담아 주세요.
- 리뷰에서 "왜 이렇게 했나요?" 를 자주 묻습니다. 이 코드베이스에는 **이유 있는
  이상한 코드**가 많아서, 의도를 확인하는 과정입니다. 트집이 아닙니다.
- 반대로, 여러분이 보기에 이상한 코드가 있다면 물어봐 주세요. 이유가 문서화되지
  않았다면 그것 자체가 고쳐야 할 문제입니다.
- 메인테이너가 1인이라 답이 늦을 수 있습니다. 일주일이 지나도 반응이 없으면
  PR 에 댓글로 한 번 더 알려 주세요.

---

## 저장소 설정 (메인테이너용)

`main` 은 보호돼 있습니다 — **직접 푸시할 수 없고, 코드 소유자(@devgyurak) 승인
없이는 머지되지 않습니다.**

저장소 파일만으로는 강제되지 않습니다. 브랜치 보호는 GitHub 설정이라 한 번 켜 줘야
합니다.

```bash
.github/scripts/setup-branch-protection.sh
```

적용되는 규칙 ([`main-protection.json`](.github/rulesets/main-protection.json)):

- main 은 PR 로만 변경 가능
- 승인 1개 이상 + [`CODEOWNERS`](.github/CODEOWNERS) 승인 필수
- 새 커밋이 올라오면 기존 승인 무효화, 마지막 푸시한 사람 외의 승인 필요
- 리뷰 코멘트를 전부 해결해야 머지 가능
- 상태 체크 `ci-ok` 통과 필수 (최신 main 기준)
- main 삭제·강제푸시 금지

적용 후 확인:

```bash
gh api repos/devgyurak/pykorail/rulesets --jq '.[] | "\(.id) \(.name) \(.enforcement)"'
git push origin main   # 거부되면 정상
```

> [!NOTE]
> **admin 도 main 에 직접 push 할 수 없습니다.** `bypass_actors` 의
> `bypass_mode` 가 `pull_request` 라서, 우회는 "PR 안에서 승인 요건을 건너뛰는 것"
> 까지만 허용되고 직접 push 는 여전히 막힙니다.
>
> 이 우회를 둔 이유는 GitHub 이 **자기 PR 을 스스로 승인하는 것을 금지**하기
> 때문입니다 — 1인 저장소에서 예외가 없으면 아무것도 머지하지 못합니다.
>
> - 본인 PR 도 예외 없이 막으려면 → `bypass_actors` 를 `[]` 로
> - 긴급 시 직접 push 도 허용하려면 → `bypass_mode` 를 `"always"` 로

---

## 릴리스 (메인테이너용)

버전의 유일한 출처는 **git 태그**입니다. 파일에 버전을 적지 않습니다.

```bash
git tag v0.2.0 && git push origin v0.2.0
```

태그를 밀면 버전 도출 → 전 버전 게이트 → Trivy → 빌드 → PyPI 업로드 →
릴리스 노트 생성이 자동으로 돕니다.

---

## 행동 강령

이 프로젝트는 [행동 강령](CODE_OF_CONDUCT.md)을 따릅니다. 참여하시는 것으로
동의한 것으로 봅니다.

## 보안

취약점은 공개 이슈가 아니라 [보안 정책](SECURITY.md)의 절차로 알려 주세요.

## 라이선스

기여하신 내용은 프로젝트와 같은 [MIT 라이선스](LICENSE)로 배포됩니다.
