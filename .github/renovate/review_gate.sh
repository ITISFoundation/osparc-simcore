#!/bin/bash
#
#  Renovate opens every PR as a draft (draftPR in .renovaterc.jsonc), so GitHub
#  does not auto-request the code owners until the checks are done. This poller
#  marks the drafts ready once their checks have all finished; the ready
#  transition makes GitHub request the code owners from CODEOWNERS by itself:
#  - all checks done + passed + 🤖-renovate-fast-lane (patch/pin/digest bumps and security
#    fixes): the request comes out but nothing waits on it, the renovate-fast
#    Mergify queue merges the PR;
#  - all checks done + passed without the label (minors/majors): the requested
#    review is what the PR then waits for;
#  - failing checks: nothing for FAIL_COOLDOWN_HOURS on the last commit, so
#    Renovate can push its own fix; then the PR gets 🤖-do-not-merge, loses
#    🤖-renovate-fast-lane, is marked ready (which requests the owners), and a
#    comment lists the failing checks. It then goes through the reviewed queue,
#    also once a fix makes its checks pass.
#  A draft that already has requested reviewers or reviews is left alone: the
#  gate reported it before or a person handles it (e.g. turned it back into a
#  draft on purpose).
#
#  Required environment: REPO, BOT, FAIL_COOLDOWN_HOURS.
#  Uses gh for API calls (GH_TOKEN must be set). GH_TOKEN must belong to the
#  Renovate App: a GitHub App cannot mark a pull request opened by another App
#  ready, so a github.token (github-actions App) run fails on the ready call.

# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit  # abort on nonzero exitstatus
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes

# --author filters server-side; GitHub search resolves the bot name to both
# the "<name>[bot]" and the "app/<name>" form the gh CLI reports in
# .author.login. --limit: the default 30 results would drop drafts once the
# repo has more open pull requests than that.
DRAFTS="$(gh pr list --repo "$REPO" --state open --base master --limit 200 \
  --author "$BOT" --json number,isDraft \
  --jq '.[] | select(.isDraft) | .number')"
if [ -z "$DRAFTS" ]; then
  echo "no draft $BOT pull requests open"
fi
for pr in $DRAFTS; do
  reviewers=$(gh api "repos/${REPO}/pulls/${pr}/requested_reviewers" \
    --jq '(.users | length) + (.teams | length)')
  reviews=$(gh api "repos/${REPO}/pulls/${pr}/reviews" --jq 'length')
  if [ "$reviewers" -gt 0 ] || [ "$reviews" -gt 0 ]; then
    echo "PR #$pr: draft with reviewers, left to them"
    continue
  fi
  checks=$(gh pr checks "$pr" --repo "$REPO" --json name,bucket 2>/dev/null || true)
  if [ -z "$checks" ] || [ "$checks" = "[]" ]; then
    echo "PR #$pr: no checks reported yet"
    continue
  fi
  if jq -e 'any(.bucket == "pending")' <<<"$checks" >/dev/null; then
    echo "PR #$pr: checks still pending"
    continue
  fi
  labels=$(gh pr view "$pr" --repo "$REPO" --json labels --jq '.labels[].name')
  if jq -e 'any(.bucket == "fail")' <<<"$checks" >/dev/null; then
    # Renovate pushes fixes itself; request a review only once it stops trying
    sha=$(gh pr view "$pr" --repo "$REPO" --json headRefOid --jq .headRefOid)
    when=$(gh api "repos/${REPO}/commits/${sha}" --jq .commit.committer.date)
    age_hours=$((( $(date -u +%s) - $(date -u -d "$when" +%s) ) / 3600))
    if [ "$age_hours" -lt "$FAIL_COOLDOWN_HOURS" ]; then
      echo "PR #$pr: failing for ${age_hours}h, waiting for Renovate to fix it"
      continue
    fi
    failed=$(jq -r '.[] | select(.bucket == "fail") | "- " + .name' <<<"$checks")
    body="> [!WARNING]"$'\n'"> The checks have been failing for ${age_hours} h on the last commit and Renovate did not fix them. This pull request is held with 🤖-do-not-merge and needs reviews, also if a later commit passes."$'\n\n'"Failing checks:"$'\n\n'"${failed}"$'\n\n'"Reviewers: fix or close it, or remove 🤖-do-not-merge once the checks pass and the update is fine to merge."
    gh pr edit "$pr" --repo "$REPO" --add-label '🤖-do-not-merge'
    if grep -qx '🤖-renovate-fast-lane' <<<"$labels"; then
      gh pr edit "$pr" --repo "$REPO" --remove-label '🤖-renovate-fast-lane'
    fi
    gh pr ready "$pr" --repo "$REPO"
    gh pr comment "$pr" --repo "$REPO" --body "$body"
    echo "PR #$pr: failing past the cool-down, held and marked ready"
  else
    gh pr ready "$pr" --repo "$REPO"
    if grep -qx '🤖-renovate-fast-lane' <<<"$labels"; then
      echo "PR #$pr: checks passed, the renovate-fast queue takes it without waiting for reviews"
    else
      echo "PR #$pr: checks passed, marked ready for review"
    fi
  fi
done
