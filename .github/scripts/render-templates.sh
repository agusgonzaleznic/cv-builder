#!/usr/bin/env bash
# Render the workflows `cvcite init` writes, with a placeholder action pin, so actionlint can lint
# them as the workflows they become in a user's repository.
#
#   .github/scripts/render-templates.sh <out-dir>
set -euo pipefail
out=${1:?usage: render-templates.sh <out-dir>}
mkdir -p "$out"
for f in src/cvcite/templates/repo/github/workflows/*.yml; do
  sed 's|{{ACTION_REF}}|agusgonzaleznic/cvcite@0000000000000000000000000000000000000000 # v0.0.0|' \
    "$f" > "$out/$(basename "$f")"
done
