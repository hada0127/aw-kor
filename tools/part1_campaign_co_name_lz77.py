"""Part 1 CO name LZ77 sheets referenced by the CO struct table 0xDF3B54 (+4).

Each sheet decodes to 384 bytes = one 32x16 OBJ cell (tiles 0..7, 4x2, 1D)
followed by one 16x16 cell (tiles 8..11, 2x2): a 48x16 name plate.  Static
evidence: the original katakana reads cleanly only in that layout (six 8x16
kana: キャサリン / リョウ / ... ; temp/claude_2026-10-06/fixA/work/co_names.png).
Original ink is palette index 10 with sparse anti-alias indices 3..8.

Korean names are CO_NAME_KO in build_korean_full.py.  Glyphs come from the
project's native 8x16 dialogue font (data/kor_glyphs_2350.bin), solid ink 10,
centred in 48px, exactly like part1_rank_labels.render_label.

0xC102A8 (Catherine, struct 0) is NOT owned here: build_korean_full.py writes
it via build_title_hangul.make_part1_catherine_block (96x8 strip order).
0xC10984 is shared by struct 10 and 11 (both ヘルボウズ) and is patched once.
0xC10AA0 (ハチ) is referenced only from 0xB42E48 (outside the struct table).
Every sheet is recompressed in place inside its original compressed span.
"""
import hashlib
import json
import struct
from functools import lru_cache
from pathlib import Path

from lz77_scan import lz77_decompress
from lz77_compress import lz77_compress_optimal

ROOT = Path(__file__).resolve().parent.parent
ROM_BASE = 0x08000000
STRUCT_TABLE, STRUCT_STRIDE, NAME_FIELD = 0xDF3B54, 0x20, 4
INK = 10
SIZE = 384
# (source, pointers, following, compressed capacity, decoded sha256, Korean, original kana)
NAMES = (
    (0xC10380, (0xDF3B78,), 0xC1040C, 139,
     '5d9485d4bba51cab8a9ee5cac41b438f73237a801568f1f96ea21aebc8d5e6f0', '료', 'リョウ'),
    (0xC1040C, (0xDF3B98,), 0xC104C0, 177,
     'd6b3d76c437bfcf50a71b4cc765bf2a7f27a9ce63f7ce932aba35d2b6c60ef4a', '맥스', 'マックス'),
    (0xC104C0, (0xDF3BB8,), 0xC10594, 211,
     '6bbe444ca6a0b87a4b747e1549c7551de9019d13a03164899a8783e13520b59b', '호이프', 'ホイップ'),
    (0xC10594, (0xDF3BD8,), 0xC10628, 147,
     '434717b50b3609c20bd85e7c66b67ef50ad2f614306fd2f8ec357cf712dd5984', '도미노', 'ドミノ'),
    (0xC10628, (0xDF3BF8,), 0xC106B0, 133,
     'e60b091f7afbd793c7ec5f3c2ac3997860fc26bbbfbc4acb963d3fe5429b83c2', '빌리', 'ビリー'),
    (0xC106B0, (0xDF3C18,), 0xC10758, 166,
     'b211fecdfd85ef2a3503957d4394694b0e137dfc9489743e9aa44eb270bb795e', '키쿠치요', 'キクチヨ'),
    (0xC10758, (0xDF3C38,), 0xC10824, 202,
     '1f3ad9d296b03700467168e489d907216ffc8d243ac0c0808b6d33a80d4a59e0', '아스카', 'アスカ'),
    (0xC10824, (0xDF3C58,), 0xC108DC, 182,
     'fb344f9a4bc2ec0bf1b680d1539807a4902042c7898bf14474672a228b5f3030', '이글', 'イーグル'),
    (0xC108DC, (0xDF3C78,), 0xC10984, 166,
     'd739a155a5f9574ab3afe9806e431293c77dbae479cb53cf7f9612ba7959adac', '모프', 'モップ'),
    (0xC10984, (0xDF3C98, 0xDF3CB8), 0xC10AA0, 282,
     '2b8221688a1219dfb4b33fdfe5db53be32e319c2db5e10315076e795f27f5769', '헬보우즈', 'ヘルボウズ'),
    (0xC10AA0, (0xB42E48,), 0xC10B34, 145,
     '797d3defb4b19fb5df7f0d457b39e0f5c46eb005aedda4dc5148ba9b34d4a1cc', '하치', 'ハチ'),
)
CATHERINE = 0xC102A8  # owned by build_korean_full.py; never written here


def source_guard(original):
    for source, pointers, following, capacity, digest, _, _ in NAMES:
        for pointer in pointers:
            if struct.unpack_from('<I', original, pointer)[0] != source + ROM_BASE:
                raise AssertionError(f'Part 1 CO name pointer changed {pointer:06X}')
        if original.count(struct.pack('<I', source + ROM_BASE)) != len(pointers):
            raise AssertionError(f'Part 1 CO name has foreign reference {source:06X}')
        decoded = lz77_decompress(original, source)
        if (decoded is None or len(decoded[0]) != SIZE or decoded[1] != capacity
                or hashlib.sha256(decoded[0]).hexdigest() != digest
                or not 0 <= following - source - capacity < 4):
            raise AssertionError(f'Part 1 CO name source/allocation changed {source:06X}')
    for i in range(12):
        pointer = STRUCT_TABLE + STRUCT_STRIDE * i + NAME_FIELD
        target = struct.unpack_from('<I', original, pointer)[0] - ROM_BASE
        if i == 0:
            if target != CATHERINE:
                raise AssertionError('Part 1 CO struct 0 name pointer changed')
        elif not any(pointer in row[1] and row[0] == target for row in NAMES):
            raise AssertionError(f'Part 1 CO struct {i} name pointer changed')


@lru_cache(maxsize=1)
def _font():
    mapping = json.loads((ROOT / 'data/syllable_to_glyph_2350.json').read_text())['map']
    return mapping, (ROOT / 'data/kor_glyphs_2350.bin').read_bytes()


def _offset(px, py):
    if px < 32:
        tile = (py // 8) * 4 + px // 8
    else:
        tile = 8 + (py // 8) * 2 + (px - 32) // 8
    return tile * 32 + (py % 8) * 4 + (px % 8) // 2


@lru_cache(maxsize=None)
def render_name(text):
    """48x16 plate (32x16 + 16x16 cells) with centred native 8x16 glyphs."""
    mapping, blob = _font()
    if not text or len(text) * 8 > 48:
        raise AssertionError('Part 1 CO name exceeds 48x16 plate')
    x0 = (48 - len(text) * 8) // 2
    raw = bytearray(SIZE)
    for column, char in enumerate(text):
        for half, part in enumerate(('top', 'bot')):
            start = mapping[char][part] * 32
            tile = blob[start:start + 32]
            if len(tile) != 32:
                raise AssertionError('Part 1 CO name font tile missing')
            for y in range(8):
                for x in range(8):
                    if (tile[y * 4 + x // 2] >> (4 * (x % 2))) & 15:
                        px, py = x0 + column * 8 + x, half * 8 + y
                        raw[_offset(px, py)] |= INK << (4 * (px % 2))
    return bytes(raw)


def _text(source):
    for row in NAMES:
        if row[0] == source:
            return row[5]
    raise KeyError(f'{source:06X}')


def render(source):
    return render_name(_text(source))


def _pointers(rom, pointers):
    return b''.join(bytes(rom[p:p + 4]) for p in pointers)


def patch(rom, original):
    source_guard(original)
    plan = []
    for source, pointers, following, capacity, _, _, _ in NAMES:
        if (_pointers(rom, pointers) != _pointers(original, pointers)
                or bytes(rom[source:following]) != original[source:following]):
            raise AssertionError(f'Part 1 CO name {source:06X} already modified by another writer')
        stream = lz77_compress_optimal(render(source), vram_safe=True)
        if len(stream) > capacity:
            raise AssertionError(f'Part 1 CO name compressed allocation overflow {source:06X}: '
                                 f'{len(stream)} > {capacity}')
        plan.append((source, capacity, stream))
    for source, capacity, stream in plan:
        rom[source:source + capacity] = stream + bytes(capacity - len(stream))
        decoded = lz77_decompress(rom, source)
        if decoded is None or decoded[0] != render(source):
            raise AssertionError(f'Part 1 CO name round trip failed {source:06X}')
    return len(plan)


def capture(rom, original):
    from part1_mission_titles import verify_vram_stream
    source_guard(original)
    regions = []
    for source, pointers, following, capacity, _, _, _ in NAMES:
        decoded = lz77_decompress(rom, source)
        if (decoded is None or len(decoded[0]) != SIZE or decoded[1] > capacity
                or _pointers(rom, pointers) != _pointers(original, pointers)
                or bytes(rom[source + capacity:following]) != original[source + capacity:following]):
            raise AssertionError(f'Part 1 CO name final allocation changed {source:06X}')
        verify_vram_stream(bytes(rom[source:source + capacity]), SIZE, 'Part 1 CO name')
        regions.append((source, bytes(rom[source:following])))
        regions.extend((p, bytes(rom[p:p + 4])) for p in pointers)
    return tuple(regions)


def expected_region_addresses():
    out = []
    for source, pointers, *_ in NAMES:
        out.append(source)
        out.extend(pointers)
    return tuple(out)


def verify(rom, regions):
    if tuple(p for p, _ in regions) != expected_region_addresses():
        raise AssertionError('Part 1 CO name snapshot missing')
    for address, raw in regions:
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError(f'Part 1 CO name overwritten after editor at {address:06X}')


def generated_matches(rom):
    for source, *_ in NAMES:
        decoded = lz77_decompress(rom, source)
        if decoded is None or decoded[0] != render(source):
            return False
    return True
