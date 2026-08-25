#!/bin/sh
# Bootstrap one Raspberry Pi for Td5 Gauge. Run as the normal desktop user:
#   ./scripts/install-pi.sh
# It installs only local software and a read-only ECU gateway. It never sends
# diagnostic write/actuator commands to the vehicle.
set -eu

usage() {
  cat <<'EOF'
Usage: ./scripts/install-pi.sh [--user USER] [--home DIRECTORY] [--build-livi]

Run this from a clone of TD5 CarPlay Gauge on Raspberry Pi OS.
  --user USER       desktop user to own the installation (default: current user)
  --home DIRECTORY  home directory for that user (default: discovered from passwd)
  --build-livi      also build the patched LIVI source; requires Node.js + pnpm
EOF
}

TD5_USER="${SUDO_USER:-$USER}"
TD5_HOME=""
BUILD_LIVI=false
while [ "$#" -gt 0 ]; do
  case "$1" in
    --user) TD5_USER="${2:?Missing value for --user}"; shift 2 ;;
    --home) TD5_HOME="${2:?Missing value for --home}"; shift 2 ;;
    --build-livi) BUILD_LIVI=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Okänt val: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$(uname -m)" in
  armv7l|aarch64) ;;
  *) printf '%s\n' 'Det här installationsskriptet är avsett för Raspberry Pi.' >&2; exit 1 ;;
esac

if ! id "$TD5_USER" >/dev/null 2>&1; then
  printf 'Användaren %s finns inte.\n' "$TD5_USER" >&2
  exit 1
fi
if [ -z "$TD5_HOME" ]; then
  TD5_HOME="$(getent passwd "$TD5_USER" | awk -F: '{print $6}')"
fi
[ -n "$TD5_HOME" ] && [ -d "$TD5_HOME" ] || { printf '%s\n' 'Kunde inte hitta användarens hemkatalog.' >&2; exit 1; }

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
TARGET_DIR="$TD5_HOME/td5gauge"

if [ "$(id -u)" -eq 0 ]; then
  printf '%s\n' 'Kör som vanlig användare, inte direkt som root. Skriptet frågar efter sudo vid behov.' >&2
  exit 1
fi

printf '%s\n' 'Installerar grundberoenden …'
sudo apt-get update
sudo apt-get install --yes python3-venv python3-pip python3-serial curl git sway

if [ "$ROOT_DIR" != "$TARGET_DIR" ]; then
  printf '%s\n' "Kopierar projektet till $TARGET_DIR …"
  mkdir -p "$TARGET_DIR"
  tar --exclude=.git --exclude=.venv --exclude=node_modules --exclude=out -C "$ROOT_DIR" -cf - . | tar -C "$TARGET_DIR" -xf -
fi
chown -R "$TD5_USER:$TD5_USER" "$TARGET_DIR"
install -d -o "$TD5_USER" -g "$TD5_USER" "$TD5_HOME/.local/share/td5gauge/logs"

printf '%s\n' 'Installerar TD5-gateway …'
su - "$TD5_USER" -c "python3 -m venv '$TARGET_DIR/.venv'"
su - "$TD5_USER" -c "'$TARGET_DIR/.venv/bin/python' -m pip install --upgrade pip"
su - "$TD5_USER" -c "'$TARGET_DIR/.venv/bin/python' -m pip install -r '$TARGET_DIR/requirements.txt'"
chmod +x "$TARGET_DIR/pi-start-gateway.sh" "$TARGET_DIR/livi-integrated-start.sh" "$TARGET_DIR/livi-source-launcher.sh" "$TARGET_DIR/scripts/"*.sh

if [ ! -e /etc/td5-gauge.conf ]; then
  sudo install -m 0644 "$TARGET_DIR/packaging/td5-gauge.conf.example" /etc/td5-gauge.conf
fi

sed -e "s|__TD5_USER__|$TD5_USER|g" -e "s|__TD5_HOME__|$TD5_HOME|g" \
  "$TARGET_DIR/packaging/td5-gateway.service" | sudo tee /etc/systemd/system/td5-gateway.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now td5-gateway.service

mkdir -p "$TD5_HOME/.config/autostart"
sed "s|__TD5_HOME__|$TD5_HOME|g" "$TARGET_DIR/packaging/td5-livi.desktop" > "$TD5_HOME/.config/autostart/td5-livi.desktop"
chown "$TD5_USER:$TD5_USER" "$TD5_HOME/.config/autostart/td5-livi.desktop"

# Sway is used by the tested full-screen setup.  Keep its Td5 settings in a
# separate file so a normal Sway configuration remains easy to recover.
mkdir -p "$TD5_HOME/.config/sway/config.d"
if [ ! -f "$TD5_HOME/.config/sway/config" ]; then
  cp /etc/sway/config "$TD5_HOME/.config/sway/config"
fi
if ! grep -Fqx 'include ~/.config/sway/config.d/*.conf' "$TD5_HOME/.config/sway/config"; then
  printf '\n# Local TD5 Gauge additions\ninclude ~/.config/sway/config.d/*.conf\n' >> "$TD5_HOME/.config/sway/config"
fi
sed "s|\$HOME|$TD5_HOME|g" "$TARGET_DIR/pi-sway-config" > "$TD5_HOME/.config/sway/config.d/td5-gauge.conf"
chown -R "$TD5_USER:$TD5_USER" "$TD5_HOME/.config/sway"

if [ "$BUILD_LIVI" = true ]; then
  if ! command -v pnpm >/dev/null 2>&1; then
    printf '%s\n' 'pnpm saknas. Installera en aktuell Node.js-version och pnpm, kör sedan om med --build-livi.' >&2
    exit 1
  fi
  printf '%s\n' 'Applicerar Td5-patch och bygger LIVI …'
  su - "$TD5_USER" -c "cd '$TARGET_DIR' && git submodule update --init --recursive && ./scripts/apply-livi-patch.sh && cd third_party/LIVI && pnpm install --frozen-lockfile && pnpm run build:app"
fi

printf '%s\n' ''
printf '%s\n' 'Klart. Starta om Pi:n för helskärmsvyn, anslut därefter K+DCAN-kabeln och slå på tändningen.'
printf '%s\n' 'Kontrollera installationen med: ~/td5gauge/scripts/td5-health-check.sh'
