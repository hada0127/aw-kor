"""A199B0 source regression under the 31424c parser interpretation.

NativeProfile checks parser bytecode compatibility only. No per-message trace
proves that A199B0 uses this consumer; neither consumer nor pixels are approved.
"""
import hashlib
import struct

import part2_native_controls as NC
from qa_part2_physical_rows import tokenize, assemble_rows
from sprite_relocations import SPRITE_STORAGE_START

SOURCE = 0xA199B0
POINTER = 0xA36B44
OLD_LEN = 128
SOURCE_SHA = '6feb973d37c2333f345b1a5d492c4f105a680c2ee601f3aa7d16c89292fe269d'
ROWS = (
    (0, 0, '근데、공중전의　이글、해상전의　나에게'),
    (0, 1, '지상전의　한나가　합류하면、두려울　게　없다。'),
    (1, 0, '자、우리　나라를、되찾자！'),
)

TEACHER_SOURCES = (
    (0xA21840, 0xA37310, 192, '802d1b626ad80408f477595fb71cb94fba1859525c867fb1fc0f5806d634c827', 0xA2185B),
    (0xA21990, 0xA3731C, 116, '3aed3151b70be1891a0b5db36113ac5a7a52fea443904c6a2e80011f36da3118', 0xA219AB),
)


# plan_C B-pin reviewed wording (2026-11-04 user, tools/bpin_contract.py).
TEACHER_FIRST_PAGE = '그렇지　않습니다、　선생님！'
# A199B0 final rows/joins after the B-pin writer replaced the reviewed
# pixel-layout re-wrap (late stage); ROWS above stay the source authority the
# layout repair is bound to.
FINAL_ROWS = (
    (0, 0, '근데、　공중전의　이글과　해상전의'),
    (0, 1, '나에게　지상전의　한나가'),
    (1, 0, '합류하면　두려울　게　없어。'),
    (2, 0, '자、　우리　나라를　되찾자！'),
)
FINAL_JOINS = (('근데、', '근데、　공중전의　이글과'), (), ('합류하면',), ('자、', '자、　우리　나라를'))


def _fold(text):
    """Wording signature: every space (incl. U+3000) removed."""
    return ''.join(text.split())


def layout_rows(source, rows, layout_repairs):
    """Expected final rows when a reviewed pixel-layout repair owns ``source``.

    ``rows`` are the contract's ((page, line, text), ...) before the layout
    stage. dialogue_pixel_layout.apply_repairs re-wraps a reviewed page into its
    ledger ``after`` rows (``rows_per_page`` rows per native page, keeping the
    allocation). Returns None when no repair owns the source. The repair must
    be bound to the contract text and must not change its wording.
    """
    specs = [s for s in layout_repairs or () if int(s['source'], 16) == source]
    if not specs:
        return None
    if len(specs) != 1:
        raise ValueError(f'{source:#x}: duplicate layout repair')
    spec = specs[0]
    per = spec.get('rows_per_page')
    if spec.get('game') != 'p2' or spec.get('profile') != 'p2_portrait' or type(per) is not int or per < 1:
        raise ValueError(f'{source:#x}: layout repair profile changed')
    reviewed = {}
    for page in spec['pages']:
        if page['page'] in reviewed:
            raise ValueError(f'{source:#x}: duplicate layout repair page')
        reviewed[page['page']] = page
    pages = sorted({page for page, _, _ in rows})
    if not set(reviewed) <= set(pages):
        raise ValueError(f'{source:#x}: layout repair page outside the contract')
    out, number = [], 0
    for page in pages:
        texts = [text for p, _, text in rows if p == page]
        if page in reviewed:
            before, after = list(reviewed[page]['before']), list(reviewed[page]['after'])
            if [t.strip('\u3000 ') for t in before] != [t.strip('\u3000 ') for t in texts]:
                raise ValueError(f'{source:#x}: layout repair is not bound to the contract text')
            if not after or _fold(''.join(after)) != _fold(''.join(texts)):
                raise ValueError(f'{source:#x}: layout repair changes wording')
            chunks = [after[i:i + per] for i in range(0, len(after), per)]
        else:
            chunks = [texts]
        for chunk in chunks:
            out.extend((number, line, text) for line, text in enumerate(chunk))
            number += 1
    return tuple(out)


def check_layout_representation(tokens, rows, expected_rows, source_rows, source_joins, label):
    """Final-state contract for a reviewed re-wrap (layout_rows).

    Rows/pages must be exactly the reviewed layout; every wait keeps its byte
    and its position relative to the (space-free) wording; the only row/page
    controls are those the layout needs; the message stays terminated.
    """
    actual = tuple((r['page'], r['line'], r['text'].strip('\u3000 ')) for r in rows)
    wanted = tuple((p, l, t.strip('\u3000 ')) for p, l, t in expected_rows)
    if actual != wanted or any(not r['controls_understood'] for r in rows):
        raise ValueError(f'{label} reviewed layout rows changed: {actual!r}')

    def waits(row_texts, row_joins):
        out, base = [], 0
        for text, joins in zip(row_texts, row_joins):
            out.extend(base + len(_fold(left)) for left in joins)
            base += len(_fold(text))
        return out

    final = waits([r['text'] for r in rows], [[j['left'] for j in r['same_row_joins']] for r in rows])
    if final != waits([t for _, _, t in source_rows], source_joins):
        raise ValueError(f'{label} text-relative wait positions changed')
    kinds = [t['kind'] for t in tokens]
    source_waits = [t['raw'] for t in tokens if t['kind'] == 'same_row']
    pages = len({p for p, _, _ in expected_rows})
    if (len(source_waits) != sum(len(j) for j in source_joins)
            or kinds.count('page') != pages
            or kinds.count('newline') != len(expected_rows) - pages
            or kinds.count('end') != 1 or kinds[-1] != 'end'):
        raise ValueError(f'{label} native control sequence changed under reviewed layout')
    return source_waits


def verify_teacher_context(rom, original, manifest, syllable_codes):
    """Source-bound first-page regression; no native-consumer/pixel approval."""
    options = dict(consumer=NC.CONSUMER, native_profile=NC.NativeProfile(rom))
    codes = {int(v, 16) if isinstance(v, str) else int(v): k
             for k, v in syllable_codes.items()}
    reports = []
    for source, pointer, old_len, digest, teacher in TEACHER_SOURCES:
        matches = [m for m in manifest if int(m['msg'], 16) == source]
        if len(matches) != 1 or matches[0]['status'] != 'relocated':
            raise ValueError('Teacher reassurance must be relocated exactly once')
        m = matches[0]
        old = bytes(original[source:source + old_len])
        if (hashlib.sha256(old).hexdigest() != digest
                or struct.unpack_from('<I', original, pointer)[0] != 0x08000000 + source
                or int(m['ptr_off'], 16) != pointer or m['old_len'] != old_len):
            raise ValueError('Teacher reassurance original context changed')
        target, length = int(m['new_addr'], 16), m['new_len']
        if (type(length) is not int or not 0 < length <= 512 or target % 4
                or not 0xA3D000 <= target < target + length <= SPRITE_STORAGE_START
                or struct.unpack_from('<I', rom, pointer)[0] != 0x08000000 + target
                or rom[teacher:teacher + 6] != original[teacher:teacher + 6]):
            raise ValueError('Teacher reassurance relocation/overlength source ownership changed')
        payload = bytes(rom[target:target + length])
        tokens = tokenize(payload, **options)
        controls = lambda ts: [t['raw'] for t in ts
                              if t['kind'] in ('same_row', 'newline', 'page', 'end')]
        if controls(tokens) != controls(tokenize(old, **options)):
            raise ValueError('Teacher reassurance source controls changed')
        page = next((t['offset'] for t in tokens if t['kind'] == 'page'), None)
        if page is None:
            raise ValueError('Teacher reassurance first page boundary missing')
        first = tokenize(payload[:page] + b'\0', **options)
        rows, unknown, terminated = assemble_rows(first, codes, 'story_layout_unverified', **options)
        if (unknown or not terminated or len(rows) != 1
                or rows[0]['text'] != TEACHER_FIRST_PAGE
                or not rows[0]['controls_understood']
                or tuple(j['left'] for j in rows[0]['same_row_joins']) != ('그렇지　않습니다、',)):
            raise ValueError('Teacher reassurance complete first-page context changed')
        reports.append({'source': hex(source), 'target': hex(target), 'first_page_text': rows[0]['text']})
    return {'status': 'PASS', 'messages': reports, 'native_consumer_verified': False,
            'pixels_verified': False, 'scope': 'source first-page text/control regression under 31424c interpretation'}


def verify(rom, original, manifest, syllable_codes, layout_repairs=None):
    """``layout_repairs``: the reviewed pixel-layout ledger once that stage ran.

    None = pre-layout state (source controls/rows exactly). Given, a ledger
    entry for SOURCE requires its reviewed re-wrap instead (layout_rows).
    """
    matches = [m for m in manifest if int(m['msg'], 16) == SOURCE]
    if len(matches) != 1 or matches[0]['status'] != 'relocated':
        raise ValueError('A199B0 context repair must be relocated exactly once')
    m = matches[0]
    old = bytes(original[SOURCE:SOURCE + OLD_LEN])
    if (hashlib.sha256(old).hexdigest() != SOURCE_SHA
            or struct.unpack_from('<I', original, POINTER)[0] != 0x08000000 + SOURCE
            or int(m['ptr_off'], 16) != POINTER or m['old_len'] != OLD_LEN):
        raise ValueError('A199B0 original context contract changed')
    target, length = int(m['new_addr'], 16), m['new_len']
    if (type(length) is not int or not 0 < length <= 512 or target % 4
            or not 0xA3D000 <= target < target + length <= SPRITE_STORAGE_START
            or struct.unpack_from('<I', rom, POINTER)[0] != 0x08000000 + target):
        raise ValueError('A199B0 relocated context ownership changed')
    options = dict(consumer=NC.CONSUMER, native_profile=NC.NativeProfile(rom))
    payload = bytes(rom[target:target + length])
    tokens = tokenize(payload, **options)
    controls = lambda ts: [t['raw'] for t in ts
                          if t['kind'] in ('same_row', 'newline', 'page', 'end')]
    codes = {int(v, 16) if isinstance(v, str) else int(v): k
             for k, v in syllable_codes.items()}
    # Conditional parser interpretation: preserve source join positions.
    # This does not establish the actual A199B0 consumer or its wait behavior.
    expected = (
        ('근데、', '근데、공중전의　이글、'),
        ('지상전의　한나가　합류하면、',),
        ('자、', '자、우리　나라를、'),
    )
    reflowed = layout_rows(SOURCE, ROWS, layout_repairs)
    import bpin_contract
    if SOURCE in bpin_contract.MESSAGES and (m.get('rewrite') or {}).get('bpin'):
        # Final state: the B-pin writer owns the whole message in its allocation.
        # Native control kinds stay those of the message it replaced; every wait
        # keeps its original byte; rows/joins are the reviewed final wording.
        replaced = bytes.fromhex(bpin_contract.MESSAGES[SOURCE]['old'])
        rows, unknown, terminated = assemble_rows(tokens, codes, 'story_layout_unverified', **options)
        if (unknown or not terminated or any(not r['controls_understood'] for r in rows)
                or tuple((r['page'], r['line'], r['text']) for r in rows) != FINAL_ROWS
                or tuple(tuple(j['left'] for j in r['same_row_joins']) for r in rows) != FINAL_JOINS):
            raise ValueError('A199B0 reviewed final context text changed')
        if (controls(tokens) != controls(tokenize(replaced, **options))
                or [t['raw'] for t in tokens if t['kind'] == 'same_row']
                != [t['raw'] for t in tokenize(old, **options) if t['kind'] == 'same_row']):
            raise ValueError('A199B0 source control sequence changed under 31424c interpretation')
        return {'source': f'0x{SOURCE:08X}', 'target': f'0x{target:08X}',
                'payload_sha256': hashlib.sha256(payload).hexdigest(), 'layout': 'bpin_reviewed_final',
                'native_consumer_verified': False, 'pixels_verified': False,
                'scope': 'reviewed final text/control regression under 31424c interpretation; native consumer unverified; pixels unverified'}
    if reflowed is not None:
        rows, unknown, terminated = assemble_rows(tokens, codes, 'story_layout_unverified', **options)
        if unknown or not terminated:
            raise ValueError('A199B0 complete context text changed')
        waits = check_layout_representation(tokens, rows, reflowed, ROWS, expected, 'A199B0')
        if waits != [t['raw'] for t in tokenize(old, **options) if t['kind'] == 'same_row']:
            raise ValueError('A199B0 source control sequence changed under 31424c interpretation')
        return {'source': f'0x{SOURCE:08X}', 'target': f'0x{target:08X}',
                'payload_sha256': hashlib.sha256(payload).hexdigest(), 'layout': 'reviewed_pixel_layout',
                'native_consumer_verified': False, 'pixels_verified': False,
                'scope': 'source text/control regression under 31424c interpretation (reviewed layout re-wrap); native consumer unverified; pixels unverified'}
    if controls(tokens) != controls(tokenize(old, **options)):
        raise ValueError('A199B0 source control sequence changed under 31424c interpretation')
    rows, unknown, terminated = assemble_rows(tokens, codes, 'story_layout_unverified', **options)
    actual = tuple((r['page'], r['line'], r['text']) for r in rows)
    if unknown or not terminated or actual != ROWS or any(not r['controls_understood'] for r in rows):
        raise ValueError('A199B0 complete context text changed')
    if tuple(tuple(j['left'] for j in r['same_row_joins']) for r in rows) != expected:
        raise ValueError('A199B0 source join positions changed under 31424c interpretation')
    return {'source': f'0x{SOURCE:08X}', 'target': f'0x{target:08X}',
            'payload_sha256': hashlib.sha256(payload).hexdigest(),
            'native_consumer_verified': False, 'pixels_verified': False,
            'scope': 'source text/control regression under 31424c interpretation; native consumer unverified; pixels unverified'}
