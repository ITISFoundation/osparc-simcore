#!/bin/bash
#
#  Renovate opens every PR as a draft (draftPR in .renovaterc.jsonc), so GitHub
#  does not auto-request the code owners until the checks are done. This poller
#  marks the drafts ready once their checks have all finished; the ready
#  transition makes GitHub request the code owners from CODEOWNERS by itself:
#  - all checks done + passed + 🤖-renovate-fast-lane (patch/pin/digest bumps,
#    Python minors, security fixes): the request comes out but nothing waits on
#    it, the renovate-fast Mergify queue merges the PR;
#  - all checks done + passed without the label (majors, other minors): the requested
#    review is what the PR then waits for;
#  - failing checks: nothing for FAIL_COOLDOWN_HOURS on the last commit, so
#    Renovate can push its own fix; then the PR gets 🤖-do-not-merge, loses
#    🤖-renovate-fast-lane, is marked ready (which requests the owners), and a
#    comment lists the failing checks. It then goes through the reviewed queue,
#    also once a fix makes its checks pass.
#  A draft that already has requested reviewers or reviews is left alone: the
#  gate reported it before or a person handles it (e.g. turned it back into a
#  draft on purpose).
#  Each draft also gets a comment listing the lockfile pins its diff moved besides the
#  dependency named in the title, updated in place on later runs. It changes no label
#  and no ready state.
#
#  Required environment: REPO, BOT, FAIL_COOLDOWN_HOURS.
#  Uses gh for API calls (GH_TOKEN must be set). GH_TOKEN must belong to the
#  Renovate App: a GitHub App cannot mark a pull request opened by another App
#  ready, so a github.token (github-actions App) run fails on the ready call.

# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit  # abort on nonzero exitstatus
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes

# First line of the moved-packages comment; the next poll finds its comment by it and
# updates that one instead of adding another
DRIFT_MARKER='<!-- renovate-drift-summary -->'

# Packages the comment lists before it truncates
DRIFT_LIST_LIMIT="${DRIFT_LIST_LIMIT:-40}"

# Reads a pull request diff on stdin and prints "<name>: <old> -> <new>" for every package
# whose lockfile pin moved, alphabetically. A pin starts at column 1, so the hunk of
# another file cannot match. Left out: a package the diff only adds or only drops, a pin
# it touches without changing, and the version the title names.
moved_pins() {
  local headline="$1"
  awk -v headline="$headline" '
    /^[+-][A-Za-z0-9._-]+(\[[A-Za-z0-9._-]+\])?==[A-Za-z0-9._+!-]+/ {
      side = substr($0, 1, 1)
      line = substr($0, 2)
      eq = index(line, "==")
      name = substr(line, 1, eq - 1)
      version = substr(line, eq + 2)
      sub(/[ \t\r]+$/, "", version)
      sub(/\[[^]]*\]$/, "", name)
      gsub(/[-_.]+/, "-", name)
      name = tolower(name)
      # one package moves in dozens of lockfiles, usually to the same version there, so
      # keep each version once
      if (side == "-") {
        seen[name] = 1
        if (index(" " old[name] " ", " " version " ") == 0) old[name] = old[name] " " version
      } else if (index(" " new[name] " ", " " version " ") == 0) {
        new[name] = new[name] " " version
      }
    }
    END {
      for (name in seen) {
        if (old[name] == "" || new[name] == "") continue
        if (headline != "" && index(" " new[name] " ", " " headline " ") > 0) continue
        olds = substr(old[name], 2)
        gsub(/ /, ", ", olds)
        news = substr(new[name], 2)
        gsub(/ /, ", ", news)
        print name ": " olds " -> " news
      }
    }
  ' | sort
}

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
  # The check reports one lockfile's compile, which fails while the layer it takes as
  # --constraint still pins the old version; the resync task
  # (.github/renovate/resync_lockfiles.py) re-resolves the tree after it. Advisory here,
  # because a resync that cannot resolve a directory fails the [sys] environment setup
  # test instead.
  checks=$(jq -c 'map(select(.name != "renovate/artifacts"))' <<<"$checks")
  if [ -z "$checks" ] || [ "$checks" = "[]" ]; then
    echo "PR #$pr: no checks reported yet"
    continue
  fi
  if jq -e 'any(.bucket == "pending")' <<<"$checks" >/dev/null; then
    echo "PR #$pr: checks still pending"
    continue
  fi
  info=$(gh pr view "$pr" --repo "$REPO" --json labels,title)
  labels=$(jq -r '.labels[].name' <<<"$info")
  # the version in the title is the one the pull request is about: "Update dependency
  # redis to v7.4.1 [Renovate]" -> 7.4.1. Any other wording leaves this empty and then
  # that package shows up in the list as well.
  headline=$(sed -n 's/.* to v\{1,\}\([0-9][^ ]*\) .*/\1/p' <<<"$(jq -r .title <<<"$info")")
  # What the resync moved on top of that package. It commits inside Renovate's own run,
  # before the pull request exists, so it cannot say so itself.
  if ! drift=$(gh pr diff "$pr" --repo "$REPO" | moved_pins "$headline"); then
    echo "PR #$pr: diff not readable, skipping the moved-packages comment"
    drift=""
  fi
  if [ -n "$drift" ]; then
    total=$(grep -c . <<<"$drift")
    # shellcheck disable=SC2016 # the backticks are markdown, not a command substitution
    listed=$(head -n "$DRIFT_LIST_LIMIT" <<<"$drift" | sed 's/^/- `/; s/$/`/')
    if [ "$total" -gt "$DRIFT_LIST_LIMIT" ]; then
      listed="${listed}"$'\n'"- and $((total - DRIFT_LIST_LIMIT)) more"
    fi
    body="${DRIFT_MARKER}"$'\n\n'"> [!NOTE]"$'\n'"> The lockfile resync moved **${total}** package(s) besides the one this pull request is about. The resync re-resolves every \`requirements/\` directory the pin reaches, uv keeps an existing pin only as a preference, and a package the resync has to free may end up at its newest release rather than at the version that unblocks it."$'\n\n'"${listed}"$'\n\n'"If one of these is what breaks a check, fix its cause on \`master\` as described in https://github.com/${REPO}/blob/master/docs/renovate.md#fixing-a-failing-renovate-pull-request."
    existing=$(gh api "repos/${REPO}/issues/${pr}/comments" --paginate \
      --jq ".[] | select(.body | startswith(\"$DRIFT_MARKER\")) | .id" | head -n 1 || true)
    if [ -z "$existing" ]; then
      gh pr comment "$pr" --repo "$REPO" --body "$body" >/dev/null
      echo "PR #$pr: commented the ${total} packages the resync moved"
    elif [ "$(gh api "repos/${REPO}/issues/comments/${existing}" --jq .body)" != "$body" ]; then
      gh api -X PATCH "repos/${REPO}/issues/comments/${existing}" -f body="$body" >/dev/null
      echo "PR #$pr: updated the moved-packages comment"
    fi
  fi
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
    body="> [!WARNING]"$'\n'"> The checks have been failing for ${age_hours} h on the last commit and Renovate did not fix them. This pull request is held with 🤖-do-not-merge and needs reviews, also if a later commit passes."$'\n\n'"Failing checks:"$'\n\n'"${failed}"$'\n\n'"Reviewers: do not push to this branch; fix or close it as described in https://github.com/${REPO}/blob/master/docs/renovate.md#fixing-a-failing-renovate-pull-request, and remove 🤖-do-not-merge once the checks pass and the update is fine to merge. 🤖-renovate-fast-lane was removed with the hold; add it back to send the pull request through the fast lane."
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
