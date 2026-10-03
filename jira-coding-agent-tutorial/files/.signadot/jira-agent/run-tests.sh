#!/bin/bash
# Runs the Playwright suite as a Signadot Job against the PR sandbox.
# Fails unless the Job succeeded: a canceled Job can still exit 0, so the Job phase decides.
# Usage: run-tests.sh <sandbox>
set -euo pipefail
sandbox="$1"

set +e
signadot job submit -f .signadot/jira-agent/playwright-job.yaml \
  --set repo="${BITBUCKET_REPO_FULL_NAME}" \
  --set branch="${BITBUCKET_BRANCH}" \
  --set commit="${BITBUCKET_COMMIT}" \
  --set sandbox="${sandbox}" \
  --attach --timeout 20m 2>&1 | tee job.log
cli_exit=${PIPESTATUS[0]}
set -e

job=$(sed -nE 's/^Job (hotrod-playwright-[a-z0-9]+) .*/\1/p' job.log | head -n 1)
test -n "$job"
echo "$job" > job-name.txt
phase=$(signadot job get "$job" -o json | jq -er '.status.attempts[0].phase')
echo "Signadot Job ${job}: ${phase}"
test "$cli_exit" -eq 0 && test "$phase" = succeeded
