#!/bin/sh
# Start the source-built Td5 + LIVI shell as one full-width vehicle UI.
set -eu

boot_log() {
  message="LIVI startup: $1"
  if command -v systemd-cat >/dev/null 2>&1; then
    printf '%s\n' "$message" | systemd-cat -t td5-livi
  else
    printf '%s\n' "$message" >&2
  fi
}

boot_log "launcher entered"

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

# Prefer an installed production binary when one is available. Keep the
# source-built Electron launch as a development/recovery fallback.
if [ -n "${TD5_LIVI_EXECUTABLE:-}" ] && [ -x "$TD5_LIVI_EXECUTABLE" ]; then
  boot_log "starting production executable $TD5_LIVI_EXECUTABLE"
  exec "$TD5_LIVI_EXECUTABLE" --ozone-platform=wayland
fi

for executable in "$LIVI_DIR"/dist/LIVI-*-linux-arm64.AppImage \
  "$LIVI_DIR/dist/linux-arm64-unpacked/livi" \
  "$LIVI_DIR/dist/linux-arm64-unpacked/LIVI"; do
  if [ -x "$executable" ]; then
    boot_log "starting packaged production executable $executable"
    exec "$executable" --ozone-platform=wayland
  fi
done

boot_log "starting source-build fallback"
exec ./node_modules/.bin/electron . --ozone-platform=wayland
