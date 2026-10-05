"""Source-bound semantic regression; native consumer and pixels remain unverified."""
import hashlib
import struct

import part2_native_controls as NC
from qa_part2_physical_rows import tokenize, assemble_rows
from sprite_relocations import SPRITE_STORAGE_START

CASES = (
    (0xA1D444, 0xA36EF8, 92,
     '17e7a1f754f17bd6f79dd5a48c6d8bef788990255e24b0c64774172f5c142598',
     ('그렇군。결국은、자신을　위한　얘기인가。',
      '위험하다느니　어쩐다느니　걱정하는　척하면서。')),
    (0xA1D4BC, 0xA36F00, 80,
     'de0d04a8d3bc2d934db6107411bcf5a3a75633565a241c7f75a37f6f12d12bbb',
     ('내　작전에　참견하고　싶다면、우선은', '주어진　전력으로　승리해　보여라。')),
)


def verify(rom, original, manifest, syllable_codes):
    options = dict(consumer=NC.CONSUMER, native_profile=NC.NativeProfile(rom))
    codes = {int(v, 16) if isinstance(v, str) else int(v): k
             for k, v in syllable_codes.items()}
    reports = []
    for source, pointer, size, digest, expected in CASES:
        old = bytes(original[source:source + size])
        if (hashlib.sha256(old).hexdigest() != digest
                or struct.unpack_from('<I', original, pointer)[0] != source + 0x08000000):
            raise ValueError('Volcano original source/pointer changed')
        matches = [m for m in manifest if int(m['msg'], 16) == source]
        if len(matches) > 1:
            raise ValueError('Duplicate volcano manifest entry')
        target, length = source, size
        if matches and matches[0]['status'] == 'relocated':
            m = matches[0]
            target, length = int(m['new_addr'], 16), m['new_len']
            if (m['old_len'] != size or int(m['ptr_off'], 16) != pointer
                    or type(length) is not int or not 0 < length <= 512 or target % 4
                    or not 0xA3D000 <= target < target + length <= SPRITE_STORAGE_START):
                raise ValueError('Volcano relocation ownership changed')
        if source == 0xA1D444 and target == source:
            raise ValueError('Overlength self-interest context must be relocated')
        if struct.unpack_from('<I', rom, pointer)[0] != target + 0x08000000:
            raise ValueError('Volcano final pointer changed')
        tokens = tokenize(bytes(rom[target:target + length]), **options)
        controls = lambda ts: [t['raw'] for t in ts
                              if t['kind'] in ('same_row', 'newline', 'page', 'end')]
        if controls(tokens) != controls(tokenize(old, **options)):
            raise ValueError('Volcano native control sequence changed')
        rows, unknown, terminated = assemble_rows(tokens, codes, 'story_layout_unverified', **options)
        actual = tuple(r['text'].strip('　 ') for r in rows)
        if (unknown or not terminated or actual != expected
                or tuple((r['page'], r['line']) for r in rows) != ((0, 0), (0, 1))
                or any(not r['controls_understood'] for r in rows)):
            raise ValueError('Volcano complete context changed: ' + repr(actual))
        joins = tuple(tuple(j['left'] for j in r['same_row_joins']) for r in rows)
        expected_joins = ((('그렇군。', '그렇군。결국은、', expected[0], expected[0]), ())
                          if source == 0xA1D444 else (('내　작전에　참견하고　싶다면、',), ()))
        if joins != expected_joins:
            raise ValueError('Volcano text-relative wait positions changed')
        reports.append({'source': hex(source), 'target': hex(target), 'rows': actual})
    return {'status': 'PASS', 'messages': reports, 'native_consumer_verified': False,
            'pixels_verified': False,
            'scope': 'source text/control/wait regression under 31424c interpretation; native consumer and pixels unverified'}
