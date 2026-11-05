"""Keep the AW2 COP title atlas in the same order as its Korean dictionary.

08380564 finds a two-byte code in A3B880, then copies the corresponding 32x32
cell from the 5B3ECC atlas. Updating only the dictionary made 강타 select the
original ド/ン cells. The native consumer, palette and pointers stay intact.
Only the active dictionary cells change (57 in the approved default); a later explicit sprite
editor overlay may replace the asset and is captured for the final guard.

fixB H (2026-11-04, spike S4): 「야마토다마시이」 needs 64 glyphs, the atlas's physical
maximum, but the native dictionary slot A3B880 holds only 61 (122 B before the
A3B8FA terminator). The dictionary moves to free space DICTIONARY (64 x 2 B +
NUL halfword) and both consumer literals (0x3806FC, 0x381300) point there.
The native slot keeps the first 61 entries (builder text writer), so a stale
reader would still map them to the right atlas cells.

gfx T5 (2026-11-05): the uniform-scale AA atlas compresses beyond the native
6,161 B slot, so the LZ77 stream moves to proven-empty ATLAS (0xFD3000, after
the B84 relocation at 0xFD2000) and both loader literals (0x380644, 0x38121C,
the only references in the original ROM) point there. The native slot at
0x5B3ECC is retired: it keeps its original bytes and is guarded unchanged.

gfx R3 (2026-11-05): the JP cut-in is upright gothic. Use pinned Hada Sans
ExtraBold at the R2 face height, retaining the 20 px advance and AA palette.
"""
from functools import lru_cache
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import json
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aw_fonts  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CORE_WITNESSES = json.loads((ROOT / 'data/graphic_hangul_shape_witnesses.json').read_text())['cutin_natural_core']
FONT_SHA256 = aw_fonts.HADASANS_EXTRABOLD_SHA256
# FixB cut-in frames 24/25/26, OBJ bank 3.  All three captured PRAM states
# agree; index 8 is the existing light-blue coverage shade between the native
# blue outline (14) and white face (1).  No palette bytes are changed.
CUTIN_OBJ3_PALETTE = ((189, 189, 213), (255, 255, 255), (255, 172, 172),
                      (255, 131, 139), (156, 106, 131), (255, 255, 205),
                      (255, 255, 106), (156, 180, 123), (213, 213, 255),
                      (156, 213, 255), (82, 156, 205), (255, 189, 139),
                      (255, 0, 255), (197, 205, 197), (49, 98, 148),
                      (0, 41, 0))
ORIGINAL_SHA256 = 'a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c'
ROM_SIZE = 0x1000000
OFFSET, SLOT_SIZE, RAW_SIZE = 0x5B3ECC, 6161, 32768
RAW_SHA256 = 'b601d62a378e3854067c15f09e024a98f1d1b0437d25f505797f01655bf68bd7'
ASSET_ID = 'lz77_005B3ECC'
NATIVE_DICTIONARY, NATIVE_DICTIONARY_SIZE = 0xA3B880, 122
DICTIONARY, DICTIONARY_SIZE, MAX_GLYPHS = 0xFD0160, 128, 64
DICTIONARY_LITERALS = (0x3806FC, 0x381300)
NAMES_START, NAMES_END, NAME_POINTERS = 0xA2955C, 0xA29830, 0xA37B3C
# Native digests of the two literal-pool regions before the dictionary move.
NATIVE_LITERAL_GUARDS = (
    (0x3806A8, 0x58, '196eb8a6fd4959e1136c449f233fbdcfd617ec9d0866ed3073d15167c2f03851'),
    (0x381234, 0xD0, '3b29f8e9793b24db7ee3b44034f8791086fec641e2b7c95add07f202b34a41fe'),
)
# Native consumers, two atlas pointers, palette, neighboring data, name pointers.
# 0x3806A8/0x381234 digests are the native code with only the two dictionary
# literals changed to DICTIONARY.
ATLAS, ATLAS_CAPACITY = 0xFD3000, 0x2000
ATLAS_POINTERS = (0x380644, 0x38121C)
# (address, size, native digest, relocated-atlas digest) of the two literal
# pools holding ATLAS_POINTERS; only those four bytes each differ.
ATLAS_POINTER_GUARDS = (
    (0x380564, 0xEC, 'f9fb9090dac028158e96c3c8f1823a8dc2a4344c166e62a69399a17f9108926f',
     '69890aa4415f4b1c7ce1c209c3ddda967d86593295d6829822e6fccb20f535c2'),
    (0x38121C, 0xC, 'bd8fb931b0dc3e6d11108bd116853c91f03165bb02b96f89a6a34f5201dc3bfe',
     '5d65c56b4359e20946ff6491e5b82146724e9d8340ff9e1044f26684ab37cba3'),
)
GUARDS = (
    (0x3806A8, 0x58, '4bb218b9236aa9213b3700a451e43c05004098c674db12175a5b328eaa04a27f'),
    (0x38118C, 0x18, '72cfae6085257a5f0ccc21369f5031dfed67ba630eda72be96a3f27e0d67c818'),
    (0x381234, 0xD0, '54e449ff9c1c660e1f2fd13162c328d37f180c2b8746d3531d727afe52245f98'),
    (0x5B3EBC, 0x10, '4b0c2404daddaba57120378648d3dcaf0e0498579748e2127eb0bfc624914475'),
    (0x5B56DD, 0x20, '2c7c5e1889322476f239cd8607469abe6c2106277a82898bc99583855e8a9dfb'),
    (0x5B5720, 0x20, '7573b09439c2fab8edaa2adad209439c78aea429072c3ccb8c964cd26a4df32e'),
    (0xA3B8FA, 2, '96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7'),
    (NAME_POINTERS, 36 * 4, 'd0265bfcbe9ba63b9e879140360022da973e69472fbc327572a95606ad7235ce'),
)


def _guard_current(rom, relocated=None):
    """relocated: True/False pins the atlas literals; None accepts either state."""
    if len(rom) != ROM_SIZE:
        raise AssertionError('Part 2 power title requires the complete 16 MiB ROM')
    for address, size, digest in GUARDS:
        if sha256(rom[address:address + size]).hexdigest() != digest:
            raise AssertionError(f'Part 2 power title consumer/pointer/palette/neighbor changed: {address:X}')
    for address, size, native, moved in ATLAS_POINTER_GUARDS:
        allowed = {True: (moved,), False: (native,), None: (native, moved)}[relocated]
        if sha256(rom[address:address + size]).hexdigest() not in allowed:
            raise AssertionError(f'Part 2 power title consumer/pointer/palette/neighbor changed: {address:X}')
    if len({_atlas_pointer(rom, a) for a in ATLAS_POINTERS}) != 1:
        raise AssertionError('Part 2 power title atlas literals disagree')


def _atlas_pointer(rom, address):
    return struct.unpack_from('<I', rom, address)[0] - 0x08000000


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
    data = Path(aw_fonts.hadasans_extrabold_path()).read_bytes()
    if sha256(data).hexdigest() != FONT_SHA256:
        raise AssertionError('Part 2 power title Hada Sans font changed')
    return data


def _ordered_pairs(rom, display_names, syllable_codes):
    addresses = tuple(p - 0x08000000 for p in struct.unpack_from('<36I', rom, NAME_POINTERS))
    names = {a: t for a, t in display_names.items() if NAMES_START <= a < NAMES_END}
    if set(names) != set(addresses):
        raise AssertionError('Part 2 power title requires the exact 36 display-name addresses')
    ordered = ''.join(dict.fromkeys(''.join(names[a] for a in addresses)))
    if (not 1 <= len(ordered) <= MAX_GLYPHS or any(not '가' <= ch <= '힣' for ch in ordered)):
        raise AssertionError(f'Part 2 power title dictionary must have 1..{MAX_GLYPHS} unique Hangul glyphs')
    try:
        pairs = [int(syllable_codes[ch]).to_bytes(2, 'big') for ch in ordered]
    except (KeyError, ValueError, OverflowError, TypeError) as exc:
        raise AssertionError('Part 2 power title has an invalid or unmapped glyph code') from exc
    if (len(set(pairs)) != len(pairs) or any(not (0x81 <= p[0] <= 0x9F or 0xE0 <= p[0] <= 0xEF)
                                           or not (0x40 <= p[1] <= 0xFC and p[1] != 0x7F) for p in pairs)):
        raise AssertionError('Part 2 power title needs unique native two-byte dictionary codes')
    return addresses, names, ordered, pairs


def relocate_dictionary(rom, original, display_names, syllable_codes):
    """Write the 64-entry dictionary to DICTIONARY and repoint both literals.

    Returns [(address, bytes, label)] for the builder's write log.
    """
    _, _, _, pairs = _ordered_pairs(rom, display_names, syllable_codes)
    blob = b''.join(pairs).ljust(DICTIONARY_SIZE, b'\0') + b'\0\0'
    native_ptr = struct.pack('<I', 0x08000000 + NATIVE_DICTIONARY)
    new_ptr = struct.pack('<I', 0x08000000 + DICTIONARY)
    for address, size, digest in NATIVE_LITERAL_GUARDS:
        if (sha256(original[address:address + size]).hexdigest() != digest
                or bytes(rom[address:address + size]) != bytes(original[address:address + size])):
            raise AssertionError(f'Part 2 power title dictionary literal pool changed: {address:X}')
    if (any(bytes(original[a:a + 4]) != native_ptr for a in DICTIONARY_LITERALS)
            or bytes(original).count(native_ptr) != len(DICTIONARY_LITERALS)):
        raise AssertionError('Part 2 power title native dictionary literal ownership changed')
    if (any(original[DICTIONARY:DICTIONARY + len(blob)]) or any(rom[DICTIONARY:DICTIONARY + len(blob)])
            or new_ptr in original or new_ptr in rom):
        raise AssertionError('Part 2 power title relocated dictionary space occupied or referenced')
    rom[DICTIONARY:DICTIONARY + len(blob)] = blob
    writes = [(DICTIONARY, blob, 'part2-power-title-dictionary-relocated')]
    for address in DICTIONARY_LITERALS:
        rom[address:address + 4] = new_ptr
        writes.append((address, new_ptr, 'part2-power-title-dictionary-literal'))
    _guard_current(rom)
    return writes


def bind_dictionary(rom, display_names, syllable_codes):
    """Match all actual ROM names and dictionary to the builder's display data.

    Call after the text writers and relocate_dictionary(), before the sprite
    editor. There is no separate hard-coded Korean dictionary to drift from
    data/display_overrides.json.
    """
    _guard_current(rom)
    addresses, names, ordered, pairs = _ordered_pairs(rom, display_names, syllable_codes)
    encoded = dict(zip(ordered, pairs))
    if (bytes(rom[DICTIONARY:DICTIONARY + DICTIONARY_SIZE]) != b''.join(pairs).ljust(DICTIONARY_SIZE, b'\0')
            or bytes(rom[DICTIONARY + DICTIONARY_SIZE:DICTIONARY + DICTIONARY_SIZE + 2]) != b'\0\0'):
        raise AssertionError('Part 2 power title ROM dictionary differs from display names')
    new_ptr = struct.pack('<I', 0x08000000 + DICTIONARY)
    if any(bytes(rom[a:a + 4]) != new_ptr for a in DICTIONARY_LITERALS):
        raise AssertionError('Part 2 power title dictionary literal is not the relocated dictionary')
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


# fixB 8_toh (2026-11-04) drew 토 at its neighbour's point size instead of
# stretching it to 24 px; the other syllables kept a per-glyph 16x24 fit, so 15
# vertical-vowel syllables (꿈 승 혼 축 골 돌 습 큰 폭 풍 충 분 술 측 흑) were still
# drawn up to 2.4x larger than wide ones (대 타 ...).
#
# gfx R3 (2026-11-05): every syllable shares one Hada Sans horizontal scale
# referenced to the 18 px width of 다. The proportional binary core is then
# expanded vertically to the fixed 23 px face height on a common baseline.
# A user-edited wider syllable is narrowed to the 18 px face. Coverage outside the
# binary face core is quantized against the live cut-in OBJ bank 3 (JP's own
# 1 -> 8 -> 10 -> 14 white/light/mid-blue/outline ramp); PRAM is not written.
# R3 keeps the R2 widths, height and AA ramp with the gothic face.
FACE_X, FACE_Y, FACE_W, FACE_H = 7, 4, 18, 24
TARGET_FACE_HEIGHT = 23
SCALE_REFERENCE = '다'
# _outline() rasterizes at 384 px from y=0; the pinned Hada Sans has uniform
# upright Hangul bodies, then each face receives the same 23 px top/baseline.
AA_RAMP = (14, 10, 8)  # outline -> mid blue -> light blue (face is 1)


@lru_cache(maxsize=4096)
def _outline(ch):
    """(cropped 384 px Hada Sans coverage, crop top)."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(aw_fonts.hadasans_extrabold_path(), 384)
    probe = Image.new('L', (768, 768))
    ImageDraw.Draw(probe).text((20, 0), ch, font=font, fill=255)
    box = probe.point(lambda v: 255 if v >= 128 else 0).getbbox()
    if box is None:
        raise AssertionError(f'Part 2 power title outline mismatch: {ch}')
    return probe.crop(box), box[1]


def uniform_scale():
    return FACE_W / _outline(SCALE_REFERENCE)[0].width


def _placement(ch):
    """Return source and fitted face geometry inside the native 32x32 cell."""
    source, _ = _outline(ch)
    base = uniform_scale()
    # Fit width at the original aspect ratio so the existing gap oracle still
    # checks the unmodified core before the final vertical row expansion.
    natural_h = max(1, round(source.height * base))
    while natural_h > 1 and round(source.width * natural_h / source.height) > FACE_W:
        natural_h -= 1
    w = max(1, round(source.width * natural_h / source.height))
    h = TARGET_FACE_HEIGHT
    x, y = FACE_X + (FACE_W - w) // 2, FACE_Y
    if not (FACE_X <= x and x + w <= FACE_X + FACE_W and FACE_Y <= y and y + h <= FACE_Y + FACE_H):
        raise AssertionError(f'Part 2 power title glyph leaves its face box: {ch}')
    return source, (w, h), (x, y)


def _natural_core(ch):
    """Existing proportional binary face, before a vertical-only enlargement."""
    from PIL import Image
    source, _ = _outline(ch)
    width = _placement(ch)[1][0]
    height = max(1, round(source.height * width / source.width))
    return source.resize((width, height), Image.Resampling.LANCZOS).point(
        lambda v: 255 if v >= 128 else 0)


def _fill(ch):
    """Binary face core in cell coordinates (32x32 L)."""
    from PIL import Image
    _, size, origin = _placement(ch)
    mask = _natural_core(ch).resize(size, Image.Resampling.NEAREST)
    result = Image.new('L', (32, 32))
    result.paste(mask, origin)
    return result


def _coverage(ch):
    from PIL import Image
    source, size, origin = _placement(ch)
    result = Image.new('L', (32, 32))
    result.paste(source.resize(size, Image.Resampling.BOX), origin)
    return result


def _glyph(ch, font):
    from PIL import Image, ImageFilter
    from hangul_pixel_fit import runs
    from sprite_text_aa import palette_blend_index
    natural = _natural_core(ch)
    # Fixed R8 witness is independent of the current resize/threshold path.
    # A missing or merged stroke changes this digest before vertical scaling.
    witness = CORE_WITNESSES.get(ch)
    if witness and sha256(natural.tobytes()).hexdigest() != witness:
        raise AssertionError(f'Part 2 power title Hada core changed: {ch}')
    mask = _fill(ch)
    # Nearest-neighbour row expansion preserves each binary stroke column.
    # Check the *final* core too, so an altered resize cannot silently close
    # counters while the original proportional oracle remains green.
    box = mask.getbbox()
    final = mask.crop(box)
    for x in range(natural.width):
        before = sum(n for n, _, _ in runs([natural.getpixel((x, y)) for y in range(natural.height)]))
        after = sum(n for n, _, _ in runs([final.getpixel((x, y)) for y in range(final.height)]))
        if before != after:
            raise AssertionError(f'Part 2 power title vertical scale closed a gap: {ch} x={x}')
    soft = _coverage(ch)
    border = mask.filter(ImageFilter.MaxFilter(3))
    pixels = []
    for y in range(32):
        row = []
        for x in range(32):
            if mask.getpixel((x, y)):
                value = 1
            elif border.getpixel((x, y)):
                value = palette_blend_index(14, 1, soft.getpixel((x, y)), AA_RAMP, (CUTIN_OBJ3_PALETTE,))
            else:
                value = 0
            row.append(value)
        pixels.append(row)
    occupied = [(x, y) for y in range(32) for x in range(32) if pixels[y][x]]
    # A 1 px outline around the 18 px face spans exactly the native 20 px
    # advance (x 6..25), as the JP katakana cells do.
    if (not occupied or any(not (6 <= x <= 25 and 3 <= y <= 28) for x, y in occupied)
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
        raise AssertionError('Part 2 power title Hada Sans font changed')
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
    if len(payload) > ATLAS_CAPACITY or len(payload) < 4 or payload[:4] != b'\x10\x00\x80\x00':
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
    if len(packed) > ATLAS_CAPACITY:
        raise AssertionError(f'Part 2 power title exceeds relocated atlas: {len(packed)} > {ATLAS_CAPACITY}')
    payload = packed.ljust(ATLAS_CAPACITY, b'\0')
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


def _retired_slot_intact(rom, original):
    if bytes(rom[OFFSET:OFFSET + SLOT_SIZE]) != bytes(original[OFFSET:OFFSET + SLOT_SIZE]):
        raise AssertionError('Part 2 power title retired native slot changed')


def patch(rom, original, display_names, syllable_codes):
    """Write the atlas to ATLAS and move both loader literals there.

    Returns the info dict; writes() lists the exact byte extents for the log.
    """
    expected, consumed = _expected(rom, original, display_names, syllable_codes)
    native = struct.pack('<I', 0x08000000 + OFFSET)
    moved = struct.pack('<I', 0x08000000 + ATLAS)
    if bytes(rom[OFFSET:OFFSET + SLOT_SIZE]) != bytes(original[OFFSET:OFFSET + SLOT_SIZE]):
        raise AssertionError('Part 2 power title asset already changed by another writer')
    if (bytes(original).count(native) != len(ATLAS_POINTERS)
            or any(bytes(original[a:a + 4]) != native or bytes(rom[a:a + 4]) != native for a in ATLAS_POINTERS)):
        raise AssertionError('Part 2 power title native atlas literal ownership changed')
    if (any(original[ATLAS:ATLAS + ATLAS_CAPACITY]) or any(rom[ATLAS:ATLAS + ATLAS_CAPACITY])
            or moved in original or moved in rom):
        raise AssertionError('Part 2 power title relocated atlas space occupied or referenced')
    _guard_current(rom, relocated=False)
    rom[ATLAS:ATLAS + ATLAS_CAPACITY] = expected
    for address in ATLAS_POINTERS:
        rom[address:address + 4] = moved
    _guard_current(rom, relocated=True)
    return {'glyphs': len(bind_dictionary(rom, display_names, syllable_codes)), 'names': 36,
            'offset': hex(ATLAS), 'retired_native_offset': hex(OFFSET), 'pointers': [hex(a) for a in ATLAS_POINTERS],
            'packed_bytes': consumed, 'slot_bytes': ATLAS_CAPACITY, 'headroom': ATLAS_CAPACITY - consumed,
            'native_slot_bytes': SLOT_SIZE, 'method': 'dictionary_ordered_lz77_relocated'}


def writes(rom):
    """[(address, bytes, label)] of the relocated atlas and its two literals."""
    return [(ATLAS, bytes(rom[ATLAS:ATLAS + ATLAS_CAPACITY]), 'part2-power-title-atlas-relocated'),
            *((a, bytes(rom[a:a + 4]), 'part2-power-title-atlas-literal') for a in ATLAS_POINTERS)]


def verify_generated(rom, original, display_names, syllable_codes):
    expected, _ = _expected(rom, original, display_names, syllable_codes)
    _guard_current(rom, relocated=True)
    _retired_slot_intact(rom, original)
    if bytes(rom[ATLAS:ATLAS + ATLAS_CAPACITY]) != expected:
        raise AssertionError('Part 2 power title generated asset overwritten before editor')


def capture_regions(rom, original, display_names, syllable_codes, *, editor_result):
    """Accept only an exact, explicitly applied editor write for a changed asset."""
    expected, _ = _expected(rom, original, display_names, syllable_codes)
    _guard_current(rom, relocated=True)
    _retired_slot_intact(rom, original)
    payload = bytes(rom[ATLAS:ATLAS + ATLAS_CAPACITY])
    _decode_bounded(payload)
    if editor_result.get('skipped', 0):
        raise AssertionError('Part 2 power title editor reported skipped writes')
    applied = [(address, bytes(data)) for sid, address, data in editor_result.get('expected_writes', [])
               if sid == ASSET_ID]
    if applied:
        binding = dictionary_binding(rom, display_names, syllable_codes)
        if editor_result.get('dictionary_bindings', {}).get(ASSET_ID) != binding:
            raise AssertionError('Part 2 power title applied editor dictionary binding is missing or stale')
        if applied != [(ATLAS, payload)]:
            raise AssertionError('Part 2 power title applied editor byte extent differs')
    if payload != expected:
        accepted = any(sid == ASSET_ID and address == ATLAS and bytes(data) == payload
                       for sid, address, data in editor_result.get('expected_writes', []))
        if not accepted:
            raise AssertionError('Part 2 power title changed without an explicit applied editor overlay')
    return {address: bytes(rom[address:address + size]) for address, size in _snapshot_extents().items()}


def _snapshot_extents():
    return {**{a: size for a, size, _ in GUARDS}, **{a: size for a, size, _, _ in ATLAS_POINTER_GUARDS},
            ATLAS: ATLAS_CAPACITY, OFFSET: SLOT_SIZE,
            DICTIONARY: DICTIONARY_SIZE + 2, NAMES_START: NAMES_END - NAMES_START}


def verify_regions(rom, regions):
    """Run after all final writers; retain accepted artwork and its bindings."""
    _guard_current(rom, relocated=True)
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
    payload = bytes(rom[ATLAS:ATLAS + ATLAS_CAPACITY])
    try:
        actual, _ = _decode_bounded(payload)
    except AssertionError as exc:
        raise ValueError('최신 한글 빌드의 기술명 그림을 확인할 수 없습니다. 빌드 후 다시 열어 주세요.') from exc
    if actual != expected:
        raise ValueError('현재 기술명 그림이 최신 한글 글자 배열과 다릅니다. 빌드 후 다시 열어 주세요.')
    return binding, actual
