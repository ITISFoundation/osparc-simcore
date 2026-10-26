#!/bin/bash

# Enforce that every third-party action referenced in a workflow or composite
# action is pinned to a full commit SHA, keeping the release in a comment:
#   uses: actions/checkout@3d3c42e5... # v7.0.1
# Local actions (./...) are path-pinned and docker:// step images follow the
# separate container-image digest policy, so both are skipped here.
#
# Usage: check-action-pins.bash [file ...]
# Without arguments it checks the staged workflow/composite-action files.

set -u

if [ "$#" -gt 0 ]; then
  files="$*"
else
  files=$(git diff --cached --name-only --diff-filter=ACM | grep -E '^\.github/(workflows|actions)/.*\.ya?ml$')
fi

[ -z "$files" ] && exit 0

status=0
for file in $files; do
  [ -f "$file" ] || continue
  offenders=""
  while IFS=: read -r lineno rest; do
    value=$(sed -E 's/.*uses:[[:space:]]*//' <<< "$rest")
    value=${value%%[[:space:]]*}
    case "$value" in
      docker://* | ./*) continue ;;
    esac
    if [[ ! $value =~ ^[^@]+@[0-9a-f]{40}([[:space:]]|$) ]]; then
      offenders+="  $file:$lineno: $value"$'\n'
    fi
  done < <(grep -nE '^[[:space:]]*-?[[:space:]]*uses[[:space:]]*:' "$file" || true)

  if [ -n "$offenders" ]; then
    echo "Error: actions must be pinned to a full commit SHA (uses: owner/repo@<40-hex> # vX.Y.Z)." >&2
    echo "  Resolve a tag with: gh api repos/<owner>/<repo>/commits/<tag> --jq .sha" >&2
    printf '%s' "$offenders" >&2
    status=1
  fi
done

exit $status
