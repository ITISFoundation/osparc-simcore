#!/bin/bash
#
#  Re-triggers the failed jobs of a CI Build Test run, once per commit, and only
#  for failures that look flaky (see chore-rerun-flaky-jobs.yml for when this
#  runs). Deterministic failures (lint, typecheck, many failed jobs) stay red.
#
#  Required environment: GITHUB_REPOSITORY, RUN_ID, HEAD_SHA, PR_NUMBER,
#  PR_HEAD_SHA. Uses gh for API calls (GH_TOKEN must be set).

# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit  # abort on nonzero exitstatus
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes
IFS=$'\n\t'

# skip draft PRs: a draft PR is not waiting to merge, so nobody is
# waiting on its red checks (the payload has no draft flag, so ask the API)
if [ "$(gh api "repos/$GITHUB_REPOSITORY/pulls/$PR_NUMBER" --jq .draft)" = "true" ]; then
  echo "PR #$PR_NUMBER is a draft; not rerunning"
  exit 0
fi

# skip stale runs: the PR head moved to a newer commit while this run was
# still failing, and that newer commit has its own run
if [ "$HEAD_SHA" != "$PR_HEAD_SHA" ]; then
  echo "run $RUN_ID is on $HEAD_SHA, PR head is now $PR_HEAD_SHA; not rerunning"
  exit 0
fi

FAILED_JOBS="$(gh api --paginate \
  "repos/$GITHUB_REPOSITORY/actions/runs/$RUN_ID/jobs?per_page=100" \
  --jq '[.jobs[] | select(.conclusion == "failure")]')"
N_FAILED="$(jq 'length' <<<"$FAILED_JOBS")"

# 0 failures (e.g. cancelled run) or more than 3: the latter is most likely
# a real integration/build breakage, not isolated flakiness
if [ "$N_FAILED" -eq 0 ] || [ "$N_FAILED" -gt 3 ]; then
  echo "$N_FAILED failed jobs (want 1..3); not rerunning"
  exit 0
fi

# lint failures never disappear on a retry; the pylint job is named
# "[unit] python-linting"
if jq -e 'any(.[]; .name | test("python-linting"))' <<<"$FAILED_JOBS" >/dev/null; then
  echo "python-linting failed; not rerunning"
  exit 0
fi

# a failed "typecheck" step (pyright) is deterministic too
if jq -e 'any(.[]; .steps[]? | select(.name == "typecheck" and .conclusion == "failure"))' \
  <<<"$FAILED_JOBS" >/dev/null; then
  echo "a typecheck step failed; not rerunning"
  exit 0
fi

echo "rerunning $N_FAILED failed job(s):"
jq -r '.[] | " - " + .name' <<<"$FAILED_JOBS"
gh api -X POST "repos/$GITHUB_REPOSITORY/actions/runs/$RUN_ID/rerun-failed-jobs"
