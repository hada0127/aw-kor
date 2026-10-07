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


def _runs(original):
    """(start, end) of every text run in the original message, split at controls."""
    end = original.index(b'\0', START)
    runs, i, run = [], START, None
    while i < end:
        b = original[i]
        if 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xEF:
            run = i if run is None else run
            i += 2
        else:
            if run is not None:
                runs.append((run, i))
                run = None
            i += 1
    if run is not None:
        runs.append((run, end))
    return runs, end + 1


def expected_before_repoint(rom, original, encode, fixed=None):
    """Complete-message contract taken from the pre-repoint ROM.

    Returns segments: ('gap', native control bytes) and ('row', alternatives).
    This row must be the two-row layout. Every other row must be its current
    (pre-repoint) text or, when the repointer repairs it, the full-fidelity
    encoding of its approved text (fixed(address)); both normalized.
    """
    rows = layout(original, encode)[ADDRESS]
    runs, end = _runs(original)
    if ADDRESS not in {a for a, _ in runs}:
        raise ValueError('Hellbowz row is not a native text run')
    segments = []
    cursor = START
    for a, b in runs:
        gap = bytes(rom[cursor:a])
        if gap != original[cursor:a]:
            raise ValueError('Hellbowz page/newline controls changed')
        segments.append(('gap', gap))
        if a == ADDRESS:
            parts = [normalize_text_segment(row, True, START) for row in rows]
            options = [b'\x72\x0a\x09'.join(parts)]
        else:
            part = bytes(rom[a:b])
            if any(x < 0x20 for x in part):
                raise ValueError('Hellbowz neighbouring row contains controls')
            parts = [normalize_text_segment(part, True, START)]
            options = [parts[0]]
            if fixed is not None and fixed(a):
                options.append(normalize_text_segment(fixed(a), True, START))
        for option in options:
            if any(text_segment_cells(p) * 4 > MAX_ROW_PIXELS for p in option.split(b'\x72\x0a\x09')):
                raise ValueError('Hellbowz row exceeds width')
        segments.append(('row', tuple(options)))
        cursor = b
    if bytes(rom[cursor:end]) != original[cursor:end]:
        raise ValueError('Hellbowz final page terminator changed')
    segments.append(('gap', original[cursor:end]))
    return tuple(segments)


def match_payload(data, segments):
    """Length of data matched by the segment contract, or raise."""
    pos = 0
    for kind, value in segments:
        if kind == 'gap':
            if data[pos:pos + len(value)] != value:
                raise ValueError(f'Hellbowz controls mismatch at +{pos}: {data[pos:pos + 12].hex()}')
            pos += len(value)
        else:
            for option in value:
                if data[pos:pos + len(option)] == option:
                    pos += len(option)
                    break
            else:
                raise ValueError(f'Hellbowz row mismatch at +{pos}: {data[pos:pos + 16].hex()} '
                                 f'expected one of {[o[:16].hex() for o in value]}')
    return pos


def verify(rom, original, segments, encode):
    """After repoint: final 0x19 command, bounded aligned allocation, complete message."""
    from sprite_relocations import SPRITE_STORAGE_START
    rows = layout(original, encode)[ADDRESS]
    if bytes(rom[POINTER - 4:POINTER]) != b'\x19\0\0\0':
        raise ValueError('Hellbowz final command opcode changed')
    target = struct.unpack_from('<I', rom, POINTER)[0] - 0x08000000
    if target == START or target % 4 or not 0xA3D000 <= target < SPRITE_STORAGE_START:
        raise ValueError('Hellbowz ending requires bounded aligned relocation')
    length = match_payload(bytes(rom[target:SPRITE_STORAGE_START]), segments)
    if target + length > SPRITE_STORAGE_START or rom[target + length - 1] != 0:
        raise ValueError('Hellbowz relocated message is unterminated or out of bounds')
    return {'status': 'PASS', 'target': hex(target), 'length': length, 'rows': list(ROWS),
            'row_pixels': [text_segment_cells(normalize_text_segment(r, True, START)) * 4 for r in rows],
            'live_pixels_verified': False}
