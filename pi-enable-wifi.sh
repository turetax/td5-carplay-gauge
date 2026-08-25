#!/bin/sh
# One-time setup: create a persistent NetworkManager profile from environment
# variables. Do not put personal Wi-Fi names or passwords in this repository.
set -eu

ssid="${TD5_WIFI_SSID:?Set TD5_WIFI_SSID in an untracked .env file}"
psk="${TD5_WIFI_PSK:?Set TD5_WIFI_PSK in an untracked .env file}"

nmcli connection delete td5-wifi >/dev/null 2>&1 || true
nmcli connection add type wifi ifname wlan0 con-name td5-wifi ssid "$ssid" connection.autoconnect yes
nmcli connection modify td5-wifi wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$psk" connection.autoconnect-priority 100
nmcli connection up td5-wifi
