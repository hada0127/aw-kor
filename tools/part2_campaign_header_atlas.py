"""Part 2 campaign header: give the Korean CAMPAIGN art its own alphabet atlas.

Trace (b19, 2026-10-13, temp/b19_20261013/trace, JP + b18 cold boot):
- LZ77 0x541BB8 (0x1400 B) is not campaign-only art. It is the 20-glyph OBJ
  header alphabet (A C D E G H I K L M N O P R S T U W Y *, 16x32 per glyph,
  0x100 B each) indexed through the width table 0x08A38D9C.
- One loader, 0x08373DEC, references it (literal 0x373E7C). It decompresses the
  atlas into the caller's EWRAM buffer (svc 0x11 via 0x08311CC0), then
  0x08373D10 copies one 0x100 B glyph per string character to OBJ VRAM with
  CpuFastSet and advances x by the table width.
- 19 callers pass ASCII strings: MODE*SELECT (0x382122, buffer 0x0200FB40),
  CAMPAIGN / HARD*CAMPAIGN (0x3772EE / 0x3772CC, buffer 0x02010B40), LINK*MODE,
  WARS*SHOP, RULE*SETTING, TEAM*SETTING, SOUND*ROOM, MAP*SELECT, COLOR*EDIT,
  NOW*LOADING.
- The old Korean campaign writer zeroed the whole alphabet and wrote Korean
  pieces into glyphs C/M/P/I/G/N, so MODE*SELECT (OBJ tiles 320.. from glyphs
  M,O,D,E,*,S,L,C,T) and every other English header went blank.

Fix: the original alphabet stays byte-identical. A copy of the loader
(0x373DEC..0x373E88, same 4-byte alignment so the pc-relative literal loads
stay valid; four BL offsets recomputed) reads a Korean alphabet copy at
ATLAS_DEST. Only the two campaign BLs call the copy, and only their two string
literals point to new strings in which the repeated 'A' (14 px) is 'Y' (14 px,
same advance), a transparent glyph in the Korean copy. All other glyphs of the
copy are the original ones, so HARD*CAMPAIGN keeps its English HARD prefix.
The destination is original 0xFF padding (0x2FA000..0x2FCC00) that no original
halfword-aligned word points into.
"""
import struct

ROM_BASE = 0x08000000
ATLAS = 0x541BB8
ATLAS_SIZE = 0x1400
GLYPH = 0x100
ALPHABET = 0xA38D9C
LOADER = 0x373DEC
LOADER_END = 0x373E88           # code + 3-word literal pool
ATLAS_LITERAL = 0x373E7C
LOADER_BLS = {0x373E18: 0x08311CC0, 0x373E28: 0x0831362C,
              0x373E30: 0x0831CDC8, 0x373E3E: 0x08373D10}
CALLS = (0x3772CC, 0x3772EE)
STRING_LITERALS = {0x3772D4: (0x08A392A8, b'HARD*CAMPAIGN'),
                   0x3772FC: (0x08A3929C, b'CAMPAIGN')}
STRING_SUBST = {b'HARD*CAMPAIGN': b'HARD*CYMPYIGN', b'CAMPAIGN': b'CYMPYIGN'}

REGION = (0x2FA000, 0x2FCC00)
EDITOR_ID = 'lz77_002FA100'     # sprite editor id of the Korean copy
CAMPAIGN_GLYPHS = 'CMPIGN'
LOADER_DEST = 0x2FA000
STRINGS_DEST = 0x2FA0A0
ATLAS_DEST = 0x2FA100


def glyph_index(original, char):
    for i in range(20):
        if original[ALPHABET + i * 8] == ord(char):
            return i
    raise AssertionError(f'header alphabet lacks {char!r}')


def glyph_width(original, char):
    return struct.unpack_from('<i', original, ALPHABET + glyph_index(original, char) * 8 + 4)[0]


def _bl(src, target):
    off = target - (ROM_BASE + src + 4)
    if not -0x400000 <= off < 0x400000 or off & 1:
        raise AssertionError(f'BL out of range {src:X}->{target:X}')
    off >>= 1
    return struct.pack('<HH', 0xF000 | ((off >> 11) & 0x7FF), 0xF800 | (off & 0x7FF))


def _bl_target(rom, src):
    h1, h2 = struct.unpack_from('<HH', rom, src)
    if h1 >> 11 != 0x1E or h2 >> 11 != 0x1F:
        raise AssertionError(f'not a BL at {src:X}')
    off = ((h1 & 0x7FF) << 12) | ((h2 & 0x7FF) << 1)
    if off & 0x400000:
        off -= 0x800000
    return ROM_BASE + src + 4 + off


def _guard(original):
    if struct.unpack_from('<I', original, ATLAS_LITERAL)[0] != ROM_BASE + ATLAS:
        raise AssertionError('header atlas literal changed')
    p = struct.pack('<I', ROM_BASE + ATLAS)
    if original.count(p) != 1:
        raise AssertionError('header atlas has another literal')
    for src, target in LOADER_BLS.items():
        if _bl_target(original, src) != target:
            raise AssertionError(f'header loader call changed at {src:X}')
    for src in CALLS:
        if _bl_target(original, src) != ROM_BASE + LOADER:
            raise AssertionError(f'campaign header call changed at {src:X}')
    for lit, (addr, text) in STRING_LITERALS.items():
        if struct.unpack_from('<I', original, lit)[0] != addr:
            raise AssertionError(f'campaign string literal changed at {lit:X}')
        if original[addr - ROM_BASE:addr - ROM_BASE + len(text) + 1] != text + b'\0':
            raise AssertionError(f'campaign string changed at {addr:X}')
        if original.count(struct.pack('<I', addr)) != 1:
            raise AssertionError(f'campaign string has another literal {addr:X}')
    if LOADER % 4 != LOADER_DEST % 4:
        raise AssertionError('loader copy must keep literal-pool alignment')
    lo, hi = REGION
    if any(b != 0xFF for b in original[lo:hi]):
        raise AssertionError('header atlas relocation target is not original padding')
    for i in range(0, len(original) - 3, 2):
        if ROM_BASE + lo <= struct.unpack_from('<I', original, i)[0] < ROM_BASE + hi:
            raise AssertionError(f'original word points into relocation region at {i:X}')
    for a, b in (('Y', 'A'),):
        if glyph_width(original, a) != glyph_width(original, b):
            raise AssertionError('substitute glyph advance differs')


def korean_atlas(original, glyph_payloads):
    """Original alphabet with Korean glyph payloads; 'Y' transparent."""
    from lz77_scan import lz77_decompress
    data, _ = lz77_decompress(original, ATLAS)
    if len(data) != ATLAS_SIZE:
        raise AssertionError('unexpected header alphabet size')
    buf = bytearray(data)
    for char, payload in glyph_payloads.items():
        if len(payload) != GLYPH or char in 'Y':
            raise AssertionError(f'bad Korean header glyph {char!r}')
        at = glyph_index(original, char) * GLYPH
        buf[at:at + GLYPH] = payload
    at = glyph_index(original, 'Y') * GLYPH
    buf[at:at + GLYPH] = bytes(GLYPH)
    return bytes(buf)


def validate_edited_atlas(original, edited):
    """Editor pixels for the Korean copy: only campaign glyphs may differ."""
    from lz77_scan import lz77_decompress
    if len(edited) != ATLAS_SIZE:
        raise AssertionError(f'edited header atlas size {len(edited)} != {ATLAS_SIZE}')
    native = lz77_decompress(original, ATLAS)[0]
    for i in range(20):
        ch = chr(original[ALPHABET + i * 8])
        part = slice(i * GLYPH, (i + 1) * GLYPH)
        if ch == 'Y':
            if any(edited[part]):
                raise AssertionError('edited header atlas: substitute glyph Y must stay transparent')
        elif ch not in CAMPAIGN_GLYPHS and edited[part] != native[part]:
            raise AssertionError(f'edited header atlas changed JP glyph {ch!r}')
    return bytes(edited)


def expected_regions(original, atlas_raw):
    from lz77_compress import lz77_compress
    _guard(original)
    comp = lz77_compress(atlas_raw, vram_safe=True)
    if ATLAS_DEST + len(comp) > REGION[1]:
        raise AssertionError('Korean header atlas does not fit relocation region')
    loader = bytearray(original[LOADER:LOADER_END])
    for src in LOADER_BLS:
        rel = src - LOADER
        loader[rel:rel + 4] = _bl(LOADER_DEST + rel, LOADER_BLS[src])
    rel = ATLAS_LITERAL - LOADER
    loader[rel:rel + 4] = struct.pack('<I', ROM_BASE + ATLAS_DEST)
    strings = bytearray()
    literals = []
    for lit, (_, text) in sorted(STRING_LITERALS.items()):
        literals.append((lit, struct.pack('<I', ROM_BASE + STRINGS_DEST + len(strings))))
        strings += STRING_SUBST[text] + b'\0'
        strings += bytes(-len(strings) % 4)
    if STRINGS_DEST + len(strings) > ATLAS_DEST or LOADER_DEST + len(loader) > STRINGS_DEST:
        raise AssertionError('header relocation layout overlaps')
    regions = [(LOADER_DEST, bytes(loader)), (STRINGS_DEST, bytes(strings)),
               (ATLAS_DEST, comp)]
    regions += [(src, _bl(src, ROM_BASE + LOADER_DEST)) for src in CALLS]
    regions += literals
    return tuple(regions)


def patch(rom, original, atlas_raw):
    if bytes(rom[ATLAS:ATLAS + 4]) != bytes(original[ATLAS:ATLAS + 4]):
        raise AssertionError('header alphabet modified by another writer')
    regions = expected_regions(original, atlas_raw)
    for address, data in regions:
        current = bytes(rom[address:address + len(data)])
        if current not in (bytes(original[address:address + len(data)]), data):
            raise AssertionError(f'header relocation target {address:X} written by another writer')
        rom[address:address + len(data)] = data
    return regions


def verify(rom, original, regions):
    from lz77_scan import lz77_decompress
    for address, raw in regions:
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError(f'header relocation overwritten at {address:06X}')
    native, consumed = lz77_decompress(original, ATLAS)
    if bytes(rom[ATLAS:ATLAS + consumed]) != bytes(original[ATLAS:ATLAS + consumed]):
        raise AssertionError('original header alphabet changed')
    if struct.unpack_from('<I', rom, ATLAS_LITERAL)[0] != ROM_BASE + ATLAS:
        raise AssertionError('MODE*SELECT loader no longer reads the original alphabet')


# Every caller of the header loader (BL -> 0x08373DEC, or the Korean copy) and
# the ROM word holding its string pointer (r0). Traced b19/b20: 18 literal
# pools plus the SYOGUN*SELECT data word 0x54EE64 loaded by 0x837D724.
HEADER_CALLERS = {
    0x332B26: 0x332B68,   # NOW*LOADING
    0x333F96: 0x334038,   # LINK*MODE
    0x3490EC: 0x34938C,   # WARS*SHOP
    0x365482: 0x3654B8,   # RULE*SETTING
    0x365BAE: 0x365C4C,   # TEAM*SETTING
    0x365C84: 0x365D48,   # TEAM*SETTING
    0x365D84: 0x365E28,   # TEAM*SETTING
    0x36E67A: 0x36E6F4,   # RULE*SETTING
    0x36EB3A: 0x36EB50,   # TEAM*SETTING
    0x36EB90: 0x36EBA8,   # RULE*SETTING
    0x36F76C: 0x36F81C,   # SOUND*ROOM
    0x36F9DC: 0x36FAA0,   # SOUND*ROOM
    0x3772CC: 0x3772D4,   # HARD*CAMPAIGN (Korean copy)
    0x3772EE: 0x3772FC,   # CAMPAIGN (Korean copy)
    0x37D74A: 0x54EE64,   # SYOGUN*SELECT (data word)
    0x38207C: 0x3820FC,   # MODE*SELECT
    0x382122: 0x382190,   # MODE*SELECT
    0x386866: 0x3868C8,   # MAP*SELECT
    0x388A34: 0x388A44,   # COLOR*EDIT
}
HEADER_STRING_MAX = 16


def header_alphabet(rom):
    return {rom[ALPHABET + i * 8] for i in range(20)}


def _is_bl(rom, a):
    h1, h2 = struct.unpack_from('<HH', rom, a)
    return h1 >> 11 == 0x1E and h2 >> 11 == 0x1F


def header_callers(rom):
    """All BLs in the ROM that reach the header loader or its Korean copy."""
    loaders = {ROM_BASE + LOADER, ROM_BASE + LOADER_DEST}
    return sorted(a for a in range(0, len(rom) - 4, 2)
                  if _is_bl(rom, a) and _bl_target(rom, a) in loaders)


def header_strings(rom):
    """{caller: (pointer_word, text_bytes)} as drawn by 0x08373D10."""
    out = {}
    for caller, word in HEADER_CALLERS.items():
        ptr = struct.unpack_from('<I', rom, word)[0]
        at = ptr - ROM_BASE
        if not 0 <= at < len(rom):
            raise AssertionError(f'header string pointer out of ROM: {caller:X} -> {ptr:X}')
        raw = bytes(rom[at:at + HEADER_STRING_MAX + 1])
        if b'\0' not in raw:
            raise AssertionError(f'header string unterminated at {ptr:X}')
        out[caller] = (word, raw[:raw.index(b'\0')])
    return out


def verify_header_strings(rom):
    """Reject any string the OBJ header drawer cannot render.

    0x08373D10 looks each byte up in the 20-entry ASCII alphabet table; any
    other byte (e.g. SJIS Korean) walks past the table and draws nothing.
    """
    callers = header_callers(rom)
    if callers != sorted(HEADER_CALLERS):
        raise AssertionError(f'header loader callers changed: {[hex(c) for c in callers]}')
    alphabet = header_alphabet(rom)
    bad = {}
    for caller, (word, text) in header_strings(rom).items():
        if not text or any(b not in alphabet for b in text):
            bad[hex(caller)] = (hex(word), text)
    if bad:
        raise AssertionError(f'header drawer strings outside the ASCII alphabet: {bad}')
    return len(HEADER_CALLERS)
