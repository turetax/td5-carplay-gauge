import unittest

from td5gauge import Td5Protocol


class ScriptedTransport:
    """Minimal half-duplex ECU stand-in: echoes TX then returns one reply."""

    def __init__(self, reply: bytes):
        self.reply = bytearray(reply)
        self.writes = bytearray()
        self.reset_count = 0

    def close(self):
        return None

    def fast_init(self, _mode):
        return None

    def reset_input(self):
        self.reset_count += 1

    def write_byte(self, value):
        self.writes.append(value)

    def read(self, count):
        output, self.reply = self.reply[:count], self.reply[count:]
        return bytes(output)


class ProtocolFrameTests(unittest.TestCase):
    def test_fixed_length_request_accepts_echo_and_valid_reply(self):
        request = bytes((0x02, 0x21, 0x09))
        frame = request + bytes((Td5Protocol.checksum(request),))
        payload = bytes((0x05, 0x61, 0x09, 0x03, 0x84))
        response = payload + bytes((Td5Protocol.checksum(payload),))
        transport = ScriptedTransport(frame + response)

        protocol = Td5Protocol("fake", transport=transport)
        self.assertEqual(protocol.transact("rpm"), response)
        self.assertEqual(bytes(transport.writes), frame)
        self.assertEqual(transport.reset_count, 1)

    def test_bad_checksum_is_rejected_without_decoding(self):
        request = bytes((0x02, 0x21, 0x09))
        frame = request + bytes((Td5Protocol.checksum(request),))
        transport = ScriptedTransport(frame + bytes((0x05, 0x61, 0x09, 0x03, 0x84, 0x00)))

        protocol = Td5Protocol("fake", transport=transport)
        with self.assertRaisesRegex(RuntimeError, "ogiltigt svar"):
            protocol.transact("rpm")
