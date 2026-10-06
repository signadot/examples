#!/bin/bash
# Deletes a sandbox if it exists. API and deletion errors fail the pipeline.
# Usage: delete-sandbox.sh <sandbox>
set -euo pipefail
sandbox="$1"

sandboxes=$(signadot sandbox list -o json)
exists=$(jq -r --arg name "$sandbox" 'any(.[]; .name == $name)' <<<"$sandboxes")
if [ "$exists" = true ]; then
  signadot sandbox delete "$sandbox"
else
  echo "Sandbox ${sandbox} is already gone."
fi
