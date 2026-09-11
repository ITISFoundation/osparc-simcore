#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit  # abort on nonzero exitstatus
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes
IFS=$'\n\t'

install() {
  # No gettext/Ollama needed: xgettext-gated tests self-skip when the binary is
  # absent and the translator tests inject a fake provider (no LLM is contacted).
  # The only opt-in dependency worth installing is node's local `typescript`
  # package, which enables the TypeScript AST extractor tests (they self-skip
  # without node + node_modules/typescript).
  make -C scripts/i18n frontend-tools-install
}

test() {
  # Self-contained uv run with the tools' deps injected via --with (no project install)
  make -C scripts/i18n test
}

# Check if the function exists (bash specific)
if declare -f "$1" >/dev/null; then
  # call arguments verbatim
  "$@"
else
  # Show a helpful error
  echo "'$1' is not a known function name" >&2
  exit 1
fi
