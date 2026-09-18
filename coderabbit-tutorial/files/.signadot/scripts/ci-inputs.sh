#!/usr/bin/env bash
set -euo pipefail
# Template substitution is textual. Restrict every substituted value before use.
invalid() { printf 'Invalid tutorial input: %s\n' "$1" >&2; exit 1; }
[[ "${PR_SHA:?}" =~ ^[0-9a-f]{40}$ ]] || invalid PR_SHA
[[ "${PR_NUMBER:?}" =~ ^[0-9]+$ ]] || invalid PR_NUMBER
[[ "${REPO_ID:?}" =~ ^[0-9]+$ ]] || invalid REPO_ID
[[ "${REPO:?}" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || invalid REPO
[[ "${CLUSTER:?}" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]] || invalid CLUSTER
[[ "${HOTROD_NAMESPACE:?}" =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$ ]] || invalid HOTROD_NAMESPACE
[[ "${RUNNER_GROUP:?}" =~ ^[a-z]([-a-z0-9]*[a-z0-9])?$ ]] || invalid RUNNER_GROUP
test "${#HOTROD_NAMESPACE}" -le 63 || invalid 'HOTROD_NAMESPACE is longer than 63 characters'
test "${#RUNNER_GROUP}" -le 30 || invalid 'SIGNADOT_RUNNER_GROUP is longer than 30 characters'
case "${TARGET_ARCH:?}" in amd64|arm64) ;; *) invalid 'HOTROD_ARCH must be amd64 or arm64' ;; esac

# Stable per repository ID + PR, valid within Signadot's 30-byte name limit.
identity=$(printf '%s:%s' "$REPO_ID" "$PR_NUMBER" | shasum -a 256)
printf 'SANDBOX=cr-%s\n' "${identity:0:24}"
image_repo=$(printf 'ghcr.io/%s/hotrod' "$REPO" | tr '[:upper:]' '[:lower:]')
printf 'IMAGE_REPOSITORY=%s\nIMAGE_TAG=%s:%s-%s\n' \
  "$image_repo" "$image_repo" "$PR_SHA" "$TARGET_ARCH"
