#!/usr/bin/env sh
set -eu

. "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/paperclip-env.sh"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

node_major_version() {
  node -p 'process.versions.node.split(".")[0]'
}

is_running() {
  if [ -f "$PAPERCLIP_PID_FILE" ]; then
    pid=$(cat "$PAPERCLIP_PID_FILE" 2>/dev/null || true)
    if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
  fi

  if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"$PAPERCLIP_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    return 0
  fi

  return 1
}

ensure_runtime() {
  if [ -x "$PAPERCLIP_BIN" ]; then
    return 0
  fi

  echo "Installing paperclipai@$PAPERCLIP_VERSION into $PAPERCLIP_RUNTIME_DIR ..."
  mkdir -p "$PAPERCLIP_RUNTIME_DIR"
  npm install --prefix "$PAPERCLIP_RUNTIME_DIR" "paperclipai@$PAPERCLIP_VERSION" --no-audit --no-fund
}

sync_config() {
  env \
    PAPERCLIP_HOME="$PAPERCLIP_HOME" \
    PAPERCLIP_INSTANCE_ID="$PAPERCLIP_INSTANCE_ID" \
    PAPERCLIP_CONFIG="$PAPERCLIP_CONFIG" \
    PAPERCLIP_DEPLOYMENT_MODE="$PAPERCLIP_DEPLOYMENT_MODE" \
    PAPERCLIP_DEPLOYMENT_EXPOSURE="$PAPERCLIP_DEPLOYMENT_EXPOSURE" \
    PAPERCLIP_PUBLIC_URL="$PAPERCLIP_PUBLIC_URL" \
    PAPERCLIP_ALLOWED_HOSTNAMES="$PAPERCLIP_ALLOWED_HOSTNAMES" \
    HOST="$PAPERCLIP_HOST" \
    PORT="$PAPERCLIP_PORT" \
    SERVE_UI="$SERVE_UI" \
    node "$ROOT_DIR/scripts/paperclip-sync-config.mjs"
}

rewrite_paths_if_needed() {
  if [ -z "$PAPERCLIP_REWRITE_FROM_ROOT" ]; then
    return 0
  fi

  if [ "$PAPERCLIP_REWRITE_FROM_ROOT" = "$PAPERCLIP_CANONICAL_PROJECT_ROOT" ]; then
    return 0
  fi

  env \
    PAPERCLIP_HOME="$PAPERCLIP_HOME" \
    PAPERCLIP_INSTANCE_ID="$PAPERCLIP_INSTANCE_ID" \
    node "$ROOT_DIR/scripts/paperclip-rewrite-paths.mjs" \
      "$PAPERCLIP_REWRITE_FROM_ROOT" \
      "$PAPERCLIP_CANONICAL_PROJECT_ROOT"
}

require_cmd node
require_cmd npm

NODE_MAJOR=$(node_major_version)
if [ "$NODE_MAJOR" -lt 20 ]; then
  echo "Node.js 20+ is required. Current version: $(node -v)" >&2
  exit 1
fi

ensure_runtime

mkdir -p "$PAPERCLIP_LOG_DIR"

if is_running; then
  echo "Paperclip is already running at $PAPERCLIP_URL"
  exit 0
fi

echo "Starting Paperclip at $PAPERCLIP_URL ..."
if [ -f "$PAPERCLIP_CONFIG" ]; then
  sync_config
  rewrite_paths_if_needed
  PAPERCLIP_COMMAND="run --config \"$PAPERCLIP_CONFIG\""
else
  PAPERCLIP_COMMAND="onboard --config \"$PAPERCLIP_CONFIG\" --yes"
fi

nohup sh -c "
  exec env \
    PAPERCLIP_HOME=\"$PAPERCLIP_HOME\" \
    PAPERCLIP_INSTANCE_ID=\"$PAPERCLIP_INSTANCE_ID\" \
    PAPERCLIP_CONFIG=\"$PAPERCLIP_CONFIG\" \
    PAPERCLIP_DEPLOYMENT_MODE=\"$PAPERCLIP_DEPLOYMENT_MODE\" \
    PAPERCLIP_DEPLOYMENT_EXPOSURE=\"$PAPERCLIP_DEPLOYMENT_EXPOSURE\" \
    PAPERCLIP_PUBLIC_URL=\"$PAPERCLIP_PUBLIC_URL\" \
    PAPERCLIP_ALLOWED_HOSTNAMES=\"$PAPERCLIP_ALLOWED_HOSTNAMES\" \
    HOST=\"$PAPERCLIP_HOST\" \
    PORT=\"$PAPERCLIP_PORT\" \
    SERVE_UI=\"$SERVE_UI\" \
    PAPERCLIP_OPEN_ON_LISTEN=false \
    \"$PAPERCLIP_BIN\" $PAPERCLIP_COMMAND
" >>"$PAPERCLIP_LAUNCH_LOG" 2>&1 &
PID=$!
echo "$PID" > "$PAPERCLIP_PID_FILE"

sleep 3

if kill -0 "$PID" 2>/dev/null; then
  echo "Paperclip started."
  echo "PID: $PID"
  echo "URL: $PAPERCLIP_URL"
  echo "Log: $PAPERCLIP_LAUNCH_LOG"
  exit 0
fi

echo "Paperclip exited early. Check $PAPERCLIP_LAUNCH_LOG" >&2
exit 1
