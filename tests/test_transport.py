import unittest
from unittest.mock import patch

from td5_transport import SerialTransport


class FakeSerial:
    def __init__(self, *_args, **_kwargs):
        self.break_condition = False
        self.calls = []

    def close(self):
        self.calls.append("close")

    def open(self):
        self.calls.append("open")

    def reset_input_buffer(self):
        self.calls.append("reset")

    def send_break(self, duration):
        self.calls.append(("send_break", duration))

    def write(self, value):
        self.calls.append(("write", value))

    def flush(self):
        self.calls.append("flush")

    def read(self, _count):
        return b""


class TransportTests(unittest.TestCase):
    def test_break_condition_is_default_compatible_strategy(self):
        transport = SerialTransport("fake", 10400, serial_factory=FakeSerial)
        with patch("td5_transport.time.sleep"):
            transport.fast_init()
        self.assertEqual(transport.serial.calls, ["close", "open", "reset"])
        self.assertFalse(transport.serial.break_condition)

    def test_send_break_is_explicit_alternative(self):
        transport = SerialTransport("fake", 10400, serial_factory=FakeSerial)
        with patch("td5_transport.time.sleep"):
            transport.fast_init("send-break")
        self.assertIn(("send_break", 0.025), transport.serial.calls)

    def test_unknown_fast_init_mode_is_rejected(self):
        transport = SerialTransport("fake", 10400, serial_factory=FakeSerial)
        with self.assertRaises(ValueError):
            transport.fast_init("unsafe")
