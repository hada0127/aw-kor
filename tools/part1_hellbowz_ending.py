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


def _pages(payload):
    """Native control skeleton per page (split after each 6B page control).

    Text = SJIS pairs; 0x20 is padding (ignored); every other byte is a
    control, kept in order.
    """
    pages, current, text, i = [], [], [], 0
    texts = []
    while i < len(payload):
        b = payload[i]
        if 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xEF:
            if not current or current[-1] != 'T':
                current.append('T')
            text.append(payload[i:i + 2])
            i += 2
            continue
        if text:
            texts.append(b''.join(text))
            text = []
        if b != 0x20:
            current.append(f'{b:02x}')
            if b == 0x6B:
                pages.append(current)
                current = []
        i += 1
    if text:
        texts.append(b''.join(text))
    pages.append(current)
    return [' '.join(page) for page in pages], texts


def _page_of_row(segments):
    """Index of the page holding ADDRESS's row in the contract skeleton."""
    raw = bytearray()
    for kind, value in segments:
        if kind == 'row' and b'\x72\x0a\x09' in value[0]:
            return len(_pages(bytes(raw))[0]) - 1
        raw += value if kind == 'gap' else value[0]
    raise ValueError('Hellbowz two-row segment missing')


def _contract_pages(segments):
    raw = b''.join(value if kind == 'gap' else value[0] for kind, value in segments)
    return _pages(raw)[0]


def _check_two_rows(page_skeleton, payload, page_index):
    """The documented split: one 72 0A 09 inside the page, both rows <= 176px."""
    if page_skeleton.split().count('72') != 1 or '72 0a 09' not in page_skeleton:
        raise ValueError('Hellbowz two-row split changed')
    start = 0
    for _ in range(page_index):
        start = _next_page(payload, start)
    end = _next_page(payload, start)
    _, texts = _pages(payload[start:end])
    if len(texts) != 2 or any(text_segment_cells(t) * 4 > MAX_ROW_PIXELS for t in texts):
        raise ValueError('Hellbowz two-row text/width invalid')
    return [text_segment_cells(t) * 4 for t in texts]


def _next_page(payload, start):
    i = start
    while i < len(payload):
        b = payload[i]
        if 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xEF:
            i += 2
        elif b == 0x6B:
            return i + 1
        else:
            i += 1
    return len(payload)


def _sha(raw):
    import hashlib
    return hashlib.sha256(raw).hexdigest()


def _fold(text):
    import unicodedata
    return unicodedata.normalize('NFKC', text).replace(' ', '')


def verify(rom, original, segments, encode, *, spacing=None, rewrite=None, before=None):
    """After repoint: final 0x19 command, bounded aligned allocation, complete message.

    Stages (each an established, reviewed representation of this message):
    - spacing None: pre-spacing state, exactly ``segments``.
    - spacing = data/dialogue_spacing_repairs.json entry for START, before=None:
      after the reviewed spacing reflow. Payload must be that entry's
      ``after_sha256``; every page the entry does not review keeps the
      contract's native control skeleton; the two-row page keeps its split.
    - before = this function's pre-overlay report: after the W3 overlay. With
      a rewrite entry for START the payload must be its ``after_sha256`` and
      chain from the pre-overlay payload; without one it must be unchanged.
      Either way the complete control skeleton equals the pre-overlay one
      and the two-row split/width invariant still holds.
    """
    from sprite_relocations import SPRITE_STORAGE_START
    rows = layout(original, encode)[ADDRESS]
    if bytes(rom[POINTER - 4:POINTER]) != b'\x19\0\0\0':
        raise ValueError('Hellbowz final command opcode changed')
    target = struct.unpack_from('<I', rom, POINTER)[0] - 0x08000000
    if target == START or target % 4 or not 0xA3D000 <= target < SPRITE_STORAGE_START:
        raise ValueError('Hellbowz ending requires bounded aligned relocation')
    if spacing is not None:
        return _verify_reviewed(rom, segments, rows, target, SPRITE_STORAGE_START,
                                spacing, rewrite, before)
    length = match_payload(bytes(rom[target:SPRITE_STORAGE_START]), segments)
    if target + length > SPRITE_STORAGE_START or rom[target + length - 1] != 0:
        raise ValueError('Hellbowz relocated message is unterminated or out of bounds')
    return {'status': 'PASS', 'target': hex(target), 'length': length, 'rows': list(ROWS),
            'row_pixels': [text_segment_cells(normalize_text_segment(r, True, START)) * 4 for r in rows],
            'live_pixels_verified': False}


def _verify_reviewed(rom, segments, rows, target, limit, spacing, rewrite, before):
    try:
        end = rom.index(0, target, limit)
    except ValueError:
        raise ValueError('Hellbowz relocated message is unterminated or out of bounds') from None
    payload = bytes(rom[target:end + 1])
    pages, _ = _pages(payload)
    row_page = _page_of_row(segments)
    if int(spacing['source'], 16) != START or spacing.get('profile') != 'p1_portrait':
        raise ValueError('Hellbowz spacing ledger entry does not own the message')
    reviewed = {page['page'] for page in spacing['pages']}
    final_pages = spacing['final_pages']
    if (row_page in reviewed or row_page >= len(final_pages)
            or [_fold(t) for t in final_pages[row_page]] != [_fold(t) for t in ROWS]):
        raise ValueError('Hellbowz spacing ledger is not bound to the two-row contract')
    if before is None:
        if _sha(payload) != spacing['after_sha256']:
            raise ValueError('Hellbowz payload differs from the reviewed spacing result')
        expected = _contract_pages(segments)
        if len(pages) != len(expected) or any(
                a != b for i, (a, b) in enumerate(zip(pages, expected)) if i not in reviewed):
            raise ValueError('Hellbowz page/newline controls changed outside reviewed spacing')
    else:
        if before.get('stage') != 'spacing' or before.get('target') != hex(target):
            raise ValueError('Hellbowz pre-overlay report missing or relocated')
        wanted = before['payload_sha256']
        if rewrite is not None:
            if int(rewrite['source'], 16) != START or rewrite['before_sha256'] != wanted:
                raise ValueError('Hellbowz rewrite does not chain from the pre-overlay payload')
            wanted = rewrite['after_sha256']
        if _sha(payload) != wanted:
            raise ValueError('Hellbowz payload differs from the reviewed overlay result')
        if pages != before['controls']:
            raise ValueError('Hellbowz native controls changed through the overlay')
    widths = _check_two_rows(pages[row_page], payload, row_page)
    return {'status': 'PASS', 'target': hex(target), 'length': len(payload),
            'stage': 'spacing' if before is None else 'overlay',
            'payload_sha256': _sha(payload), 'controls': pages,
            'rewritten': rewrite is not None and before is not None,
            'row_pixels': widths, 'live_pixels_verified': False}
