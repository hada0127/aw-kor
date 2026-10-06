"""Part 2 WAR IS OVER newspaper: give it its own copy of the original newspaper sheet.

Static RE (original ROM, 2026-10-06 candidate6):
- LZ77 0x5B5D10 (8192 B = 256 BG tiles, 6666 B compressed) is the shared
  newspaper sheet.  build_korean_full.patch_part2_menu_newspaper_bg redraws all
  256 tiles as a linear 128x128 Korean collage for the mode-menu newspaper.
- 11 literals reference the sheet.  Ten of them load it together with the
  collage tilemap 0x5B58E0 (savestates: screen block 0xF800, char block 0x8000)
  and keep the Korean collage: literals 0x334028, 0x33DDB0, 0x349364, 0x36F7C8,
  0x36FA40, 0x374CE0, 0x381EF8, 0x388934, and the two intro newspapers
  0x3699C0 / 0x369E6C (sheet -> 0x06002800, 0x5B58E0 entries + 0x140).
  0x4E00BC / 0x4E02E4 loaded next to the intro sheet are 8-bit affine maps of
  the light-beam tiles 0x4DFF70, not sheet users.
  They all keep the Korean collage.
- The only consumer with its own arrangement is the WAR IS OVER newspaper:
  0x0836BDB4 ldr r0, =0x085B5D10 (literal 0x36BE98) -> 0x06008000, with tiles
  0x508EC0 -> 0x0600CC00 and tilemap 0x509D6C (810 cells use 66 sheet tiles:
  masthead 201..215/233..247, text lines 168..175, frames 227..232, photo
  24..31/56..63/88..95).  With the collage those cells render as stripes.

Fix: copy the original compressed sheet to 0x2F8000 (0xFF padding of the
original ROM, no word in the original ROM points into 0x082F8000..+6668) and
repoint only literal 0x36BE98.  The masthead 'WARS WORLD PAPER' and the small
text lines of that newspaper stay as in the original (decorative logo/texture).
The headline itself is part2_war_over_headline (0x508EC0).
"""
import hashlib
import struct

SOURCE = 0x5B5D10
SOURCE_SIZE = 6666               # consumed bytes of the original LZ77 stream
LITERAL = 0x36BE98
LITERAL_USER = 0x36BDB4          # ldr r0, [pc, #0xe0]
DEST = 0x2F8000
DEST_LIMIT = 0x300000
ROM_BASE = 0x08000000


def _source(original):
    if original[SOURCE] != 0x10 or int.from_bytes(original[SOURCE + 1:SOURCE + 4], 'little') != 0x2000:
        raise AssertionError('newspaper sheet header changed')
    block = bytes(original[SOURCE:SOURCE + SOURCE_SIZE])
    if hashlib.sha256(block).hexdigest() != EXPECTED_SHA256:
        raise AssertionError('newspaper sheet source changed')
    return block


EXPECTED_SHA256 = '7133842856a5413dcfb429bc3537d54639355d1c44f8b52c1c9e4b3acf5d0cc4'


def _guard_original(original):
    if struct.unpack_from('<I', original, LITERAL)[0] != ROM_BASE + SOURCE:
        raise AssertionError('WAR IS OVER sheet literal changed')
    # ldr r0, [pc, #imm] at LITERAL_USER must address LITERAL
    h = struct.unpack_from('<H', original, LITERAL_USER)[0]
    if h >> 11 != 0b01001 or ((LITERAL_USER + 4) & ~3) + (h & 0xFF) * 4 != LITERAL:
        raise AssertionError('WAR IS OVER sheet loader changed')
    if any(b != 0xFF for b in original[DEST:DEST + SOURCE_SIZE + 2]):
        raise AssertionError('relocation target is not original padding')


def patch(rom, original):
    _guard_original(original)
    block = _source(original)
    current = bytes(rom[DEST:DEST + SOURCE_SIZE])
    if current not in (bytes(original[DEST:DEST + SOURCE_SIZE]), block):
        raise AssertionError('newspaper sheet relocation target written by another writer')
    literal = struct.unpack_from('<I', rom, LITERAL)[0]
    if literal not in (ROM_BASE + SOURCE, ROM_BASE + DEST):
        raise AssertionError('WAR IS OVER sheet literal modified by another writer')
    rom[DEST:DEST + SOURCE_SIZE] = block
    struct.pack_into('<I', rom, LITERAL, ROM_BASE + DEST)
    return 1


def expected_regions(original):
    return ((DEST, _source(original)), (LITERAL, struct.pack('<I', ROM_BASE + DEST)))


def capture(rom, original):
    return tuple((address, bytes(rom[address:address + len(data)]))
                 for address, data in expected_regions(original))


def verify(rom, regions):
    if tuple(address for address, _ in regions) != (DEST, LITERAL):
        raise AssertionError('newspaper sheet relocation snapshot missing')
    for address, raw in regions:
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError(f'newspaper sheet relocation overwritten at {address:06X}')


def generated_matches(rom, original):
    return all(bytes(rom[a:a + len(d)]) == d for a, d in expected_regions(original))
