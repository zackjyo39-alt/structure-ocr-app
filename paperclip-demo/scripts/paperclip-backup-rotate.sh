#!/usr/bin/env sh
set -euo

# Keeps last N backups under the configured backups directory.
# Usage: paperclip-backup-rotate.sh [RETENTION]
# RETENTION: number of backups to keep (default: 7)
RETENTION=${1:-7}
ROOT_DIR="$(cd -- "$(dirname -- "$0")/.." && pwd)"
BACKUPS_DIR="${PAPERCLIP_HOME:-$ROOT_DIR/.paperclip-home}/instances/${PAPERCLIP_INSTANCE_ID:-demo}/data/backups"
echo "Rotating backups in $BACKUPS_DIR, keeping ${RETENTION} backups"
if [ ! -d "$BACKUPS_DIR" ]; then
  echo "No backups dir found; nothing to rotate."
  exit 0
fi
BACKUP_FILES=("$(ls -1 "$BACKUPS_DIR" 2>/dev/null | sort)")
NUM=${#BACKUP_FILES[@]}
if [ "$NUM" -le "$RETENTION" ]; then
  echo "Backup count ($NUM) within retention; nothing to delete."
  exit 0
fi
TO_DELETE_COUNT=$(($NUM - $RETENTION))
for i in $(seq 1 "$TO_DELETE_COUNT"); do
  FILE="${BACKUP_FILES[$i-1]}"
  if [ -n "$FILE" ]; then
    rm -f "$BACKUPS_DIR/$FILE" || true
    echo "Deleted old backup: $FILE"
  fi
done
echo "Retention rotation complete."
