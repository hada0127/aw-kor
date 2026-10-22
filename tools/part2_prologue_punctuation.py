"""The approved Japanese-punctuation exception for the Part 2 prologue.

All edits are two-byte replacements in already rendered Korean script.  The
source row and old bytes are checked before writing, so no translation wording
or control byte can change through this path.
"""

from __future__ import annotations

# (source row, source-row byte offset, original SJIS punctuation).  Rows with
# ``relocated`` are resolved through the final dialogue manifest; the others
# retain their original ROM addresses.  The two adjacent in-place messages at
# A01A2C/A01A5C are deliberately kept out of the relocation mechanism.
PUNCTUATION = (
    (0xA01970, 24, '、', True),
    (0xA01994, 12, '。', True),
    (0xA019AB, 8, '、', True),
    (0xA01A1A, 10, '。', True),
    (0xA01A2C, 26, '、', False),
    (0xA01A5C, 16, '、', False),
    (0xA01A70, 28, '。', False),
    (0xA01A94, 6, '、', False),
    (0xA01B08, 2, '。', False),
    (0xA01B21, 24, '、', False),
    (0xA01B3F, 36, '。', False),
    (0xA01B7B, 6, '。', False),
    (0xA01B88, 12, '。', False),
    (0xA01B98, 26, '。', True),
    (0xA01BA9, 22, '、', True),
    (0xA01BBD, 20, '。', True),
    (0xA01C10, 8, '、', False),
    (0xA01C1B, 10, '。', False),
    (0xA01C2A, 26, '。', False),
    (0xA01C59, 18, '。', False),
    (0xA01C78, 14, '。', True),
)

# These three commas are followed by more text on the same physical row.
# A bare 0x20 is swallowed by the native parser; 0x8140 advances visibly.
SAME_ROW_COMMAS = (0xA019AB, 0xA01A94, 0xA01C10)


def _insert_drawn_space(rom: bytearray, manifest: list[dict], writes: list[list],
                        source: int, comma: int) -> None:
    if source == 0xA019AB:
        message = next(m for m in manifest if m.get('msg') == '0xA01970'
                       and m.get('status') == 'relocated')
        start, size = int(message['new_addr'], 16), message['new_len']
    else:
        start = source
        end = rom.index(0, start) + 1
        size = end - start
        message = None
    old = bytes(rom[start:start + size])
    offset = comma + 2 - start
    tail = b'\x6b\x00' if old.endswith(b'\x6b\x00') else b'\x00'
    pad_end = size - len(tail)
    if (old[offset:offset + 1] != b'\x77'
            or old[pad_end - 2:pad_end] != b'\x20\x20'
            or old[pad_end:] != tail):
        raise AssertionError(f'prologue comma seam/padding changed: {source:#x}')
    new = old[:offset] + b'\x81\x40' + old[offset:pad_end - 2] + tail
    if len(new) != size or new[offset:offset + 3] != b'\x81\x40\x77':
        raise AssertionError(f'prologue space changed message size: {source:#x}')
    rom[start:start + size] = new
    if message is not None:
        # Preserve each source fragment's authored bytes; the new cell sits
        # between the comma fragment and the following wait control.
        for key, spans in message['source_line_fragments'].items():
            for span in spans:
                if offset <= span[0] < pad_end - 2:
                    span[0] += 2
                elif span[0] < offset < span[0] + span[1]:
                    raise AssertionError(f'prologue space splits source fragment: {key}')
            message['line_spans'][key] = spans[0]
        for owner in writes:
            if owner[7] != 'dialogue-spacing-final-intent' or len(owner) < 9:
                continue
            key = f"0x{owner[8]['source_address']:06X}"
            spans = message['source_line_fragments'].get(key)
            if spans is None:
                continue
            lo = spans[0][0]
            hi = max(pos + length for pos, length in spans)
            owner[0], owner[1], owner[2] = start + lo, hi - lo, hi - lo
            owner[3] = new[lo:hi].hex()
            owner[8]['fragments'] = [span.copy() for span in spans]
        writes.append([start, size, size, new.hex(), None, None, None,
                       'part2-prologue-drawn-comma-space', {'source_address': source}])
    else:
        # In-place lines may have separate old writers. A final whole-message
        # owner keeps the shifted control/space sequence atomic for renderer QA.
        writes.append([start, size, size, new.hex(), None, None, None,
                       'part2-prologue-drawn-comma-space', {'source_address': source}])


def patch(rom: bytearray, manifest: list[dict], writes: list[list]) -> list[dict]:
    live = {int(key, 16): m for m in manifest if m.get('status') == 'relocated'
            for key in m.get('line_spans', {})}
    edits = []
    for source, offset, old, relocated in PUNCTUATION:
        if relocated:
            message = live.get(source)
            if message is None:
                raise AssertionError(f'prologue source {source:#x} is no longer relocated')
            key = f'0x{source:X}'
            spans = message.get('line_spans', {})
            if key not in spans or offset + 2 > spans[key][1]:
                raise AssertionError(f'prologue source span changed: {key}')
            target = int(message['new_addr'], 16) + spans[key][0] + offset
        else:
            target = source + offset
        expected = old.encode('shift_jis')
        # The Part 2 script parser rejects ASCII 0x2C/0x2E as commands.
        # Western punctuation uses one two-byte glyph cell, preserving all
        # line breaks and the native spacing budget.
        replacement = '，'.encode('shift_jis') if old == '、' else '．'.encode('shift_jis')
        if bytes(rom[target:target + 2]) != expected:
            raise AssertionError(f'prologue punctuation changed at {source:#x} / {target:#x}')
        edits.append((source, target, expected, replacement))
    if len({target for _, target, _, _ in edits}) != len(edits):
        raise AssertionError('overlapping prologue punctuation edits')
    relocated_sources = {source for source, _, _, relocated in PUNCTUATION if relocated}
    for source, target, old, new in edits:
        rom[target:target + 2] = new
        if source in relocated_sources:
            # Relocated source rows are audited through the manifest's exact
            # line spans; a final two-byte write records the replacement.
            writes.append([target, 2, 2, new.hex(), None,
                           f'{old.decode("shift_jis")} → {new.decode("shift_jis")}',
                           None, 'part2-prologue-approved-punctuation',
                           {'source_address': source, 'old_hex': old.hex()}])
        else:
            # Keep the original whole-message owner intact.  A separate
            # two-byte owner would split the native 0x77/0x72 command pair
            # between adjacent prologue lines in qa_renderer_text.
            owner = next((row for row in reversed(writes)
                          if row[3] and row[0] <= target and
                          target + 2 <= row[0] + len(bytes.fromhex(row[3])) and
                          bytes.fromhex(row[3])[target - row[0]:target - row[0] + 2] == old), None)
            if owner is None:
                raise AssertionError(f'prologue in-place writer missing at {source:#x}')
            raw = bytearray.fromhex(owner[3])
            raw[target - owner[0]:target - owner[0] + 2] = new
            owner[3] = raw.hex()
            if isinstance(owner[5], str):
                owner[5] = owner[5].replace('、', '，').replace('。', '．')
    for source in SAME_ROW_COMMAS:
        comma = next(target for current, target, _, _ in edits if current == source)
        _insert_drawn_space(rom, manifest, writes, source, comma)
    # The last in-place message gained a two-byte drawn space after A01C10.
    # Its subsequent punctuation moved by two bytes within the same slot.
    return [{'source': f'0x{source:08X}',
             'target': f'0x{target + (2 if source in (0xA01C1B, 0xA01C2A, 0xA01C59) else 0):08X}',
             'before_hex': old.hex(), 'after_hex': new.hex()}
            for source, target, old, new in edits]
