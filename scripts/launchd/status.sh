#!/bin/bash

set -euo pipefail

LABEL="${LABEL:-com.local.litellm.proxy}"
launchctl print "gui/$(id -u)/$LABEL" 2>/dev/null || launchctl list | grep -F "$LABEL" || true
