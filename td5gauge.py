#!/usr/bin/env python3
"""Read-only TD5 K-line gateway for LIVI and a raw K+DCAN serial adapter."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
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
    from serial.tools import list_ports
except ImportError:  # Helpful error when launched before installation.
    list_ports = None

from td5_signals import SIGNALS
from td5_transport import SerialTransport


BAUDRATE = 10_400
LOG_RETENTION_DAYS = 7
LOG_MAX_BYTES = 25 * 1024 * 1024
PROFILE_RETENTION_COUNT = 10
CRITICAL_ALERT_LATCH_SECONDS = 8
FUEL_DENSITY_KG_PER_L = 0.832
FUEL_WINDOW_TARGET_KM = 100.0
FUEL_WINDOW_RETAIN_KM = 120.0
LIVE_FIELDS = (
    "rpm", "speed_kmh", "voltage_v", "coolant_c", "air_c", "fuel_c",
    "map_kpa", "aap_kpa", "maf_kg_h", "wastegate_percent", "throttle_1",
    "throttle_2", "throttle_3", "throttle_supply_v", "driver_fuel_demand_mg",
    "fuel_injected_mg", "idle_fuel_demand_mg", "injector_balance",
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
    throttle_2: float | None = None
    throttle_3: float | None = None
    throttle_supply_v: float | None = None
    driver_fuel_demand_mg: float | None = None
    fuel_injected_mg: float | None = None
    idle_fuel_demand_mg: float | None = None
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
        "fuel": (bytes((0x02, 0x21, 0x1D)), 22, 100),
        "pressure": (bytes((0x02, 0x21, 0x23)), 8, 50),
        "maf_map": (bytes((0x02, 0x21, 0x1C)), 12, 50),
        "injectors": (bytes((0x02, 0x21, 0x40)), 14, 50),
        "throttle_msb": (bytes((0x02, 0x21, 0x1B)), 12, 50),
        "throttle_nnn": (bytes((0x02, 0x21, 0x1B)), 14, 50),
        "wastegate": (bytes((0x02, 0x21, 0x38)), 6, 50),
        "keep_alive": (bytes((0x02, 0x3E, 0x01)), 3, 30),
    }

    def __init__(
        self,
        port: str,
        fast_init_mode: str = "break-condition",
        transport: SerialTransport | None = None,
    ):
        # timeout is deliberately short: each Td5 transaction has a known reply length.
        self.transport = transport or SerialTransport(port, BAUDRATE)
        self.fast_init_mode = fast_init_mode
        self.nnn = False

    def close(self) -> None:
        self.transport.close()

    def fast_init(self) -> None:
        """Drive K-line low/high: 25 ms each, as required by Td5 fast init.

        This only works if the adapter's TX pin is physically connected to K-line.
        Some K+DCAN cables do not satisfy that requirement.
        """
        self.transport.fast_init(self.fast_init_mode)

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
        self.transport.reset_input()
        for byte in frame:
            self.transport.write_byte(byte)
            time.sleep(0.003)  # Td5 requires inter-byte pacing.
        time.sleep(response_delay_ms / 1000)

        # USB K+DCAN adapters commonly echo TX. Some do not, so preserve both cases.
        deadline = time.monotonic() + 0.15
        raw = bytearray()
        expected_total = len(frame) + response_length
        while time.monotonic() < deadline and len(raw) < expected_total:
            received = self.transport.read(expected_total - len(raw))
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
        self.transport.reset_input()
        for byte in frame:
            self.transport.write_byte(byte)
            time.sleep(0.003)
        time.sleep(response_delay_ms / 1000)
        raw = bytearray()
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            received = self.transport.read(64)
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

    def read_feature_configuration(self) -> str:
        """Read the Td5 0x3D feature/configuration block without changing settings.

        `21 3D` is not an established injector-code read. Store its raw bytes as
        ECU feature configuration until each flag has been mapped by differential
        testing. This must never be presented as injector classification data.
        """
        response = self.transact_variable("funktionskonfiguration", bytes((0x02, 0x21, 0x3D)))
        if len(response) < 4 or response[1:3] != bytes((0x61, 0x3D)):
            raise RuntimeError(f"funktionskonfiguration: oväntat svar ({response.hex(' ')})")
        return response[3:-1].hex(" ").upper()

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
        fuel = self.transact("fuel")
        data.driver_fuel_demand_mg = self.s16(fuel, 4) / 100
        data.fuel_injected_mg = self.s16(fuel, 10) / 100
        data.idle_fuel_demand_mg = self.s16(fuel, 18) / 100
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
        data.throttle_2 = self.u16(throttle, 6) / 1000
        if self.nnn and len(throttle) >= 12:
            data.throttle_3 = self.u16(throttle, 8) / 1000
            data.throttle_supply_v = self.u16(throttle, 12) / 1000
        else:
            data.throttle_3 = None
            data.throttle_supply_v = None
        wastegate = self.transact("wastegate")
        data.wastegate_percent = self.u16(wastegate, 4) / 1000
        self.transact("keep_alive")


class Service:
    def __init__(self, port: str | None, simulate: bool, fast_init_mode: str = "break-condition"):
        self.data = GaugeData(status="Simulerar" if simulate else "Startar")
        self.lock = threading.Lock()
        self.port, self.simulate, self.fast_init_mode = port, simulate, fast_init_mode
        self.started_at = time.time()
        self.history: deque[dict] = deque(maxlen=720)  # Twelve minutes at one sample/second.
        self.last_recorded_at = 0.0
        self.fuel_window: deque[dict[str, float]] = deque()
        self.fuel_bucket = {"distance_km": 0.0, "fuel_l": 0.0}
        self.last_fuel_sample: tuple[float, float, float] | None = None
        self.fuel_window_path = Path.home() / ".local" / "share" / "td5gauge" / "fuel-window.json"
        self.last_fuel_window_save_at = 0.0
        self._load_fuel_window()
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
        self.feature_config_raw = ""
        self.feature_config_updated_at = 0.0
        self.feature_config_error = "Inte läst ännu"
        self.feature_config_requested = False
        self.log_dir = Path.home() / ".local" / "share" / "td5gauge" / "logs"
        self.profile_dir = self.log_dir / "profiles"
        self.last_profile_path = ""
        self.last_log_prune_at = 0.0

    @staticmethod
    def _number(value: object) -> float | None:
        return float(value) if isinstance(value, (float, int)) else None

    @staticmethod
    def _connection_error_text(exc: Exception) -> str:
        """Translate common serial failures into a useful, non-technical UI text."""
        detail = str(exc)
        lower = detail.lower()
        if isinstance(exc, FileNotFoundError) or "could not open port" in lower:
            return "K+DCAN-adaptern hittades inte. Kontrollera USB-kabeln och försök igen."
        if isinstance(exc, PermissionError) or "permission denied" in lower:
            return "Pi:n saknar behörighet till K+DCAN-adaptern. Lägg användaren i gruppen dialout."
        if "ogiltigt svar" in lower or "kontrollsumma fel" in lower:
            return "ECU-svaret kunde inte tolkas. Kontrollera adapter, K-line på pin 7 och tändning."
        if "inget komplett svar" in lower or "inget svar" in lower:
            return "ECU:n svarar inte ännu. Kontrollera tändning i läge 2 och K-line-adaptern."
        return detail

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
            "map_kpa", "aap_kpa", "boost_kpa", "maf_kg_h", "wastegate_percent", "throttle_1", "throttle_2", "throttle_3", "throttle_supply_v",
            "driver_fuel_demand_mg", "fuel_injected_mg", "idle_fuel_demand_mg", "injector_balance", "engine_on",
        )}
        self._update_fuel_window(sample)
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

    def _load_fuel_window(self) -> None:
        """Restore only compact distance/fuel buckets; never retain raw ECU frames."""
        try:
            payload = json.loads(self.fuel_window_path.read_text(encoding="utf-8"))
            for bucket in payload.get("buckets", []):
                distance = float(bucket["distance_km"])
                fuel = float(bucket["fuel_l"])
                if 0 < distance <= 1 and 0 <= fuel <= 2:
                    self.fuel_window.append({"distance_km": distance, "fuel_l": fuel})
            self._trim_fuel_window()
        except (OSError, ValueError, KeyError, TypeError):
            return

    def _save_fuel_window(self) -> None:
        if self.simulate:
            return
        try:
            self.fuel_window_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"format": "td5gauge.fuel-window.v1", "buckets": list(self.fuel_window)}
            temporary = self.fuel_window_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
            temporary.replace(self.fuel_window_path)
            self.last_fuel_window_save_at = time.time()
        except OSError:
            return

    def _trim_fuel_window(self) -> None:
        total = sum(bucket["distance_km"] for bucket in self.fuel_window)
        while self.fuel_window and total > FUEL_WINDOW_RETAIN_KM:
            total -= self.fuel_window.popleft()["distance_km"]

    @staticmethod
    def _fuel_rate_lph(rpm: float | None, injected_mg: float | None) -> float | None:
        if rpm is None or injected_mg is None or rpm < 300 or injected_mg < 0:
            return None
        # Five cylinders, four-stroke: 2.5 injections per crank revolution.
        return injected_mg * rpm * 2.5 * 60 / 1_000_000 / FUEL_DENSITY_KG_PER_L

    def _update_fuel_window(self, sample: dict) -> None:
        timestamp = self._number(sample.get("updated_at"))
        speed = self._number(sample.get("speed_kmh"))
        rate = self._fuel_rate_lph(self._number(sample.get("rpm")), self._number(sample.get("fuel_injected_mg")))
        if timestamp is None or speed is None or rate is None:
            return
        previous = self.last_fuel_sample
        self.last_fuel_sample = (timestamp, speed, rate)
        if previous is None:
            return
        previous_time, previous_speed, previous_rate = previous
        elapsed = timestamp - previous_time
        if not 0 < elapsed <= 10:
            return
        distance = max(0.0, (previous_speed + speed) * elapsed / 7_200)
        fuel = max(0.0, (previous_rate + rate) * elapsed / 7_200)
        if distance <= 0:
            return
        self.fuel_bucket["distance_km"] += distance
        self.fuel_bucket["fuel_l"] += fuel
        if self.fuel_bucket["distance_km"] >= 0.1:
            self.fuel_window.append(dict(self.fuel_bucket))
            self.fuel_bucket = {"distance_km": 0.0, "fuel_l": 0.0}
            self._trim_fuel_window()
        if time.time() - self.last_fuel_window_save_at >= 30:
            self._save_fuel_window()

    def _rolling_consumption(self) -> dict:
        remaining = FUEL_WINDOW_TARGET_KM
        distance = fuel = 0.0
        for bucket in reversed(self.fuel_window):
            take = min(remaining, bucket["distance_km"])
            if take <= 0:
                continue
            distance += take
            fuel += bucket["fuel_l"] * take / bucket["distance_km"]
            remaining -= take
            if remaining <= 0:
                break
        return {
            "target_km": FUEL_WINDOW_TARGET_KM,
            "distance_km": round(distance, 1),
            "l_per_100km": round(fuel / distance * 100, 1) if distance >= FUEL_WINDOW_TARGET_KM else None,
        }

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
                "feature_configuration": report["feature_configuration"],
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

    def request_feature_config_read(self) -> None:
        """Queue one read-only Td5 feature/configuration block read."""
        with self.lock:
            self.feature_config_requested = True

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

    def _read_feature_configuration(self, connection: Td5Protocol) -> None:
        try:
            raw = connection.read_feature_configuration()
            with self.lock:
                self.feature_config_raw = raw
                self.feature_config_updated_at = time.time()
                self.feature_config_error = ""
                self.feature_config_requested = False
            self._save_readonly_profile()
        except Exception as exc:
            with self.lock:
                self.feature_config_error = str(exc)
                self.feature_config_requested = False

    def snapshot(self) -> dict:
        with self.lock:
            result = asdict(self.data)
            peaks = dict(self.peaks)
            voltage_range = list(self.ranges["voltage_v"])
            active_alerts = list(self.active_alerts.values())
            alert_history = list(self.alert_history)
            dtc = {"codes": list(self.dtcs), "raw": self.dtc_raw, "updated_at": self.dtc_updated_at, "error": self.dtc_error, "pending": self.dtc_requested}
            feature_configuration = {
                "raw": self.feature_config_raw,
                "updated_at": self.feature_config_updated_at,
                "error": self.feature_config_error,
                "pending": self.feature_config_requested,
                "read_only": True,
            }
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
        result["feature_configuration"] = feature_configuration
        consumption = self._rolling_consumption()
        consumption["current_lph"] = self._fuel_rate_lph(
            self._number(result.get("rpm")), self._number(result.get("fuel_injected_mg"))
        )
        result["consumption"] = consumption
        result["abs"] = self.abs_snapshot()
        result["signals"] = SIGNALS
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
                connection = Td5Protocol(self.port, self.fast_init_mode)
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
                        feature_config_read_requested = self.feature_config_requested
                    if read_requested:
                        self._read_dtcs(connection)
                    if feature_config_read_requested:
                        self._read_feature_configuration(connection)
                    self._record_sample()
                    if not profile_saved:
                        self._save_readonly_profile()
                        profile_saved = True
            except Exception as exc:
                with self.lock:
                    self.data.status, self.data.detail = "Frånkopplad", self._connection_error_text(exc)
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
            if request_path == "/api/feature-config/read":
                # This endpoint only queues local identifier 0x3D. The returned
                # feature/config block is read-only; it is not injector coding.
                if self.client_address[0] not in {"127.0.0.1", "::1"}:
                    self.send_error(HTTPStatus.FORBIDDEN)
                    return
                service.request_feature_config_read()
                body = b'{"accepted":true,"mode":"read-only"}'
                self.send_response(HTTPStatus.ACCEPTED)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
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
    parser.add_argument(
        "--fast-init-mode",
        choices=SerialTransport.FAST_INIT_MODES,
        default=os.environ.get("TD5_FAST_INIT_MODE", "break-condition"),
        help="K-line väckningspuls; ändra endast efter test med aktuell kabel",
    )
    args = parser.parse_args()
    if args.list_ports:
        if list_ports is None:
            raise SystemExit("Installera först beroendet: python3 -m pip install -r requirements.txt")
        for item in list_ports.comports():
            print(f"{item.device}\t{item.description}")
        return
    if not args.simulate and not args.port:
        parser.error("specify --port /dev/ttyUSB0 or use --simulate")

    service = Service(args.port, args.simulate, args.fast_init_mode)
    threading.Thread(target=service.run, name="td5-poll", daemon=True).start()
    server = ThreadingHTTPServer((args.bind, args.web_port), handler_factory(service))
    print(f"TD5 API listening on http://{args.bind}:{args.web_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAvslutar.")


if __name__ == "__main__":
    main()
