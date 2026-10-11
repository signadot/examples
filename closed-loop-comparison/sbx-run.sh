#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 (--with-skill|--without-skill) [--repo <git-url>] [--name <sandbox-name>]" >&2
  exit 2
}

case "${1:-}" in
  --with-skill)    WITH_SKILLS=1 ;;
  --without-skill) WITH_SKILLS=0 ;;
  *)               usage ;;
esac
shift

REPO_URL="${REPO_URL:-https://github.com/signadot/hotrod}"
NAME_ARG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --repo) REPO_URL="${2:?--repo requires a git URL}"; shift 2 ;;
    --name) NAME_ARG="${2:?--name requires a sandbox name}"; shift 2 ;;
    *)      usage ;;
  esac
done

REPO_DIR="$(basename "${REPO_URL%.git}")"

if [ "$WITH_SKILLS" = "1" ]; then
  for var in SIGNADOT_API_KEY SIGNADOT_ORG SIGNADOT_CLUSTER; do
    if [ -z "${!var:-}" ]; then
      echo "error: $var must be set in the environment for --with-skill" >&2
      exit 1
    fi
  done
fi

SBX_NET_POLICIES=(
  '**.signadot.com:443'
  '**.svc:*'
  '**.svc.cluster:*'
  '**.svc.cluster.local:*'
  'cdn.playwright.dev:443'
  'playwright.download.prss.microsoft.com:443'
)
for policy in "${SBX_NET_POLICIES[@]}"; do
  if ! sbx policy ls 2>/dev/null | grep -qF "$policy"; then
    echo "==> adding sbx policy allow for $policy"
    sbx policy allow network "$policy"
  fi
done

SKILLS_SRC="${SKILLS_SRC:-$PWD/agent-skills}"
SKILLS_REPO="${SKILLS_REPO:-https://github.com/signadot/agent-skills}"
SIGNADOT_INSTALL_URL="${SIGNADOT_INSTALL_URL:-https://raw.githubusercontent.com/signadot/cli/main/scripts/install.sh}"

if [ -n "$NAME_ARG" ]; then
  NAME="$NAME_ARG"
elif [ "$WITH_SKILLS" = "1" ]; then
  NAME="${SBX_NAME:-sbx-with-env}"
else
  NAME="${SBX_NAME:-sbx-without-env}"
fi

if [ "$WITH_SKILLS" = "1" ] && [ ! -d "$SKILLS_SRC/.git" ]; then
  echo "==> cloning $SKILLS_REPO -> $SKILLS_SRC"
  git clone "$SKILLS_REPO" "$SKILLS_SRC"
fi
if [ "$WITH_SKILLS" = "1" ]; then
  SKILLS_SRC="$(cd "$SKILLS_SRC" && pwd)"
fi

SBX_ROOT="$PWD/$NAME"
mkdir -p "$SBX_ROOT"
if [ ! -d "$SBX_ROOT/$REPO_DIR/.git" ]; then
  echo "==> cloning $REPO_URL -> $SBX_ROOT/$REPO_DIR"
  git clone "$REPO_URL" "$SBX_ROOT/$REPO_DIR"
fi
cd "$SBX_ROOT/$REPO_DIR"

if sbx ls 2>/dev/null | awk 'NR>1 {print $1}' | grep -qx "$NAME"; then
  read -r -p "sandbox $NAME already exists. Remove and recreate? [y/N] " ans
  if [[ "$ans" =~ ^[Yy]$ ]]; then
    echo "==> removing sandbox $NAME"
    sbx rm "$NAME"
  fi
fi

if ! sbx ls 2>/dev/null | awk 'NR>1 {print $1}' | grep -qx "$NAME"; then
  echo "==> creating sandbox $NAME (mount: $PWD)"
  if [ "$WITH_SKILLS" = "1" ]; then
    sbx create --name "$NAME" claude . "$SKILLS_SRC"
  else
    sbx create --name "$NAME" claude .
  fi
fi

echo "==> [$NAME] disabling claude away-summary recaps"
sbx exec "$NAME" bash -c '
  set -e
  mkdir -p "$HOME/.claude"
  SETTINGS="$HOME/.claude/settings.json"
  if [ -f "$SETTINGS" ]; then
    jq ".awaySummaryEnabled = false" "$SETTINGS" > "$SETTINGS.tmp" && mv "$SETTINGS.tmp" "$SETTINGS"
  else
    jq -n "{awaySummaryEnabled: false}" > "$SETTINGS"
  fi
'

echo "==> [$NAME] adding cluster suffixes to NO_PROXY in ~/.bashrc"
sbx exec "$NAME" bash -c '
  set -e
  marker="# sbx-run: NO_PROXY for cluster"
  if ! grep -qF "$marker" "$HOME/.bashrc" 2>/dev/null; then
    cat >> "$HOME/.bashrc" <<EOF

$marker
export NO_PROXY="\${NO_PROXY:+\$NO_PROXY,}.svc,.svc.cluster,.svc.cluster.local"
export no_proxy="\$NO_PROXY"
EOF
  fi
'

if [ "$WITH_SKILLS" = "1" ]; then
  echo "==> [$NAME] installing playwright + chromium for frontend previews (if missing)"
  sbx exec "$NAME" bash -c '
    set -e
    wait_for_apt() {
      for i in $(seq 1 60); do
        busy=0
        for lock in /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock /var/lib/apt/lists/lock /var/cache/apt/archives/lock; do
          if sudo fuser "$lock" >/dev/null 2>&1; then busy=1; break; fi
        done
        if [ "$busy" = "0" ]; then return 0; fi
        echo "apt is busy (lock: $lock), retrying in 5s ($i/60)"
        sleep 5
      done
      return 1
    }
    if ! ls "$HOME/.cache/ms-playwright"/chromium-*/chrome-linux/chrome >/dev/null 2>&1; then
      for attempt in 1 2 3; do
        wait_for_apt || { echo "apt still busy after wait"; }
        if sudo npx -y playwright install-deps chromium; then
          break
        fi
        echo "playwright install-deps failed (attempt $attempt/3), retrying in 10s"
        sleep 10
      done
      npx -y playwright install chromium
    fi
    if ! claude mcp list 2>/dev/null | grep -q "^playwright"; then
      claude mcp add --scope user --transport stdio playwright -- npx -y @playwright/mcp@latest --browser chromium
    fi
  '

  echo "==> [$NAME] installing grpcurl (if missing)"
  sbx exec "$NAME" bash -c '
    set -e
    if ! command -v grpcurl >/dev/null 2>&1; then
      case "$(uname -m)" in
        x86_64|amd64) garch=x86_64 ;;
        aarch64|arm64) garch=arm64 ;;
        *) echo "unsupported arch: $(uname -m)" >&2; exit 1 ;;
      esac
      ver=1.9.1
      tmp=$(mktemp -d)
      curl -sSLf "https://github.com/fullstorydev/grpcurl/releases/download/v${ver}/grpcurl_${ver}_linux_${garch}.tar.gz" \
        | tar -xz -C "$tmp" grpcurl
      sudo mv "$tmp/grpcurl" /usr/local/bin/grpcurl
      rm -rf "$tmp"
    fi
  '

  echo "==> [$NAME] installing signadot CLI (if missing) and symlinking ~/.claude/skills"
  sbx exec "$NAME" bash -c '
    set -e
    if ! command -v signadot >/dev/null 2>&1; then
      curl -sSLf '"$SIGNADOT_INSTALL_URL"' | sudo sh
    fi
    if [ ! -e "$HOME/.claude/skills" ]; then
      ln -s "'"$SKILLS_SRC"'/skills" "$HOME/.claude/skills"
    fi
  '

  if ! sbx exec "$NAME" test -f /home/agent/.signadot/config.yaml; then
    echo "==> [$NAME] writing ~/.signadot/config.yaml base config"
    printf '%s\n' "org: $SIGNADOT_ORG
local:
  debug: true
  connections:
  - cluster: $SIGNADOT_CLUSTER
    type: ControlPlaneProxy" \
      | sbx exec -i "$NAME" bash -c 'mkdir -p "$HOME/.signadot" && umask 077 && cat > "$HOME/.signadot/config.yaml"'
  fi

  echo "==> [$NAME] signadot auth login --with-api-key --insecure-storage"
  sbx exec -e SIGNADOT_API_KEY="$SIGNADOT_API_KEY" "$NAME" \
    bash -c 'signadot auth login --with-api-key "$SIGNADOT_API_KEY" --insecure-storage'

  echo "==> [$NAME] registering signadot MCP server with claude (if missing)"
  sbx exec "$NAME" bash -c '
    if ! claude mcp list 2>/dev/null | grep -q "^signadot"; then
      claude mcp add --scope user --transport stdio signadot -- signadot mcp --disable-elicitation
    fi
    echo "--- claude mcp list (inside sandbox) ---"
    claude mcp list
  '

  echo "==> [$NAME] installing SessionStart hook to auto-start signadot local connect"
  sbx exec "$NAME" bash -c '
    set -e
    mkdir -p "$HOME/.local/bin" "$HOME/.claude"
    cat > "$HOME/.local/bin/sbx-signadot-ensure" <<"EOS"
#!/bin/bash
if signadot local status >/dev/null 2>&1; then
  exit 0
fi
signadot local disconnect >/dev/null 2>&1 || true
setsid -f bash -c "signadot local connect > /tmp/signadot-connect.log 2>&1" </dev/null
EOS
    chmod +x "$HOME/.local/bin/sbx-signadot-ensure"

    HOOK_CMD="$HOME/.local/bin/sbx-signadot-ensure"
    SETTINGS="$HOME/.claude/settings.json"
    if [ -f "$SETTINGS" ]; then
      jq --arg c "$HOOK_CMD" ".hooks.SessionStart = [{matcher: \"startup|resume\", hooks: [{type: \"command\", command: \$c}]}]" \
        "$SETTINGS" > "$SETTINGS.tmp"
      mv "$SETTINGS.tmp" "$SETTINGS"
    else
      jq -n --arg c "$HOOK_CMD" "{hooks: {SessionStart: [{matcher: \"startup|resume\", hooks: [{type: \"command\", command: \$c}]}]}}" > "$SETTINGS"
    fi
  '
fi

echo "==> attaching to sandbox $NAME"
exec sbx run "$NAME"
