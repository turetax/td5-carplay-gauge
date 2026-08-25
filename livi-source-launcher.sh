#!/bin/sh
# Relaunch the source-built LIVI app from its nested compositor during testing.
set -eu

readonly PROJECT_DIR="${TD5_PROJECT_DIR:-$HOME/td5gauge}"
readonly LIVI_DIR="${TD5_LIVI_DIR:-$PROJECT_DIR/third_party/LIVI}"
cd "$LIVI_DIR"
export PATH="$HOME/.local/node-current/bin:$PATH"
export LIVI_EMBEDDED=1
exec ./node_modules/.bin/electron . "$@"
