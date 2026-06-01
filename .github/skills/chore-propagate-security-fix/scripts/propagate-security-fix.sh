#!/usr/bin/env bash
#
# propagate-security-fix.sh — Apply a security constraint and regenerate all
# pinned requirements across the monorepo.
#
# Usage:
#   .github/skills/chore-propagate-security-fix/scripts/propagate-security-fix.sh [--yes] <package> <constraint> [<cve-id>]
#
# Options:
#   -y, --yes, --force   Replace an existing constraint without prompting
#                        (use for non-interactive / CI / agent runs)
#
# Arguments:
#   package     Package name, e.g. "aiohttp"
#   constraint  pip version specifier, e.g. ">=3.11.14"
#   cve-id      Optional CVE or GHSA id, e.g. "CVE-2024-12345" or "GHSA-xxxx"
#
# Examples:
#   .github/skills/chore-propagate-security-fix/scripts/propagate-security-fix.sh aiohttp ">=3.11.14" CVE-2024-23334
#   .github/skills/chore-propagate-security-fix/scripts/propagate-security-fix.sh cryptography ">=43.0.1"
#
# What this script does:
#   1. Validates inputs.
#   2. Adds or updates a line in requirements/constraints.txt.
#   3. Runs  make -C requirements/tools reqs-all upgrade=<package>
#      which re-pins <package> across all 35+ *.txt requirement files.
#
# Prerequisites:
#   - uv must be installed (https://github.com/astral-sh/uv)
#   - Run from the repo root.
#
# Cool-down / N-1 reminder:
#   - Security fixes: apply immediately (no cool-down)
#   - Verify the fix version is available on PyPI before running.
#

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
CONSTRAINTS_FILE="${REPO_ROOT}/requirements/constraints.txt"

# ── argument validation ──────────────────────────────────────────────────────

ASSUME_YES=0

# Parse optional flags before positional args
while [[ $# -gt 0 ]]; do
  case "${1}" in
    -y|--yes|--force)
      ASSUME_YES=1
      shift
      ;;
    --)
      shift
      break
      ;;
    -*)
      echo "Error: unknown option '${1}'" >&2
      echo "Usage: $0 [--yes] <package> <constraint> [<cve-id>]" >&2
      exit 1
      ;;
    *)
      break
      ;;
  esac
done

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 [--yes] <package> <constraint> [<cve-id>]" >&2
  echo "  e.g. $0 aiohttp '>=3.11.14' CVE-2024-23334" >&2
  exit 1
fi

PACKAGE="${1}"
CONSTRAINT="${2}"
CVE_ID="${3:-}"

# Validate package name: alphanumeric, dashes, underscores, dots only
if [[ ! "${PACKAGE}" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "Error: invalid package name '${PACKAGE}'" >&2
  exit 1
fi

# Validate constraint starts with a PEP-440 operator
constraint_re='^[><=!~]'
if [[ ! "${CONSTRAINT}" =~ ${constraint_re} ]]; then
  echo "Error: constraint '${CONSTRAINT}' must start with a comparison operator (>=, ==, !=, etc.)" >&2
  exit 1
fi

FULL_SPEC="${PACKAGE}${CONSTRAINT}"

# ── announce ─────────────────────────────────────────────────────────────────

echo "====================================================================="
echo "  Security fix propagation"
echo "  Package    : ${PACKAGE}"
echo "  Constraint : ${CONSTRAINT}"
echo "  Full spec  : ${FULL_SPEC}"
[[ -n "${CVE_ID}" ]] && echo "  CVE/GHSA   : ${CVE_ID}"
echo "====================================================================="

# ── update constraints.txt ───────────────────────────────────────────────────

# Normalise package name for matching: convert _ and . to [-_.] regex
PATTERN_NAME="${PACKAGE//_/[-_.]}"
PATTERN_NAME="${PATTERN_NAME//./$PATTERN_NAME}"

COMMENT=""
if [[ -n "${CVE_ID}" ]]; then
  COMMENT="  # security: ${CVE_ID}"
fi

NEW_LINE="${FULL_SPEC}${COMMENT}"

# Check if the package already has a constraint entry
if grep -qiE "^[[:space:]]*${PACKAGE}[^=!<>]*(==|!=|>=|<=|~=|>|<)" "${CONSTRAINTS_FILE}"; then
  echo ""
  echo "Found existing constraint for '${PACKAGE}' in constraints.txt:"
  grep -iE "^[[:space:]]*${PACKAGE}[^=!<>]*(==|!=|>=|<=|~=|>|<)" "${CONSTRAINTS_FILE}"
  echo ""
  if [[ "${ASSUME_YES}" -eq 1 ]]; then
    confirm="y"
    echo "--yes given: replacing with '${NEW_LINE}'"
  else
    read -r -p "Replace it with '${NEW_LINE}'? [y/N] " confirm
  fi
  case "${confirm}" in
    [yY]|[yY][eE][sS])
      # Replace the first matching line
      # Use a temp file for portability (sed -i behaves differently on macOS vs Linux)
      sed -E "0,/^[[:space:]]*${PACKAGE}[^=!<>]*(==|!=|>=|<=|~=|>|<)/s|.*|${NEW_LINE}|" \
        "${CONSTRAINTS_FILE}" > "${CONSTRAINTS_FILE}.tmp"
      mv "${CONSTRAINTS_FILE}.tmp" "${CONSTRAINTS_FILE}"
      echo "Updated constraint in ${CONSTRAINTS_FILE}"
      ;;
    *)
      echo "Aborted. Existing constraint kept."
      exit 0
      ;;
  esac
else
  # Append a new entry under a comment block
  {
    echo ""
    [[ -n "${CVE_ID}" ]] && echo "# ${CVE_ID} security fix"
    echo "${NEW_LINE}"
  } >> "${CONSTRAINTS_FILE}"
  echo "Appended '${NEW_LINE}' to ${CONSTRAINTS_FILE}"
fi

# ── regenerate all *.txt files ───────────────────────────────────────────────

echo ""
echo "Re-pinning ${PACKAGE} across all requirements/*.txt files ..."
echo "(This runs: make -C requirements/tools reqs-all upgrade=${PACKAGE})"
echo ""

make -C "${REPO_ROOT}/requirements/tools" reqs-all "upgrade=${PACKAGE}"

# ── summary ──────────────────────────────────────────────────────────────────

echo ""
echo "====================================================================="
echo "  Done. Files updated:"
git -C "${REPO_ROOT}" diff --name-only -- '*.txt' '*.in' requirements/constraints.txt
echo ""
echo "  Next steps:"
echo "  1. Review the diff:  git diff requirements/"
echo "  2. Run tests:        make tests-unit"
echo "  3. Commit:           git add requirements/ && git commit -m 'fix(deps): ${FULL_SPEC}${CVE_ID:+ (${CVE_ID})}'"
echo "====================================================================="
