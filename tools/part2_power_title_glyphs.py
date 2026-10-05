"""Keep the AW2 COP title atlas in the same order as its Korean dictionary.

08380564 finds a two-byte code in A3B880, then copies the corresponding 32x32
cell from the 5B3ECC atlas. Updating only the dictionary made 강타 select the
original ド/ン cells. The native consumer, palette and pointers stay intact.
Only the active dictionary cells change (57 in the approved default); a later explicit sprite
editor overlay may replace the asset and is captured for the final guard.
"""
from functools import lru_cache
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
FONT = Path.home() / 'Library/Fonts/OkDanDan-Bold.otf'
FONT_SHA256 = '3b48adae2f39018dfa8e3d8264363729f024af9c7eb289dcb0479e6d7ea67472'
ORIGINAL_SHA256 = 'a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c'
ROM_SIZE = 0x1000000
OFFSET, SLOT_SIZE, RAW_SIZE = 0x5B3ECC, 6161, 32768
RAW_SHA256 = 'b601d62a378e3854067c15f09e024a98f1d1b0437d25f505797f01655bf68bd7'
ASSET_ID = 'lz77_005B3ECC'
DICTIONARY, DICTIONARY_SIZE, MAX_GLYPHS = 0xA3B880, 122, 61
NAMES_START, NAMES_END, NAME_POINTERS = 0xA2955C, 0xA29830, 0xA37B3C
# Native consumers, two atlas pointers, palette, neighboring data, name pointers.
GUARDS = (
    (0x380564, 0xEC, 'f9fb9090dac028158e96c3c8f1823a8dc2a4344c166e62a69399a17f9108926f'),
    (0x3806A8, 0x58, '196eb8a6fd4959e1136c449f233fbdcfd617ec9d0866ed3073d15167c2f03851'),
    (0x38118C, 0x18, '72cfae6085257a5f0ccc21369f5031dfed67ba630eda72be96a3f27e0d67c818'),
    (0x38121C, 0xC, 'bd8fb931b0dc3e6d11108bd116853c91f03165bb02b96f89a6a34f5201dc3bfe'),
    (0x381234, 0xD0, '3b29f8e9793b24db7ee3b44034f8791086fec641e2b7c95add07f202b34a41fe'),
    (0x5B3EBC, 0x10, '4b0c2404daddaba57120378648d3dcaf0e0498579748e2127eb0bfc624914475'),
    (0x5B56DD, 0x20, '2c7c5e1889322476f239cd8607469abe6c2106277a82898bc99583855e8a9dfb'),
    (0x5B5720, 0x20, '7573b09439c2fab8edaa2adad209439c78aea429072c3ccb8c964cd26a4df32e'),
    (0xA3B8FA, 2, '96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7'),
    (NAME_POINTERS, 36 * 4, 'd0265bfcbe9ba63b9e879140360022da973e69472fbc327572a95606ad7235ce'),
)


def _guard_current(rom):
    if len(rom) != ROM_SIZE:
        raise AssertionError('Part 2 power title requires the complete 16 MiB ROM')
    for address, size, digest in GUARDS:
        if sha256(rom[address:address + size]).hexdigest() != digest:
            raise AssertionError(f'Part 2 power title consumer/pointer/palette/neighbor changed: {address:X}')


def source(original):
    from lz77_scan import lz77_decompress
    if len(original) != ROM_SIZE or sha256(original).hexdigest() != ORIGINAL_SHA256:
        raise AssertionError('Part 2 power title original ROM changed')
    decoded = lz77_decompress(original, OFFSET)
    if (decoded is None or decoded[1] != SLOT_SIZE or len(decoded[0]) != RAW_SIZE or
            sha256(decoded[0]).hexdigest() != RAW_SHA256):
        raise AssertionError('Part 2 power title source asset changed')
    return decoded[0]


def _font_bytes():
    data = FONT.read_bytes()
    if sha256(data).hexdigest() != FONT_SHA256:
        raise AssertionError('Part 2 power title OkDanDan font changed')
    return data


def bind_dictionary(rom, display_names, syllable_codes):
    """Match all actual ROM names and dictionary to the builder's display data.

    Call after the text writers, before the sprite editor. There is no separate
    hard-coded Korean dictionary to drift from data/display_overrides.json.
    """
    _guard_current(rom)
    addresses = tuple(p - 0x08000000 for p in struct.unpack_from('<36I', rom, NAME_POINTERS))
    names = {a: t for a, t in display_names.items() if NAMES_START <= a < NAMES_END}
    if set(names) != set(addresses):
        raise AssertionError('Part 2 power title requires the exact 36 display-name addresses')
    ordered = ''.join(dict.fromkeys(''.join(names[a] for a in addresses)))
    if (not 1 <= len(ordered) <= MAX_GLYPHS or any(not '가' <= ch <= '힣' for ch in ordered)):
        raise AssertionError('Part 2 power title dictionary must have 1..61 unique Hangul glyphs')
    try:
        pairs = [int(syllable_codes[ch]).to_bytes(2, 'big') for ch in ordered]
    except (KeyError, ValueError, OverflowError, TypeError) as exc:
        raise AssertionError('Part 2 power title has an invalid or unmapped glyph code') from exc
    if (len(set(pairs)) != len(pairs) or any(not (0x81 <= p[0] <= 0x9F or 0xE0 <= p[0] <= 0xEF)
                                           or not (0x40 <= p[1] <= 0xFC and p[1] != 0x7F) for p in pairs)):
        raise AssertionError('Part 2 power title needs unique native two-byte dictionary codes')
    encoded = dict(zip(ordered, pairs))
    if bytes(rom[DICTIONARY:DICTIONARY + DICTIONARY_SIZE]) != b''.join(pairs).ljust(DICTIONARY_SIZE, b'\0'):
        raise AssertionError('Part 2 power title ROM dictionary differs from display names')
    for a, end in zip(addresses, (*addresses[1:], NAMES_END)):
        text = names[a]
        if not text or len(text) > 12:
            raise AssertionError(f'Part 2 power title name exceeds native title capacity: {a:X}')
        payload = b''.join(encoded[ch] for ch in text)
        if len(payload) >= end - a or bytes(rom[a:end]) != payload.ljust(end - a, b'\0'):
            raise AssertionError(f'Part 2 power title ROM name/padding differs: {a:X}')
    return ordered


def cell_rows(index):
    """Byte extents of four 4-tile rows in the native 32-tile-wide atlas."""
    if not 0 <= index < 64:
        raise AssertionError('power title cell index out of range')
    base = (index % 8) * 4 + (index // 8) * 128
    return tuple(((base + row * 32) * 32, 128) for row in range(4))


def decode_cell(raw, index):
    pixels = []
    for start, _ in cell_rows(index):
        for y in range(8):
            row = []
            for tile in range(4):
                for byte in raw[start + tile * 32 + y * 4:start + tile * 32 + y * 4 + 4]:
                    row.extend((byte & 15, byte >> 4))
            pixels.append(row)
    return pixels


def _glyph(ch, font):
    from PIL import Image, ImageDraw, ImageFilter
    box = font.getbbox(ch)
    fill = Image.new('L', (box[2] - box[0], box[3] - box[1]))
    ImageDraw.Draw(fill).text((-box[0], -box[1]), ch, font=font, fill=255)
    fill = fill.resize((16, 24), Image.Resampling.LANCZOS)
    mask = Image.new('L', (32, 32))
    mask.paste(fill, (8, 4))
    mask = mask.point(lambda value: 255 if value >= 112 else 0)
    border = mask.filter(ImageFilter.MaxFilter(3))
    pixels = [[1 if mask.getpixel((x, y)) else 14 if border.getpixel((x, y)) else 0
               for x in range(32)] for y in range(32)]
    occupied = [(x, y) for y in range(32) for x in range(32) if pixels[y][x]]
    if (not occupied or any(not (7 <= x <= 24 and 3 <= y <= 28) for x, y in occupied)
            or not any(1 in row for row in pixels)):
        raise AssertionError(f'Part 2 power title glyph exceeds its 20px advance: {ch}')
    return pixels


def render(original_raw, dictionary, font_bytes=None):
    from PIL import ImageFont
    if len(original_raw) != RAW_SIZE or sha256(original_raw).hexdigest() != RAW_SHA256:
        raise AssertionError('Part 2 power title source asset changed')
    if (not 1 <= len(dictionary) <= MAX_GLYPHS or len(set(dictionary)) != len(dictionary) or
            any(not '가' <= ch <= '힣' for ch in dictionary)):
        raise AssertionError('Part 2 power title render dictionary changed scope')
    font_bytes = _font_bytes() if font_bytes is None else font_bytes
    if sha256(font_bytes).hexdigest() != FONT_SHA256:
        raise AssertionError('Part 2 power title OkDanDan font changed')
    font = ImageFont.truetype(BytesIO(font_bytes), 120)
    result = bytearray(original_raw)
    for index, ch in enumerate(dictionary):
        pixels = _glyph(ch, font)
        for row, (start, _) in enumerate(cell_rows(index)):
            for tile in range(4):
                for y in range(8):
                    for x in range(0, 8, 2):
                        pos = start + tile * 32 + y * 4 + x // 2
                        result[pos] = pixels[row * 8 + y][tile * 8 + x] | (pixels[row * 8 + y][tile * 8 + x + 1] << 4)
    # Preserve every unused cell, including native reserved cells 61..63.
    for index in range(len(dictionary), 64):
        for start, size in cell_rows(index):
            if result[start:start + size] != original_raw[start:start + size]:
                raise AssertionError('Part 2 power title touched an unused glyph')
    return bytes(result)


def _decode_bounded(payload):
    """Reject out-of-slot reads, malformed lengths and VRAM-unsafe backrefs."""
    from lz77_scan import lz77_decompress
    from export_sprites import lz77_decompress as independent_decode
    if len(payload) > SLOT_SIZE or len(payload) < 4 or payload[:4] != b'\x10\x00\x80\x00':
        raise AssertionError('Part 2 power title LZ header/slot changed')
    pos, produced = 4, 0
    try:
        while produced < RAW_SIZE:
            flags = payload[pos]
            pos += 1
            for bit in range(8):
                if produced == RAW_SIZE:
                    break
                if flags & (0x80 >> bit):
                    first, second = payload[pos], payload[pos + 1]
                    length, distance = (first >> 4) + 3, ((first & 15) << 8 | second) + 1
                    if distance < 2 or distance > produced or produced + length > RAW_SIZE:
                        raise AssertionError('Part 2 power title unsafe LZ backref')
                    produced += length
                    pos += 2
                else:
                    _ = payload[pos]
                    produced += 1
                    pos += 1
    except IndexError as exc:
        raise AssertionError('Part 2 power title truncated LZ stream') from exc
    if any(payload[pos:]):
        raise AssertionError('Part 2 power title nonzero slot padding')
    a, b = lz77_decompress(payload, 0), independent_decode(payload, 0)
    if a is None or b is None or a != b or len(a[0]) != RAW_SIZE or a[1] != pos:
        raise AssertionError('Part 2 power title decoder disagreement')
    return a[0], pos


def _compress(raw):
    from lz77_compress import lz77_compress_optimal
    packed = lz77_compress_optimal(raw, vram_safe=True)
    if len(packed) > SLOT_SIZE:
        raise AssertionError(f'Part 2 power title exceeds original slot: {len(packed)} > {SLOT_SIZE}')
    payload = packed.ljust(SLOT_SIZE, b'\0')
    decoded, consumed = _decode_bounded(payload)
    if decoded != raw or consumed != len(packed):
        raise AssertionError('Part 2 power title LZ roundtrip failed')
    return payload, consumed


@lru_cache(maxsize=2)
def _payload(original_raw, dictionary, font_bytes):
    return _compress(_render_cached(original_raw, dictionary, font_bytes))


def _expected(rom, original, display_names, syllable_codes):
    raw = source(original)
    dictionary = bind_dictionary(rom, display_names, syllable_codes)
    return _payload(raw, dictionary, _font_bytes())


def patch(rom, original, display_names, syllable_codes):
    expected, consumed = _expected(rom, original, display_names, syllable_codes)
    if bytes(rom[OFFSET:OFFSET + SLOT_SIZE]) != bytes(original[OFFSET:OFFSET + SLOT_SIZE]):
        raise AssertionError('Part 2 power title asset already changed by another writer')
    rom[OFFSET:OFFSET + SLOT_SIZE] = expected
    return {'glyphs': len(bind_dictionary(rom, display_names, syllable_codes)), 'names': 36, 'offset': hex(OFFSET),
            'packed_bytes': consumed, 'slot_bytes': SLOT_SIZE, 'headroom': SLOT_SIZE - consumed,
            'method': 'dictionary_ordered_lz77_source_only'}


def verify_generated(rom, original, display_names, syllable_codes):
    expected, _ = _expected(rom, original, display_names, syllable_codes)
    if bytes(rom[OFFSET:OFFSET + SLOT_SIZE]) != expected:
        raise AssertionError('Part 2 power title generated asset overwritten before editor')


def capture_regions(rom, original, display_names, syllable_codes, *, editor_result):
    """Accept only an exact, explicitly applied editor write for a changed asset."""
    expected, _ = _expected(rom, original, display_names, syllable_codes)
    payload = bytes(rom[OFFSET:OFFSET + SLOT_SIZE])
    _decode_bounded(payload)
    if editor_result.get('skipped', 0):
        raise AssertionError('Part 2 power title editor reported skipped writes')
    applied = [(address, bytes(data)) for sid, address, data in editor_result.get('expected_writes', [])
               if sid == ASSET_ID]
    if applied:
        binding = dictionary_binding(rom, display_names, syllable_codes)
        if editor_result.get('dictionary_bindings', {}).get(ASSET_ID) != binding:
            raise AssertionError('Part 2 power title applied editor dictionary binding is missing or stale')
        if applied != [(OFFSET, payload)]:
            raise AssertionError('Part 2 power title applied editor byte extent differs')
    if payload != expected:
        accepted = any(sid == ASSET_ID and address == OFFSET and bytes(data) == payload
                       for sid, address, data in editor_result.get('expected_writes', []))
        if not accepted:
            raise AssertionError('Part 2 power title changed without an explicit applied editor overlay')
    return {address: bytes(rom[address:address + size]) for address, size in _snapshot_extents().items()}


def _snapshot_extents():
    return {**{a: size for a, size, _ in GUARDS}, OFFSET: SLOT_SIZE,
            DICTIONARY: DICTIONARY_SIZE, NAMES_START: NAMES_END - NAMES_START}


def verify_regions(rom, regions):
    """Run after all final writers; retain accepted artwork and its bindings."""
    _guard_current(rom)
    extents = _snapshot_extents()
    if set(regions) != set(extents) or any(len(regions[a]) != size for a, size in extents.items()):
        raise AssertionError('Part 2 power title final snapshot has wrong extents')
    for address, payload in regions.items():
        if bytes(rom[address:address + len(payload)]) != payload:
            raise AssertionError(f'Part 2 power title accepted bytes overwritten after editor: {address:X}')


BINDING_KEY = 'power_title_binding'


def dictionary_binding(rom, display_names, syllable_codes):
    """Bind glyph order, code meanings and every name, not just the glyph count."""
    dictionary = bind_dictionary(rom, display_names, syllable_codes)
    material = (b'part2-power-title-v1\0' + dictionary.encode('utf-8') + b'\0' +
                bytes(rom[DICTIONARY:DICTIONARY + DICTIONARY_SIZE + 2]) +
                bytes(rom[NAMES_START:NAMES_END]))
    return 'v1:' + sha256(material).hexdigest()


def validate_override_binding(rom, record, display_names, syllable_codes):
    """Fail closed without deleting a user's artwork when its map is stale."""
    binding = dictionary_binding(rom, display_names, syllable_codes)
    if record.get(BINDING_KEY) != binding:
        raise ValueError('기술명 글자 배열이 이 편집본과 다릅니다. 기존 픽셀 편집은 보존했습니다. '
                         '편집 당시의 기술명 설정을 복원하거나 최신 글자 배열을 확인해 다시 편집해 주세요.')
    return binding


@lru_cache(maxsize=2)
def _render_cached(original_raw, dictionary, font_bytes):
    return render(original_raw, dictionary, font_bytes)


def editor_view(rom, original, display_names, syllable_codes, record=None):
    """Return an editable raw atlas and a token from one patched ROM snapshot.

    A correctly bound saved edit is its own artwork source, including when it
    has not yet been built. Without one, only an actually generated Korean
    atlas may be offered: the old Japanese atlas had Korean dictionary bytes
    too, so a dictionary token alone is insufficient to approve that base.
    """
    from sprite_codec import encode_indices
    dictionary = bind_dictionary(rom, display_names, syllable_codes)
    binding = dictionary_binding(rom, display_names, syllable_codes)
    if record and record.get('indices'):
        validate_override_binding(rom, record, display_names, syllable_codes)
        grid = record['indices']
        raw = encode_indices(grid, 256, 256)
        if len(raw) != RAW_SIZE:
            raise ValueError('기술명 편집본의 타일 크기가 다릅니다. 기존 편집은 보존했습니다.')
        return binding, raw
    expected = _render_cached(source(original), dictionary, _font_bytes())
    payload = bytes(rom[OFFSET:OFFSET + SLOT_SIZE])
    try:
        actual, _ = _decode_bounded(payload)
    except AssertionError as exc:
        raise ValueError('최신 한글 빌드의 기술명 그림을 확인할 수 없습니다. 빌드 후 다시 열어 주세요.') from exc
    if actual != expected:
        raise ValueError('현재 기술명 그림이 최신 한글 글자 배열과 다릅니다. 빌드 후 다시 열어 주세요.')
    return binding, actual
