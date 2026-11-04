"""Guards for the Part 1 name trim hook (0x08F10180).

The hook replaces the native trim 0x08B11298, which the name screen calls on
confirm (0x08B48F6E) and on preload (0x08B489B8). It must strip trailing SJIS
fullwidth spaces (81 40) only. The 2026-06-01 hook also stripped 8F 5A, which
is 「요」 in the 2350 map, so 「반가워요」 was saved as 「반가워」.

Static checks run against tools/build_korean_full.py. A small Thumb
interpreter runs the hook bytes on sample buffers. With --rom PATH the built
ROM bytes are checked too.

  python3 -I tools/test_part1_name_trim_hook.py [--rom output/....gba] [-v]
"""

import argparse
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_korean_full as B  # noqa: E402

# clang --target=thumbv4t-none-eabi of the listing in plan_B.md D1
# (temp/fix_20261104/p1compose/t1/trim_hook.s).
EXPECTED_HOOK = bytes.fromhex(
    '031c00211878002806d0881c0006010e581800780028f8d100290ad0'
    '881e0006010e5a181078812802d150784028f3d00231c91800200870'
    '7047'
)
# 2026-06-01 hook (fcd853f), kept to show the interpreter reproduces the bug.
RETIRED_HOOK = bytes.fromhex(
    '031c00211878002806d0881c0006010e581800780028f8d1002910d0'
    '881e0006010e5a181078812802d08f2804d006e050784028f0d002e0'
    '50785a28ecd0c918002088707047'
)
# Native 0x08B11298..0x08B112D0 from the original ROM (a8ad7c7d...).
NATIVE_TRIM = bytes.fromhex(
    '031c00211878002806d0881c0006010e581800780028f8d1002909d0'
    '881e0006010e5a181078812802d150784028f3d0c918002088707047'
)
HOOK_FILE = 0xF10180
HOOK_SPAN = 70
SITE = 0xB11298
SITE_EXPECT = bytes.fromhex('031c002118780028')
SITE_TRAMP = bytes.fromhex('004b1847') + struct.pack('<I', 0x08F10180 | 1)

BUF = 0x02008038  # obj + 0x2C in a cold-boot run; any EWRAM address works.
CODE = 0x08F10180


def run_thumb(code, mem, r0, max_steps=2000):
    """Run a leaf Thumb-1 routine until `bx lr`. Only the opcodes the trim
    routines use are implemented; anything else raises. `mem` maps byte
    address -> value and must already contain every address read or
    written, so stray accesses fail loudly."""
    r = [0] * 16
    r[0] = r0
    z = False
    pc = CODE
    for _ in range(max_steps):
        off = pc - CODE
        if not 0 <= off < len(code) - 1:
            raise AssertionError(f'pc out of routine: {pc:#x}')
        op = code[off] | code[off + 1] << 8
        nxt = pc + 2
        top5 = op >> 11
        if op == 0x4770:  # bx lr
            return r
        if top5 == 0b00000:  # lsls rd, rm, #imm5
            rd, rm, imm = op & 7, (op >> 3) & 7, (op >> 6) & 31
            r[rd] = (r[rm] << imm) & 0xFFFFFFFF
            z = r[rd] == 0
        elif top5 == 0b00001:  # lsrs rd, rm, #imm5 (imm != 0 here)
            rd, rm, imm = op & 7, (op >> 3) & 7, (op >> 6) & 31
            assert imm
            r[rd] = r[rm] >> imm
            z = r[rd] == 0
        elif (op >> 9) == 0b0001100:  # adds rd, rn, rm
            rd, rn, rm = op & 7, (op >> 3) & 7, (op >> 6) & 7
            r[rd] = (r[rn] + r[rm]) & 0xFFFFFFFF
            z = r[rd] == 0
        elif (op >> 9) == 0b0001110:  # adds rd, rn, #imm3
            rd, rn, imm = op & 7, (op >> 3) & 7, (op >> 6) & 7
            r[rd] = (r[rn] + imm) & 0xFFFFFFFF
            z = r[rd] == 0
        elif (op >> 9) == 0b0001111:  # subs rd, rn, #imm3
            rd, rn, imm = op & 7, (op >> 3) & 7, (op >> 6) & 7
            r[rd] = (r[rn] - imm) & 0xFFFFFFFF
            z = r[rd] == 0
        elif top5 == 0b00100:  # movs rd, #imm8
            rd = (op >> 8) & 7
            r[rd] = op & 0xFF
            z = r[rd] == 0
        elif top5 == 0b00101:  # cmp rn, #imm8
            z = r[(op >> 8) & 7] == (op & 0xFF)
        elif top5 == 0b00110:  # adds rd, #imm8
            rd = (op >> 8) & 7
            r[rd] = (r[rd] + (op & 0xFF)) & 0xFFFFFFFF
            z = r[rd] == 0
        elif top5 in (0b01110, 0b01111):  # strb / ldrb rd, [rn, #imm5]
            rd, rn, imm = op & 7, (op >> 3) & 7, (op >> 6) & 31
            addr = r[rn] + imm
            if addr not in mem:
                raise AssertionError(f'access outside buffer: {addr:#x} at {pc:#x}')
            if top5 == 0b01111:
                r[rd] = mem[addr]
            else:
                mem[addr] = r[rd] & 0xFF
        elif (op >> 8) in (0xD0, 0xD1):  # beq / bne
            take = z if (op >> 8) == 0xD0 else not z
            if take:
                imm = op & 0xFF
                imm = imm - 0x100 if imm & 0x80 else imm
                nxt = pc + 4 + imm * 2
        elif top5 == 0b11100:  # b
            imm = op & 0x7FF
            imm = imm - 0x800 if imm & 0x400 else imm
            nxt = pc + 4 + imm * 2
        else:
            raise AssertionError(f'unsupported opcode {op:04x} at {pc:#x}')
        pc = nxt
    raise AssertionError('routine did not return')


def trim(code, data, size=0x20):
    """Return the buffer after running `code` on `data` (padded with 0xEE
    beyond the explicit bytes so stray writes are visible)."""
    raw = bytes(data) + b'\xee' * (size - len(data))
    mem = {BUF + i: b for i, b in enumerate(raw)}
    run_thumb(code, mem, BUF)
    return bytes(mem[BUF + i] for i in range(size))


def h(s):
    return bytes.fromhex(s.replace(' ', ''))


SP = '8140'
BANGAWOYO = '8cae 8840 8f6c 8f5a'  # 반가워요


class StaticTest(unittest.TestCase):
    def test_builder_constant_pinned(self):
        self.assertEqual(B.PART1_NAME_TRIM_HOOK, EXPECTED_HOOK)
        self.assertEqual(len(B.PART1_NAME_TRIM_HOOK), 58)

    def test_fits_retired_span(self):
        self.assertEqual(B.PART1_NAME_TRIM_HOOK_SPAN, HOOK_SPAN)
        self.assertLessEqual(len(B.PART1_NAME_TRIM_HOOK), HOOK_SPAN)

    def test_no_8f5a_compare(self):
        code = B.PART1_NAME_TRIM_HOOK
        halves = [code[i:i + 2] for i in range(0, len(code), 2)]
        self.assertNotIn(bytes.fromhex('8f28'), halves)  # cmp r0, #0x8F
        self.assertNotIn(bytes.fromhex('5a28'), halves)  # cmp r0, #0x5A

    def test_site_and_trampoline(self):
        self.assertEqual(B.PART1_NAME_TRIM_HOOK_FILE, HOOK_FILE)
        self.assertEqual(B.PART1_NAME_TRIM_HOOK_RT, 0x08F10180)
        self.assertEqual(B.PART1_NAME_TRIM_SITE, SITE)
        self.assertEqual(B.PART1_NAME_TRIM_EXPECT, SITE_EXPECT)
        self.assertEqual(NATIVE_TRIM[:8], SITE_EXPECT)


class BehaviourTest(unittest.TestCase):
    def test_keeps_trailing_yo(self):
        data = h(BANGAWOYO + SP * 2 + '00')
        self.assertEqual(trim(EXPECTED_HOOK, data)[:9], h(BANGAWOYO + '00'))

    def test_retired_hook_reproduces_bug(self):
        data = h(BANGAWOYO + SP * 2 + '00')
        self.assertEqual(trim(RETIRED_HOOK, data)[:7], h('8cae 8840 8f6c 00'))

    def test_yo_in_every_position(self):
        for name in ('8f5a', '8f5a 8840', '8840 8f5a', '8f5a 8f5a 8f5a 8f5a 8f5a 8f5a'):
            n = len(h(name))
            pad = SP * ((12 - n) // 2)
            out = trim(EXPECTED_HOOK, h(name + pad + '00'))
            self.assertEqual(out[:n + 1], h(name + '00'), name)

    def test_six_chars_full(self):
        name = '8cae 8840 8f6c 8f5a 8840 8f5a'
        out = trim(EXPECTED_HOOK, h(name + '00'))
        self.assertEqual(out[:13], h(name + '00'))
        self.assertEqual(out[13:], b'\xee' * (0x20 - 13))

    def test_strips_trailing_spaces_keeps_middle(self):
        out = trim(EXPECTED_HOOK, h('8840' + SP + '88e9' + SP * 3 + '00'))
        self.assertEqual(out[:7], h('8840 8140 88e9 00'))
        out = trim(EXPECTED_HOOK, h('8840' + SP * 5 + '00'))
        self.assertEqual(out[:3], h('8840 00'))

    def test_other_81_and_40_pairs_kept(self):
        for last in ('8141', '8148', '4081', '8340'):
            out = trim(EXPECTED_HOOK, h('8840' + last + SP + '00'))
            self.assertEqual(out[:5], h('8840' + last + '00'), last)

    def test_empty_and_all_spaces(self):
        # Empty: nothing written past buf[0].
        out = trim(EXPECTED_HOOK, h('00'))
        self.assertEqual(out[:1], b'\x00')
        self.assertEqual(out[1:], b'\xee' * 0x1F)
        # All spaces: buf[0] = 0 (native writes buf[2] and keeps one space).
        out = trim(EXPECTED_HOOK, h(SP * 6 + '00'))
        self.assertEqual(out[0], 0)
        self.assertEqual(out[1:13], h('40' + SP * 5 + '00'))

    def test_matches_native_except_all_stripped(self):
        cases = [
            BANGAWOYO + SP * 2 + '00',
            '8cae 8840 8f6c 8f5a 8840 8f5a 00',
            '8840' + SP + '88e9' + SP * 3 + '00',
            '8341 8343 8345 8347 8349 834a 00',
            '8840 8141 8140 00',
        ]
        for c in cases:
            self.assertEqual(trim(EXPECTED_HOOK, h(c)), trim(NATIVE_TRIM, h(c)), c)
        for c in ('00', SP * 6 + '00'):
            native = trim(NATIVE_TRIM, h(c))
            self.assertEqual(native[2], 0, c)  # native terminates at buf+2

    def test_stray_store_detected(self):
        # The first plan listing encoded `strb r0,[r1]` as 0070 (strb r0,[r0]).
        broken = EXPECTED_HOOK[:0x36] + bytes.fromhex('0070') + EXPECTED_HOOK[0x38:]
        with self.assertRaises(AssertionError):
            trim(broken, h(BANGAWOYO + '00'))


ROM_PATH = None


@unittest.skipUnless(ROM_PATH or '--rom' in sys.argv, 'no --rom given')
class RomTest(unittest.TestCase):
    def test_rom_bytes(self):
        rom = Path(ROM_PATH).read_bytes()
        self.assertEqual(rom[HOOK_FILE:HOOK_FILE + len(EXPECTED_HOOK)], EXPECTED_HOOK)
        self.assertEqual(rom[HOOK_FILE + len(EXPECTED_HOOK):HOOK_FILE + HOOK_SPAN],
                         bytes(HOOK_SPAN - len(EXPECTED_HOOK)))
        self.assertEqual(rom[SITE:SITE + 8], SITE_TRAMP)
        self.assertEqual(rom[HOOK_FILE + HOOK_SPAN:HOOK_FILE + 0x80], bytes(0x80 - HOOK_SPAN))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument('--rom')
    args, rest = ap.parse_known_args()
    ROM_PATH = args.rom
    unittest.main(argv=[sys.argv[0]] + rest)
