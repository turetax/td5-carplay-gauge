#!/bin/sh
# Start the source-built Td5 + LIVI shell as one full-width vehicle UI.
set -eu

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
if [ -z "${WAYLAND_DISPLAY:-}" ]; then
  # When launched by Sway this is already set.  The fallback is only for
  # recovery over SSH: a stale nested-compositor socket can be newer than
  # Sway's socket, so prefer the oldest live Wayland socket.
  WAYLAND_DISPLAY="$(find "$XDG_RUNTIME_DIR" -maxdepth 1 -type s -name 'wayland-*' -printf '%T@ %f\n' | sort -n | awk 'NR == 1 { print $2 }')"
  export WAYLAND_DISPLAY
fi
readonly PROJECT_DIR="${TD5_PROJECT_DIR:-$HOME/td5gauge}"
readonly LIVI_DIR="${TD5_LIVI_DIR:-$PROJECT_DIR/third_party/LIVI}"
export PATH="$HOME/.local/node-current/bin:$PATH"
export APPIMAGE="$PROJECT_DIR/livi-source-launcher.sh"
export LIVI_EMBEDDED=1

cd "$LIVI_DIR"
exec ./node_modules/.bin/electron . --ozone-platform=wayland
