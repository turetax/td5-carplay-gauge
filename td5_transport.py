"""Small, testable serial transport for the TD5 K-line gateway.

The diagnostic protocol deliberately lives above this layer. Keeping framing and
serial timing here makes the decoder testable without a car and allows
adapter-specific fast-init strategies without changing ECU commands.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

try:
    import serial
except ImportError:  # pragma: no cover - reported only on an uninstalled Pi
    serial = None


class SerialTransport:
    """Own one pyserial device and provide K-line-safe primitives.

    ``break-condition`` is the established default for the current K+DCAN
    setup. ``send-break`` exists for adapters whose Linux driver implements an
    OS-timed break more accurately. It is intentionally opt-in: timing must be
    validated on the actual cable and ECU before changing the default.
    """

    FAST_INIT_MODES = ("break-condition", "send-break")

    def __init__(
        self,
        port: str,
        baudrate: int,
        *,
        timeout: float = 0.06,
        write_timeout: float = 1,
        serial_factory: Callable[..., Any] | None = None,
    ) -> None:
        if serial_factory is None:
            if serial is None:
                raise RuntimeError("pyserial saknas. Kör: python3 -m pip install -r requirements.txt")
            serial_factory = serial.Serial
        self.port = port
        self.serial = serial_factory(port, baudrate, timeout=timeout, write_timeout=write_timeout)

    def close(self) -> None:
        self.serial.close()

    def reset_input(self) -> None:
        self.serial.reset_input_buffer()

    def write_byte(self, value: int) -> None:
        self.serial.write(bytes((value,)))
        self.serial.flush()

    def read(self, count: int) -> bytes:
        return self.serial.read(count)

    def fast_init(self, mode: str = "break-condition") -> None:
        """Generate the TD5 25 ms low / 25 ms high K-line wake-up pulse."""
        if mode not in self.FAST_INIT_MODES:
            supported = ", ".join(self.FAST_INIT_MODES)
            raise ValueError(f"Okänt K-line init-läge: {mode} (välj {supported})")

        self.serial.close()
        self.serial.open()
        if mode == "break-condition":
            self.serial.break_condition = True
            time.sleep(0.0255)
            self.serial.break_condition = False
        else:
            # Some FTDI/Linux combinations generate a more stable pulse this
            # way. It remains explicitly opt-in until verified in the vehicle.
            self.serial.send_break(duration=0.025)
        time.sleep(0.0255)
        self.reset_input()
