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
                or rows[0]['text'] != '그렇지　않습니다、선생님！'
                or not rows[0]['controls_understood']
                or tuple(j['left'] for j in rows[0]['same_row_joins']) != ('그렇지　않습니다、',)):
            raise ValueError('Teacher reassurance complete first-page context changed')
        reports.append({'source': hex(source), 'target': hex(target), 'first_page_text': rows[0]['text']})
    return {'status': 'PASS', 'messages': reports, 'native_consumer_verified': False,
            'pixels_verified': False, 'scope': 'source first-page text/control regression under 31424c interpretation'}


def verify(rom, original, manifest, syllable_codes):
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
    if controls(tokens) != controls(tokenize(old, **options)):
        raise ValueError('A199B0 source control sequence changed under 31424c interpretation')
    codes = {int(v, 16) if isinstance(v, str) else int(v): k
             for k, v in syllable_codes.items()}
    rows, unknown, terminated = assemble_rows(tokens, codes, 'story_layout_unverified', **options)
    actual = tuple((r['page'], r['line'], r['text']) for r in rows)
    if unknown or not terminated or actual != ROWS or any(not r['controls_understood'] for r in rows):
        raise ValueError('A199B0 complete context text changed')
    # Conditional parser interpretation: preserve source join positions.
    # This does not establish the actual A199B0 consumer or its wait behavior.
    expected = (
        ('근데、', '근데、공중전의　이글、'),
        ('지상전의　한나가　합류하면、',),
        ('자、', '자、우리　나라를、'),
    )
    if tuple(tuple(j['left'] for j in r['same_row_joins']) for r in rows) != expected:
        raise ValueError('A199B0 source join positions changed under 31424c interpretation')
    return {'source': f'0x{SOURCE:08X}', 'target': f'0x{target:08X}',
            'payload_sha256': hashlib.sha256(payload).hexdigest(),
            'native_consumer_verified': False, 'pixels_verified': False,
            'scope': 'source text/control regression under 31424c interpretation; native consumer unverified; pixels unverified'}
