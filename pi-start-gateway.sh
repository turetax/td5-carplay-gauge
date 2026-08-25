#!/bin/sh
# Starts on every Pi boot. Td5Gauge itself keeps retrying until the K-line
# cable and Td5 ECU become available.
set -eu

CONFIG_FILE="${TD5_CONFIG_FILE:-/etc/td5-gauge.conf}"
if [ -r "$CONFIG_FILE" ]; then
  # The file is installed locally by scripts/install-pi.sh.  It contains only
  # simple KEY=value settings and is never committed to Git.
  # shellcheck disable=SC1090
  . "$CONFIG_FILE"
fi

find_serial_port() {
  if [ -n "${TD5_SERIAL_PORT:-}" ] && [ -e "$TD5_SERIAL_PORT" ]; then
    printf '%s\n' "$TD5_SERIAL_PORT"
    return 0
  fi

  # /dev/serial/by-id survives reboots and USB port ordering, unlike ttyUSB0.
  # The fallback keeps compatibility with adapters that do not expose by-id.
  for port in /dev/serial/by-id/*; do
    [ -e "$port" ] || continue
    printf '%s\n' "$port"
    return 0
  done
  printf '%s\n' /dev/ttyUSB0
}

PORT="$(find_serial_port)"
PYTHON="$HOME/td5gauge/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON=/usr/bin/python3

exec "$PYTHON" "$HOME/td5gauge/td5gauge.py" --port "$PORT"
