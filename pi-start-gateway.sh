#!/bin/sh
# Starts on every Pi boot. Td5Gauge itself keeps retrying until /dev/ttyUSB0
# and the Td5 ECU become available.
exec /usr/bin/python3 "$HOME/td5gauge/td5gauge.py" --port /dev/ttyUSB0
