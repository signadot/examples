#!/bin/bash
# Publishes the Signadot result on the pull request as a Bitbucket Code Insights report.
# Pipelines' local proxy authenticates the call, so no token is needed.
# Usage: report.sh <PENDING|PASSED|FAILED> <preview-url> <sandbox> [job]
set -euo pipefail
result="$1" preview="$2" sandbox="$3" job="${4:-}"

details="Sandbox ${sandbox} runs this pull request's services alongside the shared HotROD baseline."
if [ -n "$job" ]; then
  details="${details} Playwright ran as Signadot Job ${job}."
fi

body=$(jq -n --arg r "$result" --arg p "$preview" --arg d "$details" --arg j "$job" '{
  title: "Signadot sandbox",
  report_type: "TEST",
  reporter: "Signadot",
  result: $r,
  details: $d,
  link: $p,
  data: ([{title: "Preview", type: "LINK", value: {text: "Open the preview", href: $p}}]
    + if $j == "" then [] else
        [{title: "Test run", type: "LINK",
          value: {text: "Open the Signadot Job", href: ("https://app.signadot.com/testing/jobs/" + $j + "/overview")}}]
      end)
}')

curl -sSf --proxy 'http://localhost:29418' -X PUT \
  "http://api.bitbucket.org/2.0/repositories/${BITBUCKET_REPO_FULL_NAME}/commit/${BITBUCKET_COMMIT}/reports/signadot" \
  -H 'Content-Type: application/json' \
  -d "$body"
