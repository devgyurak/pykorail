# CLAUDE.md

@AGENTS.md

위 파일이 이 저장소의 규범입니다 — 아키텍처 계층, 외부 API 불변식, Python/ruff/ty
규약, 테스트 규칙(제어 흐름 금지 · 커버리지 90%)이 전부 거기 있습니다. 아래는
Claude Code 에서만 의미 있는 내용입니다.

## 서브에이전트

- `architecture-guard` — 계층 위반, 상속/가변성 규칙 위반을 잡습니다. `_async/`·`_sync/`·
  resources·모델·클라이언트를 건드린 뒤 호출하세요.
- `wire-parity-auditor` — 요청 페이로드가 바뀌지 않았는지 증명합니다. `constants.py`,
  `auth/`, `crypto.py`, `transport.py`, `_async/` 리소스의 폼 필드를 건드렸다면
  **반드시** 호출하세요.
- `test-author` — 규약(제어 흐름 금지, parametrize, 90% 커버리지)에 맞는 pytest 를
  씁니다. 커버리지가 떨어졌을 때 부르세요.

## 스킬

- `verify` — 전체 게이트(format → lint → typecheck → test+coverage)를 순서대로 실행.
- `add-endpoint` — 새 코레일 엔드포인트 추가 절차. **APK 디컴파일 검증이 0단계**입니다.
- `add-error-code` — 새 응답 코드를 예외 계층에 매핑하는 절차.
- `commit` — 커밋 메시지·PR 제목·브랜치 이름 규약(`ADD:`/`FIX:`/`REF:`/`DEL:`/
  `DOCS:`/`UPT:`). 커밋하거나 PR 을 열기 전에 읽으세요.

## I/O 계층

`src/pykorail/_sync` · `tests/_sync` 는 `_async` 에서 `scripts/unasync.py` 가 만드는
**생성물**입니다 — 손으로 고치지 마세요. `_async` 를 고친 뒤
`uv run python scripts/unasync.py` 를 돌리고, `uv run python scripts/unasync.py --check`
로 최신인지 확인합니다(테스트·CI 도 같은 검사를 돌립니다). 자세한 규칙은 AGENTS.md §2-9.

## 도구 사용

- 셸에서 `python`/`pip` 대신 항상 `uv run` 을 쓰세요.
- 파일 검색은 Grep/Glob 을 쓰고 `grep`/`find` 셸 호출은 피하세요.
- 넓은 탐색이 필요하면 Explore 서브에이전트에 위임하고 결론만 받으세요.
- 커밋은 사용자가 요청할 때만 합니다.
