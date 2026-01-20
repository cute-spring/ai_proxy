#!/bin/bash

set -euo pipefail

LABEL="${LABEL:-com.local.litellm.proxy}"
PLIST_PATH="${HOME}/Library/LaunchAgents/${LABEL}.plist"

if [ -f "$PLIST_PATH" ]; then
  launchctl stop "$LABEL" >/dev/null 2>&1 || true
  launchctl unload -w "$PLIST_PATH" >/dev/null 2>&1 || true
  rm -f "$PLIST_PATH"
  echo "已卸载: $PLIST_PATH"
else
  echo "未找到: $PLIST_PATH"
fi
