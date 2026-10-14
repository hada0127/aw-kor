#!/usr/bin/env python3
"""Link-play client (1-cart VS multiboot program) Korean font — Design A.

RE and design: temp/linkclient_20261013/plan.md (2026-10-13).

The host DMA-copies a headerless client program to EWRAM 0x02000000 and also runs
it during 1-cart VS (Part 2 program 0x0890DC7C..0x089463FC, Part 1 program
0x08EC6374..0x08EFE2D8).  The client draws text only through its own per-char
renderer: a linear search of a 60-halfword charset table, then an 8x16 cell in a
4096-byte glyph sheet (64 cells).  Design A swaps that table and sheet in place for
the Hangul syllables the live strings need, keeps the host code points
(data/syllable_to_code_2350.json, native SJIS punctuation), and writes the live
strings with fullwidth punctuation, native controls ``r w Q n k`` and NUL padding.

Everything else inside the client images is restored to the original bytes except
the LZ77 art blocks that other build stages localize (``ASSET_LZ77``).  This also
keeps the three dead program copies (0x089463FC..0x089F0000) and the stage-1
header range (0x08902A8C..0x0890DC7C) free of text-import writes.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lz77_scan import lz77_decompress  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYLCODE = os.path.join(BASE, 'data', 'syllable_to_code_2350.json')

EWRAM = 0x02000000
TABLE_HALFWORDS = 60          # original in-place table size (120 bytes)
MAX_CODES = TABLE_HALFWORDS - 1   # one 0x8140 sentinel halfword must remain
SHEET_CELLS = 64
SHEET_BYTES = 0x1000
SENTINEL = b'\x40\x81'        # halfword 0x8140; distinct from the code bytes 81 40 (U+3000)
CONTROLS = frozenset(b'rwQnk')
INK = 0xA

# The five 120-byte charset tables (one per client image incl. dead copies).
CHARSET_TABLES = (0x94298C, 0x97AE40, 0x9B36E4, 0x9EBF88, 0xEFAAD4)
DEAD_COPIES = (0x9463FC, 0x9F0000)
STAGE1_HEADERS = (0x902A8C, 0x90DC7C)

# LZ77 art blocks inside the client images that other reviewed stages localize
# (owner in brackets).  Extents are the original consumed length, 4-byte aligned.
ASSET_LZ77 = (
    # item7_multiboot_factory_tooltip
    0x92A9B0, 0x964638, 0x99CEDC, 0x9D5780, 0xEE532C,
    # part1_supply_popup
    0x92BF3C, 0x965BC4, 0x99E468, 0x9D6D0C, 0xEE7720,
    # patch_part2_battle_start_day_overlay_obj
    0x92DF84, 0x966C0C, 0x99F4B0, 0x9D7D54, 0x92EB5C, 0x9677E4, 0x9A0088, 0x9D892C,
    # patch_part1_compact_info_weapon_labels
    0x92F0F4, 0x967D7C, 0x9A0620, 0x9D8EC4,
    # patch_part2_result_success_overlay_obj
    0x930520, 0x9691A8, 0x9A1A4C, 0x9DA2F0, 0xEE8A64,
    # link_error_bitmaps (sheet, map)
    0x930B30, 0x930E94, 0x9697B8, 0x969B1C, 0x9A205C, 0x9A23C0, 0x9DA900, 0x9DAC64,
    0xEE9730, 0xEE9A94,
    # patch_part1_compact_info_weapon_labels / day banner / result failure overlay
    0xEE436C, 0xEE5E14, 0xEE8F68,
)

PUNCT = {'　': b'\x81\x40', '！': b'\x81\x49', '？': b'\x81\x48', '，': b'\x81\x43', '▼': b'\x81\xA5'}
PUNCT_FROM_ORIGINAL = ('　', '！', '？')   # copied from the original client cells
HALFWIDTH_TO_FULL = {' ': '　', '!': '！', '?': '？', ',': '，'}


class Spec:
    def __init__(self, name, rom, size, layout, table_ew, sheet_ew, live):
        self.name, self.rom, self.size, self.layout = name, rom, size, layout
        self.table_ew, self.sheet_ew, self.live = table_ew, sheet_ew, live

    @property
    def end(self):
        return self.rom + self.size

    @property
    def table(self):
        return self.rom + self.table_ew - EWRAM

    @property
    def sheet(self):
        return self.rom + self.sheet_ew - EWRAM

    @property
    def row(self):
        return 0x20 if self.layout == 'p2' else 0x10

    def cell(self, index):
        r = self.row
        return (index & (r - 1)) | ((index & ~(r - 1) & 0xFF) << 1)


# (item, ROM file offset, slot bytes, original Japanese, Korean, wording source)
# Korean = the B-team/b25 wording with punctuation made fullwidth; controls inline.
_P2_LIVE = (
    ('preload_page0', 0x942A38, 12, 'はいえ▼', '예아뇨▼', 'csv 0x942A38'),
    ('preload_page1', 0x942A44, 40, '待機攻撃合流降伏する終了とじるシステム', '대기공격합류항복종료닫기시스템', 'address_text_overrides 0x942A44'),
    ('preload_page2', 0x942A6C, 8, '攻撃', '공격', 'build control word 0x942A6C'),
    ('label_end', 0x929660, 8, '終了', '종료', 'build command-label'),
    ('label_system', 0x929668, 12, 'システム', '시스템', 'csv 0x929668'),
    ('label_surrender', 0x929674, 12, '降伏する', '항복', 'address_text_overrides 0x929674'),
    ('label_wait', 0x929680, 8, '待機', '대기', 'build command-label'),
    ('label_join', 0x929688, 8, '合流', '합류', 'build command-label'),
    ('label_attack', 0x929690, 6, '攻撃', '공격', 'build command-label'),
    ('yesno', 0x942CC4, 17, '　はい　　いいえ', '　예　　　아뇨', 'csv 0x942CC4 (option columns kept)'),
    ('defeat_red', 0x9450BC, 36, 'レッドスター軍は敗北しました！！ww', '레드스타군은　패배했습니다！！ww', 'csv 0x9450BC'),
    ('defeat_blue', 0x9450E0, 36, 'ブルームーン軍は敗北しました！！ww', '블루문　군은　패배했습니다！！ww', 'csv 0x9450E0'),
    ('defeat_green', 0x945104, 40, 'グリーンアース軍は敗北しました！！ww', '그린어스군은　패배했습니다！！ww', 'csv 0x945104'),
    ('defeat_yellow', 0x94512C, 40, 'イエローコメット軍は敗北しました！！ww', '옐로　코멧군은　패배했습니다！！ww', 'csv 0x94512C'),
    ('defeat_black', 0x945154, 40, 'ブラックホール軍は敗北しました！！ww', '블랙홀군은　패배했습니다！！ww', 'csv 0x945154'),
    ('surrender_confirm', 0x9452B8, 60, '降伏すると負けになっちゃうけど、r本当に降伏する？　wQn',
     '항복하면　패배가　되어　버리지만r정말　항복할래？　wQn', 'csv 0x9452B8 + 0x9452D9 (b25 line 1 drops the comma)'),
    ('army_yellow', 0x929400, 20, 'イエローコメット', '옐로　코멧', 'csv 0x929400'),
    ('army_green', 0x929414, 16, 'グリーンアース', '그린어스', 'csv 0x929414'),
    ('army_blue', 0x929424, 16, 'ブルームーン', '블루문　군', 'csv 0x929424'),
    ('army_red', 0x929434, 16, 'レッドスター', '레드스타', 'csv 0x929434'),
    ('unit_bomber_fighter', 0x929508, 8, '攻撃機', '공격기', 'address_text_overrides 0x929508'),
    ('unit_none', 0x9295B0, 8, 'なし', '없음', 'build unit-opt-label'),
)
_P1_LIVE = (
    ('preload_page0', 0xEFAB80, 12, 'はいえ▼', '예아뇨▼', 'csv 0xEFAB80'),
    ('preload_page1', 0xEFAB8C, 40, '待機攻撃合流降伏する終了とじるシステム', '대기공격합류항복종료닫기시스템', 'csv 0xEFAB8C'),
    ('preload_page2', 0xEFABB4, 8, '攻撃', '공격', 'build control word 0xEFABB4'),
    ('label_end', 0xEE258C, 8, '終了', '종료', 'build control word 0xEE258C'),
    ('label_system', 0xEE2594, 12, 'システム', '시스템', 'csv 0xEE2594'),
    ('label_surrender', 0xEE25A0, 12, '降伏する', '항복', 'address_text_overrides 0xEE25A0'),
    ('label_wait', 0xEE25AC, 8, '待機', '대기', 'build control word 0xEE25AC'),
    ('label_join', 0xEE25B4, 8, '合流', '합류', 'build control word 0xEE25B4'),
    ('label_attack', 0xEE25BC, 6, '攻撃', '공격', 'build control word 0xEE25BC'),
    ('yesno', 0xEFAE0C, 17, '　はい　　いいえ', '　예　　　아뇨', 'csv 0xEFAE0C (option columns kept)'),
    ('defeat_red', 0xEFD8A4, 36, 'レッドスター軍は敗北しました！！ww', '레드스타군은　패배했습니다！！ww', 'csv 0xEFD8A4'),
    ('defeat_blue', 0xEFD8C8, 36, 'ブルームーン軍は敗北しました！！ww', '블루문　군은　패배했습니다！！ww', 'csv 0xEFD8C8'),
    ('defeat_green', 0xEFD8EC, 40, 'グリーンアース軍は敗北しました！！ww', '그린어스군은　패배했습니다！！ww', 'csv 0xEFD8EC'),
    ('defeat_yellow', 0xEFD914, 40, 'イエローコメット軍は敗北しました！！ww', '옐로코멧군은　패배했습니다！！ww', 'csv 0xEFD914'),
    ('defeat_black', 0xEFD93C, 40, 'ブラックホール軍は敗北しました！！ww', '블랙홀군은　패배했습니다！！ww', 'csv 0xEFD93C'),
    ('surrender_confirm', 0xEFDAA0, 60, '降伏すると負けになっちゃうけど、r本当に降伏する？　wQn',
     '항복하면　패배가　되지만，r정말　항복할래？　wQn', 'csv 0xEFDAA0 + 0xEFDAC1'),
    ('army_yellow', 0xEE232C, 20, 'イエローコメット', '옐로　코멧', 'csv 0xEE232C'),
    ('army_green', 0xEE2340, 16, 'グリーンアース', '그린어스', 'csv 0xEE2340'),
    ('army_blue', 0xEE2350, 16, 'ブルームーン', '블루문', 'csv 0xEE2350'),
    ('army_red', 0xEE2360, 16, 'レッドスター', '레드스타', 'csv 0xEE2360'),
    ('unit_bomber_fighter', 0xEE2434, 8, '攻撃機', '공격기', 'address_text_overrides 0xEE2434'),
    ('unit_none', 0xEE24DC, 8, 'なし', '없음', 'build control word 0xEE24DC'),
)

SPECS = (
    Spec('P2', 0x90DC7C, 0x38780, 'p2', 0x02034D10, 0x0201E708, _P2_LIVE),
    Spec('P1', 0xEC6374, 0x37F64, 'p1', 0x02034760, 0x0201CFF8, _P1_LIVE),
)

# Whole client-image ranges the stage owns (restored to original outside the
# asset blocks and the stage's own writes).
CLIENT_RANGES = (
    ('stage1_headers',) + STAGE1_HEADERS,
    ('p2_program', 0x90DC7C, 0x90DC7C + 0x38780),
    ('dead_copies',) + DEAD_COPIES,
    ('p1_program', 0xEC6374, 0xEC6374 + 0x37F64),
)


class LinkClientFontError(AssertionError):
    pass


def load_codes(path=SYLCODE):
    with open(path, encoding='utf-8') as stream:
        raw = json.load(stream)
    return {k: int(v, 16).to_bytes(2, 'big') for k, v in raw.items()
            if isinstance(v, str) and v.startswith('0x')}


def is_hangul(ch):
    return '가' <= ch <= '힣'


def tokens(text):
    """Split a live string into ('char', ch) / ('ctl', byte) tokens."""
    out = []
    for ch in text:
        if ord(ch) < 0x80:
            if ord(ch) not in CONTROLS:
                raise LinkClientFontError(f'halfwidth byte {ch!r} is not a native control in {text!r}')
            out.append(('ctl', ord(ch)))
        else:
            out.append(('char', ch))
    return out


def lines(text):
    """Visible characters per line (controls removed; 'r' starts a new line)."""
    result = ['']
    for kind, value in tokens(text):
        if kind == 'ctl':
            if value == ord('r'):
                result.append('')
        else:
            result[-1] += value
    return result


def jp_tokens(raw):
    """Decode original slot bytes into tokens (SJIS pairs / control bytes)."""
    out, i = [], 0
    while i < len(raw):
        b = raw[i]
        if b < 0x80:
            out.append(('ctl', b))
            i += 1
        else:
            out.append(('char', raw[i:i + 2].decode('cp932')))
            i += 2
    return out


def encode(text, codes):
    out = bytearray()
    for kind, value in tokens(text):
        if kind == 'ctl':
            out.append(value)
        elif value in PUNCT:
            out += PUNCT[value]
        elif is_hangul(value):
            if value not in codes:
                raise LinkClientFontError(f'no host code for {value!r}')
            out += codes[value]
        else:
            raise LinkClientFontError(f'unsupported character {value!r} in {text!r}')
    return bytes(out)


def glyph_order(spec, extra=''):
    """Table order: punctuation used (fixed order, ▼ and 　 always), then syllables."""
    used = set(extra)
    for item in spec.live:
        used.update(ch for kind, ch in tokens(item[4]) if kind == 'char')
    used.update('▼　')
    punct = [p for p in PUNCT if p in used]
    syllables = sorted(ch for ch in used if is_hangul(ch))
    other = sorted(ch for ch in used if ch not in PUNCT and not is_hangul(ch))
    if other:
        raise LinkClientFontError(f'{spec.name}: unsupported glyphs {other}')
    return punct + syllables


def _ink(tile):
    return bytes(((INK if b & 15 else 0) | ((INK if b >> 4 else 0) << 4)) for b in tile)


def _comma():
    top, bottom = bytearray(32), bytearray(32)
    for row, cols in ((3, (1, 2)), (4, (1, 2)), (5, (2,)), (6, (1,))):
        for col in cols:
            bottom[row * 4 + col // 2] |= INK << ((col & 1) * 4)
    return bytes(top), bytes(bottom)


def render_glyph(ch):
    if ch == '，':
        return _comma()
    import render_galmuri_8x16 as galmuri
    if galmuri._font_cache is None:   # same BDF as host dialogue; cwd-independent load
        from bdf import load_bdf
        galmuri._font_cache = load_bdf(os.path.join(BASE, 'reference', 'fonts', 'Galmuri11-Condensed.bdf'))[0]
    top, bottom = galmuri.render_char(ch, ink=INK)
    if not any(top) and not any(bottom):
        raise LinkClientFontError(f'Galmuri has no glyph for {ch!r}')
    return _ink(top), _ink(bottom)


def original_table(orig, spec):
    codes, pos = [], spec.table
    for _ in range(TABLE_HALFWORDS):
        codes.append(bytes(orig[pos:pos + 2]))
        pos += 2
    if orig[pos:pos + 4] != bytes(4):
        raise LinkClientFontError(f'{spec.name}: original table terminator moved')
    return codes


def original_cell(orig, spec, code):
    table = original_table(orig, spec)
    index = table.index(code)
    cell = spec.cell(index)
    top = bytes(orig[spec.sheet + cell * 32:spec.sheet + cell * 32 + 32])
    bottom = bytes(orig[spec.sheet + (cell + spec.row) * 32:spec.sheet + (cell + spec.row) * 32 + 32])
    return top, bottom


def check_live_item(orig, spec, item):
    name, off, slot, jp, ko, _source = item
    raw = bytes(orig[off:off + slot])
    jp_bytes = jp.replace('r', '\x72')
    native = raw.split(b'\0', 1)[0]
    if native.decode('cp932', 'replace') != jp_bytes or any(raw[len(native):]):
        raise LinkClientFontError(f'{spec.name} {name}: original slot changed at 0x{off:X}')
    if not spec.rom <= off < off + slot <= spec.end:
        raise LinkClientFontError(f'{spec.name} {name}: slot outside program')
    jp_ctl = [v for k, v in jp_tokens(native) if k == 'ctl']
    ko_ctl = [v for k, v in tokens(ko) if k == 'ctl']
    if jp_ctl != ko_ctl:
        raise LinkClientFontError(f'{spec.name} {name}: control sequence {bytes(ko_ctl)!r} != native {bytes(jp_ctl)!r}')
    if name.startswith('preload_'):
        return   # glyph preload code lists, not displayed lines: slot fit only
    jl, kl = lines(jp), lines(ko)
    if len(jl) != len(kl) or any(len(k) > len(j) for j, k in zip(jl, kl)):
        raise LinkClientFontError(f'{spec.name} {name}: line widths {list(map(len, kl))} exceed native {list(map(len, jl))}')


def build_program(orig, spec, codes):
    """Return {absolute offset: bytes} writes for one client program + report."""
    order = glyph_order(spec)
    if len(order) > MAX_CODES:
        raise LinkClientFontError(f'{spec.name}: {len(order)} codes > {MAX_CODES} (charset table capacity)')
    if len(order) > SHEET_CELLS:
        raise LinkClientFontError(f'{spec.name}: {len(order)} cells > {SHEET_CELLS}')
    entries = [PUNCT[ch] if ch in PUNCT else codes[ch] for ch in order]
    table = b''.join(entries) + SENTINEL * (TABLE_HALFWORDS - len(entries))
    sheet = bytearray(SHEET_BYTES)
    for index, ch in enumerate(order):
        if ch in PUNCT_FROM_ORIGINAL:
            top, bottom = original_cell(orig, spec, PUNCT[ch])
        else:
            top, bottom = render_glyph(ch)
        cell = spec.cell(index)
        sheet[cell * 32:cell * 32 + 32] = top
        sheet[(cell + spec.row) * 32:(cell + spec.row) * 32 + 32] = bottom
    writes = {spec.table: table, spec.sheet: bytes(sheet)}
    strings = []
    for item in spec.live:
        name, off, slot, jp, ko, source = item
        check_live_item(orig, spec, item)
        enc = encode(ko, codes)
        if len(enc) >= slot:
            raise LinkClientFontError(f'{spec.name} {name}: {len(enc)} bytes do not fit slot {slot} with NUL')
        writes[off] = enc + bytes(slot - len(enc))
        strings.append({'item': name, 'rom': f'0x{off:06X}', 'ewram': f'0x{off - spec.rom + EWRAM:08X}',
                        'slot': slot, 'jp': jp, 'ko': ko, 'source': source, 'bytes': len(enc)})
    report = {'image': spec.name, 'codes': len(order), 'capacity_codes': MAX_CODES,
              'cells': len(order), 'capacity_cells': SHEET_CELLS,
              'glyphs': ''.join(order), 'strings': strings}
    return writes, report


def asset_mask(orig):
    """Byte ranges of the LZ77 art blocks other stages own (original extents)."""
    ranges = []
    for off in ASSET_LZ77:
        dec = lz77_decompress(bytes(orig[off:off + 0x10000]), 0)
        if dec is None:
            raise LinkClientFontError(f'asset 0x{off:X} is not an LZ77 block in the original')
        ranges.append((off, off + ((dec[1] + 3) & ~3)))
    return sorted(ranges)


def owned_ranges(spec):
    out = [(spec.table, spec.table + TABLE_HALFWORDS * 2), (spec.sheet, spec.sheet + SHEET_BYTES)]
    out += [(item[1], item[1] + item[2]) for item in spec.live]
    return sorted(out)


def _in(ranges, i):
    for a, b in ranges:
        if a <= i < b:
            return True
    return False


def _runs(indices):
    runs = []
    for i in indices:
        if runs and i <= runs[-1][1] + 16:
            runs[-1][1] = i
        else:
            runs.append([i, i])
    return [(a, b + 1) for a, b in runs]


def apply(rom, orig, write_log=None, codes=None):
    """Build stage: restore client images, write tables/sheets/live strings.

    Returns a JSON-able report.  ``write_log`` entries inside the client ranges
    are removed (the client encoding is gated by qa_link_client_font instead).
    """
    codes = codes or load_codes()
    assets = asset_mask(orig)
    for spec in SPECS:
        for a, b in assets:
            if not (b <= spec.sheet or a >= spec.sheet + SHEET_BYTES):
                raise LinkClientFontError(f'{spec.name}: sheet overlaps asset 0x{a:X}')
    reverted = []
    for name, start, end in CLIENT_RANGES:
        changed = [i for i in range(start, end) if rom[i] != orig[i] and not _in(assets, i)]
        for i in changed:
            rom[i] = orig[i]
        reverted += [(name, a, b) for a, b in _runs(changed)]
    reports = []
    for spec in SPECS:
        writes, report = build_program(orig, spec, codes)
        for off, data in writes.items():
            rom[off:off + len(data)] = data
        reports.append(report)
    dropped = 0
    if write_log is not None:
        keep = []
        for row in write_log:
            a = row[0]
            n = max(row[1] or 0, row[2] or 0, 1)
            if any(a < e and a + n > s for _, s, e in CLIENT_RANGES):
                dropped += 1
                continue
            keep.append(row)
        write_log[:] = keep
    problems = verify(rom, orig, codes)
    if problems:
        raise LinkClientFontError(f'link client font verify failed: {problems[:10]}')
    return {'images': reports, 'reverted_runs': [(n, f'0x{a:06X}', f'0x{b:06X}') for n, a, b in reverted],
            'reverted_bytes': sum(b - a for _, a, b in reverted), 'write_log_dropped': dropped,
            'asset_blocks': [(f'0x{a:06X}', f'0x{b:06X}') for a, b in assets]}


# ---------------------------------------------------------------------------
# Final-ROM checks (shared by the build and tools/qa_link_client_font.py)

def _controls(body):
    out, pos = [], 0
    while pos < len(body):
        if body[pos] < 0x80:
            out.append(body[pos])
            pos += 1
        else:
            pos += 2
    return out


def decode_table(rom, spec):
    out = []
    for k in range(TABLE_HALFWORDS):
        code = bytes(rom[spec.table + 2 * k:spec.table + 2 * k + 2])
        if code == SENTINEL:
            break
        out.append(code)
    return out


def _expected_glyph(orig, spec, ch):
    """Independent expectation for one table entry (QA only; never used by the build)."""
    if ch in PUNCT_FROM_ORIGINAL:
        return original_cell(orig, spec, PUNCT[ch])
    if ch == '，':
        return _comma()
    import render_galmuri_8x16 as galmuri
    if galmuri._font_cache is None:
        from bdf import load_bdf
        galmuri._font_cache = load_bdf(os.path.join(BASE, 'reference', 'fonts', 'Galmuri11-Condensed.bdf'))[0]
    top, bottom = galmuri.render_char(ch)          # default ink 9

    def remap(tile):                               # explicit nibble 9 -> 0xA
        out = bytearray()
        for b in tile:
            lo, hi = b & 15, b >> 4
            lo = 0xA if lo == 9 else lo
            hi = 0xA if hi == 9 else hi
            out.append(lo | (hi << 4))
        return bytes(out)
    return remap(top), remap(bottom)


def _glyph_pixel_problems(rom, orig, spec, table, codes):
    by_code = {v: k for k, v in codes.items()}
    by_code.update({v: k for k, v in PUNCT.items()})
    problems = []
    for index, code in enumerate(table):
        ch = by_code.get(code)
        if ch is None:
            problems.append(f'{spec.name}: table code {code.hex()} has no known glyph')
            continue
        cell = spec.cell(index)
        top = bytes(rom[spec.sheet + cell * 32:spec.sheet + cell * 32 + 32])
        bottom = bytes(rom[spec.sheet + (cell + spec.row) * 32:spec.sheet + (cell + spec.row) * 32 + 32])
        if (top, bottom) != _expected_glyph(orig, spec, ch):
            problems.append(f'{spec.name}: glyph pixels mismatch at cell {index} for {ch!r} ({code.hex()})')
    return problems


def verify(rom, orig, codes=None):
    codes = codes or load_codes()
    problems = []
    assets = asset_mask(orig)
    for spec in SPECS:
        table = decode_table(rom, spec)
        if len(table) > MAX_CODES:
            problems.append(f'{spec.name}: table has {len(table)} codes (> {MAX_CODES}) / no sentinel')
        if len(set(table)) != len(table):
            problems.append(f'{spec.name}: duplicate table codes')
        tail = rom[spec.table + 2 * len(table):spec.table + 2 * TABLE_HALFWORDS]
        if tail != SENTINEL * (TABLE_HALFWORDS - len(table)):
            problems.append(f'{spec.name}: table tail is not 0x8140 sentinel fill')
        if rom[spec.table + 2 * TABLE_HALFWORDS:spec.table + 2 * TABLE_HALFWORDS + 4] != bytes(4):
            problems.append(f'{spec.name}: reserved halfwords after table changed')
        for index in range(len(table)):
            cell = spec.cell(index)
            top = rom[spec.sheet + cell * 32:spec.sheet + cell * 32 + 32]
            bottom = rom[spec.sheet + (cell + spec.row) * 32:spec.sheet + (cell + spec.row) * 32 + 32]
            if table[index] != PUNCT['　'] and not any(top) and not any(bottom):
                problems.append(f'{spec.name}: empty glyph cell {index} for code {table[index].hex()}')
        problems.extend(_glyph_pixel_problems(rom, orig, spec, table, codes))
        tset = set(table)
        pages = {}
        for item in spec.live:
            name, off, slot = item[0], item[1], item[2]
            raw = bytes(rom[off:off + slot])
            body = raw.split(b'\0', 1)[0]
            if any(raw[len(body):]):
                problems.append(f'{spec.name} {name}: non-NUL padding')
            pos = 0
            seq = []
            while pos < len(body):
                b = body[pos]
                if b < 0x80:
                    if b not in CONTROLS:
                        problems.append(f'{spec.name} {name}: halfwidth byte 0x{b:02X} at +{pos}')
                    pos += 1
                    continue
                code = body[pos:pos + 2]
                if code not in tset:
                    problems.append(f'{spec.name} {name}: code {code.hex()} not in table')
                seq.append(code)
                pos += 2
            pages[name] = set(seq)
            orig_raw = bytes(orig[off:off + slot]).split(b'\0', 1)[0]
            if _controls(orig_raw) != _controls(body):
                problems.append(f'{spec.name} {name}: control bytes differ from native')
        for page, labels in (('preload_page1', ('label_end', 'label_system', 'label_surrender',
                                                 'label_wait', 'label_join')),
                             ('preload_page2', ('label_attack',)),
                             ('preload_page0', ('yesno',))):
            need = set().union(*(pages.get(x, set()) for x in labels)) - {PUNCT['　']}
            missing = need - pages.get(page, set())
            if missing:
                problems.append(f'{spec.name}: {page} lacks label codes {sorted(c.hex() for c in missing)}')
        owned = owned_ranges(spec)
        for i in range(spec.rom, spec.end):
            if rom[i] != orig[i] and not _in(owned, i) and not _in(assets, i):
                problems.append(f'{spec.name}: byte 0x{i:06X} differs outside table/sheet/live/asset')
                break
    for table in CHARSET_TABLES:
        if not any(spec.table == table for spec in SPECS):
            if rom[table:table + 120] != orig[table:table + 120]:
                problems.append(f'dead charset table 0x{table:X} changed')
    for name, start, end in (('stage1_headers',) + STAGE1_HEADERS, ('dead_copies',) + DEAD_COPIES):
        for i in range(start, end):
            if rom[i] != orig[i] and not _in(assets, i):
                problems.append(f'{name}: byte 0x{i:06X} differs from original outside asset blocks')
                break
    return problems
