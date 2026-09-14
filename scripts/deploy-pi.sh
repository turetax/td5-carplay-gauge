#!/usr/bin/env bash
# Incremental, rollback-safe deployment to the installed Raspberry Pi.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PI_HOST="${TD5_PI_HOST:-td5pi.local}"
PI_USER="${TD5_PI_USER:-jakob}"
PI_KEY="${TD5_PI_KEY:-$HOME/.ssh/td5pi_deploy_key}"
REMOTE_LIVI="${TD5_REMOTE_LIVI:-/home/$PI_USER/livi-td5-src}"
REMOTE_PROJECT="${TD5_REMOTE_PROJECT:-/home/$PI_USER/td5gauge}"

if [[ ! -f "$PI_KEY" ]]; then
  printf 'SSH-nyckeln saknas: %s\n' "$PI_KEY" >&2
  exit 1
fi

SSH=(ssh -i "$PI_KEY" -o BatchMode=yes -o ConnectTimeout=8)
RSYNC_SSH="ssh -i $PI_KEY -o BatchMode=yes -o ConnectTimeout=8"
TARGET="$PI_USER@$PI_HOST"

printf 'Synkroniserar gateway och startfiler till %s …\n' "$TARGET"
"${SSH[@]}" "$TARGET" "mkdir -p '$REMOTE_PROJECT/scripts' '$REMOTE_PROJECT/packaging' '$REMOTE_LIVI'"
rsync -az --itemize-changes -e "$RSYNC_SSH" \
  "$ROOT_DIR/td5gauge.py" \
  "$ROOT_DIR/td5_protocol.py" \
  "$ROOT_DIR/td5_signals.py" \
  "$ROOT_DIR/td5_transport.py" \
  "$ROOT_DIR/pi-start-gateway.sh" \
  "$ROOT_DIR/livi-integrated-start.sh" \
  "$ROOT_DIR/livi-source-launcher.sh" \
  "$ROOT_DIR/requirements.txt" \
  "$TARGET:$REMOTE_PROJECT/"
rsync -az --itemize-changes -e "$RSYNC_SSH" \
  "$ROOT_DIR/scripts/td5-health-check.sh" \
  "$TARGET:$REMOTE_PROJECT/scripts/"
rsync -az --itemize-changes -e "$RSYNC_SSH" \
  "$ROOT_DIR/packaging/livi-power.sh" \
  "$ROOT_DIR/packaging/99-TD5-livi-power" \
  "$TARGET:$REMOTE_PROJECT/packaging/"

printf 'Synkroniserar ändrade LIVI-källfiler till %s …\n' "$TARGET"
rsync -az --itemize-changes -e "$RSYNC_SSH" \
  --exclude '.git/' \
  --exclude 'coverage/' \
  --exclude 'dist/' \
  --exclude 'node_modules/' \
  --exclude 'out/' \
  "$ROOT_DIR/third_party/LIVI/" "$TARGET:$REMOTE_LIVI/"

rsync -az --itemize-changes -e "$RSYNC_SSH" \
  "$ROOT_DIR/livi-integrated-start.sh" \
  "$ROOT_DIR/livi-source-launcher.sh" \
  "$TARGET:$REMOTE_LIVI/"

# Keep the currently working output until the new renderer, main process and
# preload bundles have all built successfully. A failed update therefore does
# not leave the dashboard unusable.
"${SSH[@]}" "$TARGET" "set -eu
export PATH=/home/$PI_USER/.local/node-current/bin:\$PATH
cd '$REMOTE_LIVI'
backup=out.td5-deploy-backup
rm -rf \"\$backup\"
[ ! -d out ] || cp -a out \"\$backup\"
if ! pnpm run typecheck || ! pnpm run build:app; then
  rm -rf out
  [ ! -d \"\$backup\" ] || mv \"\$backup\" out
  exit 1
fi
rm -rf \"\$backup\"
pids=\"\$(pgrep -f '^$REMOTE_LIVI/node_modules/.*/electron' || true)\"
[ -z \"\$pids\" ] || kill \$pids
gateway_pid=\"\$(pgrep -u '$PI_USER' -f '$REMOTE_PROJECT/td5gauge.py' || true)\"
[ -z \"\$gateway_pid\" ] || kill \$gateway_pid
sleep 2
TD5_PROJECT_DIR='$REMOTE_PROJECT' TD5_LIVI_DIR='$REMOTE_LIVI' \
  nohup '$REMOTE_PROJECT/livi-integrated-start.sh' >/tmp/livi-integrated.log 2>&1 </dev/null &"

printf '%s\n' 'Klart: ny version byggd och LIVI omstartad.'
