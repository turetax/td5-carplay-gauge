#!/bin/sh
# Fixed root helper for the in-vehicle UI. No arbitrary command execution.
set -eu

case "${1:-}" in
  poweroff) exec systemctl poweroff ;;
  reboot) exec systemctl reboot ;;
  *) printf '%s\n' 'usage: livi-power.sh poweroff|reboot' >&2; exit 2 ;;
esac
