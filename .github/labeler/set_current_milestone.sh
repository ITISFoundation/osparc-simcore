#!/bin/bash
#
#  Puts a pull request into the current milestone: the open milestone with the
#  earliest due date, overdue or not, because a sprint milestone stays in use
#  until it is closed. Does nothing when no open milestone has a due date.
#
#  Required environment: REPO, PR_NUMBER.
#  Uses gh for API calls (GH_TOKEN must be set).

# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit  # abort on nonzero exitstatus
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes

milestone=$(gh api "repos/${REPO}/milestones?state=open&per_page=100" \
  --jq '[.[] | select(.due_on != null)] | sort_by(.due_on) | first | .number // empty')
if [ -z "$milestone" ]; then
  echo "No open milestone with a due date, leaving PR #${PR_NUMBER} without milestone"
  exit 0
fi
# a pull request is an issue to the API; the issues endpoint sets its milestone
gh api --method PATCH "repos/${REPO}/issues/${PR_NUMBER}" -F "milestone=${milestone}" \
  --jq '"PR #\(.number) added to milestone \(.milestone.title)"'
