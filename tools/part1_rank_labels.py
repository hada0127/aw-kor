"""Observed Part 1 rank-card labels, within their original compressed allocations."""
import hashlib
import json
import struct
from pathlib import Path

from lz77_scan import lz77_decompress
from lz77_compress import lz77_compress_optimal

ROOT = Path(__file__).resolve().parent.parent
# source, pointer, next allocation, original decoded SHA, Korean text, x offset
LABELS = (
    (0xBF13F4, 0xDFA360, 0xBF1460,
     '2f3944152d3605911929553366378d0b07310368a5dc765cc7f86394e37fc031', '브론즈', 0),
    (0xBF1460, 0xDFA364, 0xBF14C4,
     '866246acb3a293d1bf748fa9ff288857544cabca010c1bf273185f8936b06c39', '아이언', 0),
    (0xBF14C4, 0xDFA368, 0xBF152C,
     '2196ae84f066291c216adcf92f374381fc7382ecd359b83a40b4e51905704eb3', '스틸', 0),
    (0xBF152C, 0xDFA36C, 0xBF1598,
     '7204f89638c67cd52a9aaf21e9ca2211b0b3c4273be3e9461bd1444ae22e85dd', '실버', 0),
    (0xBF1598, 0xDFA370, 0xBF15F8,
     '42e5b88853fd18e946b0105f8a365d2d94cff48647ffcea1f84b6ab06d6850fb', '골드', 0),
    (0xBF15F8, 0xDFA374, 0xBF1660,
     'a9f6f16912333ce815e00188bf859149de96ab8bbd56d34a89c420bb4c77cc56', '플래티넘', 0),
    (0xBF1660, 0xDFA378, 0xBF16A4,
     'bd006c29bd7a95381956eed5b91a5f4efd2736213e286e532159c6f02c554516', '래트', 3),
    # 2026-10-06: remaining animal ranks (table entries 7..21), same x offset as 래트.
    # Loanword transliteration like 래트; 캣/도그/드래곤 follow existing project text.
    (0xBF16A4, 0xDFA37C, 0xBF16F8,
     '9547df73294ade0e04179128660e792df68550e42d26871cf0080edad7351cfb', '치킨', 3),
    (0xBF16F8, 0xDFA380, 0xBF1754,
     '80c34f0ac5ae5f62d4c429bbc3269d4a2f2bcb1b7da3cefeeb6599bce2d38a95', '래빗', 3),
    (0xBF1754, 0xDFA384, 0xBF17AC,
     '617f997347041d137abb9ab81d2b27b79c9b871f4440dc503284975ce79522e7', '캣', 3),
    (0xBF17AC, 0xDFA388, 0xBF1808,
     'd2590d8347da9f49bfe961d00ade9cf8ec13723f5202bb0fcf4fb8882b150f24', '도그', 3),
    (0xBF1808, 0xDFA38C, 0xBF1864,
     '41d7a485012dff3a19782c6fc258cf4fa837821f336ba3e22e3892bb2eb3ddbd', '몽키', 3),
    (0xBF1864, 0xDFA390, 0xBF18B8,
     'cfd678c896dc9cd72c9941b2c70c3bc35ac50c8d17be2c244457302fe65e90d1', '시프', 3),
    (0xBF18B8, 0xDFA394, 0xBF1924,
     'c0917eae28099826c426fa8232ef958a2cedf7ea7a1b17c7bf5cf0a51c624b7b', '가젤', 3),
    (0xBF1924, 0xDFA398, 0xBF197C,
     '36ca8f0ebf1550b8187d49a4ca789cc1045ec910dda409c8ff80dc63f8a35042', '호스', 3),
    (0xBF197C, 0xDFA39C, 0xBF19D8,
     'f1156b2ef878b14898ac3c6029302e249dc6e9acefadb1018127dfb1965af79b', '울프', 3),
    (0xBF19D8, 0xDFA3A0, 0xBF1A2C,
     'd06ce88b608f22fd1277d1f85b43abd3b6e34ec3e5e07f2eb7bcfd880167241a', '불', 3),
    (0xBF1A2C, 0xDFA3A4, 0xBF1A94,
     '97dc2a4e9fd425a7152974df28c48cfade11f9c58db74184b3eb856fb9009dff', '팬서', 3),
    (0xBF1A94, 0xDFA3A8, 0xBF1AE4,
     '53545f27e6a1d750990c5b0d5d924535e45f1a3c0f93145b999f57407f827315', '베어', 3),
    (0xBF1AE4, 0xDFA3AC, 0xBF1B4C,
     'c0ba7ab42cd6775da909c2884d803ca0b23b7c0e34f3096b86c69d47b5c86d00', '타이거', 3),
    (0xBF1B4C, 0xDFA3B0, 0xBF1BB8,
     'b32321b356394ddcdeaf57136acd2203fa90dca624d9c65efbbe0e2ef5aad262', '라이온', 3),
    (0xBF1BB8, 0xDFA3B4, 0xBF1C18,
     '9cabe67601d5d44a542f99b292b33fc066fa4eab9b2191db9ff718759d063587', '드래곤', 3),
)
# The last table entry (0xDFA3B4) is followed by this non-pointer word instead
# of the next label pointer; its allocation ends at 0xBF1C18 (single reference).
TABLE_END, TABLE_END_WORD = 0xDFA3B8, 0x80000006


def original_label(original, spec):
    source, pointer, following, expected_hash, _, _ = spec
    next_word = TABLE_END_WORD if pointer + 4 == TABLE_END else following + 0x08000000
    if struct.unpack_from('<II', original, pointer) != (source + 0x08000000, next_word):
        raise AssertionError('rank label pointer/allocation changed')
    decoded = lz77_decompress(original, source)
    if (decoded is None or len(decoded[0]) != 256
            or hashlib.sha256(decoded[0]).hexdigest() != expected_hash
            or source + decoded[1] > following):
        raise AssertionError('rank label source changed')
    return decoded


def render_label(text, x_offset):
    # Reuse the native 8x16 dialogue font, preserving its size and glyph spacing.
    mapping = json.loads((ROOT / 'data/syllable_to_glyph_2350.json').read_text())['map']
    blob = (ROOT / 'data/kor_glyphs_2350.bin').read_bytes()
    if not text or x_offset < 0 or x_offset + len(text) * 8 > 32:
        raise AssertionError('rank label exceeds 32x16 allocation')
    raw = bytearray(256)
    for column, char in enumerate(text):
        for half, part in enumerate(('top', 'bot')):
            start = mapping[char][part] * 32
            tile = blob[start:start + 32]
            if len(tile) != 32:
                raise AssertionError('rank label font tile missing')
            for y in range(8):
                for x in range(8):
                    if not ((tile[y * 4 + x // 2] >> (4 * (x % 2))) & 15):
                        continue
                    px, py = x_offset + column * 8 + x, half * 8 + y
                    offset = (py // 8 * 4 + px // 8) * 32 + py % 8 * 4 + px % 8 // 2
                    # Original rank palette: index 10 is the solid text ink.
                    raw[offset] |= 10 << (4 * (px % 2))
    return bytes(raw)


def patch_rank_labels(rom, original):
    for spec in LABELS:
        source, pointer, _, _, text, x_offset = spec
        _, capacity = original_label(original, spec)
        if bytes(rom[pointer:pointer + 8]) != bytes(original[pointer:pointer + 8]):
            raise AssertionError('rank label live pointer changed')
        expected = render_label(text, x_offset)
        compressed = lz77_compress_optimal(expected, vram_safe=True)
        if len(compressed) > capacity:
            raise AssertionError('rank label compressed allocation overflow')
        # Never borrow alignment padding or the following asset's bytes.
        rom[source:source + capacity] = compressed + bytes(capacity - len(compressed))
        if lz77_decompress(rom, source)[0] != expected:
            raise AssertionError('rank label round trip failed')
    return len(LABELS)


def capture_rank_regions(rom, original):
    """Freeze the post-editor assets; explicit pixel edits remain supported."""
    regions = []
    for spec in LABELS:
        source, pointer = spec[:2]
        _, capacity = original_label(original, spec)
        if bytes(rom[pointer:pointer + 8]) != bytes(original[pointer:pointer + 8]):
            raise AssertionError('rank label final pointer changed')
        decoded = lz77_decompress(rom, source)
        if decoded is None or len(decoded[0]) != 256 or decoded[1] > capacity:
            raise AssertionError('rank label final compressed allocation invalid')
        regions.extend(((source, bytes(rom[source:source + capacity])),
                        (pointer, bytes(rom[pointer:pointer + 8]))))
    return tuple(regions)


def verify_rank_regions(rom, regions):
    if len(regions) != len(LABELS) * 2:
        raise AssertionError('rank label ownership evidence missing')
    for address, expected in regions:
        if bytes(rom[address:address + len(expected)]) != expected:
            raise AssertionError(f'rank label overwritten at {address:08X}')
