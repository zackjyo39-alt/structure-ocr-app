#!/usr/bin/env sh
set -eu

. "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/paperclip-env.sh"

stop_pid() {
  target_pid="$1"

  if ! kill -0 "$target_pid" 2>/dev/null; then
    return 1
  fi

  kill "$target_pid"

  i=0
  while [ "$i" -lt 10 ]; do
    if ! kill -0 "$target_pid" 2>/dev/null; then
      return 0
    fi
    sleep 1
    i=$((i + 1))
  done

  echo "Process $target_pid did not exit after 10s." >&2
  return 1
}

if [ -f "$PAPERCLIP_PID_FILE" ]; then
  PID=$(cat "$PAPERCLIP_PID_FILE" 2>/dev/null || true)
  if [ -n "${PID:-}" ] && stop_pid "$PID"; then
    rm -f "$PAPERCLIP_PID_FILE"
    echo "Stopped Paperclip (pid $PID)."
    exit 0
  fi
fi

if command -v lsof >/dev/null 2>&1; then
  PID=$(lsof -tiTCP:"$PAPERCLIP_PORT" -sTCP:LISTEN 2>/dev/null | head -n 1 || true)
  if [ -n "${PID:-}" ] && stop_pid "$PID"; then
    rm -f "$PAPERCLIP_PID_FILE"
    echo "Stopped Paperclip (pid $PID)."
    exit 0
  fi
fi

echo "Paperclip is not running."
