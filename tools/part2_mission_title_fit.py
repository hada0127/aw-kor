"""Fit the observed 10/11-code campaign titles without changing their text.

The native title animation uses fixed 24px cells, independently of the map
renderer glyph advances. Short titles keep that path; long titles use 20px
cells and ink contained within 19px. Unknown longer source titles fail build.
"""
import hashlib
import struct

from lz77_scan import lz77_decompress

BASE = 0xF66000
TABLE = 0xF66800
GLYPHS = 0xF68000
END = 0xF70000
FREE_SHA = '02b1c2234680617802901a77eae606ad02e4ddb4282ccbc60061eac5b2d90bba'
# tools/asm/part2_mission_title_fit.s, clang arm-none-eabi / arm7tdmi.
CODE = bytes.fromhex(
    '49460091f0b5040000250178002902d001350230f9e72000092d06d8002100228023'
    '114f00f01ff817e000262078002812d061780002084302340c4d2988884201d00c35'
    'fae768687102094a8918094f00f009f80136e9e73000f0bc02bc8e46000405490847'
    '3847e5c437080068f60800100106c11c3108f5c7370851460988092903d842001218'
    'd20002e0820012189200e021891a009600480047b9ce37083188092903d842001218'
    'd20002e0820012189200e021891a009701480047c04619cf3708'
)
SITES = (
    (0x37C7E4, bytes.fromhex('49460091002100228023fff779fe0004'), BASE),
    (0x37CEAC, bytes.fromhex('42001218d200e021891a0096'), BASE + 0x7C),
    (0x37CF0C, bytes.fromhex('42001218d200e021891a0097'), BASE + 0xA0),
)

TITLE_START = 0xA2D000
TITLE_END = 0xA2D8B0


def is_pair_title(address):
    return address is not None and TITLE_START <= address < TITLE_END


def valid_pair(code):
    lead, trail = code >> 8, code & 255
    return (0x81 <= lead <= 0x9F or 0xE0 <= lead <= 0xFC) and 0x40 <= trail <= 0xFC and trail != 0x7F


def encode_pair_title(text, syllables):
    """Encode authored title text, never a story command stream.

    The title consumers always advance two bytes, including digits and signs.
    Unsupported characters fail instead of silently disappearing or blanking.
    """
    result = bytearray()
    for char in text:
        if char in syllables:
            code = syllables[char]
            raw = int(code, 16).to_bytes(2, 'big') if isinstance(code, str) else code.to_bytes(2, 'big')
        else:
            if char == ' ':
                char = '\u3000'
            elif 0x21 <= ord(char) <= 0x7E:
                char = chr(ord(char) + 0xFEE0)
            try:
                raw = char.encode('shift_jis')
            except UnicodeEncodeError as error:
                raise AssertionError(f'unsupported mission title character: {char!r}') from error
        if len(raw) != 2 or not valid_pair(int.from_bytes(raw, 'big')):
            raise AssertionError(f'invalid mission title pair for {char!r}')
        result.extend(raw)
    return bytes(result)


def strict_titles(original, titles):
    """Select campaign pair titles by immutable source, including relocations."""
    return [row for row in titles if is_pair_title(struct.unpack_from('<I', original, row[0])[0] - 0x08000000)]


def compact_glyph(raw):
    if len(raw) != 512:
        raise AssertionError('mission title glyph is not 32x32 4bpp')
    pixels = [[0] * 32 for _ in range(32)]
    xs = []
    for y in range(32):
        for x in range(32):
            a = (y // 8 * 4 + x // 8) * 32 + y % 8 * 4 + x % 8 // 2
            value = raw[a] >> (4 * (x % 2)) & 15
            pixels[y][x] = value
            if value:
                xs.append(x)
    if not xs or max(xs) < 19:
        return bytes(raw)
    left, right = min(xs), max(xs)
    width = right - left + 1
    target = min(19, width)
    start = min(left, 19 - target)
    result = bytearray(512)
    for y in range(32):
        for x in range(target):
            value = pixels[y][left + min(width - 1, (2 * x + 1) * width // (2 * target))]
            px = start + x
            a = (y // 8 * 4 + px // 8) * 32 + y % 8 * 4 + px % 8 // 2
            result[a] |= value << (4 * (px % 2))
    return bytes(result)


def active_titles(original, rom):
    result = []
    # 0x08324E04 is the actual title accessor: map IDs 0..179 use
    # descriptor[ID * 0x5c + 0x14] as a message-table index. IDs 180..191
    # use user-map names (0x0833D244; 17-byte field, at most eight pairs).
    pointers = set()
    for map_id in range(180):
        field = 0x9EFDE8 + map_id * 0x5C + 0x14
        if rom[field:field + 2] != original[field:field + 2]:
            raise AssertionError('mission title descriptor index changed')
        index = struct.unpack_from('<H', original, field)[0]
        pointer = 0xA357B4 + index * 4
        if not 0xA38084 <= pointer <= 0xA3834C:
            raise AssertionError('mission title descriptor points outside title table')
        pointers.add(pointer)
    for pointer in sorted(pointers):
        old = struct.unpack_from('<I', original, pointer)[0] - 0x08000000
        address = struct.unpack_from('<I', rom, pointer)[0] - 0x08000000
        if not 0 <= address < len(rom):
            raise AssertionError('mission title pointer outside ROM')
        # An in-place string may shrink, but must never consume its neighbour.
        original_end = original.find(b'\0', old)
        limit = original_end + 1 if address == old else len(rom)
        if original_end < 0:
            raise AssertionError('source mission title has no terminator')
        codes = []
        end = address
        while True:
            if end >= limit:
                raise AssertionError('mission title has no terminator')
            if rom[end] == 0:
                break
            if end + 1 >= limit:
                raise AssertionError('mission title ends in a partial code')
            if rom[end + 1] == 0:
                raise AssertionError('invalid mission title pair: partial code before terminator')
            codes.append(rom[end] << 8 | rom[end + 1])
            if is_pair_title(old) and not valid_pair(codes[-1]):
                raise AssertionError(f'invalid mission title pair: {old:08X} / {codes[-1]:04X}')
            end += 2
            if len(codes) > 11:
                raise AssertionError(f'mission title exceeds verified 11-code layout: {old:08X}')
        result.append((pointer, address, tuple(codes), bytes(rom[address:end + 1])))
    if len(result) != 179:
        raise AssertionError('native mission title pointer inventory changed')
    return result


def patch(rom, original, literal_compress):
    for start, end, expected in (
        (0x324E04, 0x324E44, 'd64bf0587285b9353690a378c0b277a29192c41b4bcf699c1fed86d76852ce89'),
        (0x33D244, 0x33D26C, '4cb5023f31507a8a1912a6d10f1a8634efda40e082ed189c12b935461d8df6ad'),
    ):
        if hashlib.sha256(original[start:end]).hexdigest() != expected or rom[start:end] != original[start:end]:
            raise AssertionError('mission title accessor changed')
    if hashlib.sha256(original[BASE:END]).hexdigest() != FREE_SHA:
        raise AssertionError('mission title layout source reservation changed')
    if bytes(rom[BASE:END]) != original[BASE:END]:
        raise AssertionError('mission title layout reservation already occupied')
    for address, expected, _ in SITES:
        if original[address:address + len(expected)] != expected or bytes(rom[address:address + len(expected)]) != expected:
            raise AssertionError(f'mission title layout hook site changed: {address:08X}')
    titles = active_titles(original, rom)
    strict_needed = {code for _, _, codes, _ in strict_titles(original, titles) for code in codes}
    needed = {code for _, _, codes, _ in titles if len(codes) > 9 for code in codes}
    entries = []
    for address in range(0xF40000, 0xF42000 - 11, 12):
        entry = bytes(rom[address:address + 12])
        if struct.unpack_from('<I', entry, 4)[0] == 0:
            break
        entries.append(entry)
    else:
        raise AssertionError('mission title glyph table is unterminated')
    table = bytearray()
    glyphs = bytearray()
    seen = set()
    dedup = {}
    rom_bytes = bytes(rom)
    for entry in entries:
        code, _, pointer, advance = struct.unpack('<HHII', entry)
        if code in seen:
            raise AssertionError(f'duplicate mission title glyph: {code:04X}')
        seen.add(code)
        if code in needed | strict_needed:
            if not 0x08000000 <= pointer < 0x08000000 + len(rom):
                raise AssertionError(f'mission title glyph pointer outside ROM: {code:04X}')
            decoded = lz77_decompress(rom_bytes, pointer - 0x08000000)
            if decoded is None or len(decoded[0]) != 512:
                raise AssertionError(f'mission title glyph cannot decompress: {code:04X}')
            if code in (needed | strict_needed) and code != 0x8140 and not any(decoded[0]):
                raise AssertionError(f'mission title has blank visible glyph: {code:04X}')
        if code in needed:
            raw = compact_glyph(decoded[0])
            if raw not in dedup:
                dedup[raw] = 0x08000000 + GLYPHS + len(glyphs)
                glyphs.extend(literal_compress(raw))
                while len(glyphs) % 4:
                    glyphs.append(0)
            pointer = dedup[raw]
        modified = bytearray(entry)
        struct.pack_into('<I', modified, 4, pointer)
        table.extend(modified)
    if (needed | strict_needed) - seen:
        raise AssertionError('mission title contains an unregistered glyph')
    table.extend(bytes(12))
    if BASE + len(CODE) > TABLE or TABLE + len(table) > GLYPHS or GLYPHS + len(glyphs) > END:
        raise AssertionError('mission title fitting assets overlap reservation')
    rom[BASE:BASE + len(CODE)] = CODE
    rom[TABLE:TABLE + len(table)] = table
    rom[GLYPHS:GLYPHS + len(glyphs)] = glyphs
    regions = [(BASE, bytes(rom[BASE:END]))]
    for address, expected, target in SITES:
        # All three sites are word-aligned and r1 is dead at trampoline entry.
        assert address % 4 == 0 and len(expected) >= 8 and len(expected) % 2 == 0
        trampoline = bytes.fromhex('00490847') + struct.pack('<I', 0x08000001 + target)
        replacement = trampoline + bytes.fromhex('c046') * ((len(expected) - 8) // 2)
        rom[address:address + len(expected)] = replacement
        regions.append((address, replacement))
    for pointer, address, _, raw in titles:
        regions.extend(((pointer, bytes(rom[pointer:pointer + 4])), (address, raw)))
    return tuple(regions), {'titles': len(titles), 'long_titles': sum(len(x[2]) > 9 for x in titles),
                            'compact_codes': len(needed), 'glyph_bytes': len(glyphs)}
