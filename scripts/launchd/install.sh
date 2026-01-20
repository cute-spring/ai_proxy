#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LABEL="${LABEL:-com.local.litellm.proxy}"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
PLIST_PATH="${LAUNCH_AGENTS_DIR}/${LABEL}.plist"
TEMPLATE_PATH="${ROOT_DIR}/scripts/launchd/com.local.litellm.proxy.plist.template"
LOG_DIR="${ROOT_DIR}/logs/launchd"
STDOUT_LOG="${LOG_DIR}/stdout.log"
STDERR_LOG="${LOG_DIR}/stderr.log"
PLISTBUDDY="/usr/libexec/PlistBuddy"

mkdir -p "$LAUNCH_AGENTS_DIR"
mkdir -p "$LOG_DIR"

if [ ! -f "$TEMPLATE_PATH" ]; then
  echo "模板不存在: $TEMPLATE_PATH"
  exit 1
fi

PROJECT_DIR="${PROJECT_DIR:-$ROOT_DIR}"
if [ ! -d "$PROJECT_DIR" ]; then
  echo "PROJECT_DIR 不存在: $PROJECT_DIR"
  exit 1
fi

sed \
  -e "s|__LABEL__|${LABEL}|g" \
  -e "s|__PROJECT_DIR__|${PROJECT_DIR}|g" \
  -e "s|__STDOUT_LOG__|${STDOUT_LOG}|g" \
  -e "s|__STDERR_LOG__|${STDERR_LOG}|g" \
  "$TEMPLATE_PATH" > "$PLIST_PATH"

if [ -f "${PROJECT_DIR}/.env" ]; then
  if [ -x "$PLISTBUDDY" ]; then
    if grep -qE '^[[:space:]]*LITELLM_HOST=' "${PROJECT_DIR}/.env"; then
      HOST_VALUE="$(sed -nE 's/^[[:space:]]*LITELLM_HOST=(.*)$/\1/p' "${PROJECT_DIR}/.env" | tail -n 1 | tr -d '"' | tr -d "'")"
      if [ -n "$HOST_VALUE" ]; then
        "$PLISTBUDDY" -c "Add :EnvironmentVariables:LITELLM_HOST string $HOST_VALUE" "$PLIST_PATH" >/dev/null 2>&1 || \
        "$PLISTBUDDY" -c "Set :EnvironmentVariables:LITELLM_HOST $HOST_VALUE" "$PLIST_PATH" >/dev/null 2>&1 || true
      fi
    fi
    if grep -qE '^[[:space:]]*LITELLM_PORT=' "${PROJECT_DIR}/.env"; then
      PORT_VALUE="$(sed -nE 's/^[[:space:]]*LITELLM_PORT=(.*)$/\1/p' "${PROJECT_DIR}/.env" | tail -n 1 | tr -d '"' | tr -d "'")"
      if [ -n "$PORT_VALUE" ]; then
        "$PLISTBUDDY" -c "Add :EnvironmentVariables:LITELLM_PORT string $PORT_VALUE" "$PLIST_PATH" >/dev/null 2>&1 || \
        "$PLISTBUDDY" -c "Set :EnvironmentVariables:LITELLM_PORT $PORT_VALUE" "$PLIST_PATH" >/dev/null 2>&1 || true
      fi
    fi
  fi
fi

launchctl unload -w "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl load -w "$PLIST_PATH"
launchctl start "$LABEL" >/dev/null 2>&1 || true

echo "已安装: $PLIST_PATH"
echo "查看日志:"
echo "  $STDOUT_LOG"
echo "  $STDERR_LOG"
