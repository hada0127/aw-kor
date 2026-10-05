"""Part 1 unit-list compact unit names (종류 column) and the infinite-ammo mark.

Evidence (2026-10-06, play ROM ab9627..., state
output/qa/part1_2026-10-05/m20_claude/0053_A_0698792.ss0):

* The unit list loads three compact glyph dictionaries through the table at
  0xB12F5C (はいえ▼, 0xD82D48, 0xD82E1C).  BG0 row cells index a de-duplicated
  glyph cache built from those dictionaries, so a string can only show chars
  that occur in the loaded dictionary; missing codes draw as blank.
* Part 1 unit records at 0xD848B4.. hold the full name at +0 and a compact name
  at +4.  Natively the compact names are dictionary placeholder kanji
  (卦揖煎奢 = squeezed 軽戦車, ...).  The Korean build rewrote those slots with
  reserved Korean codes, which no compact dictionary contains, so the 종류
  column rendered blank.  patch_part2_ui_context_tokens() already rewrote the
  dictionaries to Korean-glyph placeholder kanji (軽戦車倶 -> 경전차); this
  module points the compact strings at those same placeholder codes.
* Three compact slots are shared with full-name/weapon fields (歩兵, ロケット砲,
  対空箕紗炒).  Their placeholder kanji resolve through the kanji table to the
  same FONT_BASE tiles that patch_part2_ui_kanji_glyphs() rendered with
  render_char(), which are byte-identical to the KOR_BASE glyphs of the reserved
  codes they replace, so normal-renderer consumers keep the same pixels.
* 夢弦 (0x83FF2C / 0xBE7130) is the native two-cell infinite-ammo symbol; its
  FONT_BASE tiles must stay original and 夢 must stay in the unit-list
  dictionaries (build_korean_full keeps it in the equipment padding).
"""
import struct

KANJI_TABLE = (0xB80B7C, 0xB8180C)
FONT_FILE = 0xB974D0
PAD = '倶'

# (record +4 pointer field, string address, native compact string, placeholder, Korean)
COMPACT_NAMES = (
    (0xD848B8, 0xB81B28, '歩兵', '歩兵', '보병'),
    (0xD8493C, 0xB81ACC, 'バズーカ兵', '船再外兵', '바주카병'),  # 航 slot is name-grid owned
    (0xD849C0, 0xB81AA0, '呪鵜煎奢', '重戦車', '중전차'),
    (0xD84AC8, 0xB81A6C, '卦揖煎奢', '軽戦車', '경전차'),
    (0xD84B4C, 0xB81A40, '邸鎖津奢', '定察車', '정찰차'),
    (0xD84BD0, 0xB81A14, '湯楚宇奢', '補給車', '보급차'),
    (0xD84D5C, 0xB819F4, '磁蘇卯鳳', '自走砲', '자주포'),
    (0xD84DE0, 0xB819C4, 'ロケット砲', '路編砲', '로켓포'),
    (0xD84F6C, 0xB81994, '鯛倶迂煎奢', '大空戦車', '대공전차'),
    (0xD84FF0, 0xB81970, '対空箕紗炒', '対空箕紗炒', '대공미사일'),
    (0xD85074, 0xB81950, '洗賭菟忌', '戦闘魯', '전투기'),
    (0xD850F8, 0xB8192C, '麦夏軌忌', '爆撃魯', '폭격기'),
    (0xD85200, 0xB81900, '洗賭羽屁璃', '戦闘芋魯', '전투헬기'),
    (0xD85284, 0xB818D0, '湯楚芋屁璃', '水送芋魯', '수송헬기'),
    (0xD85308, 0xB818C0, '洗寡牟', '戦艦', '전함'),
    (0xD8538C, 0xB81890, '娯餌亥癇', '娯餌艦', '호위함'),
    (0xD85410, 0xB81854, '湯楚得銭', '水送選', '수송선'),
    (0xD85494, 0xB81840, '腺酢維癇', '潜水艦', '잠수함'),
)

# Live dictionaries (pointer table 0xB12F60/0xB12F64/0xB12FC4) and their unreferenced
# Part 1 copies, which patch_part2_ui_context_tokens() keeps in sync.
DICTIONARIES = (0xD82D48, 0xD82E1C, 0xD82F30, 0x8055D4, 0x8056A8, 0x8057BC)
LIVE_POINTERS = ((0xB12F60, 0xD82D48), (0xB12F64, 0xD82E1C), (0xB12FC4, 0xD82F30))
# Weapon dictionaries (compact unit-info panel); the battle one is relocated by
# patch_part1_battle_dictionary(), so it is read through its live pointer.
WEAPON_DICTIONARIES = ((0xD82998, None), (0x805224, None), (0xD82A1C, 0xB12EE4))
# Other record fields that share a compact slot (full name +0 / weapon fields).
SHARED_FIELDS = (
    (0xD848B4, 0xB81B28, 'infantry full name'),
    (0xD84DDC, 0xB819C4, 'rocket full name'), (0xD84DE4, 0xB819C4, 'rocket weapon'),
    (0xD84FEC, 0xB81970, 'AA missile full name'), (0xD84FF4, 0xB81970, 'AA missile weapon'),
    (0xD85078, 0xB81970, 'fighter weapon 1'),
)
# Pad/duplicate cells replaced so the dictionaries also preload 수송/선 glyphs.
# (address, expected after context tokens, replacement)
DICTIONARY_EDITS = (
    (0xD82E16, '倶', '選'), (0x8056A2, '倶', '選'),          # unit list: tail pad
    (0xD82E9E, '倶芋', '水送'), (0x80572A, '倶芋', '水送'),  # unit list 2: tail pad + duplicate
    (0xD83012, '倶', '選'), (0x80589E, '倶', '選'),          # result status: 総数 pad
)
INFINITE_AMMO = '夢弦'
INFINITE_AMMO_SOURCES = (0x83FF2C, 0xBE7130)
INFINITE_AMMO_DICTIONARIES = (0xD82D48, 0xD82E1C, 0x8055D4, 0x8056A8)


def _sjis(text):
    return text.encode('shift_jis')


def _codes(raw):
    return [bytes(raw[i:i + 2]) for i in range(0, len(raw) - 1, 2)]


def dictionary_codes(rom, start):
    end = start
    while bytes(rom[end:end + 2]) != b'\0\0':
        end += 2
        if end - start > 0x200:
            raise AssertionError(f'unterminated compact dictionary at 0x{start:X}')
    return set(_codes(rom[start:end]))


def _kanji_slots(original):
    slots = {}
    for pos in range(*KANJI_TABLE, 6):
        sjis_le, top, bottom = struct.unpack_from('<HHH', original, pos)
        slots[bytes([sjis_le & 0xFF, sjis_le >> 8])] = (top, bottom)
    return slots


def _glyph(rom, slots, code):
    top, bottom = slots[code]
    return (bytes(rom[FONT_FILE + top * 32:FONT_FILE + top * 32 + 32]),
            bytes(rom[FONT_FILE + bottom * 32:FONT_FILE + bottom * 32 + 32]))


def validate_source(original):
    for field, address, native, _, _ in COMPACT_NAMES:
        if struct.unpack_from('<I', original, field)[0] != address + 0x08000000:
            raise AssertionError(f'unit compact-name pointer changed at 0x{field:X}')
        raw = _sjis(native)
        if bytes(original[address:address + len(raw) + 1]) != raw + b'\0':
            raise AssertionError(f'unit compact-name source changed at 0x{address:X}')
    for pointer, target in LIVE_POINTERS + tuple((p, t) for t, p in WEAPON_DICTIONARIES if p):
        if struct.unpack_from('<I', original, pointer)[0] != target + 0x08000000:
            raise AssertionError(f'compact dictionary pointer changed at 0x{pointer:X}')
    for field, target, _ in SHARED_FIELDS:
        if struct.unpack_from('<I', original, field)[0] != target + 0x08000000:
            raise AssertionError(f'shared compact-name field pointer changed at 0x{field:X}')
    for address in INFINITE_AMMO_SOURCES:
        if bytes(original[address:address + 6]) != _sjis(INFINITE_AMMO) + b'\0\0':
            raise AssertionError(f'infinite-ammo symbol source changed at 0x{address:X}')


def payloads():
    result = []
    for _, address, native, placeholder, korean in COMPACT_NAMES:
        slot = len(_sjis(native))
        raw = _sjis(placeholder)
        if len(raw) > slot or len(placeholder) != len(korean):
            raise AssertionError(f'unit compact name does not fit at 0x{address:X}')
        result.append((address, slot, raw + bytes(slot - len(raw)), korean))
    return tuple(result)


def _check_dictionary_edits(rom, *, applied):
    for address, before, after in DICTIONARY_EDITS:
        expected = _sjis(after if applied else before)
        if bytes(rom[address:address + len(expected)]) != expected:
            state = 'final' if applied else 'pre-patch'
            raise AssertionError(f'compact dictionary {state} bytes changed at 0x{address:X}')


def verify_semantics(rom, original, subs, render_char):
    """Each compact name must be loadable by every dictionary that natively carried it,
    and its placeholder glyphs must be exactly the intended Korean syllables."""
    slots = _kanji_slots(original)
    for field, address, native, placeholder, korean in COMPACT_NAMES:
        if ''.join(subs.get(ch, '?') for ch in placeholder) != korean:
            raise AssertionError(f'unit compact placeholder meaning changed: {placeholder}')
        live = struct.unpack_from('<I', rom, field)[0] - 0x08000000
        end = live
        while rom[end] != 0:
            end += 1
        if bytes(rom[live:end]) != _sjis(placeholder):
            raise AssertionError(f'unit compact name bytes changed at 0x{live:X}')
        for ch, syllable in zip(placeholder, korean):
            if _glyph(rom, slots, _sjis(ch)) != tuple(render_char(syllable)):
                raise AssertionError(f'unit compact glyph changed: {ch}->{syllable}')
        sources = [(start, start) for start in DICTIONARIES]
        sources += [(start, struct.unpack_from('<I', rom, pointer)[0] - 0x08000000 if pointer else start)
                    for start, pointer in WEAPON_DICTIONARIES]
        for start, live_start in sources:
            if set(_codes(_sjis(native))) <= dictionary_codes(original, start):
                if not set(_codes(_sjis(placeholder))) <= dictionary_codes(rom, live_start):
                    raise AssertionError(
                        f'compact dictionary 0x{live_start:X} cannot render {korean} at 0x{address:X}')
    names = {address: (placeholder, korean) for _, address, _, placeholder, korean in COMPACT_NAMES}
    for field, target, label in SHARED_FIELDS:
        if struct.unpack_from('<I', rom, field)[0] != target + 0x08000000:
            raise AssertionError(f'shared {label} pointer changed at 0x{field:X}')
        placeholder, korean = names[target]
        if bytes(rom[target:target + len(_sjis(placeholder)) + 1]) != _sjis(placeholder) + b'\0':
            raise AssertionError(f'shared {label} string changed at 0x{target:X}')
        if ''.join(subs.get(ch, '?') for ch in placeholder) != korean:
            raise AssertionError(f'shared {label} no longer reads {korean}')
    for ch in INFINITE_AMMO:
        if _glyph(rom, slots, _sjis(ch)) != _glyph(original, slots, _sjis(ch)):
            raise AssertionError(f'infinite-ammo glyph {ch} overwritten')
    for start in INFINITE_AMMO_DICTIONARIES:
        if not set(_codes(_sjis(INFINITE_AMMO))) <= dictionary_codes(rom, start):
            raise AssertionError(f'infinite-ammo symbol not preloaded by 0x{start:X}')
    for address in INFINITE_AMMO_SOURCES:
        if bytes(rom[address:address + 6]) != bytes(original[address:address + 6]):
            raise AssertionError(f'infinite-ammo symbol string changed at 0x{address:X}')


def patch(rom, original):
    """Write compact names and dictionary preload edits; returns WRITE_LOG-style rows."""
    validate_source(original)
    _check_dictionary_edits(rom, applied=False)
    for field, address, _, _, _ in COMPACT_NAMES:
        if rom[field:field + 4] != original[field:field + 4]:
            raise AssertionError(f'unit compact-name live pointer changed at 0x{field:X}')
    for address, before, after in DICTIONARY_EDITS:
        rom[address:address + len(_sjis(after))] = _sjis(after)
    rows = []
    for address, slot, payload, korean in payloads():
        rom[address:address + slot] = payload
        used = len(payload.rstrip(b'\0'))
        rows.append([address, slot, used, payload[:used].hex(), 0, korean, None,
                     'part1-unit-compact-name'])
    return rows


def capture_regions(rom, original):
    validate_source(original)
    _check_dictionary_edits(rom, applied=True)
    spans = [(address, slot) for address, slot, _, _ in payloads()]
    spans += [(field, 4) for field, *_ in COMPACT_NAMES]
    spans += [(address, len(_sjis(after))) for address, _, after in DICTIONARY_EDITS]
    return tuple((a, bytes(rom[a:a + n])) for a, n in spans)


def verify_regions(rom, regions):
    if len(regions) != 2 * len(COMPACT_NAMES) + len(DICTIONARY_EDITS):
        raise AssertionError('unit compact-name evidence missing')
    for address, expected in regions:
        if bytes(rom[address:address + len(expected)]) != expected:
            raise AssertionError(f'unit compact name overwritten at 0x{address:X}')
