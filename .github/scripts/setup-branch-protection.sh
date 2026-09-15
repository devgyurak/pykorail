#!/usr/bin/env bash
# main 브랜치 보호 규칙(ruleset)을 적용합니다.
#
#   .github/scripts/setup-branch-protection.sh
#
# 저장소 파일만으로는 머지를 막을 수 없습니다 — 브랜치 보호는 GitHub **저장소 설정**
# 이라 API 로 한 번 켜 줘야 합니다. `.github/CODEOWNERS` 는 "누가 승인해야 하는가" 만
# 정하고, "승인 없이는 못 머지" 는 이 스크립트가 만드는 ruleset 이 강제합니다.
#
# 필요한 것: gh CLI 로그인 + 대상 저장소 admin 권한.
# 여러 번 실행해도 안전합니다 (있으면 갱신).

set -euo pipefail

RULESETS_DIR="$(dirname "$0")/../rulesets"

command -v gh >/dev/null || {
  echo "gh CLI 가 필요합니다: https://cli.github.com" >&2
  exit 1
}

REPO="${1:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
echo "대상 저장소: $REPO"

apply_ruleset() {
  local file="$1"
  local name
  name="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['name'])" "$file")"

  # 이름이 같은 ruleset 이 이미 있으면 새로 만들지 않고 갱신합니다.
  local existing_id
  existing_id="$(
    gh api "repos/$REPO/rulesets" --jq ".[] | select(.name == \"$name\") | .id" 2>/dev/null || true
  )"

  if [ -n "$existing_id" ]; then
    echo "  '$name' 갱신 (id=$existing_id)"
    gh api --method PUT "repos/$REPO/rulesets/$existing_id" --input "$file" >/dev/null
  else
    echo "  '$name' 생성"
    gh api --method POST "repos/$REPO/rulesets" --input "$file" >/dev/null
  fi
}

apply_ruleset "$RULESETS_DIR/main-protection.json"
apply_ruleset "$RULESETS_DIR/tag-protection.json"

echo
echo "main 브랜치:"
echo "  · main 은 PR 로만 변경 가능 (직접 푸시 금지)"
echo "  · 승인 1개 이상 + CODEOWNERS(@devgyurak) 승인 필수"
echo "  · 새 커밋이 올라오면 기존 승인 무효화"
echo "  · 마지막 푸시한 사람 외의 승인 필요"
echo "  · 리뷰 코멘트 전부 해결해야 머지 가능"
echo "  · 상태 체크 'ci-ok' 통과 필수 (최신 main 기준)"
echo "  · main 삭제·강제푸시 금지"
echo
echo "태그 (릴리스 트리거):"
echo "  · 태그 생성·수정·삭제는 저장소 admin 만 가능"
echo
echo "admin 우회 범위:"
echo "  · main 직접 push        → 막힙니다 (admin 도 예외 없음, bypass_mode=pull_request)"
echo "  · 본인 PR 을 승인 없이 머지 → 됩니다"
echo "  · 태그 push             → admin 만 가능 (bypass_mode=always)"
echo
echo "  1인 저장소에서는 자기 PR 을 스스로 승인할 수 없어, 이 우회가 없으면"
echo "  아무것도 머지하지 못합니다. 본인 PR 도 예외 없이 막으려면"
echo "  main-protection.json 의 bypass_actors 를 [] 로 바꾸고 다시 실행하세요."
echo "  반대로 긴급 상황에 직접 push 도 허용하려면 bypass_mode 를 always 로 바꾸세요."
echo
echo "확인:"
echo "  gh api repos/$REPO/rulesets --jq '.[] | \"\\(.id) \\(.name) \\(.target) \\(.enforcement)\"'"
echo "  git push origin main   # → 거부되면 정상"
