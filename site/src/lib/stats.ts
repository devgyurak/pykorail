// 히어로에 보여 줄 패키지 현황(현재 버전 · 누적 다운로드 · 지원 파이썬)을 **빌드 시점에** 읽습니다.
//
// 브라우저에서 읽지 않는 이유는 둘입니다. pepy.tech API 는 키가 필요해 브라우저에 둘 수 없고,
// 이 사이트는 페이지를 열어도 제3자에게 요청이 가지 않게 만들었습니다 (custom.css 의 서체 주석).
// 대가는 신선도입니다 — 숫자는 마지막 빌드 때의 값이고, 릴리스 태그는 빌드를 일으키지 않습니다.
// 새 버전은 릴리스 뒤 release.yml 의 배포 훅이 main 을 다시 빌드할 때 반영됩니다 (docs/site.md).
//
// 버전을 여기에 적지 않고 PyPI 에서 읽는 것은 저장소 규약(버전의 출처는 git 태그 하나)과 같은
// 이유입니다. 읽지 못하면 해당 항목만 빠지고 빌드는 계속됩니다 — PyPI 가 잠깐 느리다고 문서
// 배포가 막히면 안 됩니다.
const PYPI = "https://pypi.org/pypi/pykorail/json";
// 누적 다운로드는 pepy.tech 에서 읽습니다. pypistats 는 최근 180일치만 줘서 첫 릴리스가 그 창을
// 벗어나면 합계가 더는 누적이 아니게 됩니다.
const PEPY = "https://api.pepy.tech/api/v2/projects/pykorail";
const TIMEOUT_MS = 8000;

export interface PackageStats {
  version?: string;
  totalDownloads?: number;
  python?: string;
}

async function fetchJson(url: string, headers: Record<string, string> = {}): Promise<unknown> {
  try {
    const response = await fetch(url, {
      headers: { accept: "application/json", ...headers },
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (response.ok) return await response.json();
    console.warn(`[stats] ${url} → HTTP ${response.status}; 해당 항목 없이 빌드합니다`);
  } catch (error) {
    console.warn(`[stats] ${url} 을 읽지 못했습니다 (${String(error)}); 해당 항목 없이 빌드합니다`);
  }
  return undefined;
}

// 응답 모양을 믿지 않고 한 단계씩 확인하며 내려갑니다.
function dig(value: unknown, ...keys: string[]): unknown {
  return keys.reduce<unknown>(
    (current, key) =>
      typeof current === "object" && current !== null ? (current as Record<string, unknown>)[key] : undefined,
    value,
  );
}

// 키는 두 곳에서 옵니다: 로컬은 site/.env.local(Astro 가 import.meta.env 로 읽어 줍니다),
// Cloudflare 빌드는 대시보드에 넣은 시크릿(process.env). 이 모듈은 빌드 때만 돌고 값은 요청
// 헤더로만 쓰이므로 산출물(dist/)에 들어가지 않습니다 — 로그에도 찍지 마세요.
function pepyKey(): string | undefined {
  const key: unknown = import.meta.env.PEPY_API_KEY ?? process.env.PEPY_API_KEY;
  return typeof key === "string" && key.trim() !== "" ? key.trim() : undefined;
}

async function fetchTotalDownloads(): Promise<number | undefined> {
  const key = pepyKey();
  if (key === undefined) {
    // 키가 없다고 다른 출처로 채우지 않습니다. 기준(미러 포함 여부)이 다른 숫자가 같은 라벨로
    // 번갈아 나오면 안 됩니다.
    console.warn("[stats] PEPY_API_KEY 가 없습니다; TOTAL DOWNLOADS 없이 빌드합니다 (docs/site.md)");
    return undefined;
  }
  const total = dig(await fetchJson(PEPY, { "X-API-Key": key }), "total_downloads");
  return typeof total === "number" && Number.isFinite(total) ? total : undefined;
}

// 한 번의 빌드에서 히어로가 두 번 렌더링돼도 요청은 한 번만 나갑니다 (pepy 무료 한도는 분당 5회).
let cached: Promise<PackageStats> | undefined;

export function packageStats(): Promise<PackageStats> {
  cached ??= loadPackageStats();
  return cached;
}

async function loadPackageStats(): Promise<PackageStats> {
  const [pypi, totalDownloads] = await Promise.all([fetchJson(PYPI), fetchTotalDownloads()]);
  const version = dig(pypi, "info", "version");
  const requires = dig(pypi, "info", "requires_python");
  // ">=3.11" 꼴만 "3.11+" 로 줄여 보여 줍니다. 상한이 붙는 등 모양이 달라지면 틀린 말을 하느니 뺍니다.
  const floor = typeof requires === "string" ? /^>=\s*(\d+\.\d+)$/.exec(requires.trim()) : null;
  return {
    version: typeof version === "string" ? version : undefined,
    totalDownloads,
    python: floor ? `${floor[1]}+` : undefined,
  };
}
