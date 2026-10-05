"""Part 1 compact UI labels that the compact glyph-bank renderer must be able to draw.

Evidence: temp/claude_2026-10-06/sweep_compact/findings.json (C1-C8, S1-S4),
static sweep of candidate2 (sha256 8c1016e3...).

Mechanism (static RE, same as part1_unit_list_compact_labels):

* A screen first preloads glyph banks: a loader stub (0xB12F5C, 0xB12F90, ...)
  reads two-byte codes from one or more dictionaries, and some screens append
  extra pair lists with 0xB12BA8 (the append reads byte *pairs*, so a single
  ASCII byte shifts every following code).
* Strings are then drawn through 0xB1311C; a code absent from the loaded banks
  draws as a blank cell.  Kanji resolve through the kanji table to FONT_BASE
  tiles (patched by patch_part2_ui_kanji_glyphs: placeholder kanji -> Korean
  glyphs), Korean reserved codes resolve through the relocated kanji table.

The Korean text writer had replaced these labels with reserved codes that no
loaded bank contains, so the labels rendered blank.  This module rewrites each
consumer string with codes that its screen preloads (native kanji aliases or
reserved codes) and edits a few pad cells of the dictionaries.  verify() decodes
every consumer the way the compact renderer would (load set + glyph) and fails
the build if any label would be blank or show a different syllable.

Not covered here (static trace incomplete, see notes): CO name pool group
0xB13020 draw site; group 0xB12FF0 appends the CO name itself (0xB41540).
"""
import struct

FONT_FILE = 0xB974D0
KANJI_TABLE = (0xB80B7C, 0xB8180C)
SYMBOL_TABLE = 0xB8027C
PAD = '倶'
MIRROR_DELTA = 0xD82F30 - 0x8057BC   # unreferenced 0x805xxx copies of the D82xxx dictionaries

# Loader stubs (literal pool -> dictionaries) that are live (have callers).
# Dead stubs 0xB12E5C/0xB12E9C/0xB12F1C (S2) are excluded on purpose.
GROUP_STUBS = {
    0xB12CC8: 3, 0xB12D0C: 2, 0xB12D3C: 2, 0xB12D6C: 2, 0xB12D9C: 2,
    0xB12DFC: 5, 0xB12E24: 1, 0xB12EDC: 3, 0xB12F5C: 3, 0xB12F90: 2,
    0xB12FC0: 2, 0xB12FF0: 2, 0xB13020: 2, 0xB13050: 2, 0xB13090: 2,
    0xB130C0: 2,
}
EXTRA_GROUPS = {0xB130E0: (0xD8273C, 0xD83198)}   # katakana bank (link screens)

UNIT_LIST, STATUS, RESULT, RESULT_ALT = 0xB12F5C, 0xB12F90, 0xB12FC0, 0xB12FF0
RULES, UNIT_INFO, TERRAIN = 0xB13090, 0xB12EDC, 0xB13050
# Advisory check (verify() report, not a failure): label banks that natively preloaded
# the whole original string but not the new one.  Kana syllabary / CO-name pools are
# left out: they cover katakana words by coincidence, not because they draw them.
NATIVE_CHECK_GROUPS = (UNIT_LIST, STATUS, RESULT, RESULT_ALT, RULES, UNIT_INFO, TERRAIN)
# Only originals containing kanji are used (short katakana words such as ルール are
# covered by unrelated banks by coincidence).
# Strings drawn from one table: a bank counts as a native consumer only if it covered
# every member (the battle bank covers ブルームーン alone by coincidence).
FAMILIES = ((0xB84F28, 0xB84F38, 0xB84F4C, 0xB84F5C, 0xB84F6C),)

# Tree connectors of the unit list (cargo rows).  Natively the codes 0x81A8 / 0x81AB
# use FONT_BASE slot 351 for their top half, which the Part 1 name grid owns ('s'),
# so they now draw a letter fragment.  Two otherwise unused kanji (absent from every
# source text, not reserved, exclusive non-name-grid slots) carry the original tiles.
CONNECTORS = {
    '奇': ((0x81A8, 0), (0x81A8, 8)),   # last-child connector: orig top 351 + bottom 95
    '材': ((0x81AB, 0), (0x81AB, 8)),   # middle connector: orig top 351 + bottom 335
}

# Consumer strings: (address, slot, new spec or None=verify only, expected text,
#                    explicit groups, appends, native source text or None)
# spec: Korean syllables -> reserved codes, everything else -> Shift-JIS.
# expected: what the compact renderer must show (pads/blank cells dropped).
STRINGS = (
    # C2 battle status (fn 0xB4183C, bank group 0xB12F90 + append 0xBE701C)
    (0xDF8B72, 4, '拠点', '거점', (STATUS,), (0xBE701C,), '拠点'),
    (0xDF8B7A, 4, None, '수입', (STATUS, TERRAIN), (0xBE701C,), None),   # terrain screen bank has reserved 수입
    (0xDF8B82, 4, '全滅', '전멸', (STATUS, RESULT), (0xBE701C,), '全滅'),
    (0xDF8BA2, 6, '軍資金', '군자금', (STATUS,), (0xBE701C,), '軍資金'),
    (0xDF8BC6, 8, '不残倶倶', '불참', (STATUS,), (0xBE701C,), None),
    (0xDF8BD2, 8, '中立拠点', '중립거점', (STATUS,), (0xBE701C,), '中立拠点'),
    (0xDF8B5A, 2, None, '？', (STATUS,), (0xBE701C,), None),
    # fn 0xB41720 (bank group not traced: check every candidate group)
    (0xDF8BAE, 8, '戦闘状況', '전투상황', (STATUS, RESULT, RESULT_ALT), (), '戦闘状況'),
    (0xDF8BBA, 8, '部隊倶倶', '부대', (STATUS, RESULT, RESULT_ALT), (), None),
    # C1 battle result (fn 0xB426E8, group 0xB12FC0)
    (0xDF8B8A, 4, '生존', '생존', (RESULT,), (), None),   # 存 is aliased to 장 (S4)
    (0xDF8BDE, 8, '総生産数', '총생산수', (RESULT,), (), '総生産数'),
    (0xDF8BEA, 8, '総全滅数', '총전멸수', (RESULT,), (), '総全滅数'),
    (0xDF8C1A, 12, '部隊状況倶倶', '부대상황', (RESULT,), (), None),
    # army names via table 0xDF2B84 (fns 0xB4183C/0xB426E8/0xB47284)
    (0xB84F28, 14, '聞落法', '블랙홀', (UNIT_LIST, STATUS, RESULT, RESULT_ALT), (), None),
    (0xB84F38, 16, '礼路個目', '옐로코멧', (UNIT_LIST, STATUS, RESULT, RESULT_ALT), (), None),
    (0xB84F4C, 14, '近緑湖寸', '그린어스', (UNIT_LIST, STATUS, RESULT, RESULT_ALT), (), None),
    (0xB84F5C, 12, '聞隣問', '블루문', (UNIT_LIST, STATUS, RESULT, RESULT_ALT), (), None),
    (0xB84F6C, 12, '令駄寸多', '레드스타', (UNIT_LIST, STATUS, RESULT, RESULT_ALT), (), None),
    # C8 score screen (bank 0xBE7308 loaded in fn 0xB4C668, drawn in fn 0xB4CAE4)
    (0xDF8B62, 2, '日', '일', (), (0xBE7308,), '日'),
    (0xDF8BF6, 8, None, '획득', (), (0xBE7308,), None),
    (0xDF8C02, 8, None, '종합', (), (0xBE7308,), None),
    # C5 unit list "no equipment" (fn 0xB46E80, group 0xB12F5C)
    (0xDF8C0E, 8, '装備無員', '장비없음', (UNIT_LIST,), (), None),
    # C4 unit list connectors
    (0xBE7124, 2, '奇', '奇', (UNIT_LIST,), (), None),
    (0xBE7128, 2, '材', '材', (UNIT_LIST,), (), None),
    (0xBE712C, 2, None, '｜', (UNIT_LIST,), (), None),
    # C3 rule settings list (group 0xB13090, table 0xB838C8)
    (0xB839F0, 6, '규칙　', '규칙', (RULES,), (), None),
    (0xB839C4, 8, '초기수입', '초기수입', (RULES,), (), None),
    (0xB839B4, 12, '매턴수입　　', '매턴수입', (RULES,), (), None),
    # C6 compact unit-info weapon fields (group 0xB12EDC, record +8/+0x10)
    (0xB81884, 10, '対潜箕紗炒', '대잠미사일', (UNIT_INFO,), (), '対潜箕紗炒'),
    (0xB818F4, 10, '対地箕紗炒', '대지미사일', (UNIT_INFO,), (), '対地箕紗炒'),
    (0xB81924, 4, '爆弾', '폭탄', (UNIT_INFO,), (), '爆弾'),
    (0xB81A94, 8, '重戦車砲', '중전차포', (UNIT_INFO,), (), '重戦車砲'),
    (0xB81A60, 8, '軽戦車砲', '경전차포', (UNIT_INFO,), (), '軽戦車砲'),
    (0xB81AC0, 10, '船再外砲', '바주카포', (UNIT_INFO,), (), None),
    (0xB819E8, 10, '充高砲', '캐논포', (UNIT_INFO,), (), None),
    (0xB81988, 10, '射甲砲', '발칸포', (UNIT_INFO,), (), None),
    (0xB81B04, 10, '魯傑兎', '기관총', (UNIT_INFO,), (), None),
    (0xB81874, 14, '対空魯傑兎', '대공기관총', (UNIT_INFO,), (), None),
    (0xB81B14, 16, '装備無員', '장비없음', (UNIT_INFO,), (), None),
    # C7 link status (append 0xB8319C at 0xB32D12, katakana bank) and transfer
    # screen (append 0xB8322C at 0xB342EA is its only bank)
    (0xB831BC, 6, None, '미접속', (0xB130E0,), (0xB8319C,), None),
    (0xB831C4, 6, None, '준비중', (0xB130E0,), (0xB8319C,), None),
    (0xB831CC, 10, None, '준비중', (0xB130E0,), (0xB8319C,), None),
    (0xB831D8, 6, None, '접속중', (0xB130E0,), (0xB8319C,), None),
    (0xB83254, 16, '전송　중입니다。', '전송중입니다。', (), (0xB8322C,), None),
    (0xB83268, 24, '잠시　기다려　주십시오。', '잠시기다려주십시오。', (), (0xB8322C,), None),
)

# Preload pair lists (append sources).  None spec = restore original bytes.
APPENDS = (
    (0xBE701C, 18, None),                     # 拠点全滅ふさんか？ (native, keeps ？ preloaded)
    (0xB8319C, 22, '미접속준비중　에러'),    # pairs only; 에러 for the 接続エラー row
    (0xB8322C, 36, '전송중입니다。잠시기려주십오　'),
)

# Dictionary pad/cell edits: (address, before spec, after spec); mirrored to 0x805xxx.
# The status pages (groups 0xB12F90 / 0xB12FC0 / 0xB12FF0) switch banks without redrawing
# the tab row: cells keep the glyph-cache *index* of page 1.  The three banks share an
# identical 54-code prefix (digits, army names, 戦闘占領将軍状況生産ユニット嗣汚虞姐), so
# every prefix code has the same dedup index on every page.  New codes therefore go
# into the last prefix pad cell (same cell in all three, nothing after it in the prefix)
# or after the prefix (page-only).  Candidate3 put 존 inside the D82F30 prefix, which
# shifted 戦闘状況/部隊 by one tile on the production page (存→ '존전군상 ◀ 산부').
SHARED_PREFIX_BANKS = (0xD82EA4, 0xD82F30, 0xD83020)
SHARED_PREFIX_CODES = 54
PAGE_GROUPS = (STATUS, RESULT, RESULT_ALT)
PAGE_PERSISTENT = (0xDF8BAE, 0xDF8BBA, 0xB84F28, 0xB84F38, 0xB84F4C, 0xB84F5C, 0xB84F6C)
DICTIONARY_EDITS = (
    (0xD82F0E, PAD, '湖'),        # status bank: last shared-prefix pad (近緑湖 = 그린어)
    (0xD82F9A, PAD, '湖'),        # result bank: same prefix cell
    (0xD8308A, PAD, '湖'),        # status-alt bank: same prefix cell (natively carries army names)
    (0xD82FA6, PAD, '존'),        # result bank, after the prefix: 生존
    (0xD82F14, '収入', '수입'),   # status bank, after the prefix: DF8B7A keeps the terrain screen's reserved 수입
    (0xD82E14, PAD, '湖'),        # unit list bank: last pad before the tail 選
)
BANK_EDITS = (
    (0xBE731C, 'かくとくそうごう', '획득종합' + PAD * 4),   # score bank (no mirror)
)


def encode_spec(spec, syl_to_code):
    out = bytearray()
    for ch in spec:
        if '가' <= ch <= '힣':
            out += syl_to_code[ch].to_bytes(2, 'big')
        else:
            raw = ch.encode('shift_jis')
            if len(raw) != 2:
                raise AssertionError(f'compact UI spec has a single-byte char: {spec!r}')
            out += raw
    return bytes(out)


def _codes(raw):
    return [bytes(raw[i:i + 2]) for i in range(0, len(raw) - 1, 2)]


def _cstr(rom, address, limit=64):
    """Pairs up to the first NUL byte (0A 00 script terminators end at 0A)."""
    end = address
    while end < address + limit and rom[end] != 0 and rom[end:end + 2] != b'\x0a\x00':
        end += 2 if rom[end] >= 0x81 else 1
    raw = bytes(rom[address:end])
    if any(b < 0x81 and b != 0x20 for b in raw[0::2]):
        raise AssertionError(f'compact UI string has single-byte data at 0x{address:X}')
    return raw


def dictionary_codes(rom, start):
    end = start
    while bytes(rom[end:end + 2]) != b'\0\0':
        end += 2
        if end - start > 0x400:
            raise AssertionError(f'unterminated compact dictionary at 0x{start:X}')
    return set(_codes(rom[start:end]))


def group_banks(rom, group):
    if group in EXTRA_GROUPS:
        return EXTRA_GROUPS[group]
    banks = []
    for pointer in range(group, group + 4 * GROUP_STUBS[group], 4):
        value = struct.unpack_from('<I', rom, pointer)[0]
        if 0x08D80000 <= value < 0x08E00000 or 0x08F00000 <= value < 0x09000000:
            banks.append(value - 0x08000000)
    return tuple(banks)


def loaded_codes(rom, group, appends=()):
    codes = set()
    if group is not None:
        for bank in group_banks(rom, group):
            codes |= dictionary_codes(rom, bank)
    for address in appends:
        codes |= set(_codes(_cstr(rom, address, 64)))
    return codes


def _kanji_slots(original):
    slots = {}
    for pos in range(*KANJI_TABLE, 6):
        sjis_le, top, bottom = struct.unpack_from('<HHH', original, pos)
        slots[bytes([sjis_le & 0xFF, sjis_le >> 8])] = (top, bottom)
    return slots


def _tile(rom, slot):
    return bytes(rom[FONT_FILE + slot * 32:FONT_FILE + slot * 32 + 32])


def _symbol_slot(original, sjis, delta):
    idx = (((sjis + 0xFFFF7EC0) & 0xFFF8) << 1) + (sjis & 7)
    return struct.unpack_from('<H', original, SYMBOL_TABLE + (idx + delta) * 2)[0]


def connector_tiles(original):
    return {ch: tuple(_tile(original, _symbol_slot(original, s, d)) for s, d in halves)
            for ch, halves in CONNECTORS.items()}


def decode_cell(rom, original, code, subs, render_char, code_to_syllable, slots):
    """What one compact cell shows: a Korean syllable, a symbol, '' (blank) or '?'."""
    value = int.from_bytes(code, 'big')
    if code in (b'\x20\x20', b'\x81\x40') or code == PAD.encode('shift_jis'):
        return ''
    if value in code_to_syllable:
        return code_to_syllable[value]
    try:
        ch = code.decode('shift_jis')
    except UnicodeDecodeError:
        return '?'
    if code in slots:
        top, bottom = slots[code]
        glyph = (_tile(rom, top), _tile(rom, bottom))
        if ch in CONNECTORS:
            return ch if glyph == connector_tiles(original)[ch] else '?'
        if ch in subs:
            return subs[ch] if glyph == tuple(render_char(subs[ch])) else '?'
        return '?'
    if 0x8140 <= value < 0x8400:
        same = all(_tile(rom, _symbol_slot(original, value, d)) == _tile(original, _symbol_slot(original, value, d))
                   for d in (0, 8))
        return ch if same else '?'
    return ch if '０' <= ch <= '９' else '?'


def validate_source(original):
    for address, slot, spec, _, _, _, native in STRINGS:
        if native is not None:
            raw = native.encode('shift_jis')
            if bytes(original[address:address + len(raw)]) != raw:
                raise AssertionError(f'compact UI native source changed at 0x{address:X}')
    for address, size, spec in APPENDS:
        if original[address + size:address + size + 2] != b'\0\0':
            raise AssertionError(f'compact UI append source boundary changed at 0x{address:X}')
    for ch in CONNECTORS:
        if ch not in {c.decode('shift_jis') for c in _kanji_slots(original)}:
            raise AssertionError(f'connector placeholder {ch} missing from kanji table')


def _write(rom, address, slot, payload, text, rows):
    if len(payload) > slot:
        raise AssertionError(f'compact UI payload overflow at 0x{address:X}: {len(payload)} > {slot}')
    full = payload + bytes(slot - len(payload))
    rom[address:address + slot] = full
    rows.append([address, slot, slot, full.hex(), None, text, None, 'part1-compact-ui'])


def patch(rom, original, syl_to_code, name_grid_slots):
    """Rewrite consumer strings, preload lists, dictionary cells and connector glyphs.

    Returns WRITE_LOG rows.  Runs after the last text writer and the final name grid.
    """
    validate_source(original)
    slots = _kanji_slots(original)
    owned = {s for pair in name_grid_slots for s in pair}
    used_slots = [s for pos in range(*KANJI_TABLE, 6) for s in struct.unpack_from('<HH', original, pos + 2)]
    rows = []
    for ch, tiles in connector_tiles(original).items():
        top, bottom = slots[ch.encode('shift_jis')]
        if {top, bottom} & owned or used_slots.count(top) != 1 or used_slots.count(bottom) != 1:
            raise AssertionError(f'connector placeholder {ch} slots are shared')
        for slot, tile in zip((top, bottom), tiles):
            rom[FONT_FILE + slot * 32:FONT_FILE + slot * 32 + 32] = tile
    for address, before, after in DICTIONARY_EDITS + BANK_EDITS:
        old = encode_spec(before, syl_to_code)
        new = encode_spec(after, syl_to_code)
        if len(old) != len(new):
            raise AssertionError(f'compact dictionary edit length changed at 0x{address:X}')
        targets = [address]
        if (address, before, after) in DICTIONARY_EDITS:
            targets.append(address - MIRROR_DELTA)
        for target in targets:
            if bytes(rom[target:target + len(old)]) != old:
                raise AssertionError(f'compact dictionary cell changed before edit at 0x{target:X}')
            rom[target:target + len(new)] = new
            rows.append([target, len(new), len(new), new.hex(), None, after, None, 'part1-compact-dictionary'])
    for address, size, spec in APPENDS:
        payload = bytes(original[address:address + size]) if spec is None else encode_spec(spec, syl_to_code)
        _write(rom, address, size, payload, spec or 'native preload', rows)
    for address, slot, spec, expected, _, _, _ in STRINGS:
        if spec is not None:
            _write(rom, address, slot, encode_spec(spec, syl_to_code), expected, rows)
    return rows


def verify(rom, original, syl_to_code, subs, render_char, *, written_only=False):
    """Static compact-renderer decode of every consumer string; returns the decoded table.

    written_only skips the verify-only rows (spec None), whose bytes come from the
    full build's earlier writers (used by unit tests on a partially built ROM).
    """
    slots = _kanji_slots(original)
    code_to_syllable = {code: s for s, code in syl_to_code.items()}
    report = []
    for address, slot, spec, expected, groups, appends, _ in STRINGS:
        if written_only and spec is None:
            continue
        raw = _cstr(rom, address, slot)
        if spec is not None and raw != encode_spec(spec, syl_to_code):
            raise AssertionError(f'compact UI string overwritten at 0x{address:X}')
        codes = _codes(raw)
        shown = ''.join(decode_cell(rom, original, code, subs, render_char, code_to_syllable, slots)
                        for code in codes)
        if shown != expected:
            raise AssertionError(f'compact UI string 0x{address:X} shows {shown!r}, expected {expected!r}')
        # Every explicit consumer group, plus every live group that natively drew the
        # original string, must preload each visible code.
        check = set(groups) or {None}
        visible = [c for c in codes
                   if decode_cell(rom, original, c, subs, render_char, code_to_syllable, slots)]
        for group in check:
            missing = [c.hex() for c in visible if c not in loaded_codes(rom, group, appends)]
            if missing:
                raise AssertionError(f'compact UI 0x{address:X} group {group and hex(group)}: '
                                     f'codes {missing} are not preloaded')
        # Advisory only: label banks that natively preloaded the whole original (kanji
        # strings / complete families) but do not preload the new string.  Coverage by
        # unrelated banks is common (shared kana/unit-name chars), so this is reported
        # for review instead of failing the build.
        native = _cstr(original, address, slot)
        family = next((f for f in FAMILIES if address in f), (address,))
        natives = [set(_codes(_cstr(original, a, 64))) for a in family]
        has_kanji = any(int.from_bytes(c, 'big') >= 0x889F for c in _codes(native))
        advisory = sorted(hex(g) for g in (NATIVE_CHECK_GROUPS if has_kanji else ())
                          if g not in check
                          and all(n <= loaded_codes(original, g, ()) for n in natives)
                          and any(c not in loaded_codes(rom, g, appends) for c in visible))
        report.append((address, expected, shown, sorted(hex(g) if g else '-' for g in check), advisory))
    verify_page_persistence(rom, original, syl_to_code, subs, render_char, slots, code_to_syllable)
    for address, before, after in DICTIONARY_EDITS:
        new = encode_spec(after, syl_to_code)
        for target in (address, address - MIRROR_DELTA):
            if bytes(rom[target:target + len(new)]) != new:
                raise AssertionError(f'compact dictionary edit lost at 0x{target:X}')
    for address, size, spec in APPENDS:
        raw = bytes(rom[address:address + size])
        if raw[:len(raw.rstrip(b'\0'))] and any(b < 0x81 for b in raw.rstrip(b'\0')[0::2]):
            raise AssertionError(f'preload list 0x{address:X} lost pair alignment')
    return report


def cache_order(rom, group):
    """Glyph-cache order of a bank group: first occurrence of each code, banks in order."""
    order = []
    for bank in group_banks(rom, group):
        end = bank
        while bytes(rom[end:end + 2]) != b'\0\0':
            code = bytes(rom[end:end + 2])
            if code not in order:
                order.append(code)
            end += 2
    return order


def verify_page_persistence(rom, original, syl_to_code, subs, render_char, slots=None, code_to_syllable=None):
    """Rows drawn on one status page must still read correctly after switching pages.

    Emulates the switch: a cell keeps the cache index it got under the drawing page's
    bank group, then shows whatever code the other page's group put at that index.
    """
    slots = slots or _kanji_slots(original)
    code_to_syllable = code_to_syllable or {code: s for s, code in syl_to_code.items()}
    prefixes = [_codes(rom[b:b + 2 * SHARED_PREFIX_CODES]) for b in SHARED_PREFIX_BANKS]
    if any(p != prefixes[0] for p in prefixes):
        raise AssertionError('status page banks lost their identical shared prefix')
    orders = {g: cache_order(rom, g) for g in PAGE_GROUPS}
    rows = {r[0]: r for r in STRINGS}
    checked = 0
    for address in PAGE_PERSISTENT:
        _, slot, _, expected, _, _, _ = rows[address]
        codes = [c for c in _codes(_cstr(rom, address, slot))
                 if decode_cell(rom, original, c, subs, render_char, code_to_syllable, slots)]
        for drawn in PAGE_GROUPS:
            for shown in PAGE_GROUPS:
                text = ''
                for code in codes:
                    index = orders[drawn].index(code)
                    if index >= len(orders[shown]):
                        raise AssertionError(f'page tile 0x{address:X} index {index} missing on page {shown:#x}')
                    text += decode_cell(rom, original, orders[shown][index], subs, render_char,
                                        code_to_syllable, slots)
                if text != expected:
                    raise AssertionError(f'page switch {drawn:#x}->{shown:#x} shows {text!r} at 0x{address:X}, '
                                         f'expected {expected!r}')
                checked += 1
    return checked
