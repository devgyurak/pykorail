// 빌드 시점에 저장소의 Markdown 을 사이트로 복사합니다. 페이지마다 원본은 하나 —
// README.md · docs/ · CONTRIBUTING.md 가 기준이고 여기서 손으로 고치는 것은 없습니다.
// 만들어진 파일은 gitignore 대상입니다. 파일마다 하는 일:
//   - 첫 H1 을 front matter 의 title 로 옮기고 본문에서는 지웁니다 (제목은 Starlight 가 그립니다).
//   - README 는 첫 `## ` 앞(배너 · 배지 · 링크 줄)을 잘라냅니다.
//   - GitHub 알림(`> [!WARNING]`)을 Starlight aside(`:::caution`)로 바꿉니다.
//   - 저장소 링크를 고쳐 씁니다: 사이트에 있는 페이지 → base 아래의 경로, 그 밖 → GitHub 의 파일.
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SITE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const REPO = path.resolve(SITE, "..");
const BASE = (process.env.SITE_BASE ?? "/").replace(/\/$/, "");
const GITHUB = "https://github.com/devgyurak/pykorail";

// 저장소 파일 → 사이트 경로. 공개 범위가 이 목록 하나로 정해집니다 — 여기 없는 파일
// (docs/protocol-evidence-*.json 등)은 사이트에 올라가지 않습니다.
const PAGES = {
  "README.md": { route: "/overview/", out: "overview.md", title: "개요" },
  "docs/reference.md": { route: "/reference/", out: "reference.md" },
  "CONTRIBUTING.md": { route: "/contributing/", out: "contributing.md" },
};
const CONTENT = path.join(SITE, "src/content/docs");

// GitHub 알림 종류 → Starlight aside. IMPORTANT 는 대응하는 종류가 없어 제목을 단 note 로 둡니다.
const ASIDES = {
  NOTE: "note",
  TIP: "tip",
  IMPORTANT: "note[중요]",
  WARNING: "caution",
  CAUTION: "danger",
};

function rewriteTarget(target, fromFile) {
  if (/^([a-z]+:|#|mailto:)/i.test(target)) return target;
  const [file, hash] = target.split("#");
  const resolved = path.posix.normalize(path.posix.join(path.posix.dirname(fromFile), file));
  const anchor = hash ? `#${hash}` : "";
  if (PAGES[resolved]) return `${BASE}${PAGES[resolved].route}${anchor}`;
  return `${GITHUB}/blob/main/${resolved}${anchor}`;
}

function asides(text) {
  return text.replace(
    /^> \[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\n((?:>.*(?:\n|$))*)/gm,
    (_, kind, quoted) => `:::${ASIDES[kind]}\n${quoted.replace(/^> ?/gm, "").trimEnd()}\n:::\n`,
  );
}

function transform(text, fromFile, titleOverride) {
  let body = text.replace(/\r\n/g, "\n");
  if (fromFile === "README.md") {
    // README 에는 H1 이 없습니다 — 제목 자리에 배너 이미지가 있습니다. `\n# ` 로 자르면
    // 코드 블록 안의 주석(`# [KTX 101] …`)에 걸리므로 첫 `## ` 에서 자릅니다.
    const start = body.indexOf("\n## ");
    if (start < 0) throw new Error("README.md 에서 첫 `## ` 제목을 찾지 못했습니다");
    body = body.slice(start + 1);
  }
  // 코드 펜스 밖에서만 손댑니다 — 예제 코드의 `# ` 주석이나 `](…)` 는 그대로 둬야 합니다.
  const parts = body.split(/(^```[\s\S]*?^```)/m);
  let title = titleOverride;
  body = parts
    .map((part, i) => {
      if (i % 2 === 1) return part;
      let prose = part;
      const h1 = title ? null : prose.match(/^# (.+)$/m);
      if (h1) {
        title = h1[1].replace(/`/g, "").trim();
        prose = prose.replace(h1[0], "");
      }
      return asides(prose)
        .replace(/\]\(([^)\s]+)\)/g, (_, t) => `](${rewriteTarget(t, fromFile)})`)
        .replace(/\b(src|srcset|href)="([^"]+)"/g, (_, a, t) => `${a}="${rewriteTarget(t, fromFile)}"`);
    })
    .join("");
  title ??= path.basename(fromFile, ".md");
  const editUrl = `${GITHUB}/edit/develop/${fromFile}`;
  const front = `---\ntitle: ${JSON.stringify(title)}\neditUrl: ${JSON.stringify(editUrl)}\n---\n`;
  return front + body.replace(/^\n+/, "\n");
}

for (const [from, { out, title }] of Object.entries(PAGES)) {
  const dest = path.join(CONTENT, out);
  await mkdir(path.dirname(dest), { recursive: true });
  await writeFile(dest, transform(await readFile(path.join(REPO, from), "utf8"), from, title));
}
console.log(`synced ${Object.keys(PAGES).length} pages (base ${BASE || "/"})`);
