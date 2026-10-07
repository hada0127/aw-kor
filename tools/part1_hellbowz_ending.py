"""Part 1 final-battle Hellbowz defeat line 0xDD0BCB (wording from the 쪼롱이 standard).

The approved wording (data/dialogue_overrides.json, commit 2d0b6af) needs 50 bytes
in a 40-byte slot, so fit/strip dropped every space and the ellipsis. Words stay
unchanged; the message (0xDD0BB0, referenced once by a 0x19 command at 0xDE7E6C)
is relocated and the row is split with the native in-page newline 72 0A 09
(same control as the message's last page) at the space after 걸음만:
  row 1  앞으로 한 걸음　앞으로 한 걸음만
  row 2  더 가면 됐는데・・・!
Both rows stay within the 176px portrait row budget used by part1_m19_dialogue.
"""
import struct

from dialogue_repoint import normalize_text_segment, text_segment_cells

START, POINTER, ADDRESS = 0xDD0BB0, 0xDE7E6C, 0xDD0BCB
TEXT = '앞으로 한 걸음　앞으로 한 걸음만 더 가면 됐는데・・・!'
ROWS = ('앞으로 한 걸음　앞으로 한 걸음만', '더 가면 됐는데・・・!')
MAX_ROW_PIXELS = 176


def source_guard(original):
    ref = struct.pack('<I', START + 0x08000000)
    if original[POINTER - 4:POINTER] != b'\x19\0\0\0' or original[POINTER:POINTER + 4] != ref:
        raise ValueError('Hellbowz ending message pointer ownership changed')
    if original.count(ref) != 1:
        raise ValueError('Hellbowz ending message has more than one reference')
    end = original.index(b'\0', START)
    if b'\x72\x0a\x09' not in original[START:end]:
        raise ValueError('Hellbowz ending native newline reference changed')


def layout(original, encode):
    source_guard(original)
    if ' '.join(ROWS) != TEXT:
        raise ValueError('Hellbowz layout changes approved wording')
    rows = tuple(encode(text, ADDRESS) for text in ROWS)
    normalized = tuple(normalize_text_segment(row, True, START) for row in rows)
    if (any(not row or any(b < 0x20 for b in row) for row in normalized)
            or any(text_segment_cells(row) * 4 > MAX_ROW_PIXELS for row in normalized)):
        raise ValueError('Hellbowz row text/control/width invalid')
    return {ADDRESS: rows}


def verify(rom, original, encode):
    """After repoint: the 0x19 pointer moved and the relocated payload carries both rows."""
    rows = layout(original, encode)[ADDRESS]
    target = struct.unpack_from('<I', rom, POINTER)[0] - 0x08000000
    if target == START:
        raise ValueError('Hellbowz ending message was not relocated')
    end = rom.index(b'\0', target)
    joined = b'\x72\x0a\x09'.join(normalize_text_segment(row, True, START) for row in rows)
    if joined not in bytes(rom[target:end]):
        raise ValueError('Hellbowz ending rows missing from relocated message')
    return {'status': 'PASS', 'target': hex(target), 'rows': list(ROWS),
            'row_pixels': [text_segment_cells(normalize_text_segment(r, True, START)) * 4 for r in rows],
            'live_pixels_verified': False}
