#!/usr/bin/env bash
# develop · main 브랜치 보호 규칙(ruleset)을 적용합니다.
#
#   .github/scripts/setup-branch-protection.sh
#
# 저장소 파일만으로는 머지를 막을 수 없습니다 — 브랜치 보호는 GitHub **저장소 설정**
# 이라 API 로 한 번 켜 줘야 합니다. `.github/CODEOWNERS` 는 "누가 승인해야 하는가" 만
# 정하고, "승인 없이는 못 머지" 는 이 스크립트가 만드는 ruleset 이 강제합니다.
#
# 두 브랜치의 역할:
#   · develop — 작업 PR 이 모이는 곳. 규칙이 여기로 옮겨 왔습니다.
#   · main    — 릴리스 전용. develop 을 merge 커밋으로만 머지합니다 (squash·rebase 금지).
#
# 주의: 머지 **권한** 은 ruleset 이 아니라 저장소 write 권한이 정합니다. 협업자는
# @devgyurak 뿐이고, 본인 PR 은 스스로 승인할 수 없어 항상 admin 우회로 머지됩니다.
# 그 우회는 ci-ok·strict(최신 상태) 요구까지 함께 건너뜁니다 — 즉 이 ruleset 이 실제로
# 보장하는 것은 직접 푸시·강제 푸시·삭제 금지이고, ci-ok 는 본인이 눈으로 확인해야 합니다.
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

apply_ruleset "$RULESETS_DIR/develop-protection.json"
apply_ruleset "$RULESETS_DIR/main-protection.json"
apply_ruleset "$RULESETS_DIR/tag-protection.json"

echo
echo "develop 브랜치 (작업 PR 이 모이는 곳):"
echo "  · PR 로만 변경 가능 (직접 푸시 금지)"
echo "  · 승인 1개 이상 + CODEOWNERS(@devgyurak) 승인 필수"
echo "  · 새 커밋이 올라오면 기존 승인 무효화"
echo "  · 마지막 푸시한 사람 외의 승인 필요"
echo "  · 리뷰 코멘트 전부 해결해야 머지 가능"
echo "  · 상태 체크 'ci-ok' 통과 필수 (최신 develop 기준)"
echo "  · develop 삭제·강제푸시 금지"
echo
echo "main 브랜치 (릴리스 전용):"
echo "  · PR 로만 변경 가능 — develop 을 merge 커밋으로만 머지합니다 (squash·rebase 금지)"
echo "  · 규칙은 develop 과 같습니다 (승인 1 + CODEOWNERS + ci-ok + 삭제·강제푸시 금지)"
echo "  · 태그는 이 브랜치에서 밀지만, 보호는 태그 ruleset 이 따로 겁니다"
echo
echo "태그 (릴리스 트리거):"
echo "  · 태그 생성·수정·삭제는 저장소 admin 만 가능"
echo
echo "admin 우회 범위:"
echo "  · develop · main 직접 push → 막힙니다 (admin 도 예외 없음, bypass_mode=pull_request)"
echo "  · 본인 PR 을 승인 없이 머지    → 됩니다 (ci-ok·strict 도 함께 건너뜁니다)"
echo "  · 태그 push                   → admin 만 가능 (bypass_mode=always)"
echo
echo "  머지 권한은 ruleset 이 아니라 write 권한이 정합니다 — 이 ruleset 이 실제로"
echo "  보장하는 것은 직접 푸시·강제 푸시·삭제 금지입니다. 본인 PR 을 admin 우회로"
echo "  머지할 때는 ci-ok 가 초록인지 반드시 눈으로 확인하세요."
echo
echo "  1인 저장소에서는 자기 PR 을 스스로 승인할 수 없어, 이 우회가 없으면"
echo "  아무것도 머지하지 못합니다. 본인 PR 도 예외 없이 막으려면 두"
echo "  ruleset 의 bypass_actors 를 [] 로 바꾸고 다시 실행하세요."
echo "  반대로 긴급 상황에 직접 push 도 허용하려면 bypass_mode 를 always 로 바꾸세요."
echo
echo "확인:"
echo "  gh api repos/$REPO/rulesets --jq '.[] | \"\\(.id) \\(.name) \\(.target) \\(.enforcement)\"'"
echo "  git push origin develop   # → 거부되면 정상"
echo "  git push origin main      # → 거부되면 정상"
