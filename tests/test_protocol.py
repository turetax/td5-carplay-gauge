import unittest
from td5gauge import Td5Protocol, WabcoDProtocol


class ProtocolTests(unittest.TestCase):
    def test_checksum(self):
        self.assertEqual(Td5Protocol.checksum(bytes((0x02, 0x21, 0x09))), 0x2C)

    def test_integer_decoding(self):
        response = bytes((0, 0, 0, 0x01, 0xF4, 0))
        self.assertEqual(Td5Protocol.u16(response, 4), 500)
        negative = bytes((0, 0, 0, 0xFF, 0xFE, 0))
        self.assertEqual(Td5Protocol.s16(negative, 4), -2)

    def test_seed_key_is_deterministic(self):
        seed = bytes((0, 0, 0, 0x12, 0x34, 0))
        self.assertEqual(Td5Protocol.keygen(seed), Td5Protocol.keygen(seed))

    def test_wabco_fault_decoder_keeps_unknown_bits_explicit(self):
        block = bytearray(16)
        block[0] = 1
        block[3] = 1 << 4
        faults = WabcoDProtocol.decode_fault_block(bytes(block))
        self.assertEqual(faults[0]["code"], "BIT-01-01")
        self.assertEqual(faults[1]["code"], "020")

if __name__ == "__main__":
    unittest.main()
