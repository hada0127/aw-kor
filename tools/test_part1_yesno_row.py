"""Static and cold-boot guards for the wide Part 1 yes/no layout."""

import argparse
import hashlib
import json
import os
import struct
import tempfile
import unittest
from pathlib import Path


ROW = 0xD835BC
LOAD = 0xD8273C
HOOK = 0xF10000
WIDE_CURSOR = 0xF10200
EXPECTED_WIDE_CURSOR = bytes.fromhex(
    '00b50198fff70eff00bd'
)
ROW_DISPATCH = 0xF10280
EXPECTED_ROW_DISPATCH = bytes.fromhex(
    '0db504a106230a88028002300231013bf9d10dbde280640164016401e480e6800000000000000000'
    '0000000000000000000000000000000000000000000000000db504a106230a88028002300231013b'
    'f9d10dbde380640164016401e580e780000000000000000000000000000000000000000000000000'
    '0000000000000000'
)
ROW_SOURCE = 0xF10320
EXPECTED_ROW_SOURCE = bytes.fromhex(
    '10b582b0044b049c0094059c0194002102f4f4fe02b010bd8003f108'
)
NAME_ROW = 0xF10380
EXPECTED_NAME_ROW = bytes.fromhex('81408eec8140814081408e9b89af0000')
EXPECTED_ROW = bytes.fromhex('814081408eec814081408e9b89af0000')
EXPECTED_LOAD = bytes.fromhex('8eec8e9b89af8140')  # E2/E4/E6/E8: 예, 아, 뇨, blank
LINK_ROW = bytes.fromhex('81408eec8140814081408e9b89af000000')
COMPACT_LOAD = bytes.fromhex('8eec8e9b89af81a500000000')
CURSOR_HELPER = bytes.fromhex(
    '00988069054902880a8002890a814030403102880a8002890a81ffbdce600006'
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
    assert len(EXPECTED_WIDE_CURSOR) == 10 and len(CURSOR_HELPER) == 32
    assert CURSOR_HELPER[-4:] == bytes.fromhex('ce600006'), 'cursor destination changed'
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
    assert hook[0xAA:0xE0] == bytes(0x36), 'retired compact writers must remain padding'
    assert rom[0xF103A0:0xF103A0 + len(CURSOR_HELPER)] == CURSOR_HELPER, 'cursor helper changed'
    assert rom[0xF10400:0xF10400 + 136] == bytes(136), 'unused prompt classifier must be zero'
    for start, old_len, current in ((WIDE_CURSOR, 48, EXPECTED_WIDE_CURSOR),
                                    (ROW_SOURCE, 36, EXPECTED_ROW_SOURCE),
                                    (0xF103A0, 48, CURSOR_HELPER)):
        assert rom[start + len(current):start + old_len] == bytes(old_len - len(current)), 'retired helper bytes remain'
    # Any legacy selection or x9 fallback here would reintroduce a slot-0x03001100 shake.
    for helper in (EXPECTED_WIDE_CURSOR, EXPECTED_ROW_DISPATCH,
                   EXPECTED_ROW_SOURCE, CURSOR_HELPER):
        assert bytes.fromhex('0828ec08') not in helper, 'stale resource identity returned'
        assert bytes.fromhex('00f0') not in helper[:12], 'conditional classifier call returned'


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


def check_audit_rom_sha(rows, expected_sha):
    """Every candidate capture used by this audit must identify this ROM."""
    for row in rows:
        if 'b40_npz' in row:
            assert row.get('b40_sha') == expected_sha, 'summary capture SHA does not match supplied ROM'
    metas = {Path(r['b40_npz']).parent / 'meta.json' for r in rows if 'b40_npz' in r}
    assert metas, 'audit has no candidate captures'
    for meta_path in metas:
        meta = json.loads(meta_path.read_text())
        assert meta['sha'] == expected_sha, f'{meta_path}: capture SHA does not match supplied ROM'


def _opening_cursor(frames):
    import numpy as np

    counts = []
    for x in (56, 88):
        crop = frames[:40, 140:151, x:x + 8, :3]
        yellow = (crop[..., 0] > 180) & (crop[..., 1] > 110) & (crop[..., 2] < 130)
        counts.append(yellow.sum(axis=(1, 2)))
    selected = np.flatnonzero((counts[0] >= 6) | (counts[1] >= 6))
    assert len(selected), 'opening cursor not captured'
    frame = int(selected[0])
    assert (counts[0][frame] >= 6) != (counts[1][frame] >= 6), 'ambiguous opening selection'
    return frame, 'yes' if counts[0][frame] >= 6 else 'no', counts


def check_audit_summary(path, rom_sha):
    """Reject a compact fallback in the forced slot-0x03001100 hint captures."""
    import numpy as np

    rows = json.loads(path.read_text())
    check_audit_rom_sha(rows, rom_sha)
    # These opening frames are compared without cursor masking. The first
    # visible selection must agree with the original and the wide row must
    # already be present; a cursor-only repair is a regression.
    for tag, site, expected in (('ng_skip400', '0xdf8e0e', 'yes'),
                                ('modeback_w450', '0xdf2a8e', 'no'),
                                ('solo_d9f9b6', '0xd9f9ca', 'no'),
                                ('solo_d822d8', '0xd822e8', 'no')):
        hits = [r for r in rows if r.get('tag') == tag and r.get('site') == site and 'b40_npz' in r]
        assert hits, f'{tag} {site}: opening audit missing'
        r = hits[0]
        orig = np.load(r['orig_npz'])['f']
        candidate = np.load(r['b40_npz'])['f']
        orig_frame, orig_selection, _ = _opening_cursor(orig)
        frame, selection, counts = _opening_cursor(candidate)
        assert orig_selection == expected == selection, f'{tag}: opening selection {selection} != original {orig_selection}'
        assert frame >= r['b40_draws'][0][0], f'{tag}: cursor appears before wide row at frame {frame}'
        assert counts[0][frame] < 6 or counts[1][frame] < 6, f'{tag}: both cursor columns active'
    for site in ('0xd9313e', '0xd94826'):
        hits = [r for r in rows if r.get('site') == site and r.get('tag') == 'force']
        assert len(hits) == 1, f'{site}: forced audit event missing'
        r = hits[0]
        assert len(r['b40_draws']) == 1, f'{site}: row layout changed {r["b40_draws"]}'
        assert not any(r['b40_in']), f'{site}: input redrew non-cursor pixels'
        meta = json.loads((path.parent / 'runs' / 'force_b40_hle' / 'meta.json').read_text())
        events = [e for e in meta['events'] if e['site'] == site]
        assert len(events) == 1, f'{site}: event metadata missing'
        assert any(h[0].lower() == '0x3001100' for h in events[0]['hosts_at_detect']), f'{site}: slot-0x03001100 case missing'
    cursor_sites = {'0xd9313e', '0xd94826', '0xdf8e0e', '0xdf8ed0',
                    '0xdf295e', '0xdfcf22', '0xdf2a8e'}
    checked = 0
    for r in rows:
        if r.get('site') not in cursor_sites or 'b40_npz' not in r:
            continue
        npz = Path(r['b40_npz'])
        frames = np.load(npz)['f']
        meta = json.loads((npz.parent / 'meta.json').read_text())
        event = meta['events'][int(npz.stem.split('_')[0][2:])]
        for label, start, stop, x in (('RIGHT', event['idx_right'], event['idx_left'], 88),
                                      ('LEFT', event['idx_left'], len(frames), 56)):
            crop = frames[start:stop, 140:151, x:x + 8]
            yellow = (crop[:, :, :, 0] > 180) & (crop[:, :, :, 1] > 110) & (crop[:, :, :, 2] < 130)
            assert yellow.sum(axis=(1, 2)).max() >= 6, f'{r["tag"]} {r["site"]}: {label} cursor missing at wide x{x // 8}'
        checked += 1
    assert checked >= 7, f'wide cursor coverage too small: {checked}'
    print(f'PASS: {checked} audited Part 1 prompts keep visible x7/x11 cursors; forced slot-0x03001100 hints draw one row')


class Part1YesNoRowTest(unittest.TestCase):
    def test_audit_metadata_rom_binding(self):
        root = Path(__file__).resolve().parents[1] / 'temp'
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as dirname:
            capture = Path(dirname) / 'meta.json'
            capture.write_text(json.dumps({'sha': 'old-rom'}))
            rows = [{'b40_npz': str(capture.parent / 'ev00.npz'), 'b40_sha': 'supplied-rom'}]
            with self.assertRaisesRegex(AssertionError, 'capture SHA does not match'):
                check_audit_rom_sha(rows, 'supplied-rom')
            capture.write_text(json.dumps({'sha': 'supplied-rom'}))
            check_audit_rom_sha(rows, 'supplied-rom')
            rows[0]['b40_sha'] = 'old-rom'
            with self.assertRaisesRegex(AssertionError, 'summary capture SHA does not match'):
                check_audit_rom_sha(rows, 'supplied-rom')

    @unittest.skipUnless(os.environ.get('AW_TEST_ROM'), 'AW_TEST_ROM required')
    def test_live_yesno_payloads(self):
        check(Path(os.environ['AW_TEST_ROM']).read_bytes())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('rom', type=Path)
    parser.add_argument('--intro-skip-harness', type=Path)
    parser.add_argument('--audit-summary', type=Path)
    args = parser.parse_args()
    check(args.rom.read_bytes())
    if args.intro_skip_harness:
        check_intro_skip(args.rom, args.intro_skip_harness)
    if args.audit_summary:
        check_audit_summary(args.audit_summary, hashlib.sha256(args.rom.read_bytes()).hexdigest())
    print('PASS: unconditional wide Part 1 yes/no payloads and overlay cells')
