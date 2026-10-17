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
    '00b500f0fdf8002905d00548054901800548064901800198fff704ff00bdc046'
    'ce600006baa100000e610006bba10000'
)
ROW_DISPATCH = 0xF10280
EXPECTED_ROW_DISPATCH = bytes.fromhex(
    '0db500f0bdf8002901d105a100e007a106230a88028002300231013bf9d10dbd'
    'e2806401e480e680e8806401e280640164016401e480e6800000000000000000'
    '0db500f09df8002901d105a100e007a106230a88028002300231013bf9d10dbd'
    'e3806401e580e780e9806401e380640164016401e580e7800000000000000000'
)
ROW_SOURCE = 0xF10320
EXPECTED_ROW_SOURCE = bytes.fromhex(
    '10b582b000f06cf8002900d0044b049c0094059c0194002102f4f0fe02b010bd'
    '8003f108'
)
NAME_ROW = 0xF10380
EXPECTED_NAME_ROW = bytes.fromhex('81408eec8140814081408e9b89af0000')
EXPECTED_ROW = bytes.fromhex('814081408eec814081408e9b89af0000')
EXPECTED_LOAD = bytes.fromhex('8eec8e9b89af8140')  # E2/E4/E6/E8: 예, 아, 뇨, blank
LINK_ROW = bytes.fromhex('81408eec8140814081408e9b89af000000')
COMPACT_LOAD = bytes.fromhex('8eec8e9b89af81a500000000')
CURSOR_HELPER = bytes.fromhex(
    '07480188074a914209d0042300f028f8002900d05b00c2520348044ac252ffbd'
    'ce600006baa100000e610006bba10000'
)
PROMPT_ID = bytes.fromhex(
    '1db5194b194800f024f8002910d1184800f01ff800290bd11648174a0468002c02d04468'
    '9c4203d060309042f6d30ee0046a124be31a012b07d9114be31a012b03d9104be31a012b'
    '01d801211dbd00211dbd0468002c02d044689c4201d00021704701217047c046fc26d808'
    'a0100003e00f0003000e0003001d0003118edf08d38edf08c604e108'
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
    assert rom[0xF10400:0xF10400 + len(PROMPT_ID)] == PROMPT_ID, 'intro-independent prompt classifier changed'
    # A skipped WARS intro leaves the old +0x3c resource word as 0/08EC2A88.
    # All four paths must call the VM script classifier instead of reading it.
    for helper in (EXPECTED_WIDE_CURSOR, EXPECTED_ROW_DISPATCH,
                   EXPECTED_ROW_SOURCE, CURSOR_HELPER):
        assert bytes.fromhex('0828ec08') not in helper, 'stale resource identity returned'


def check_intro_skip(rom_path, harness):
    """Cold boot through a 3 s WARS skip, then check both live choice rows."""
    import numpy as np
    from qa_visual_regions import KEYS, MGBADriver

    out = Path(__file__).resolve().parents[1] / 'temp/part1_yesno_intro_skip_regression'
    out.mkdir(parents=True, exist_ok=True)
    driver = MGBADriver(rom_path.resolve(), out, harness.resolve())
    raw = out / 'frame.raw'

    def advance(key, frames):
        driver.cmd(f'keys {KEYS[key] if key else 0}')
        driver.frames(frames)
        driver.cmd('keys 0')

    def capture(frames):
        result = []
        for _ in range(frames):
            driver.frames(1)
            driver.cmd(f'shot {raw}')
            data = raw.read_bytes()
            width, height = struct.unpack_from('<HH', data)
            channels = data[4]
            result.append(np.frombuffer(data[5:], np.uint8).reshape(height, width, channels)[139:151, 50:130, :3].copy())
        return np.stack(result)

    try:
        for key, frames in ((None,1250),('START',6),(None,170),('A',6),
                            (None,180),('START',6),(None,180),('START',6),
                            (None,240),('A',6),(None,90),('A',6),(None,90),
                            ('A',6),(None,90),('A',6),(None,300)):
            advance(key, frames)
        advance('START',6)
        name = capture(100)
        for key, frames in (('A',6),(None,150),('A',6),(None,240),
                            ('A',6),(None,240),('A',6)):
            advance(key, frames)
        first_time = capture(100)
    finally:
        driver.close()
        raw.unlink(missing_ok=True)
    assert driver.proc.returncode == 0, f'emulator exit {driver.proc.returncode}'
    for label, frames in (('name', name), ('first_time', first_time)):
        delta = np.any(frames[1:] != frames[:-1], axis=3).sum(axis=(1, 2))
        draws = np.flatnonzero(delta[19:] >= 100) + 20
        assert len(draws) == 1, f'{label}: row redraws at {draws.tolist()}'
        ink = np.flatnonzero((frames[-1, 3:10, 16:80].sum(axis=2) < 200).any(axis=0)) + 66
        assert len(ink) and ink.max() >= 110, f'{label}: wide row missing'
    print('PASS: cold-boot WARS intro skip: one >=100-pixel change after frame 19 per prompt; final ink reaches x110')


class Part1YesNoRowTest(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('AW_TEST_ROM'), 'AW_TEST_ROM required')
    def test_live_yesno_payloads(self):
        check(Path(os.environ['AW_TEST_ROM']).read_bytes())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('rom', type=Path)
    parser.add_argument('--intro-skip-harness', type=Path)
    args = parser.parse_args()
    check(args.rom.read_bytes())
    if args.intro_skip_harness:
        check_intro_skip(args.rom, args.intro_skip_harness)
    print('PASS: live yes/no payloads and name overlay cells')
