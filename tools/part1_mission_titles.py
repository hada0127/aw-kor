"""Part 1 campaign mission-start title banners, table-driven over 0xE12BF4.

The mission-start banner consumer reads one LZ77 sheet per mission from the
63-entry pointer table at 0xE12BF4 (same consumer as the M19/M20 titles in
part1_m19_title.py / part1_m20_title.py).  Each 2048-byte sheet is two native
64x32 OBJ cells in 1D order (tiles 0..31 = left half, 32..63 = right half).

Entries 14..27 of the table are 1024-byte "extension" cells for missions 0..13;
all but one point at the shared blank 0xC12F58.  Entry 16 (0xC12E40) carries
the overflow of mission 2 (前線基地を確保せよ！): in the original the glyph せ is
split across the right edge of 0xC1100C and the left edge of 0xC12E40 tiles
0..15 laid out as one 32x32 cell (4x4 tiles), so the mission-2 banner is a
160x32 canvas = 128x32 main sheet + 32x32 extension (static evidence:
temp/claude_2026-10-06/fixA/work/c1100c_ext.png).  Extension tiles 16..31 are
blank in the original and stay blank.

Skipped (owned by other writers): 0xC10B34 / 0xC11D9C / 0xC1205C
(build_korean_full.py), 0xC15A68 (part1_m19_title), 0xC15C5C
(part1_m20_title) and the shared blank filler 0xC12F58.

Korean text = B-team mission names (data/bteam_baseline.json, 0xB81D80..0xB82018)
verbatim when available; see TITLES for per-entry source notes.

Style = M19/M20: Galmuri7 at integer 2x, ink 10, lower-right shadow 13,
3x3 outline 15.  Titles too wide for 2x Galmuri7 fall back to Galmuri11 1x
with the same palette roles (see layout()).  Every sheet is recompressed with
the project's optimal VRAM-safe LZ77 encoder inside its original compressed
allocation; pointers never move.
"""
import hashlib
import struct
from functools import lru_cache
from pathlib import Path

from bdf import load_bdf, glyph_grid
from lz77_scan import lz77_decompress
from lz77_compress import lz77_compress_optimal

ROOT = Path(__file__).resolve().parent.parent
TABLE, TABLE_ENTRIES = 0xE12BF4, 63
ROM_BASE = 0x08000000
INK, SHADOW, OUTLINE = 10, 13, 15
# Owned by other writers or shared filler; never touched by this module.
SKIP = frozenset((0xC10B34, 0xC11D9C, 0xC1205C, 0xC15A68, 0xC15C5C, 0xC12F58))

# Extension cell of mission 2 (table index 16): source, following, capacity, size, sha.
EXTENSION = (0xC12E40, 0xC12F58, 279, 1024,
             '1dda8ed23cc54c614f10637c976c553306e9b5311402ff23b93fd8517d7fcd61', (16,))
EXTENSION_OWNER = 0xC1100C

# (source, following, compressed capacity, decoded sha256, table indices, Korean, source note)
TITLES = (
    (0xC10DC0, 0xC1100C, 588, '69d97089b515cd0dea06d6069b145309d4d1d13847caa2502c2a2411392a5782',
     (1,), '초반전!', 'new: 序盤戦！ (0x00B8200C has no B-team text)'),
    (0xC1100C, 0xC112DC, 717, 'a0ecf43bf195d33abeeaeaee72acf337cb412394f3dc889f04be7e5d66f4d5a8',
     (2,), '전선 기지를 확보하라!', 'bteam 0x00B81FF4'),
    (0xC112DC, 0xC11598, 699, '6a00f491c2016b0dbc05c50f2a98b18f06588a941eede133d9ccdd5f7c92cf27',
     (3,), '싸워라　고물 전차!', 'bteam 0x00B81FDC'),
    (0xC11598, 0xC118A8, 783, '188cb3125be2a59e7657a8bf8d21788a994b837a3dce2665142e4431c075a028',
     (4,), '적 부대를 해치워라!', 'bteam 0x00B81FC4'),
    (0xC118A8, 0xC11B84, 732, '3e7c6b30a541dce88ec9f16e16597829e6941a788a5ddb70a144ad837b48f4a5',
     (5,), '지상 최강! 중전차!!', 'bteam 0x00B81FAC'),
    (0xC11B84, 0xC11D9C, 536, 'c9f013659ec3166e7c6a8ae8d5f706f233ac736c8629f4b8d14e3cfee678fe11',
     (6,), '드래곤플라이!', 'bteam 0x00B81F98'),
    (0xC122DC, 0xC12500, 546, '6a76326eff166a1ac7fcb53cbfabfe92d3d783becb2f6f2155230d148b38f09b',
     (9,), '도그 파이트!', 'bteam 0x00B81F5C'),
    (0xC12500, 0xC1275C, 604, 'a42ccac8a0e9d08090117c7fdd344cb9fa29d8630a5f155dc233a572539c530b',
     (10,), '바다 저편에', 'bteam 0x00B81F4C'),
    (0xC1275C, 0xC129E0, 644, '9c62770f6794fcb1a1a205b91c82b7155ea77d8c679b3c8fcfeaa9e86787acc6',
     (11,), '백은의 세계', 'bteam 0x00B81F40'),
    (0xC129E0, 0xC12BE0, 509, '0fe07169b90996cf9a1381ceaf6ce4e52a69893565d2d8bfb1ea8dfa8d3e5623',
     (12,), '결전!', 'existing: dialogue 0x00DF95F5 「결전」 (mission-name reference)'),
    (0xC12BE0, 0xC12E40, 607, '7a49d0e09058be1c34c081b1b5055b8f76b48b1a99562826c6b6fb78bd82b9ce',
     (13,), '과외 수업', 'existing: bteam dialogue 0x00D9F17A/0x00DA0A00 과외 수업'),
    (0xC12FD8, 0xC131CC, 498, '4f63db140e6628fcdec8f73487c3bc656f8765820ec532021e6d175bc78d80cb',
     (28,), '개전!', 'existing: translation_for_import 0x00805104 개전!'),
    (0xC131CC, 0xC133DC, 525, '10a6bdf00b0a611e7c43df09372ab162c93d6f827b5b9d95efa76a63b997dd75',
     (29,), '건 파이터!', 'bteam 0x00B81F10'),
    (0xC133DC, 0xC135D8, 506, '2139b4c37b755d5a4fb1e99bae687ac71a210a505d15ade0b381b08ed40c9df8',
     (30,), '하늘의 용사!', 'bteam 0x00B81F04'),
    (0xC135D8, 0xC13844, 617, 'e869ddfab9bd6716cb07bbad4ab1b970f20bc1ef3ce189f2566b9e60ca2bbed5',
     (31, 35), '맥스 출격!', 'bteam 0x00B81EF4'),
    (0xC13844, 0xC13A34, 493, '3a84cfd1058141e8ba14de12ce8ddf183e1a880583c68b733d3710870ce6aee9',
     (36,), '스나이퍼!', 'bteam 0x00B81EA8'),
    (0xC13A34, 0xC13CAC, 629, '64ef7379723adf230719668f9fb0ffb5bbe1b66aea56c34f4f3f71106f8e0eb9',
     (37,), '눈 속의 싸움!', 'bteam 0x00B81E98'),
    (0xC13CAC, 0xC13EE0, 562, '71e40bee67a700dfb203f5a9f0c30749cf8eae9b3f3ff938e8bf2815260afd12',
     (38,), '3명의 과거', 'bteam 0x00B81E8C'),
    (0xC13EE0, 0xC1420C, 810, 'f2bb148c03e3153123b69bfbebecaad234b6ef90ed9b80c1fc82705cc0be8c7c',
     (39,), '특수 부대장 도미노!', 'bteam 0x00B81E78'),
    (0xC1420C, 0xC14488, 633, 'c2a8178669e8fd3cc4e810bceaaca4e33d01ab9f9bcb4af75a3642c92df5af34',
     (40,), '키쿠치요 등장!', 'bteam 0x00B81E64'),
    (0xC14488, 0xC14770, 744, '84f9501304a7fb67bd1ea4fd09eaa9d792dc71eeb07398f81158876ba25c998c',
     (41,), '최강! 키쿠치요 부대', 'bteam 0x00B81E50'),
    (0xC14770, 0xC14A2C, 697, '8c314bf79468ccd852e628a2fceff2fab4ece8a4d5e6d9be9d24b60a529d7adf',
     (42,), '키쿠치요의 실수?', 'bteam 0x00B81E38'),
    (0xC14A2C, 0xC14C9C, 624, 'd28ce453a11f546d51d93808aaf89a607e790ce3e3a268948a2fa777a71be554',
     (43,), '분단 작전!', 'bteam 0x00B81E2C'),
    (0xC14C9C, 0xC14EE8, 586, '70f1624c4fa31f7790fe211b28560672f9ea167764033daedca8f4ff456a9893',
     (44,), '도미노의 능력!', 'bteam 0x00B81E1C'),
    (0xC14EE8, 0xC1513C, 595, 'a66302e1839ced2e7201110eeba45dcceecc67510035c4884766c9f81c432e3f',
     (45,), '아스카의 노림수!', 'bteam 0x00B81E08'),
    (0xC1513C, 0xC15394, 598, 'fe887164d8b5b146bd24f32e4cc397c8d74498a6fac4d82e7833ad166177dc75',
     (46, 47, 48), '캡틴 모프!', 'bteam 0x00B81DF0'),
    (0xC15394, 0xC15594, 510, '46fad1f46000377ff4e6ac71731d723f22300d6979cfd8309a3d6972ade885ff',
     (49, 50, 51), '해전!', 'existing term: bteam 0x00A2D62C/0x00D9C4B2 해전 (B81DE8 has no B-team text)'),
    (0xC15594, 0xC15808, 625, 'e0795d543d82aeb63a213819b9fcbcabb40bdc01d3a8ee9ee4bd61b1322119c0',
     (52, 53, 54), '거대한 날개!', 'bteam 0x00B81DD4'),
    (0xC15808, 0xC15A68, 606, 'fba259640ff11e148b110297114f20c1e93a9cd71c5dc1d3071614bd3aa54e9a',
     (55, 56, 57), '전투 뒤에서', 'bteam 0x00B81DC4'),
    (0xC15E00, 0xC160B8, 695, 'bc2ccfddc1c6c26c784bbc86057e276f0f18a121330eaf48c07623f452eadd13',
     (60,), '결판! 칠흑의 숲!', 'bteam 0x00B81D94'),
    (0xC160B8, 0xC1636C, 692, '57ece2b57ecc26fbdf4570922aa58612c0c2857edfa34062cee06cc5fc7671e0',
     (32,), '맥스의 약점!?', 'bteam 0x00B81EE0'),
    (0xC1636C, 0xC165D8, 617, '318bda5ceeca64f40163b05de7e5874246d58bee1de410886b7f84d7ad2b58db',
     (33,), '호이프 해군!', 'bteam 0x00B81ED0'),
    (0xC165D8, 0xC1689C, 708, '8bacaf0a2a1270b026ca2986457917faacc0ac4d3f56f29884437c9f31961049',
     (34,), '호이프 해군 터보!', 'bteam 0x00B81EB8'),
    (0xC1689C, 0xC16B38, 668, '7b3b708efe4f3567a6b82bc2fc6ae1d2d47ea62cdc7d5a018cc2b3b68485d6b4',
     (61,), '최강의 라이벌!', 'bteam 0x00B81D80'),
)
SPACES = (' ', '　')


def _all_blocks():
    """(source, following, capacity, size, sha, indices) for every owned block."""
    for source, following, capacity, digest, indices, _, _ in TITLES:
        yield source, following, capacity, 2048, digest, indices
    yield EXTENSION


def source_guard(original):
    """Original ROM must match the analysed table, allocations and decoded art."""
    expected = {}
    for i in range(TABLE_ENTRIES):
        target = struct.unpack_from('<I', original, TABLE + 4 * i)[0] - ROM_BASE
        expected.setdefault(target, []).append(i)
    for source, following, capacity, size, digest, indices in _all_blocks():
        if source in SKIP:
            raise AssertionError('Part 1 mission title skip set overlaps an owned block')
        if tuple(expected.get(source, ())) != tuple(indices):
            raise AssertionError(f'Part 1 mission title table changed for {source:06X}')
        # Every live reference to the sheet must be one of its own table slots.
        if original.count(struct.pack('<I', source + ROM_BASE)) != len(indices):
            raise AssertionError(f'Part 1 mission title has foreign reference {source:06X}')
        decoded = lz77_decompress(original, source)
        if (decoded is None or len(decoded[0]) != size or decoded[1] != capacity
                or hashlib.sha256(decoded[0]).hexdigest() != digest
                or not 0 <= following - source - capacity < 4):
            raise AssertionError(f'Part 1 mission title source/allocation changed {source:06X}')
    for source in SKIP:
        if source not in expected:
            raise AssertionError('Part 1 mission title skipped sheet left the table')


@lru_cache(maxsize=None)
def _font(name):
    font, _ = load_bdf(str(ROOT / 'reference/fonts' / name))
    return font


def _hangul(char):
    return 0xAC00 <= ord(char) <= 0xD7A3


def _ink_g7x2(text, fixed):
    """M19/M20 style: Galmuri7 at integer 2x, glyph top at y=8."""
    font, ink, cursor = _font('Galmuri7.bdf'), set(), 0
    for char in text:
        if char in SPACES:
            cursor += 8 if fixed else 6
            continue
        grid, width, height, xoffset, yoffset = glyph_grid(font[ord(char)])
        top = 7 - height - yoffset
        if not (1 <= width <= 7 and xoffset >= 0 and 0 <= top and top + height <= 8):
            raise AssertionError(f'Part 1 mission title Galmuri7 cell/baseline changed: {char}')
        for y in range(height):
            for x in range(width):
                if grid[y][x]:
                    for dy in (0, 1):
                        for dx in (0, 1):
                            ink.add((cursor + 2 * (x + xoffset) + dx, 8 + 2 * (top + y) + dy))
        if fixed and _hangul(char):
            cursor += 16
        else:
            cursor += 2 * (xoffset + width) + 2
    return ink


def _ink_g11(text):
    """Fallback for long titles: Galmuri11 at 1x, glyph top at y=10."""
    font, ink, cursor = _font('Galmuri11.bdf'), set(), 0
    for char in text:
        if char in SPACES:
            cursor += 4
            continue
        grid, width, height, xoffset, yoffset = glyph_grid(font[ord(char)])
        top = 11 - height - yoffset
        if not (1 <= width <= 12 and xoffset >= 0 and 0 <= top and top + height <= 12):
            raise AssertionError(f'Part 1 mission title Galmuri11 cell/baseline changed: {char}')
        for y in range(height):
            for x in range(width):
                if grid[y][x]:
                    ink.add((cursor + x + xoffset, 10 + top + y))
        cursor += xoffset + width + 2
    return ink


def layout(text, width):
    """Return (tier, ink set) centred in a width x 32 canvas.

    Tier order: 'g7x2' (exact M19 advance), 'g7x2_tight' (proportional 2x
    advance), 'g11' (Galmuri11 1x).  Ink must stay within x 1..width-2 and
    y 1..30 so the outline/shadow never leave the native cells.
    """
    for tier, ink in (('g7x2', lambda: _ink_g7x2(text, True)),
                      ('g7x2_tight', lambda: _ink_g7x2(text, False)),
                      ('g11', lambda: _ink_g11(text))):
        ink = ink()
        if not ink:
            raise AssertionError('Part 1 mission title has no ink')
        x0 = min(x for x, _ in ink)
        x1 = max(x for x, _ in ink)
        span = x1 - x0 + 1
        if span <= width - 2:
            shift = (width - span) // 2 - x0
            placed = {(x + shift, y) for x, y in ink}
            if any(not (1 <= x < width - 1 and 1 <= y < 31) for x, y in placed):
                raise AssertionError('Part 1 mission title exceeds native OBJ cells')
            return tier, placed
    raise AssertionError(f'Part 1 mission title does not fit {width}px: {text}')


def _pixels(text, width):
    _, ink = layout(text, width)
    pixels = [[0] * width for _ in range(32)]
    for x, y in ink:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                pixels[y + dy][x + dx] = OUTLINE
    for x, y in ink:
        pixels[y + 1][x + 1] = SHADOW
    for x, y in ink:
        pixels[y][x] = INK
    return pixels


def _pack(pixels, x_base, width, cell_w, size):
    """Pack canvas columns [x_base, x_base+width) as 1D cells of cell_w x 32."""
    raw = bytearray(size)
    cols = cell_w // 8
    for y in range(32):
        for x in range(width):
            value = pixels[y][x_base + x]
            if not value:
                continue
            tile = (x // cell_w) * cols * 4 + (y // 8) * cols + (x % cell_w) // 8
            offset = tile * 32 + (y % 8) * 4 + (x % 8) // 2
            raw[offset] |= value << (4 * (x % 2))
    return bytes(raw)


@lru_cache(maxsize=None)
def render(source):
    """Decoded replacement bytes for one owned sheet (main or extension)."""
    if source == EXTENSION[0]:
        text = _text(EXTENSION_OWNER)
        return _pack(_pixels(text, 160), 128, 32, 32, 1024)
    text = _text(source)
    width = 160 if source == EXTENSION_OWNER else 128
    return _pack(_pixels(text, width), 0, 128, 64, 2048)


def _text(source):
    for row in TITLES:
        if row[0] == source:
            return row[5]
    raise KeyError(f'{source:06X}')


def _pointer_bytes(rom, indices):
    return b''.join(bytes(rom[TABLE + 4 * i:TABLE + 4 * i + 4]) for i in indices)


def compressed(source, capacity):
    stream = lz77_compress_optimal(render(source), vram_safe=True)
    if len(stream) > capacity:
        raise AssertionError(f'Part 1 mission title compressed allocation overflow {source:06X}: '
                             f'{len(stream)} > {capacity}')
    return stream


def patch(rom, original):
    source_guard(original)
    plan = []
    for source, following, capacity, size, _, indices in _all_blocks():
        if (_pointer_bytes(rom, indices) != _pointer_bytes(original, indices)
                or bytes(rom[source:following]) != original[source:following]):
            raise AssertionError(f'Part 1 mission title {source:06X} already modified by another writer')
        plan.append((source, capacity, compressed(source, capacity)))
    # All streams are prepared before the first write: an overflow never leaves a partial patch.
    for source, capacity, stream in plan:
        rom[source:source + capacity] = stream + bytes(capacity - len(stream))
        decoded = lz77_decompress(rom, source)
        if decoded is None or decoded[0] != render(source):
            raise AssertionError(f'Part 1 mission title round trip failed {source:06X}')
    return len(plan)


def capture(rom, original):
    source_guard(original)
    regions = []
    for source, following, capacity, size, _, indices in _all_blocks():
        decoded = lz77_decompress(rom, source)
        if (decoded is None or len(decoded[0]) != size or decoded[1] > capacity
                or _pointer_bytes(rom, indices) != _pointer_bytes(original, indices)
                or bytes(rom[source + capacity:following]) != original[source + capacity:following]):
            raise AssertionError(f'Part 1 mission title final allocation changed {source:06X}')
        verify_vram_stream(bytes(rom[source:source + capacity]), size)
        # Approved editor pixel changes remain supported; freeze their final bytes.
        regions.append((source, bytes(rom[source:following])))
        for i in indices:
            regions.append((TABLE + 4 * i, bytes(rom[TABLE + 4 * i:TABLE + 4 * i + 4])))
    return tuple(regions)


def expected_region_addresses():
    out = []
    for source, _, _, _, _, indices in _all_blocks():
        out.append(source)
        out.extend(TABLE + 4 * i for i in indices)
    return tuple(out)


def verify(rom, regions):
    if tuple(p for p, _ in regions) != expected_region_addresses():
        raise AssertionError('Part 1 mission title snapshot missing')
    for address, raw in regions:
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError(f'Part 1 mission title overwritten after editor at {address:06X}')


def generated_matches(rom):
    for source, *_ in _all_blocks():
        decoded = lz77_decompress(rom, source)
        if decoded is None or decoded[0] != render(source):
            return False
    return True


def verify_vram_stream(stream, size, label='Part 1 mission title'):
    """Validate the final stream for BIOS halfword VRAM decompression too."""
    if stream[:4] != bytes((0x10, size & 0xFF, (size >> 8) & 0xFF, size >> 16)):
        raise AssertionError(f'{label} LZ header changed')
    count, cursor = 0, 4
    try:
        while count < size:
            flags = stream[cursor]
            cursor += 1
            for bit in range(7, -1, -1):
                if count >= size:
                    break
                if flags & (1 << bit):
                    a, b = stream[cursor], stream[cursor + 1]
                    cursor += 2
                    distance = ((a & 15) << 8 | b) + 1
                    if not 2 <= distance <= count:
                        raise AssertionError(f'{label} unsafe VRAM LZ distance')
                    count += (a >> 4) + 3
                else:
                    _ = stream[cursor]
                    cursor += 1
                    count += 1
                if count > size:
                    raise AssertionError(f'{label} LZ output overrun')
    except IndexError as exc:
        raise AssertionError(f'{label} truncated LZ stream') from exc
    return cursor
