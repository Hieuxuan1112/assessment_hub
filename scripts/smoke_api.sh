#!/usr/bin/env bash
# Real-HTTP smoke test of the Partner API (Frappe v2 route).
#
# Usage: scripts/smoke_api.sh <base_url> <tokens_env_file>
#   base_url         e.g. http://127.0.0.1:8000 (the default site must have sample content)
#   tokens_env_file  file with MANAGER_TOKEN=key:secret and VIEWER_TOKEN=key:secret
set -euo pipefail

BASE_URL="${1:?base url, e.g. http://127.0.0.1:8000}"
ENV_FILE="${2:?path to tokens env file}"
# shellcheck disable=SC1090
source "$ENV_FILE"
: "${MANAGER_TOKEN:?MANAGER_TOKEN missing}" "${VIEWER_TOKEN:?VIEWER_TOKEN missing}"

API="$BASE_URL/api/v2/method/assessment_hub.api.v1"
BODY="$(mktemp)"
trap 'rm -f "$BODY"' EXIT
PASS=0
FAIL=0

# request METHOD TOKEN PATH [JSON] -> prints HTTP status, body saved to $BODY
request() {
  local method="$1" token="$2" path="$3" data="${4:-}"
  local args=(-s -o "$BODY" -w '%{http_code}' -X "$method" -H "Accept: application/json")
  [ -n "$token" ] && args+=(-H "Authorization: token $token")
  [ -n "$data" ] && args+=(-H "Content-Type: application/json" --data "$data")
  curl "${args[@]}" "$API.$path"
}

# check NAME EXPECTED_STATUS ACTUAL_STATUS JQ_BOOLEAN_EXPRESSION
check() {
  local name="$1" expected="$2" actual="$3" expr="$4"
  local status_ok=0
  if [ "$expected" = "4xx" ]; then [[ "$actual" == 4* ]] && status_ok=1; else [ "$actual" = "$expected" ] && status_ok=1; fi
  if [ "$status_ok" = 1 ] && jq -e "$expr" "$BODY" >/dev/null 2>&1; then
    PASS=$((PASS + 1)); printf '  \033[32mPASS\033[0m %s\n' "$name"
  else
    FAIL=$((FAIL + 1)); printf '  \033[31mFAIL\033[0m %s (HTTP %s, expected %s)\n' "$name" "$actual" "$expected"
    head -c 600 "$BODY"; echo
  fi
}

answers_ok='[{"content":"Yes","score":1},{"content":"No","score":0}]'

echo "== Assessments"
code=$(request GET "$VIEWER_TOKEN" "assessments.list_assessments?page_length=2")
check "viewer lists with pagination" 200 "$code" '(.data.items | length) <= 2 and .data.pagination.page_length == 2 and (.data.pagination | has("has_more"))'

code=$(request GET "$VIEWER_TOKEN" "assessments.list_assessments?status=Draft&search=Frappe%20Framework")
check "filter by status + search" 200 "$code" '(.data.items | length) >= 1 and all(.data.items[]; .status == "Draft")'
DRAFT_ID=$(jq -r '.data.items[0].id' "$BODY")

code=$(request GET "$VIEWER_TOKEN" "assessments.list_assessments?status=Archived")
check "archived filter" 200 "$code" '(.data.items | length) >= 1'
ARCHIVED_ID=$(jq -r '.data.items[0].id' "$BODY")

code=$(request GET "$VIEWER_TOKEN" "assessments.list_assessments?updated_since=2000-01-01%2000:00:00&page_length=50")
check "updated_since sorts ascending" 200 "$code" '[.data.items[].updated_at] as $u | $u == ($u | sort)'

code=$(request GET "$VIEWER_TOKEN" "assessments.list_assessments?start=0&page=1")
check "start + page -> 400 INVALID_PARAMETER" 400 "$code" '.errors[0].code == "INVALID_PARAMETER"'

code=$(request GET "$VIEWER_TOKEN" "assessments.get_assessment?id=$DRAFT_ID&include_questions=1")
check "get with nested questions and answers" 200 "$code" '.data.id != null and (.data.questions | length) >= 1 and (.data.questions[0].answers | type) == "array"'

code=$(request GET "$VIEWER_TOKEN" "assessments.get_assessment?id=ASM-99999999")
check "unknown id -> 404 NOT_FOUND" 404 "$code" '.errors[0].code == "NOT_FOUND"'

echo "== Questions"
code=$(request POST "$MANAGER_TOKEN" "questions.create_question" "{\"assessment_id\":\"$DRAFT_ID\",\"content\":\"<p>Smoke question</p>\",\"answers\":$answers_ok}")
check "manager creates question + answers" 200 "$code" '.data.id != null and (.data.answers | length) == 2'

code=$(request POST "$VIEWER_TOKEN" "questions.create_question" "{\"assessment_id\":\"$DRAFT_ID\",\"content\":\"<p>Nope</p>\",\"answers\":$answers_ok}")
check "viewer create -> 403 PERMISSION_DENIED" 403 "$code" '.errors[0].code == "PERMISSION_DENIED"'

code=$(request POST "$MANAGER_TOKEN" "questions.create_question" "{\"assessment_id\":\"$DRAFT_ID\",\"content\":\"<p>Bad</p>\",\"answers\":[{\"content\":\"A\",\"score\":1},{\"content\":\"B\",\"score\":-1}]}")
check "invalid answer -> 422 VALIDATION_ERROR" 422 "$code" '.errors[0].code == "VALIDATION_ERROR"'

code=$(request POST "$MANAGER_TOKEN" "questions.create_question" "{\"assessment_id\":\"$ARCHIVED_ID\",\"content\":\"<p>Late</p>\",\"answers\":$answers_ok}")
check "archived assessment -> 409 INVALID_STATE" 409 "$code" '.errors[0].code == "INVALID_STATE"'

code=$(request GET "$VIEWER_TOKEN" "questions.list_questions?assessment_id=$DRAFT_ID&include_answers=1")
check "list questions sorted by sort_order" 200 "$code" '[.data.items[].sort_order] as $s | $s == ($s | sort) and (.data.items[0] | has("answers"))'

code=$(request GET "$VIEWER_TOKEN" "questions.list_questions")
check "missing assessment_id -> 400 MISSING_PARAMETER" 400 "$code" '.errors[0].code == "MISSING_PARAMETER"'

echo "== Framework-level rejections (Frappe's own error body)"
code=$(request GET "" "assessments.list_assessments")
check "no token -> 4xx" 4xx "$code" 'true'
code=$(request GET "$MANAGER_TOKEN" "questions.create_question")
check "GET on POST-only endpoint -> 4xx" 4xx "$code" 'true'

echo
echo "Smoke result: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
