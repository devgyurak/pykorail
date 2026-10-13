// @ts-check
import starlight from "@astrojs/starlight";
import { defineConfig } from "astro/config";

// 사이트가 서빙되는 위치. 기본값이 곧 운영 환경(자체 도메인의 루트)입니다. 다른 곳의 하위
// 경로에 올릴 때만 SITE_BASE(와 SITE_URL)를 지정하세요. scripts/sync-docs.mjs 와
// scripts/check-links.mjs 가 같은 SITE_BASE 를 읽으므로, 고쳐 쓴 링크와 검사하는 링크가
// Astro 가 실제로 서빙하는 경로와 항상 일치합니다.
const site = process.env.SITE_URL ?? "https://pykorail.devgyurak.com";
const base = process.env.SITE_BASE ?? "/";

export default defineConfig({
  site,
  base,
  integrations: [
    starlight({
      title: "pykorail",
      description: "코레일(KTX) 스마트 예매 비공식 Python 클라이언트",
      // 문서가 한국어 하나뿐이라 로케일도 루트 하나입니다. UI 문자열(검색, 목차 등)이 한국어로 나옵니다.
      defaultLocale: "root",
      locales: { root: { label: "한국어", lang: "ko" } },
      social: [{ icon: "github", label: "GitHub", href: "https://github.com/devgyurak/pykorail" }],
      sidebar: [
        { label: "시작하기", items: [{ slug: "overview", label: "개요" }] },
        { label: "레퍼런스", items: [{ slug: "reference", label: "API 레퍼런스" }] },
        {
          label: "프로젝트",
          items: [
            { slug: "contributing", label: "기여 가이드" },
            // 릴리스 노트는 저장소에 파일로 없습니다 — 태그에서 GitHub 가 자동 생성합니다.
            { label: "릴리스 노트", link: "https://github.com/devgyurak/pykorail/releases" },
            { label: "PyPI", link: "https://pypi.org/project/pykorail/" },
          ],
        },
      ],
      // 랜딩 페이지만 site/ 에 있습니다. 동기화된 페이지는 각자 원본 파일로 editUrl 을 겁니다.
      // 작업 위치는 develop 이라 저장소 파일 링크도 develop 을 가리킵니다.
      editLink: { baseUrl: "https://github.com/devgyurak/pykorail/edit/develop/site/" },
      lastUpdated: false,
      // 코드 블록 모서리를 승차권의 설치 명령 칩(6px)과 같은 계열로 맞춥니다.
      expressiveCode: { styleOverrides: { borderRadius: "8px" } },
      customCss: [
        "@fontsource/ibm-plex-sans-kr/400.css",
        "@fontsource/ibm-plex-sans-kr/500.css",
        "@fontsource/ibm-plex-sans-kr/700.css",
        "@fontsource/jetbrains-mono/400.css",
        "@fontsource/jetbrains-mono/500.css",
        "@fontsource/jetbrains-mono/700.css",
        "./src/styles/custom.css",
      ],
      components: {
        Hero: "./src/components/Hero.astro",
        SiteTitle: "./src/components/SiteTitle.astro",
      },
    }),
  ],
});
