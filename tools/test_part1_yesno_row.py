"""Static guards for the live Part 1 yes/no payloads and name overlay."""

import argparse
import os
import struct
import unittest
from pathlib import Path


ROW = 0xD835BC
LOAD = 0xD8273C
HOOK = 0xF10000
WIDE_CURSOR = 0xF10200
EXPECTED_WIDE_CURSOR = bytes.fromhex(
    '00b50198c16b064a914205d10548064901800648064901800198'
    'fff703ff00bd0828ec08ce600006baa100000e610006bba10000'
)
ROW_DISPATCH = 0xF10280
EXPECTED_ROW_DISPATCH = bytes.fromhex(
    '0db4039ad26b1d498a4201d005a100e007a106230a8802800230'
    '0231013bf9d10dbc7047e2806401e480e680e8806401e2806401'
    '64016401e480e680000000000db4039ad26b0d498a4201d005a1'
    '00e007a106230a88028002300231013bf9d10dbc7047e3806401'
    'e580e780e9806401e380640164016401e580e7800828ec08'
)
ROW_SOURCE = 0xF10320
EXPECTED_ROW_SOURCE = bytes.fromhex(
    '10b582b0e46b06498c4200d1054b049c0094059c0194'
    '002102f4f0fe02b010bd0828ec088003f108'
)
NAME_ROW = 0xF10380
EXPECTED_NAME_ROW = bytes.fromhex('81408eec8140814081408e9b89af0000')
EXPECTED_ROW = bytes.fromhex('814081408eec814081408e9b89af0000')
EXPECTED_LOAD = bytes.fromhex('8eec8e9b89af8140')  # E2/E4/E6/E8: 예, 아, 뇨, blank
LINK_ROW = bytes.fromhex('81408eec8140814081408e9b89af000000')
COMPACT_LOAD = bytes.fromhex('8eec8e9b89af81a500000000')
CURSOR_HELPER = bytes.fromhex(
    '08480188084a91420ad004230099c96b064ca14200d15b00c252'
    '0548054ac252ffbdc046ce600006baa100000828ec080e610006'
    'bba10000'
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
    assert hook[6:10] == bytes.fromhex('00f0fbf8'), 'wide-row cursor branch changed'
    assert rom[WIDE_CURSOR:WIDE_CURSOR + len(EXPECTED_WIDE_CURSOR)] == EXPECTED_WIDE_CURSOR
    assert rom[ROW_DISPATCH:ROW_DISPATCH + len(EXPECTED_ROW_DISPATCH)] == EXPECTED_ROW_DISPATCH
    assert rom[ROW_SOURCE:ROW_SOURCE + len(EXPECTED_ROW_SOURCE)] == EXPECTED_ROW_SOURCE
    assert rom[NAME_ROW:NAME_ROW + len(EXPECTED_NAME_ROW)] == EXPECTED_NAME_ROW
    assert rom[0xB18D26:0xB18D2A] == bytes.fromhex('f7f3fbfa')
    # E2/E4/E6/E8 feed x8/x12/x13; the native row owns the same geometry.
    assert hook[0xE8:0xF8] == bytes.fromhex(
        'e2800000e4800000e6800000e8800000')
    assert hook[0x118:0x11C] == bytes.fromhex('2017f008')  # 뇨 top
    assert hook[0x120:0x124] == bytes.fromhex('8018f008')  # 뇨 bottom
    assert hook[0x128:0x12C] == hook[0x130:0x134] == bytes.fromhex('209ff008')
    assert rom[0xF09F20:0xF09F40] == bytes(32)
    assert hook[0x140:0x144] == bytes.fromhex('64010000')  # six cells
    assert hook[0x138:0x140] == bytes.fromhex('d060000610610006')  # top/bottom x8
    assert hook[0x8E:0x92] == bytes.fromhex('00f0f7f8')
    assert hook[0x94:0x98] == bytes.fromhex('00f014f9')
    assert rom[0xB18D2C:0xB18D30] == bytes.fromhex('f7f368f9'), 'hook branch target changed'
    assert rom[0xB18D40:0xB18D48] == bytes.fromhex('004b18470d00f108'), 'frame hook target changed'
    assert hook[0x98:0x9A] == bytes.fromhex('82e1'), 'cursor helper branch changed'
    assert rom[0xF103A0:0xF103A0 + len(CURSOR_HELPER)] == CURSOR_HELPER, 'cursor helper changed'


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
