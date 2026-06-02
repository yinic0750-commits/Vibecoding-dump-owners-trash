#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

if command -v python3 >/dev/null 2>&1; then
  exec python3 "$SCRIPT_DIR/agent_resource_monitor.py" "$@"
fi

if command -v python >/dev/null 2>&1 && python -c 'import sys; raise SystemExit(sys.version_info[0] < 3)' >/dev/null 2>&1; then
  exec python "$SCRIPT_DIR/agent_resource_monitor.py" "$@"
fi

printf '%s\n' "resource-monitor: python3 is required but was not found." >&2
exit 127
