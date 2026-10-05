"""Fail closed for individually observed portrait dialogue repairs.

This verifies text/control contracts, not pixels or campaign coverage.
Consumer evidence and screenshots are recorded in docs/research.md.
"""
import hashlib
import struct

import part2_native_controls as NC
from qa_part2_physical_rows import tokenize, assemble_rows
from sprite_relocations import SPRITE_STORAGE_START


CONTRACTS = {
    0xA1F944: {
        'pointer': 0xA37170, 'old_len': 104,
        'source_sha256': 'bdd8fb5cd2e0cf5fe7d94a9f0488883ea3f254fb898bbb15ddd4a499c05cbbaf',
        'rows': ('・・・하지만、그렇게도　말할　수', '없게　된　모양이구나、　키쿠치요여。'),
        'first_row_wait_prefixes': ('・・・하지만、', '・・・하지만、그렇게도　말할　수'),
    },
    0xA1F9D8: {
        'pointer': 0xA37178, 'old_len': 124,
        'source_sha256': '4efb344a31e4d2734954e43934365b0eb16a72a2b58b5ebac87d1059aa2762cc',
        'rows': ('사령관이　３명　있으면　상황에　따른', '작전　행동을　기대할　수　있어요！'),
        'first_row_wait_prefixes': ('사령관이　３명　있으면　상황에　따른',),
    },
}


def verify(rom, original, manifest, syllable_codes, *, contracts=None):
    """Require the actual native pointer to own each complete repaired message."""
    contracts = CONTRACTS if contracts is None else contracts
    profile = NC.NativeProfile(rom)
    options = dict(consumer=NC.CONSUMER, native_profile=profile)
    codes = {int(v, 16) if isinstance(v, str) else int(v): k
             for k, v in syllable_codes.items()}
    report = []
    for source, contract in contracts.items():
        matches = [m for m in manifest if int(m['msg'], 16) == source]
        if len(matches) != 1 or matches[0]['status'] != 'relocated':
            raise ValueError(f'Dialogue layout repair not relocated: {source:#x}')
        m = matches[0]
        pointer = contract['pointer']
        original_payload = bytes(original[source:source + contract['old_len']])
        if (hashlib.sha256(original_payload).hexdigest() != contract['source_sha256']
                or struct.unpack_from('<I', original, pointer)[0] != 0x08000000 + source
                or int(m['ptr_off'], 16) != pointer or m['old_len'] != contract['old_len']):
            raise ValueError(f'Dialogue layout source contract changed: {source:#x}')
        target, length = int(m['new_addr'], 16), m['new_len']
        if (type(length) is not int or not 0 < length <= 512 or target % 4
                or not 0xA3D000 <= target < target + length <= SPRITE_STORAGE_START
                or struct.unpack_from('<I', rom, pointer)[0] != 0x08000000 + target):
            raise ValueError(f'Dialogue layout target contract changed: {source:#x}')
        payload = bytes(rom[target:target + length])
        tokens = tokenize(payload, **options)
        controls = lambda ts: [t['raw'] for t in ts
                              if t['kind'] in ('same_row', 'newline', 'page', 'end')]
        if controls(tokens) != controls(tokenize(original_payload, **options)):
            raise ValueError(f'Dialogue layout native controls changed: {source:#x}')
        rows, unknown, terminated = assemble_rows(tokens, codes, 'story_layout_unverified', **options)
        page = [row for row in rows if row['page'] == 1]
        if (unknown or not terminated or len(page) != 2
                or tuple(row['text'] for row in page) != contract['rows']
                or tuple(join['left'] for join in page[0]['same_row_joins']) != contract['first_row_wait_prefixes']
                or page[1]['same_row_joins']
                or any(not row['controls_understood'] or row['half_cells'] > 44 for row in page)):
            raise ValueError(f'Dialogue layout complete text/rows changed: {source:#x}')
        report.append({'source': f'0x{source:08X}', 'target': f'0x{target:08X}',
                       'payload_sha256': hashlib.sha256(payload).hexdigest(),
                       'row_half_cells': [row['half_cells'] for row in page]})
    return report
