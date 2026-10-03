#!/bin/bash
# Prints the HotROD services this branch changes relative to <base-ref>, one per line.
# A change to code every service shares (cmd/, pkg/, internal/, go.mod, go.sum, Dockerfile) prints all of them.
set -euo pipefail
base="$1"
git rev-parse --verify --quiet "$base" >/dev/null || { echo "cannot resolve $base" >&2; exit 2; }
changed=$(git diff --name-only "$base"...HEAD)
if grep -qE '^(cmd|pkg|internal)/|^go\.(mod|sum)$|^Dockerfile$' <<<"$changed"; then
  printf '%s\n' driver frontend location route
else
  sed -nE 's#^services/(driver|frontend|location|route)/.*#\1#p' <<<"$changed" | sort -u
fi
