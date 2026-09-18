#!/usr/bin/env bash
set -euo pipefail
case "${TARGET_ARCH:?}" in
  amd64|arm64) ;;
  *) printf 'Invalid tutorial input: HOTROD_ARCH must be amd64 or arm64\n' >&2; exit 1 ;;
esac
# The Makefile runs HotROD's own frontend build (yarn, from the committed lockfile)
# and then the Go binary.
go test ./...
go vet ./...
make build GOOS=linux GOARCH="$TARGET_ARCH"
