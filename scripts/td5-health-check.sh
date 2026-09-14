#!/bin/sh
# Read-only post-installation diagnostic. Safe to run with or without the car.
set -eu

SERVICE="${TD5_SERVICE_NAME:-td5-gateway.service}"
printf '%s\n' 'TD5 Gauge – systemkontroll'

if ! command -v systemctl >/dev/null 2>&1; then
  printf '%s\n' '• Systemd hittades inte; kör denna kontroll på Raspberry Pi OS.'
elif systemctl is-active --quiet "$SERVICE"; then
  printf '%s\n' '✓ Gateway-tjänsten körs'
else
  printf '%s\n' '✗ Gateway-tjänsten körs inte'
  printf '%s\n' "  Kör: sudo systemctl status $SERVICE"
fi

if ls /dev/serial/by-id/* >/dev/null 2>&1; then
  printf '%s\n' '✓ USB-serieadapter hittad:'
  ls -1 /dev/serial/by-id/*
elif [ -e /dev/ttyUSB0 ]; then
  printf '%s\n' '✓ USB-serieadapter hittad: /dev/ttyUSB0'
else
  printf '%s\n' '• Ingen K+DCAN-adapter syns ännu. Anslut kabeln och slå på tändningen.'
fi

if command -v curl >/dev/null 2>&1 && curl --fail --silent --max-time 2 http://127.0.0.1:8080/api/live >/dev/null; then
  printf '%s\n' '✓ Gateway-API svarar lokalt'
else
  printf '%s\n' '• Gateway-API svarar inte ännu; kontrollera tjänsten ovan.'
fi

if command -v journalctl >/dev/null 2>&1; then
  printf '%s\n' '• Senaste startmätpunkter:'
  journalctl -b --no-pager -o short-monotonic -t td5-livi -t td5-gateway 2>/dev/null | tail -n 12 || true
fi

if command -v vcgencmd >/dev/null 2>&1; then
  throttle_raw="$(vcgencmd get_throttled 2>/dev/null || true)"
  throttle_hex="${throttle_raw#*=}"
  case "$throttle_hex" in
    0x*)
      throttle_value=$((throttle_hex))
      if [ $((throttle_value & 1)) -ne 0 ]; then
        printf '%s\n' '✗ UNDERVOLTAGE NU — byt nätaggregat/kabel innan fortsatt belastning'
      elif [ $((throttle_value & 4)) -ne 0 ]; then
        printf '%s\n' '✗ Pajen är strypt just nu; kontrollera ström och temperatur'
      elif [ $((throttle_value & 0x50000)) -ne 0 ]; then
        printf '%s\n' '• Underspänning/strypning har inträffat sedan senaste uppstart'
      else
        printf '%s\n' '✓ Ingen underspänning eller strypning registrerad'
      fi
      ;;
  esac
fi
