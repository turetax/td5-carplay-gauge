#!/bin/sh
# Apply the Td5 UI changes after initializing the pinned LIVI submodule.
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
LIVI_DIR="$ROOT_DIR/third_party/LIVI"
PATCH_FILE="$ROOT_DIR/patches/livi-td5-gauge.patch"
EXPECTED_REVISION=$(cat "$ROOT_DIR/third_party/LIVI.UPSTREAM_REVISION")

test "$(git -C "$LIVI_DIR" rev-parse HEAD)" = "$EXPECTED_REVISION" || {
  printf '%s\n' 'LIVI revision differs from the patch base; update or regenerate the patch first.' >&2
  exit 1
}

git -C "$LIVI_DIR" apply --check "$PATCH_FILE"
git -C "$LIVI_DIR" apply "$PATCH_FILE"
printf '%s\n' 'Applied Td5 Gauge patch to LIVI.'
