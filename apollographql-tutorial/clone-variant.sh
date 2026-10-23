#!/usr/bin/env bash
# clone-variant.sh
# Usage: ./clone-variant.sh <GRAPH> <SRC_VARIANT> <DST_VARIANT>
# Example: ./clone-variant.sh my-graph staging dev-feature

set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 <GRAPH> <SRC_VARIANT> <DST_VARIANT>" >&2
  exit 1
fi

GRAPH="$1"
SRC="$2"
DST="$3"

# Dependencies check
command -v rover >/dev/null 2>&1 || { echo "Error: rover is not installed or not on PATH" >&2; exit 1; }
command -v jq >/dev/null 2>&1     || { echo "Error: jq is not installed or not on PATH" >&2; exit 1; }

echo "Copying subgraphs from $GRAPH@$SRC -> $GRAPH@$DST"

# List subgraphs (name + url) in source variant.
# A read loop instead of mapfile keeps this working on macOS's Bash 3.2.
SUBGRAPHS=()
while IFS= read -r line; do
  SUBGRAPHS+=("$line")
done < <(
  rover --format json subgraph list "$GRAPH@$SRC" \
  | jq -r '.data.subgraphs[] | [.name, (.url // "")] | @tsv'
)

if [[ ${#SUBGRAPHS[@]} -eq 0 ]]; then
  echo "No subgraphs found in $GRAPH@$SRC" >&2
  exit 1
fi

for entry in "${SUBGRAPHS[@]}"; do
  name="${entry%%$'\t'*}"
  url="${entry#*$'\t'}"

  if [[ -z "$name" ]]; then
    echo "Skipping an entry with empty subgraph name" >&2
    continue
  fi

  if [[ -z "$url" ]]; then
    echo "Warning: subgraph '$name' has no routing URL in $GRAPH@$SRC; skipping." >&2
    continue
  fi

  echo "→ Publishing '$name' to $GRAPH@$DST with URL: $url"

  # Fetch schema from source and publish to destination
  rover subgraph fetch "$GRAPH@$SRC" --name "$name" \
    | rover subgraph publish "$GRAPH@$DST" \
        --name "$name" \
        --routing-url "$url" \
        --schema -

  echo "✓ Published '$name'"
done

echo "Done. All subgraphs copied to $GRAPH@$DST."
