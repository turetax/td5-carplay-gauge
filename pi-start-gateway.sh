#!/bin/sh
# Starts on every Pi boot. Td5Gauge itself keeps retrying until the K-line
# cable and Td5 ECU become available.
set -eu

if command -v systemd-cat >/dev/null 2>&1; then
  printf '%s\n' 'Gateway startup: launcher entered' | systemd-cat -t td5-gateway
fi

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

if command -v systemd-cat >/dev/null 2>&1; then
  printf 'Gateway startup: starting Python on %s\n' "$PORT" | systemd-cat -t td5-gateway
fi

exec "$PYTHON" "$HOME/td5gauge/td5gauge.py" --port "$PORT" \
  --fast-init-mode "${TD5_FAST_INIT_MODE:-break-condition}"
