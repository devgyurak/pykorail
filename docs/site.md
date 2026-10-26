# 문서 사이트

<https://pykorail.devgyurak.com> 의 랜딩 페이지와 문서는 [`site/`](../site/) 에 있고
[Astro Starlight](https://starlight.astro.build) 로 빌드합니다. 거기서 직접 쓰는 것은 랜딩
페이지(`site/src/content/docs/index.mdx`) 하나뿐입니다. 나머지 페이지는 빌드 시점에
`site/scripts/sync-docs.mjs` 가 저장소의 Markdown 에서 만들어 냅니다 — **`README.md` ·
`docs/reference.md` · `CONTRIBUTING.md` 를 고치세요. 복사본은 고치지 않습니다.**

| 원본 | 사이트 경로 |
| --- | --- |
| `README.md` (첫 `## ` 부터) | `/overview/` |
| `docs/reference.md` | `/reference/` |
| `CONTRIBUTING.md` | `/contributing/` |

공개 범위는 `sync-docs.mjs` 의 `PAGES` 목록 하나로 정해집니다. 거기 없는 파일
(`docs/protocol-evidence-*.json` 등)은 사이트에 올라가지 않습니다. 페이지를 추가하려면
`PAGES`, `site/astro.config.mjs` 의 `sidebar`, `.github/workflows/site.yml` 의 경로 필터
세 곳에 넣으세요.

이 저장소에서 Node 를 쓰는 곳은 `site/` 뿐입니다. 파이썬 게이트(`uv run …`)와는 무관합니다.

## 로컬에서 보기

Node 22.12 이상 (`site/package.json` 의 `engines`). `site/.nvmrc` 는 22 계열 최신을 고릅니다.

```sh
cd site
npm ci
npm run dev        # http://localhost:4321/
```

랜딩 페이지는 고치는 대로 다시 그려집니다. 저장소 문서를 고친 뒤에는 `npm run sync` 로 다시
복사하세요. 운영 빌드를 미리 보려면 `npm run build && npm run preview`.

`npm run build` 는 문서를 복사하고, 빌드하고, 내부 링크가 하나라도 풀리지 않으면 실패합니다.
빌드는 항상 `astro build --force` 로 콘텐츠 캐시를 비우고 시작합니다 — 캐시된 페이지가 이전
빌드의 스타일시트 해시를 가리켜 코드 블록만 스타일 없이 나오는 일이 실제로 있었습니다.

## 설정

| 변수 | 기본값 | 뜻 |
| --- | --- | --- |
| `SITE_URL` | `https://pykorail.devgyurak.com` | 사이트가 서빙되는 출처 (canonical URL, sitemap) |
| `SITE_BASE` | `/` | 그 출처 아래의 경로. 하위 경로에 올릴 때만 지정합니다 (예: `/pykorail`) |

## 디자인

테마는 README 배너(Claude Design "pykorail Banner")에서 왔습니다. 2a 라이트 → 라이트 테마,
2b 다크 → 다크 테마이고, 색 토큰은 `site/src/styles/custom.css` 한 곳에 있습니다.

- **히어로** (`Hero.astro`) — 왼쪽에 제목 · 설치 명령 · 버튼 · 패키지 현황, 오른쪽에 승차권.
  승차권은 배너의 것을 이미지가 아니라 마크업으로 다시 짠 그림이고, 안의 열차 · 좌석은 예시입니다.
- **코드 + 출발 안내판** (`Demo.astro` · `Board.astro`) — 안내판은 시안 1b 의 표. 행은 README
  "빠른 시작" 의 출력 예시와 같으니, 그쪽 예시를 바꾸면 여기도 함께 바꾸세요.
- **알아두면 좋은 것 · 끝맺음** (`Facts.astro` · `Closing.astro`) — 문구는 README 의 같은 이름
  표와 경고에서 왔습니다.
- 서체(IBM Plex Sans KR · JetBrains Mono)는 `@fontsource` 로 자체 호스팅합니다. 페이지를
  열어도 제3자에게 가는 요청이 없습니다.

### 패키지 현황 (버전 · 다운로드)

히어로의 `VERSION` · `TOTAL DOWNLOADS` · `PYTHON` 은 `site/src/lib/stats.ts` 가 **빌드
시점에** 읽어 넣습니다. 버전과 지원 파이썬은 PyPI 에서, 누적 다운로드는 pepy.tech API 에서
옵니다. 버전을 어디에도 적지 않는다는 저장소 규약 그대로이고, 페이지를 여는 사람의 브라우저는
두 곳에 요청하지 않습니다.

- 숫자는 **마지막 빌드 때의 값**입니다. 릴리스 태그는 사이트 빌드를 일으키지 않으므로,
  `release.yml` 의 `site` 잡이 PyPI 업로드 뒤 배포 훅(아래 5번)으로 `main` 을 다시 빌드시킵니다.
  `site` 잡은 훅을 부른 뒤 실제 페이지에 새 버전이 보일 때까지 확인합니다(최대 15분). 보이지 않으면
  잡이 빨갛게 실패하므로, 그때는 대시보드에서 최신 빌드를 다시 실행하면 됩니다.
- 누적 다운로드는 pepy.tech 의 `total_downloads` 입니다 (pepy 배지와 같은 숫자). PyPI 는
  설치가 아니라 다운로드를 세므로 "설치 수" 라고 부르지 않습니다.
- **pepy.tech API 는 키가 필요합니다** (`PEPY_API_KEY`). <https://pepy.tech> 에 로그인해
  프로필에서 발급하고 — 무료 플랜으로 충분합니다 — 두 곳에 넣습니다.
  - 로컬: `site/.env.example` 을 `site/.env.local` 로 복사해 값을 채웁니다. `.env.local` 은
    gitignore 대상입니다.
  - 배포: 아래 Cloudflare 설정의 빌드 시크릿.
- 키가 없거나 읽지 못하면 그 항목만 빠지고 빌드는 계속됩니다 (빌드 로그에 `[stats]` 경고).
  `site.yml` 의 PR 빌드에는 키를 주지 않으므로 거기서는 항상 빠집니다. 다른 출처로 대신
  채우지 않는 것은, 기준이 다른 숫자가 같은 라벨로 번갈아 나오면 안 되기 때문입니다.
- 키는 빌드 때 요청 헤더로만 쓰이고 산출물(`dist/`)에는 들어가지 않습니다.

## Cloudflare Workers 에 배포하기

사이트는 정적이라 Worker 스크립트 없이 Workers 정적 자산(`site/wrangler.jsonc`)으로
서빙합니다. Cloudflare 가 이 저장소에서 직접 빌드하므로(Workers Builds) GitHub 에는 Cloudflare
API 토큰을 두지 않고, 빌드 트리거 URL 하나(`CLOUDFLARE_DEPLOY_HOOK`)만 둡니다. 그 URL 은 `main`
빌드 하나를 일으킬 뿐 배포 내용을 바꿀 수 없습니다. `main` 이 아닌 브랜치마다 미리보기 URL 이 생깁니다.

1. Cloudflare 대시보드 → **Workers & Pages → Create application → Import a repository** →
   `devgyurak/pykorail` 선택.
2. 설정:

   | 항목 | 값 |
   | --- | --- |
   | Project name | `pykorail` (`site/wrangler.jsonc` 의 `name` 과 같아야 합니다) |
   | Production branch | `main` |
   | Build command | `npm run build` |
   | Deploy command | `npx wrangler deploy` |
   | Preview command (`main` 이 아닌 브랜치) | `npx wrangler preview` — 기본값 그대로 |
   | Path (advanced settings — 루트 디렉터리) | `/site` |

3. 빌드 변수 (advanced):

   | 이름 | 값 |
   | --- | --- |
   | `NODE_VERSION` | `22` |
   | `PEPY_API_KEY` | pepy.tech API 키 — **Secret** 으로 추가 (없으면 `TOTAL DOWNLOADS` 만 빠집니다) |

   `SITE_URL` 과 `SITE_BASE` 는 지정하지 않아도 됩니다 — 기본값이 이 도메인의 루트입니다.

4. 첫 배포 뒤: Worker → **Settings → Domains & Routes → Add → Custom domain** →
   `pykorail.devgyurak.com`. `devgyurak.com` 존이 Cloudflare 에 있으므로 DNS 레코드와
   인증서가 자동으로 만들어집니다. 레코드를 먼저 손으로 추가하지 마세요.

5. 배포 훅 (릴리스 뒤 재빌드): Worker → **Settings → Builds → Deploy hooks → Add** 에서 이름을 정하고
   branch 를 `main` 으로 고른 뒤 URL 을 복사합니다. 훅을 만든 뒤 `curl -X POST '<URL>'` 한 번으로
   `main` 빌드가 생기는지 확인하고, URL 을 GitHub 저장소의 Actions 시크릿 `CLOUDFLARE_DEPLOY_HOOK`
   에 넣습니다. URL 이 새면 훅을 지우고 다시 만드세요 — 지우면 이전 URL 은 무효가 됩니다.
   시크릿이 없으면 `release.yml` 의 `site` 잡이 실패합니다.

6. Build watch paths: **Settings → Builds → Build watch paths** 의 includes 에 `site/*`, `README.md`,
   `docs/reference.md`, `CONTRIBUTING.md` 를 넣습니다. Cloudflare 문서는 `*` 를 "0개 이상의 문자"로
   정의하고 예시로 `docs/*` 를 듭니다. 다만 `site/*` 가 `site/src/…` 같은 중첩 경로까지 걸리는지는
   문서에 명시되어 있지 않습니다. 켠 뒤 `site/src/` 아래만 바꾼 PR 을 올려 빌드가 생기는지
   확인하세요. 그 밖의 변경(라이브러리 코드 등)으로는 빌드가 생기지 않을 것으로 봅니다. **배포 훅이 실제 릴리스에서 사이트를 다시 빌드하는 것을 확인한 뒤에** 켜세요.
   훅보다 먼저 켜면 문서를 바꾸지 않은 릴리스에서는 빌드가 전혀 생기지 않습니다.

`wrangler` 는 버전을 고정한 dev 의존성이라 `npx wrangler` 가 잠긴 버전을 씁니다. 배포하지
않고 번들만 확인하려면 `npm run build && npx wrangler deploy --dry-run`.

`site/public/_headers` 가 Cloudflare 가 붙이는 응답 헤더를 정합니다 (프레임 금지, MIME
스니핑 금지, HSTS, 해시가 붙은 자산의 불변 캐싱).

## CI

`.github/workflows/site.yml` 이 `site/` 나 위 원본 문서를 건드린 PR 에서 `npm run check`
(astro check)와 같은 빌드 · 링크 검사를 돌립니다. 경로 필터가 있어 필수 체크는 아닙니다 —
필수는 계속 `ci-ok` 하나입니다.
다만 `ci.yml` 의 Trivy 는 저장소 전체를 보므로 `site/package-lock.json` 의 HIGH · CRITICAL
취약점은 `ci-ok` 를 막습니다. 그래서 Dependabot 이 `site/` 의 npm 의존성도 범프합니다.
