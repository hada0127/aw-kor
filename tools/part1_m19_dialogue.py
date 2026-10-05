"""Observed portrait-row overflow; preserve words, pages and other row writers."""
import hashlib
import struct

from dialogue_repoint import normalize_text_segment, text_segment_cells
from sprite_relocations import SPRITE_STORAGE_START

START, END, POINTER, ADDRESS = 0xDCF608, 0xDCF69C, 0xDE5694, 0xDCF656
SPANS = ((0xDCF60A, 40), (0xDCF635, 28), (ADDRESS, 40), (0xDCF683, 20))
TEXT = '누군지는 모르겠지만,정말 머리 끝까지 화났어!'
ROWS = ('누군지는 모르겠지만,정말', '머리 끝까지 화났어!')
NEXT_TEXT = '각오하라고-!'
APPROVED_NEIGHBORS = {
    0xDCF60A: '그래서 다른 사령관들도,레드스타에게',
    0xDCF635: '싸움을 걸어왔던 거구나!',
    0xDCF683: NEXT_TEXT,
}
SOURCE_SHA = 'c0ce5ed04b779fd22ed39ba811e5eb5b5593eb485432cbdde22b09114a78fae8'
# Portrait text begins at x56. Keep an 8px right margin in a 240px screen.
# The existing Part1 fullwidth advance model is 8px (qa_pixel_width.py).
MAX_ROW_PIXELS = 176


def source_guard(original):
    ref = struct.pack('<I', START + 0x08000000)
    if (hashlib.sha256(original[START:END]).hexdigest() != SOURCE_SHA
            or original[POINTER - 4:POINTER] != b'\x19\0\0\0'
            or original[POINTER:POINTER + 4] != ref or original.count(ref) != 1):
        raise ValueError('M19 dialogue source/pointer ownership changed')
    # The first page already uses the same native two-row control.
    if original[0xDCF632:0xDCF635] != b'\x72\x0a\x09':
        raise ValueError('M19 native newline reference changed')


def layout(original, encode):
    source_guard(original)
    if ' '.join(ROWS) != TEXT:
        raise ValueError('M19 layout changes approved wording')
    rows = tuple(encode(text, ADDRESS) for text in ROWS)
    normalized = tuple(normalize_text_segment(row, True, START) for row in rows)
    if (any(not row or any(b < 0x20 for b in row) for row in normalized)
            or any(text_segment_cells(row) * 4 > MAX_ROW_PIXELS for row in normalized)):
        raise ValueError('M19 portrait row text/control/width invalid')
    return {ADDRESS: rows}


def expected_before_repoint(rom, original, encode):
    """Bind untouched translated spans before relocation, not after mutation."""
    rows = layout(original, encode)[ADDRESS]
    result = bytearray()
    cursor = START
    for address, length in SPANS:
        gap = bytes(rom[cursor:address])
        if gap != original[cursor:address]:
            raise ValueError('M19 page/newline controls changed')
        result += gap
        parts = rows if address == ADDRESS else (bytes(rom[address:address + length]),)
        if any(any(b < 0x20 for b in part) for part in parts):
            raise ValueError('M19 text span contains controls')
        if address in APPROVED_NEIGHBORS:
            actual = normalize_text_segment(parts[0], True, START).rstrip(b' ')
            approved = normalize_text_segment(encode(APPROVED_NEIGHBORS[address], address), True, START)
            if actual != approved:
                raise ValueError(f'M19 neighboring dialogue changed: {address:08X}')
        if any(text_segment_cells(normalize_text_segment(part, True, START)) * 4 > MAX_ROW_PIXELS
               for part in parts):
            raise ValueError('M19 neighboring portrait row exceeds width')
        result += b'\x72\x0a\x09'.join(normalize_text_segment(part, True, START) for part in parts)
        cursor = address + length
    if bytes(rom[cursor:END]) != original[cursor:END]:
        raise ValueError('M19 final page terminator changed')
    result += original[cursor:END]
    return bytes(result)


def verify(rom, original, expected_payload, encode):
    rows = layout(original, encode)[ADDRESS]
    if bytes(rom[POINTER - 4:POINTER]) != b'\x19\0\0\0':
        raise ValueError('M19 final command opcode changed')
    target = struct.unpack_from('<I', rom, POINTER)[0] - 0x08000000
    if (target % 4 or not 0xA3D000 <= target < target + len(expected_payload) <= SPRITE_STORAGE_START
            or target + len(expected_payload) > len(rom)):
        raise ValueError('M19 dialogue requires bounded aligned relocation')
    if bytes(rom[target:target + len(expected_payload)]) != expected_payload:
        raise ValueError('M19 final wording/pages/other rows mismatch')
    return {'status': 'PASS', 'target': hex(target), 'rows': list(ROWS),
            'row_pixels': [text_segment_cells(normalize_text_segment(row, True, START)) * 4 for row in rows],
            'live_pixels_verified': False}
