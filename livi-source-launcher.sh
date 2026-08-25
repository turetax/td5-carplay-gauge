#!/bin/sh
# Relaunch the source-built LIVI app from its nested compositor during testing.
set -eu

readonly LIVI_DIR="${TD5_LIVI_DIR:-$HOME/livi-td5-src}"
cd "$LIVI_DIR"
export PATH="$HOME/.local/node-current/bin:$PATH"
export LIVI_EMBEDDED=1
exec ./node_modules/.bin/electron . "$@"
