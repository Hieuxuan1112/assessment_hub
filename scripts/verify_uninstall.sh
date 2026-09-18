#!/usr/bin/env bash
# Proves assessment_hub installs, uninstalls without leftovers, and reinstalls cleanly.
# Run from the bench directory: bash apps/assessment_hub/scripts/verify_uninstall.sh <site>
set -euo pipefail

SITE="${1:?site name}"
APP="assessment_hub"
FAIL=0

count() {  # count DOCTYPE FILTERS_JSON -> prints integer
  # `bench execute` only prints its return value when truthy (`if ret: print(ret)` in
  # frappe/commands/utils.py), so a real count of 0 produces NO output. Default to 0.
  local result
  result="$(bench --site "$SITE" execute frappe.db.count --args "[\"$1\", $2]" 2>/dev/null | tail -n 1 | tr -dc '0-9')"
  echo "${result:-0}"
}

expect() {  # expect LABEL EXPECTED ACTUAL
  if [ "$2" = "$3" ]; then printf '  \033[32mOK\033[0m   %s = %s\n' "$1" "$3"
  else printf '  \033[31mFAIL\033[0m %s = %s (expected %s)\n' "$1" "$3" "$2"; FAIL=1; fi
}

ROLES='{"name": ["in", ["Assessment Manager", "Assessment Viewer"]]}'
ROLE_LINKS='{"role": ["in", ["Assessment Manager", "Assessment Viewer"]]}'

echo "== Uninstalling $APP from $SITE"
bench --site "$SITE" uninstall-app "$APP" --yes --no-backup

echo "== Leftover check"
expect "DocType (module Assessment Hub)" 0 "$(count DocType '{"module": "Assessment Hub"}')"
expect "Module Def" 0 "$(count "Module Def" '{"name": "Assessment Hub"}')"
expect "Workspace" 0 "$(count Workspace '{"module": "Assessment Hub"}')"
expect "Number Card" 0 "$(count "Number Card" '{"module": "Assessment Hub"}')"
expect "Workspace Sidebar" 0 "$(count "Workspace Sidebar" '{"name": "Assessment Hub"}')"
expect "Desktop Icon" 0 "$(count "Desktop Icon" '{"name": "Assessment Hub"}')"
expect "Role" 0 "$(count Role "$ROLES")"
expect "Has Role" 0 "$(count "Has Role" "$ROLE_LINKS")"
expect "Custom DocPerm" 0 "$(count "Custom DocPerm" "$ROLE_LINKS")"

echo "== Reinstalling"
bench --site "$SITE" install-app "$APP"
expect "Role after reinstall" 2 "$(count Role "$ROLES")"
expect "DocType after reinstall" 4 "$(count DocType '{"module": "Assessment Hub"}')"
bench --site "$SITE" migrate

[ "$FAIL" -eq 0 ] && echo "Uninstall/reinstall verification passed" || { echo "Uninstall/reinstall verification FAILED"; exit 1; }
