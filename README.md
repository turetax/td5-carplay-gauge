# TD5 CarPlay Gauge

A Raspberry Pi-based infotainment system with real-time engine monitoring and
Apple CarPlay for Land Rover Defender and Discovery 2 models powered by the
2.5-litre, five-cylinder TD5 diesel engine.

This is an independent hobby/diagnostic project. It is not affiliated with or
endorsed by JLR, Land Rover, Apple, Google, Spotify, or other trademark owners.

The TD5 dashboard is integrated directly into LIVI and runs as part of the same
full-width vehicle interface as CarPlay. Engine data is read from the TD5 ECU
through a K+DCAN cable and presented in a touch-friendly dashboard built for the
project's 1920 × 440 display.

## Features

* Live TD5 engine data inside the LIVI interface
* Apple CarPlay integration through LIVI, intended for use with a Carlinkit adapter
* Coolant temperature, engine speed, voltage, fuel temperature, intake air
  temperature, MAP, calculated boost, MAF, wastegate, throttle, and injector
  balance readings
* Session peaks, trends, local history, and alert history
* Read-only ECU fault-code retrieval
* Visual warnings and an audible high-coolant-temperature alarm
* Automatic reconnection when the K+DCAN cable or ECU becomes available
* Touch-optimized interface for an in-vehicle ultra-wide display

## How it works

The system consists of two cooperating processes on the Raspberry Pi:

1. The Python TD5 gateway communicates with the ECU through `/dev/ttyUSB0`. It
   performs the TD5 diagnostic login, continuously reads engine values, and
   exposes them through a local API at `http://127.0.0.1:8080`.
2. LIVI runs as the single full-screen vehicle interface. Its built-in TD5 page
   reads the local gateway API and displays live values, history, warnings, and
   diagnostic information. LIVI also manages the CarPlay projection session.

The gateway and dashboard are read-oriented. Fault-code requests only read stored
and active faults; they do not clear codes, change ECU settings, or perform actuator
commands.

## Hardware

The current installation uses:

* A Raspberry Pi 4 Model B running Raspberry Pi OS
* An 11.26-inch touchscreen (1920 × 440) with an IPS panel, HDMI video input,
  and USB touch input
* A K+DCAN USB cable with an FTDI-compatible serial interface and K-line connected
  to OBD pin 7
* A Carlinkit CPC200-CCPA USB adapter for wired or wireless Apple CarPlay. The
  adapter has been purchased but has not yet arrived, so this hardware combination
  has not yet been tested in the project.

The touchscreen is detected as an ILITEK USB device and mapped to the HDMI output
by the included Wayland configuration.

### Display installation

A complete guide for installing the display in the vehicle will be added later.
It will cover physical mounting, bracket design, cable routing, dashboard fitment,
and the final in-vehicle connections. Until that guide and the power solution have
been completed and tested, the display should be treated as a bench-tested part of
the project rather than a ready-to-install vehicle kit.

### Vehicle power solution

The vehicle power solution has not yet been finalized. Work is ongoing on a safe
and reliable way to power the Raspberry Pi, display, and connected USB devices in
the vehicle.

> **Warning:** Do not connect the Raspberry Pi, display, or USB hardware directly
> to the vehicle's 12 V electrical system. These devices require properly regulated
> power, and a direct connection can permanently damage the equipment, overheat
> wiring, or create a fire risk.

A vehicle electrical system is not a clean, constant 12 V supply. Its voltage can
drop during engine cranking and rise significantly during charging or electrical
transients. The final solution therefore needs an automotive-rated DC-DC converter,
appropriate input protection, a fuse installed close to the power source, correctly
rated wiring, and sufficient output capacity for the complete system.

The power controller must also monitor the ignition state. When the ignition is
switched off, it should keep the Raspberry Pi powered long enough to complete an
orderly shutdown before disconnecting power. Cutting power immediately can corrupt
the filesystem or SD card and may prevent the system from starting correctly the
next time. Until a tested power solution is documented, this project should only be
powered from a suitable protected and regulated bench supply during testing.

### CarPlay hardware status

LIVI provides the software integration for CarPlay, but the planned Carlinkit
CPC200-CCPA dongle has not yet been connected or verified with this installation.
CarPlay support should therefore be considered untested until the adapter arrives
and has been validated on the Raspberry Pi.

## Raspberry Pi installation

Start with a fresh Raspberry Pi OS installation with the desktop, a network
connection during installation, and a supported touchscreen. Use a dedicated Pi
and SD card: this installer configures the desktop user to start the vehicle
interface automatically.

1. Flash Raspberry Pi OS (64-bit, desktop) using Raspberry Pi Imager. Create a
   normal user and enable Wi-Fi or Ethernet for the initial installation.
2. On the Pi, clone this repository and initialize the included LIVI source:

   ```sh
   git clone --recurse-submodules REPOSITORY_URL td5-carplay-gauge
   cd td5-carplay-gauge
   ```

3. Run the installer as that normal desktop user. It asks for the administrator
   password only to install packages and register the gateway service:

   ```sh
   ./scripts/install-pi.sh
   ```

4. If Node.js and `pnpm` are already installed, add `--build-livi` to build the
   integrated Td5/LIVI interface in the same step. Otherwise follow LIVI's
   documented Raspberry Pi build prerequisites, then run:

   ```sh
   ./scripts/install-pi.sh --build-livi
   ```

5. Restart the Pi. The gateway starts at boot and the full-screen dashboard is
   registered as a desktop autostart application. Connect the K+DCAN cable,
   turn the ignition to position II, and wait for the ECU state in the footer.

The installer deliberately defaults to the local-only API and read-only ECU
operations. It does not clear faults, change ECU configuration, or actuate ABS
components. Verify the wiring and software after installation with:

```sh
~/td5gauge/scripts/td5-health-check.sh
```

### First-boot configuration

`/etc/td5-gauge.conf` is created on the Pi. Normally it needs no changes: the
startup script prefers the stable `/dev/serial/by-id/...` identity of the first
USB serial adapter and only falls back to `/dev/ttyUSB0`. If several serial
adapters are connected, set the exact path in that file, then restart the
gateway:

```sh
sudo systemctl restart td5-gateway.service
```

For a production-quality kit, distribute a tested SD-card image containing the
already-built LIVI bundle. That avoids compiling Node/Electron on the buyer's
Pi and makes the above first boot genuinely flash-card, connect, and drive.

## Manual source setup

Clone the repository and enter the project directory:

```sh
git clone REPOSITORY_URL td5-carplay-gauge
cd td5-carplay-gauge
git submodule update --init
```

Create a Python virtual environment and install the TD5 gateway dependency:

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Replace `REPOSITORY_URL` with the HTTPS or SSH clone URL shown on the repository's
GitHub page. No fixed username or local installation path is required.

Apply the TD5 interface changes to the pinned LIVI source:

```sh
./scripts/apply-livi-patch.sh
```

The automated installer above is the recommended setup for a Raspberry Pi. More
detailed documentation for manual package installation, startup configuration,
display setup, and physical vehicle installation will be added as the hardware
setup is finalized.

## Runtime

For a manual or temporary test, start the TD5 gateway with:

```sh
python3 td5gauge.py --port /dev/ttyUSB0
```

The gateway keeps retrying until both the USB adapter and TD5 ECU are available.
It listens only on `127.0.0.1` by default because the API is intended for the TD5
page inside LIVI. Do not expose the diagnostic API to an untrusted network.
The installed system starts the gateway through `td5-gateway.service` and launches
the integrated LIVI interface through the desktop autostart entry installed by
`scripts/install-pi.sh`.

To try the dashboard without a connected vehicle or K+DCAN cable, start it with
simulated TD5 data:

```sh
python3 td5gauge.py --simulate
```

## Roadmap

The project is currently focused on read-only diagnostics. Planned future work
includes:

* Adding carefully controlled ECU write operations
* Clearing diagnostic trouble codes from the TD5 ECU
* Supporting the ABS bleed procedure through the diagnostic interface
* Integrating a reversing camera into the LIVI interface
* Developing the vehicle power solution, including ignition-state detection and a
  controlled shutdown sequence so the Raspberry Pi can shut down safely before
  power is removed
* Publishing complete instructions for mounting and connecting the ultra-wide
  display in the vehicle

ECU write operations and ABS service procedures are safety-critical features.
They will require validated protocol support, clear user confirmation, appropriate
interlocks, and testing on compatible hardware before being enabled for general
use.

## Important

* This is not generic OBD-II. The TD5 uses its own diagnostic login and command
  flow.
* K+DCAN cables vary. OBD pin 7 must be electrically connected to K-line, and the
  USB chipset must expose a serial port.
* Never run multiple diagnostic applications against the same ECU connection.
* Disconnect the K+DCAN cable before using workshop diagnostic equipment.
* Do not use the displayed values as the sole basis for safety-critical decisions
  while driving.
* Keep Wi-Fi names, passwords, SSH keys, diagnostic profiles, and vehicle logs out
  of Git. `.env.example` documents the optional Wi-Fi variables.

## LIVI source dependency

`third_party/LIVI` is an upstream Git repository. Publish it as a pinned
submodule/fork and retain the Td5 changes as a patch or a commit in that fork;
do not publish an uncommitted nested working tree. This repository includes
`patches/livi-td5-gauge.patch`, generated against the revision recorded in
`third_party/LIVI.UPSTREAM_REVISION`. After cloning, initialize the submodule and
run `scripts/apply-livi-patch.sh` before building LIVI.

## Projects this work builds upon

* [BinOwl TD5 Gauge](https://github.com/k0sci3j/BinOwl_Td5Gauge) provides the
  foundation for the TD5 diagnostic protocol, login sequence, and command
  structure.
* [LIVI – Linux In-Vehicle Infotainment](https://github.com/f-io/LIVI) provides
  the Raspberry Pi infotainment and CarPlay platform into which the TD5 dashboard
  is integrated.

Many thanks to these projects and their contributors.

## License

This project contains a derivative port of the TD5 diagnostic command flow from
the BinOwl TD5 Gauge firmware and is distributed under
[GPL-3.0-or-later](COPYING). Refer to the upstream projects for their respective
license terms and attribution requirements.
