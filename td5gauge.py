#!/usr/bin/env python3
"""Read-only TD5 K-line gateway for LIVI and a raw K+DCAN serial adapter."""

from __future__ import annotations

import argparse
import csv
import json
import math
import threading
import time
from collections import deque
from datetime import datetime
from urllib.parse import urlsplit
from dataclasses import asdict, dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    import serial
    from serial.tools import list_ports
except ImportError:  # Helpful error when launched before installation.
    serial = None
    list_ports = None


BAUDRATE = 10_400
LOG_RETENTION_DAYS = 7
LOG_MAX_BYTES = 25 * 1024 * 1024
PROFILE_RETENTION_COUNT = 10
CRITICAL_ALERT_LATCH_SECONDS = 8
LIVE_FIELDS = (
    "rpm", "speed_kmh", "voltage_v", "coolant_c", "air_c", "fuel_c",
    "map_kpa", "aap_kpa", "maf_kg_h", "wastegate_percent", "throttle_1",
    "injector_balance",
)


@dataclass
class GaugeData:
    status: str = "Inte ansluten"
    detail: str = "Väntar på K-line-adapter"
    updated_at: float = 0.0
    rpm: int | None = None
    speed_kmh: int | None = None
    voltage_v: float | None = None
    coolant_c: float | None = None
    air_c: float | None = None
    fuel_c: float | None = None
    map_kpa: float | None = None
    aap_kpa: float | None = None
    maf_kg_h: float | None = None
    wastegate_percent: float | None = None
    throttle_1: float | None = None
    injector_balance: list[float] | None = None


class Td5Protocol:
    """Td5 K-line protocol ported from BinOwl's published GPL-3.0 firmware."""

    # name: (request bytes, response byte count, ECU response delay in milliseconds)
    COMMANDS = {
        "init": (bytes((0x81, 0x13, 0xF7, 0x81)), 5, 35),
        "diagnostic": (bytes((0x02, 0x10, 0xA0)), 3, 35),
        "seed": (bytes((0x02, 0x27, 0x01)), 6, 50),
        "rpm": (bytes((0x02, 0x21, 0x09)), 6, 50),
        "voltage": (bytes((0x02, 0x21, 0x10)), 8, 50),
        "temps": (bytes((0x02, 0x21, 0x1A)), 20, 100),
        "speed": (bytes((0x02, 0x21, 0x0D)), 5, 50),
        "pressure": (bytes((0x02, 0x21, 0x23)), 8, 50),
        "maf_map": (bytes((0x02, 0x21, 0x1C)), 12, 50),
        "injectors": (bytes((0x02, 0x21, 0x40)), 14, 50),
        "throttle_msb": (bytes((0x02, 0x21, 0x1B)), 12, 50),
        "throttle_nnn": (bytes((0x02, 0x21, 0x1B)), 14, 50),
        "wastegate": (bytes((0x02, 0x21, 0x38)), 6, 50),
        "keep_alive": (bytes((0x02, 0x3E, 0x01)), 3, 30),
    }

    def __init__(self, port: str):
        if serial is None:
            raise RuntimeError("pyserial saknas. Kör: python3 -m pip install -r requirements.txt")
        # timeout is deliberately short: each Td5 transaction has a known reply length.
        self.serial = serial.Serial(port, BAUDRATE, timeout=0.06, write_timeout=1)
        self.nnn = False

    def close(self) -> None:
        self.serial.close()

    def fast_init(self) -> None:
        """Drive K-line low/high: 25 ms each, as required by Td5 fast init.

        This only works if the adapter's TX pin is physically connected to K-line.
        Some K+DCAN cables do not satisfy that requirement.
        """
        self.serial.close()
        # Some serial drivers configure custom baud rates on reopen. The break is used as
        # the reliable way to drive a USB serial TX line low.
        self.serial.open()
        self.serial.break_condition = True
        time.sleep(0.0255)
        self.serial.break_condition = False
        time.sleep(0.0255)
        self.serial.reset_input_buffer()

    @staticmethod
    def checksum(payload: bytes) -> int:
        return sum(payload) & 0xFF

    @staticmethod
    def keygen(seed_response: bytes) -> int:
        q = seed_response[4] | (seed_response[3] << 8)
        cycles = (((q >> 12) & 0x8) | ((q >> 5) & 0x4) | ((q >> 3) & 0x2) | (q & 0x1)) + 1
        for _ in range(cycles):
            bit = ((q >> 1) ^ (q >> 2) ^ (q >> 8) ^ (q >> 9)) & 1
            shifted = (q >> 1) | (bit << 15)
            q = shifted & ~1 if ((q >> 3) & 1 and (q >> 13) & 1) else shifted | 1
        return q

    def transact(self, name: str, request_override: bytes | None = None) -> bytes:
        request, response_length, response_delay_ms = self.COMMANDS[name]
        if request_override is not None:
            request = request_override
        frame = request + bytes((self.checksum(request),))
        self.serial.reset_input_buffer()
        for byte in frame:
            self.serial.write(bytes((byte,)))
            self.serial.flush()
            time.sleep(0.003)  # Td5 requires inter-byte pacing.
        time.sleep(response_delay_ms / 1000)

        # USB K+DCAN adapters commonly echo TX. Some do not, so preserve both cases.
        deadline = time.monotonic() + 0.15
        raw = bytearray()
        expected_total = len(frame) + response_length
        while time.monotonic() < deadline and len(raw) < expected_total:
            received = self.serial.read(expected_total - len(raw))
            if received:
                raw.extend(received)
            else:
                time.sleep(0.002)
        response = bytes(raw[len(frame):]) if raw.startswith(frame) else bytes(raw)
        # Td5 key-access acknowledgement is a special four-byte positive response
        # (04 67 01 00) on NNN ECUs; unlike the measurement frames it does not carry
        # the additive checksum used by the rest of this protocol.
        valid_key_ack = name == "key" and response == bytes((0x04, 0x67, 0x01, 0x00))
        if len(response) != response_length or not response or (not valid_key_ack and self.checksum(response[:-1]) != response[-1]):
            raise RuntimeError(f"{name}: ogiltigt svar ({raw.hex(' ') or 'inget svar'})")
        return response

    def transact_variable(self, name: str, request: bytes, response_delay_ms: int = 100) -> bytes:
        """Read a complete ECU-framed response whose payload length is supplied by the ECU.

        This is deliberately limited to read-only commands.  The first byte of a
        KWP response declares its data length, so an incomplete or checksum-bad
        response is rejected rather than being partially decoded.
        """
        frame = request + bytes((self.checksum(request),))
        self.serial.reset_input_buffer()
        for byte in frame:
            self.serial.write(bytes((byte,)))
            self.serial.flush()
            time.sleep(0.003)
        time.sleep(response_delay_ms / 1000)
        raw = bytearray()
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            received = self.serial.read(64)
            if received:
                raw.extend(received)
            else:
                time.sleep(0.002)
            starts = (len(frame),) if raw.startswith(frame) else (0,)
            for start in starts:
                if len(raw) <= start:
                    continue
                length = raw[start] & 0x7F
                has_addresses = bool(raw[start] & 0x80)
                if not 1 <= length <= 48:
                    continue
                total = 1 + (2 if has_addresses else 0) + length + 1
                if len(raw) < start + total:
                    continue
                response = bytes(raw[start:start + total])
                if self.checksum(response[:-1]) == response[-1]:
                    return response
                raise RuntimeError(f"{name}: kontrollsumma fel ({raw.hex(' ')})")
        raise RuntimeError(f"{name}: inget komplett svar ({raw.hex(' ') or 'inget svar'})")

    def read_faults(self) -> tuple[list[dict], str]:
        """Read Td5 local identifier 0x20.  This request never clears or changes ECU data."""
        response = self.transact_variable("felkoder", bytes((0x02, 0x21, 0x20)))
        if len(response) < 4 or response[1:3] != bytes((0x61, 0x20)):
            raise RuntimeError(f"felkoder: oväntat svar ({response.hex(' ')})")
        payload = response[3:-1]
        if len(payload) % 2:
            raise RuntimeError(f"felkoder: ogiltig datalängd ({response.hex(' ')})")
        output_names = ("EGR-spjäll", "Wastegate", "EGR-vakuum", "Temperaturmätare", "Gaspedal 1", "Gaspedal 2", "MAF-krets", "MAP-krets")
        sensor_names = ("Insugslufttemperatur", "Bränsletemperatur", "Kylvätsketemperatur", "Batterispänning", "Referensspänning", "Omgivningstemperatur", "Gaspedal-matning", "Atmosfärtryck")
        faults: list[dict] = []
        for index, counter in zip(payload[::2], payload[1::2]):
            if index == 0 and counter == 0:
                continue
            group, sub = index // 8 + 1, index % 8 + 1
            if group in (1, 3, 5):
                description = output_names[sub - 1]
            elif group in (2, 4, 6):
                description = sensor_names[sub - 1]
            else:
                description = "Okänd Td5-funktionsgrupp"
            state = "AKTIV" if group in (5, 6) else "LAGRAD"
            faults.append({"code": f"{group}-{sub}", "state": state, "description": description, "counter": counter})
        return faults, payload.hex(" ").upper()

    def connect(self) -> None:
        self.fast_init()
        self.transact("init")
        self.transact("diagnostic")
        seed = self.transact("seed")
        key = self.keygen(seed)
        key_request = bytes((0x04, 0x27, 0x02, key >> 8, key & 0xFF))
        # The key response is 4 bytes long, but request differs from the stored commands.
        self.COMMANDS["key"] = (key_request, 4, 50)
        self.transact("key")

    @staticmethod
    def u16(response: bytes, offset: int) -> int:
        return response[offset] | (response[offset - 1] << 8)

    @staticmethod
    def s16(response: bytes, offset: int) -> int:
        value = Td5Protocol.u16(response, offset)
        return value - 65536 if value >= 32768 else value

    def poll(self, data: GaugeData) -> None:
        rpm = self.transact("rpm")
        data.rpm = self.u16(rpm, 4)
        voltage = self.transact("voltage")
        data.voltage_v = ((voltage[6] | (voltage[5] << 8) | voltage[7]) / 1000)
        temps = self.transact("temps")
        data.coolant_c = self.s16(temps, 4) / 10 - 273
        data.air_c = self.s16(temps, 8) / 10 - 273
        data.fuel_c = self.s16(temps, 16) / 10 - 273
        speed = self.transact("speed")
        data.speed_kmh = speed[3]
        pressure = self.transact("pressure")
        data.map_kpa = self.u16(pressure, 4) / 100
        data.aap_kpa = self.u16(pressure, 6) / 100
        maf_map = self.transact("maf_map")
        data.maf_kg_h = self.u16(maf_map, 8) / 10
        injectors = self.transact("injectors")
        data.injector_balance = [self.s16(injectors, pos) for pos in (4, 6, 8, 10, 12)]
        throttle_name = "throttle_nnn" if self.nnn else "throttle_msb"
        try:
            throttle = self.transact(throttle_name)
        except RuntimeError:
            self.nnn = not self.nnn
            throttle = self.transact("throttle_nnn" if self.nnn else "throttle_msb")
        data.throttle_1 = self.u16(throttle, 4) / 1000
        wastegate = self.transact("wastegate")
        data.wastegate_percent = self.u16(wastegate, 4) / 1000
        self.transact("keep_alive")


class Service:
    def __init__(self, port: str | None, simulate: bool):
        self.data = GaugeData(status="Simulerar" if simulate else "Startar")
        self.lock = threading.Lock()
        self.port, self.simulate = port, simulate
        self.started_at = time.time()
        self.history: deque[dict] = deque(maxlen=720)  # Twelve minutes at one sample/second.
        self.last_recorded_at = 0.0
        self.peaks = {"coolant_c": None, "boost_kpa": None, "rpm": None}
        self.ranges = {"voltage_v": [None, None]}
        self.alert_history: deque[dict] = deque(maxlen=20)
        self.active_alerts: dict[str, dict] = {}
        self.critical_latch_until: dict[str, float] = {}
        self.dtcs: list[dict] = []
        self.dtc_raw = ""
        self.dtc_updated_at = 0.0
        self.dtc_error = "Inte läst ännu"
        # DTC reads are read-only, but they still occupy the single K-line.
        # Keep them user-requested after the initial connection check instead of
        # injecting a diagnostic frame into the live polling loop every 30 seconds.
        self.dtc_requested = False
        self.log_dir = Path.home() / ".local" / "share" / "td5gauge" / "logs"
        self.profile_dir = self.log_dir / "profiles"
        self.last_profile_path = ""
        self.last_log_prune_at = 0.0

    @staticmethod
    def _number(value: object) -> float | None:
        return float(value) if isinstance(value, (float, int)) else None

    def _record_sample(self) -> None:
        """Keep a compact in-memory history and a local CSV only for real ECU data."""
        with self.lock:
            payload = asdict(self.data)
        timestamp = payload["updated_at"]
        with self.lock:
            if not timestamp or timestamp - self.last_recorded_at < 1:
                return
            self.last_recorded_at = timestamp
        payload["boost_kpa"] = (
            payload["map_kpa"] - payload["aap_kpa"]
            if payload["map_kpa"] is not None and payload["aap_kpa"] is not None else None
        )
        payload["engine_on"] = bool((payload["rpm"] or 0) >= 400)
        sample = {key: payload.get(key) for key in (
            "updated_at", "rpm", "speed_kmh", "voltage_v", "coolant_c", "air_c", "fuel_c",
            "map_kpa", "aap_kpa", "boost_kpa", "maf_kg_h", "wastegate_percent", "throttle_1", "injector_balance", "engine_on",
        )}
        with self.lock:
            self.history.append(sample)
            self._evaluate_alerts(sample)
            for key in self.peaks:
                value = self._number(sample[key])
                if value is not None:
                    self.peaks[key] = value if self.peaks[key] is None else max(self.peaks[key], value)
            voltage = self._number(sample["voltage_v"])
            if voltage is not None:
                low, high = self.ranges["voltage_v"]
                self.ranges["voltage_v"] = [voltage if low is None else min(low, voltage), voltage if high is None else max(high, voltage)]
        if not self.simulate:
            self._append_csv(sample)

    def _evaluate_alerts(self, sample: dict) -> None:
        """Record warning intervals; this is read-only and never modifies the ECU."""
        current: dict[str, dict] = {}

        def rising_level(name: str, value: float | None, thresholds: list[tuple[str, float]], release: float) -> str | None:
            """Return an ascending alert level with hysteresis around its threshold."""
            if value is None:
                return None
            rank = {level: index for index, (level, _) in enumerate(thresholds, 1)}
            raw = next((level for level, threshold in reversed(thresholds) if value >= threshold), None)
            previous = self.active_alerts.get(name, {}).get("level")
            held = None
            if previous in rank:
                previous_threshold = dict(thresholds)[previous]
                if value >= previous_threshold - release:
                    held = previous
            if raw is None:
                return held
            return raw if held is None or rank[raw] >= rank[held] else held

        def add(name: str, value: float | None, level: str, unit: str) -> None:
            if value is not None:
                current[name] = {"name": name, "value": round(value, 1), "level": level, "unit": unit}

        coolant, voltage = self._number(sample["coolant_c"]), self._number(sample["voltage_v"])
        fuel, air, map_kpa = self._number(sample["fuel_c"]), self._number(sample["air_c"]), self._number(sample["map_kpa"])
        coolant_level = rising_level("Coolant", coolant, [("warn", 98), ("danger", 103), ("critical", 105)], 2)
        if coolant_level:
            add("Coolant", coolant, coolant_level, "°C")
        if sample["engine_on"] and voltage is not None:
            previous = self.active_alerts.get("Alternator", {}).get("level")
            low_warn = voltage < 13.2 or (previous == "warn" and voltage < 13.4)
            low_danger = voltage < 13.0 or (previous == "danger" and voltage < 13.2)
            high_danger = voltage > 15.0 or (previous == "danger" and voltage > 14.8)
            if low_warn or high_danger:
                add("Alternator", voltage, "danger" if low_danger or high_danger else "warn", "V")
        fuel_level = rising_level("Fuel temp", fuel, [("warn", 75), ("danger", 85)], 2)
        if fuel_level:
            add("Fuel temp", fuel, fuel_level, "°C")
        air_level = rising_level("Inlet air", air, [("warn", 65), ("danger", 80)], 2)
        if air_level:
            add("Inlet air", air, air_level, "°C")
        map_level = rising_level("MAP", map_kpa, [("warn", 230), ("danger", 240)], 5)
        if map_level:
            add("MAP", map_kpa, map_level, "kPa")
        now = sample["updated_at"]
        for name, previous in self.active_alerts.items():
            if previous.get("level") == "critical" and now < self.critical_latch_until.get(name, 0):
                replacement = current.get(name, {})
                if replacement.get("level") != "critical":
                    held = dict(previous)
                    held["latched"] = True
                    if replacement.get("value") is not None:
                        held["value"] = replacement["value"]
                    current[name] = held
        for name, event in list(self.active_alerts.items()):
            if name not in current:
                event["ended_at"] = now
                event["duration_s"] = round(now - event["started_at"])
                self.alert_history.appendleft(event)
        for name, event in current.items():
            previous = self.active_alerts.get(name)
            event["started_at"] = previous["started_at"] if previous else now
            event["duration_s"] = round(now - event["started_at"])
            if event["level"] == "critical" and not event.get("latched"):
                self.critical_latch_until[name] = now + CRITICAL_ALERT_LATCH_SECONDS
        self.active_alerts = current

    def _append_csv(self, sample: dict) -> None:
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            if time.time() - self.last_log_prune_at > 3600:
                self._prune_logs()
                self.last_log_prune_at = time.time()
            path = self.log_dir / f"td5-{datetime.fromtimestamp(sample['updated_at']).strftime('%Y-%m-%d')}.csv"
            is_new = not path.exists()
            with path.open("a", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=sample.keys())
                if is_new:
                    writer.writeheader()
                writer.writerow(sample)
        except OSError:
            # Logging must never stop the live dashboard if storage is unavailable.
            return

    def _prune_logs(self) -> None:
        """Bound dashboard logs so they cannot consume the Pi's storage."""
        cutoff = time.time() - LOG_RETENTION_DAYS * 24 * 60 * 60
        files = sorted(self.log_dir.glob("td5-*.csv"), key=lambda item: item.stat().st_mtime)
        kept: list[Path] = []
        for path in files:
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
                else:
                    kept.append(path)
            except OSError:
                continue
        total = sum(path.stat().st_size for path in kept if path.exists())
        for path in kept:
            if total <= LOG_MAX_BYTES:
                break
            try:
                total -= path.stat().st_size
                path.unlink()
            except OSError:
                continue

    def _save_readonly_profile(self) -> None:
        """Store one compact, non-sensitive diagnostic profile on the SD card.

        This helps validate the installed ECU/cable later without retaining
        security-access seed/key exchanges or any command capable of changing a
        controller.  It is intentionally a report, not a packet trace.
        """
        if self.simulate:
            return
        report = self.snapshot()
        payload = {
            "format": "td5gauge.readonly-profile.v1",
            "captured_at": time.time(),
            "safety": {
                "read_only": True,
                "excluded": [
                    "security seed/key values",
                    "fault-clear commands",
                    "ABS pump/valve commands",
                    "firmware or calibration data",
                ],
            },
            "transport": {
                "serial_port": self.port,
                "baudrate": BAUDRATE,
                "physical_layer": "ISO 9141-2 K-line · OBD pin 7",
                "engine_protocol": "Td5 KWP2000, 10400 baud",
            },
            "engine": {
                "connection": {
                    key: report.get(key)
                    for key in ("status", "detail", "updated_at", "age_s")
                },
                "live_sample": {
                    key: report.get(key)
                    for key in LIVE_FIELDS
                },
                "faults": report["dtc"],
            },
            "abs": report["abs"],
            "limitations": [
                "ABS-controller has not been queried until its read-only protocol is validated.",
                "A saved engine profile cannot be used to infer an ABS bleed command.",
            ],
        }
        try:
            self.profile_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.fromtimestamp(payload["captured_at"]).strftime("%Y%m%d-%H%M%S")
            path = self.profile_dir / f"td5-readonly-{timestamp}.json"
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(path)
            profiles = sorted(self.profile_dir.glob("td5-readonly-*.json"), key=lambda item: item.stat().st_mtime)
            for old_profile in profiles[:-PROFILE_RETENTION_COUNT]:
                old_profile.unlink(missing_ok=True)
            self.last_profile_path = str(path)
        except OSError:
            # Capturing evidence must never interrupt the live display.
            return

    def request_dtc_read(self) -> None:
        """Queue one read-only request for the existing ECU session."""
        with self.lock:
            self.dtc_requested = True

    def abs_snapshot(self) -> dict:
        """Report ABS diagnostic readiness without transmitting to the ABS ECU.

        The 1999 Defender wiring routes both the engine ECU and WABCO D ABS ECU
        to OBD pin 7.  The exact WABCO address and read identifiers have not yet
        been validated for this adapter, so this deliberately reports readiness
        rather than guessing a request frame on a brake controller.
        """
        with self.lock:
            engine_status = self.data.status
        connected = engine_status == "Ansluten"
        return {
            "expected_controller": "WABCO D ABS · Defender 1999–2003",
            "transport": "Delad K-line · OBD pin 7",
            "engine_kline_ready": connected,
            "state": "Redo för verifierad ABS-profil" if connected else "Väntar på K-line och tändning",
            "detail": (
                "Motor-ECU svarar på K-line. ABS-protokollet är ännu inte validerat."
                if connected else "Anslut K-line-adaptern och slå på tändningen."
            ),
            "read_only": True,
        }

    def _read_dtcs(self, connection: Td5Protocol) -> None:
        try:
            codes, raw = connection.read_faults()
            with self.lock:
                self.dtcs, self.dtc_raw = codes, raw
                self.dtc_updated_at = time.time()
                self.dtc_error = ""
                self.dtc_requested = False
        except Exception as exc:
            with self.lock:
                self.dtc_error = str(exc)
                self.dtc_requested = False

    def snapshot(self) -> dict:
        with self.lock:
            result = asdict(self.data)
            peaks = dict(self.peaks)
            voltage_range = list(self.ranges["voltage_v"])
            active_alerts = list(self.active_alerts.values())
            alert_history = list(self.alert_history)
            dtc = {"codes": list(self.dtcs), "raw": self.dtc_raw, "updated_at": self.dtc_updated_at, "error": self.dtc_error, "pending": self.dtc_requested}
        result["age_s"] = round(time.time() - result["updated_at"], 1) if result["updated_at"] else None
        result["session"] = {
            "started_at": self.started_at,
            "duration_s": round(time.time() - self.started_at),
            "peaks": peaks,
            "voltage_range": voltage_range,
            "log_active": not self.simulate,
            "alerts": {"active": active_alerts, "history": alert_history},
        }
        result["dtc"] = dtc
        result["abs"] = self.abs_snapshot()
        result["profile"] = {
            "last_saved": self.last_profile_path or None,
            "retention_count": PROFILE_RETENTION_COUNT,
            "read_only": True,
        }
        return result

    def history_snapshot(self) -> dict:
        with self.lock:
            samples = list(self.history)
        return {"samples": samples, "max_samples": self.history.maxlen}

    def run(self) -> None:
        if self.simulate:
            self._simulate()
            return
        while True:
            connection = None
            try:
                with self.lock:
                    self.data.status, self.data.detail = "Ansluter", f"Öppnar {self.port}"
                connection = Td5Protocol(self.port)
                connection.connect()
                with self.lock:
                    self.data.status, self.data.detail = "Ansluten", "Td5 ECU svarar"
                self._read_dtcs(connection)
                profile_saved = False
                while True:
                    # Keep serial I/O outside the lock, then publish the completed
                    # sample atomically so the web UI cannot get mixed PID samples.
                    sample = GaugeData()
                    connection.poll(sample)
                    with self.lock:
                        for field in LIVE_FIELDS:
                            setattr(self.data, field, getattr(sample, field))
                        self.data.updated_at = time.time()
                        read_requested = self.dtc_requested
                    if read_requested:
                        self._read_dtcs(connection)
                    self._record_sample()
                    if not profile_saved:
                        self._save_readonly_profile()
                        profile_saved = True
            except Exception as exc:
                with self.lock:
                    self.data.status, self.data.detail = "Frånkopplad", str(exc)
                time.sleep(3)
            finally:
                if connection:
                    try:
                        connection.close()
                    except Exception:
                        pass

    def _simulate(self) -> None:
        start = time.monotonic()
        while True:
            t = time.monotonic() - start
            with self.lock:
                self.data.status, self.data.detail = "Simulerar", "Ingen kabel används"
                self.data.rpm = round(850 + 250 * (1 + math.sin(t / 2)))
                self.data.speed_kmh = max(0, round(30 + 30 * math.sin(t / 9)))
                self.data.voltage_v = round(14.1 + .1 * math.sin(t), 2)
                self.data.coolant_c, self.data.air_c, self.data.fuel_c = 88.0, 32.0, 56.0
                self.data.map_kpa, self.data.aap_kpa = 115.0, 99.5
                self.data.maf_kg_h, self.data.wastegate_percent, self.data.throttle_1 = 32.0, 41.0, 1.8
                self.data.injector_balance = [-4, 1, 2, -1, 3]
                self.data.updated_at = time.time()
                self.dtcs, self.dtc_raw = [], ""
                self.dtc_updated_at, self.dtc_error, self.dtc_requested = time.time(), "", False
            self._record_sample()
            time.sleep(.25)


def handler_factory(service: Service) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            return

        def do_GET(self) -> None:
            request_path = urlsplit(self.path).path
            if request_path == "/api/live":
                body = json.dumps(service.snapshot()).encode()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                # LIVI runs its renderer from its own app:// origin. This endpoint
                # is read-only live telemetry; allow that local dashboard to poll
                # it without granting browser access to any write operation.
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if request_path == "/api/history":
                body = json.dumps(service.history_snapshot()).encode()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        def do_POST(self) -> None:
            request_path = urlsplit(self.path).path
            if request_path == "/api/abs/identify":
                if self.client_address[0] not in {"127.0.0.1", "::1"}:
                    self.send_error(HTTPStatus.FORBIDDEN)
                    return
                # Intentionally no ABS frame is transmitted here. This confirms
                # transport readiness before a validated, read-only ABS profile is
                # introduced; actuation remains unavailable.
                body = json.dumps(service.abs_snapshot()).encode()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if request_path == "/api/dtc/read":
                # POST prevents browser prefetching, caches and link scanners from
                # accidentally queuing a diagnostic action. This only requests a
                # read-only ECU query; it never clears faults or writes settings.
                if self.client_address[0] not in {"127.0.0.1", "::1"}:
                    self.send_error(HTTPStatus.FORBIDDEN)
                    return
                service.request_dtc_read()
                body = b'{"accepted":true,"mode":"read-only"}'
                self.send_response(HTTPStatus.ACCEPTED)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                # LIVI's app:// renderer is local but has a different origin.
                # Source-address validation above is the access boundary.
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(HTTPStatus.NOT_FOUND)
    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="Serial port, for example /dev/ttyUSB0")
    parser.add_argument("--simulate", action="store_true", help="Kör dashboard utan bil/kabel")
    parser.add_argument("--list-ports", action="store_true", help="Lista seriella USB-portar och avsluta")
    parser.add_argument("--web-port", type=int, default=8080, help="Webbport (standard: 8080)")
    parser.add_argument("--bind", default="127.0.0.1", help="Lyssningsadress (standard: endast denna dator/Pi)")
    args = parser.parse_args()
    if args.list_ports:
        if list_ports is None:
            raise SystemExit("Installera först beroendet: python3 -m pip install -r requirements.txt")
        for item in list_ports.comports():
            print(f"{item.device}\t{item.description}")
        return
    if not args.simulate and not args.port:
        parser.error("specify --port /dev/ttyUSB0 or use --simulate")

    service = Service(args.port, args.simulate)
    threading.Thread(target=service.run, name="td5-poll", daemon=True).start()
    server = ThreadingHTTPServer((args.bind, args.web_port), handler_factory(service))
    print(f"TD5 API listening on http://{args.bind}:{args.web_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAvslutar.")


if __name__ == "__main__":
    main()
