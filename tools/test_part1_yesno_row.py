"""Static guards for the live Part 1 yes/no payloads and name overlay."""

import argparse
import os
import unittest
from pathlib import Path


ROW = 0xD835BC
LOAD = 0xD8273C
HOOK = 0xF10000
EXPECTED_ROW = bytes.fromhex('814081408eec814081408e9b89af0000')
EXPECTED_LOAD = bytes.fromhex('8eec8e9b89af8140')  # E2/E4/E6/E8: 예, 아, 뇨, blank
LINK_ROW = bytes.fromhex('81408eec8140814081408e9b89af000000')
COMPACT_LOAD = bytes.fromhex('8eec8e9b89af81a500000000')
CURSOR_HELPER = bytes.fromhex(
    '04480188044a914203d082800348044a8280ffbd'
    'ce600006baa100000e610006bba10000'
)


def check(rom):
    assert rom[ROW:ROW + 16] == EXPECTED_ROW, 'campaign prompt must end in 아뇨'
    assert rom[LOAD:LOAD + 8] == EXPECTED_LOAD, 'name-confirm glyph slots changed'
    for address in (0x942CC4, 0xEFAE0C):
        assert rom[address:address + 17] == LINK_ROW, hex(address)
    for address in (0x942A38, 0xEFAB80):
        assert rom[address:address + 12] == COMPACT_LOAD, hex(address)
    assert rom[0x804FC8:0x804FC8 + 8] == bytes.fromhex('81408eec8e9b89af')
    assert rom[0xA34B6C:0xA34B6C + 16] == bytes.fromhex(
        '81408eec8140814081408e9b89af0000')

    hook = rom[HOOK:HOOK + 0x180]
    # E2/E4/E6/E8 feed x8/x10/x11/x12, with x9 and x13 blank.
    assert hook[0xE8:0xF8] == bytes.fromhex(
        'e2800000e4800000e6800000e8800000')
    assert hook[0x118:0x11C] == bytes.fromhex('2017f008')  # 뇨 top
    assert hook[0x120:0x124] == bytes.fromhex('8018f008')  # 뇨 bottom
    assert hook[0x128:0x12C] == hook[0x130:0x134] == bytes.fromhex('209ff008')
    assert rom[0xF09F20:0xF09F40] == bytes(32)
    assert hook[0x140:0x144] == bytes.fromhex('64010000')  # six cells
    assert hook[0x138:0x140] == bytes.fromhex('d060000610610006')  # top/bottom x8
    assert hook[0xD8:0xDE] == bytes.fromhex('194941817047')  # last overlay write
    assert rom[0xB18D2C:0xB18D30] == bytes.fromhex('f7f368f9'), 'hook branch target changed'
    assert rom[0xB18D40:0xB18D48] == bytes.fromhex('004b18470d00f108'), 'frame hook target changed'
    assert hook[0x154:0x178] == CURSOR_HELPER, 'cursor helper changed'


class Part1YesNoRowTest(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('AW_TEST_ROM'), 'AW_TEST_ROM required')
    def test_live_yesno_payloads(self):
        check(Path(os.environ['AW_TEST_ROM']).read_bytes())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('rom', type=Path)
    args = parser.parse_args()
    check(args.rom.read_bytes())
    print('PASS: live yes/no payloads and name overlay cells')
