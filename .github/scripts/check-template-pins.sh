#!/usr/bin/env bash
# The workflows `cv-builder init` writes live under src/, where Dependabot does not look. Fail when
# one of them pins an action differently from this repository's own workflows or action.yml, so
# a Dependabot update here cannot leave the templates behind.
#
#   .github/scripts/check-template-pins.sh [templates-dir]
set -euo pipefail
templates=${1:-src/cv_builder/templates/repo/github/workflows}
extract() { grep -rhoE 'uses: [^ @#]+@[0-9a-f]{40} # v[^ ]+' "$@" | sed 's/^uses: //' | sort -u; }
ours=$(extract .github/workflows action.yml)
theirs=$(extract "$templates")
fail=0
compared=0
while IFS= read -r ref; do
  [ -n "$ref" ] || continue
  action=${ref%%@*}
  mine=$(grep -F "$action@" <<<"$ours" || true)
  [ -n "$mine" ] || continue
  compared=$((compared + 1))
  if ! grep -qxF "$ref" <<<"$ours"; then
    echo "FAIL template pin '$ref' differs from '$mine'"
    fail=1
  else
    echo "ok   $ref"
  fi
done <<<"$theirs"
if [ "$compared" -eq 0 ]; then
  echo "FAIL no template pin shares an action with this repository's workflows"
  exit 1
fi
exit "$fail"
