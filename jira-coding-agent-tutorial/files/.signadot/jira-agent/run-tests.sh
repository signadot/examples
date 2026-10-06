#!/bin/bash
# Runs the Playwright suite as a Signadot Job against the PR sandbox.
# Usage: run-tests.sh <sandbox>
set -euo pipefail
sandbox="$1"
rm -f job-name.txt

set +e
signadot job submit -f .signadot/jira-agent/playwright-job.yaml \
  --set repo="${BITBUCKET_REPO_FULL_NAME}" \
  --set branch="${BITBUCKET_BRANCH}" \
  --set commit="${BITBUCKET_COMMIT}" \
  --set sandbox="${sandbox}" \
  --wait --timeout 20m -o json > job.json
cli_exit=$?
set -e

job=$(jq -er '.name | select(type == "string" and length > 0)' job.json)
printf '%s\n' "$job" > job-name.txt
# Select the newest attempt explicitly instead of depending on array order.
phase=$(jq -er '.status.attempts | max_by(.createdAt) | .phase' job.json)
echo "Signadot Job ${job}: ${phase}"
echo "Logs and artifacts: https://app.signadot.com/testing/jobs/${job}/overview"
# A failed CLI request, cancellation or timeout must never pass the step.
test "$cli_exit" -eq 0 && test "$phase" = succeeded
