#!/bin/bash
# Posts a one-time PR comment when workflows_signatures.json changes,
# warning OPS that Temporalio workflows must be shut down before deploying.
#
# Usage:
#   bash ci/github/helpers/ops-temporal-maintenance-comment.bash <repo> <pr_number>
#
# Environment:
#   GH_TOKEN  — GitHub token with pull-requests:write scope

set -o errexit
set -o nounset
set -o pipefail
IFS=$'\n\t'

REPO=$1
PR_NUMBER=$2
MARKER="OPS-TEMPORALIO-MAINTENANCE-REQUIRED"
TARGET_FILE="services/dynamic-scheduler/workflows_signatures.json"

# Check if comment already exists
EXISTING=$(gh api \
  "repos/${REPO}/issues/${PR_NUMBER}/comments" \
  --jq ".[] | select(.body | contains(\"${MARKER}\")) | .id" \
  | head -1)

if [ -n "$EXISTING" ]; then
  echo "Comment already exists (id=${EXISTING}), skipping."
  exit 0
fi

# Post the comment
gh api "repos/${REPO}/issues/${PR_NUMBER}/comments" \
  --method POST \
  --field body="<!-- ${MARKER} -->
## ⚠️ Temporalio Maintenance Required Before Deploy

This PR modifies \`${TARGET_FILE}\`, which means **workflow or activity implementations have changed**.

Before deploying, OPS **must** shut down all running Temporalio workflows to prevent stale executions.

**Steps:**
1. Do not merge without notifying OPS
2. OPS shuts down running workflows via \`POST /ops/temporalio-workflows:shutdown\`
3. Deploy the new code
4. Resolve/acknowledge this comment once confirmed ✅

_Triggered automatically because \`${TARGET_FILE}\` was changed._"

echo "✅ Comment posted."
