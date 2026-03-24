#!/usr/bin/env sh
set -eu

. "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/paperclip-env.sh"

RUNNING_PID=""

if [ -f "$PAPERCLIP_PID_FILE" ]; then
  PID=$(cat "$PAPERCLIP_PID_FILE" 2>/dev/null || true)
  if [ -n "${PID:-}" ] && kill -0 "$PID" 2>/dev/null; then
    RUNNING_PID="$PID"
  fi
fi

if [ -z "$RUNNING_PID" ] && command -v lsof >/dev/null 2>&1; then
  PID=$(lsof -tiTCP:"$PAPERCLIP_PORT" -sTCP:LISTEN 2>/dev/null | head -n 1 || true)
  if [ -n "${PID:-}" ]; then
    RUNNING_PID="$PID"
  fi
fi

if [ -n "$RUNNING_PID" ]; then
  echo "Status: running"
  echo "PID: $RUNNING_PID"
else
  echo "Status: stopped"
fi

echo "URL: $PAPERCLIP_URL"
echo "Config: $PAPERCLIP_CONFIG"
echo "Home: $PAPERCLIP_HOME"
echo "Launch log: $PAPERCLIP_LAUNCH_LOG"

if command -v curl >/dev/null 2>&1; then
  HEALTH=$(curl -fsS "$PAPERCLIP_URL/api/health" 2>/dev/null || true)
  if [ -n "$HEALTH" ]; then
    echo "Health: $HEALTH"
  fi
fi

# Show the latest available database backup for quick health check
BACKUPS_DIR="$PAPERCLIP_HOME/instances/$PAPERCLIP_INSTANCE_ID/data/backups"
if [ -d "$BACKUPS_DIR" ]; then
  LATEST_BACKUP=$(ls -1 "$BACKUPS_DIR" 2>/dev/null | sort -r | head -n 1 || true)
  if [ -n "$LATEST_BACKUP" ]; then
    echo "Latest backup: $LATEST_BACKUP"
  fi
fi
