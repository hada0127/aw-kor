"""Allow observed map-list live states through the compact map hook.

The single/link list renders with state 0x03000F20 initially and 0x030010A0
when scrolling; Trial MAP SELECT also uses 0x03000EC0 and 0x03001040.
Map records use 0x03001220 initially and 0x03001280 on scroll.
Both initialize a hidden 0x03000F80 buffer first. Keep rejecting that hidden
buffer. Single/link uses eight cells in six rows plus the category title;
records use seven cells in an eight-row EWRAM ring and a separate 112-tile
BG character window. Trial MAP SELECT redraws through 0x03000EC0 after its
first 0x03000F20 pass; both passes need the single/link row layout.
"""
import hashlib
import struct

HOOK = 0xF30600
HOOK_SIZE = 0x118
TABLE_END_OFFSET = 0x100
HOOK_LAYOUT_SHA256 = 'abeac7c57bc4b8a9d8a36201e303e2252002115c5036b27e248fd871ef0c64da'
SITE = 0xF30614
EXPECTED = bytes.fromhex('3548874260d13548')
GATE = 0xF30720
# tools/asm/part1_record_map_gate.s. All targets preserve Thumb state.
CODE = bytes.fromhex(
    '0b48874210d0603887420dd0094887420ad06030874207d0'
    '0748874204d06038874201d0054800470548064b1847c046'
    '200f000320120003a0100003dd06f308a01cb8081d06f308'
)
TRAMPOLINE = bytes.fromhex('00480047') + struct.pack('<I', 0x08000000 + GATE + 1)
SOURCE_SITE = 0xF30626
SOURCE_EXPECTED = bytes.fromhex('34488542')
SOURCE_TRAMPOLINE = bytes.fromhex('3c480047')
SOURCE_PTR = 0xF30718
SOURCE_GATE = 0xF31F80
SOURCE_GATE_CODE = bytes.fromhex(
    '0948854202d3094885420ad30848854207d00230854204d00230854201d0'
    '0548004705480047c046b4d0a508ecd0a5082a8cdf08dd06f3083b06f308'
)
ROW_STATE_GATE = 0xF31FC0
ROW_STATE_GATE_CODE = bytes.fromhex(
    '039f0648874207d06038874204d00448874201d00348004703480047'
    'a0100003c00e0003a907f308d507f308'
)
ROW_SITE = 0xF3065E
ROW_EXPECTED = bytes.fromhex('06293cd2301cc009072528400628')
ROW_GATE = 0xF307A8
ROW_CODE = bytes.fromhex(
    '039f0f48874211d0b00a114da84291d107298fd2301cc00907252840c5002d1a68184000'
    '0749091807480047082981d2301cc009072528400628044f3847c046'
    '200f0003800200009506f3086d06f30800800000'
)
# This site is only halfword-aligned: NOP first, then an aligned literal load.
ROW_TRAMPOLINE = (bytes.fromhex('c04600480047') + struct.pack('<I', 0x08000000 + ROW_STATE_GATE + 1)
                  + bytes.fromhex('c046c046'))
WRITES = ((SITE, TRAMPOLINE), (GATE, CODE), (ROW_SITE, ROW_TRAMPOLINE),
          (ROW_GATE, ROW_CODE), (SOURCE_SITE, SOURCE_TRAMPOLINE),
          (SOURCE_PTR, struct.pack('<I', 0x08000000 + SOURCE_GATE + 1)),
          (SOURCE_GATE, SOURCE_GATE_CODE), (ROW_STATE_GATE, ROW_STATE_GATE_CODE))


def patch(rom, original):
    """Validate every writer before mutating, including the complete old hook."""
    if len(rom) != len(original) or len(rom) < ROW_STATE_GATE + len(ROW_STATE_GATE_CODE):
        raise AssertionError('record map gate requires matching complete ROMs')
    layout = bytearray(rom[HOOK:HOOK + HOOK_SIZE])
    table_end = struct.unpack_from('<I', layout, TABLE_END_OFFSET)[0]
    if not 0x08F30800 < table_end <= 0x08000000 + SOURCE_GATE or (table_end - 0x08F30800) % 8:
        raise AssertionError('record map gate requires a valid glyph table extent')
    layout[TABLE_END_OFFSET:TABLE_END_OFFSET + 4] = bytes(4)
    if hashlib.sha256(layout).hexdigest() != HOOK_LAYOUT_SHA256:
        raise AssertionError('existing compact map hook layout changed')
    if bytes(rom[SITE:SITE + len(EXPECTED)]) != EXPECTED:
        raise AssertionError('compact map state gate changed')
    if bytes(rom[ROW_SITE:ROW_SITE + len(ROW_EXPECTED)]) != ROW_EXPECTED:
        raise AssertionError('compact map row gate changed')
    if bytes(rom[SOURCE_SITE:SOURCE_SITE + len(SOURCE_EXPECTED)]) != SOURCE_EXPECTED:
        raise AssertionError('compact map source gate changed')
    # The gap is between the old hook ending F30718 and inactive B84 slot F30780.
    if GATE < HOOK + HOOK_SIZE or GATE + len(CODE) > 0xF30780:
        raise AssertionError('record map gate overlaps a neighboring hook')
    if not 0xF307A8 <= ROW_GATE < ROW_GATE + len(ROW_CODE) <= 0xF30800:
        raise AssertionError('record map row gate overlaps a neighboring hook')
    if (SOURCE_PTR + 4 > 0xF30720 or
            SOURCE_GATE + len(SOURCE_GATE_CODE) > ROW_STATE_GATE or
            ROW_STATE_GATE + len(ROW_STATE_GATE_CODE) > 0xF32000):
        raise AssertionError('link map source gate overlaps a neighboring hook')
    for address, code in ((GATE, CODE), (ROW_GATE, ROW_CODE),
                          (SOURCE_PTR, struct.pack('<I', 0x08000000 + SOURCE_GATE + 1)),
                          (SOURCE_GATE, SOURCE_GATE_CODE), (ROW_STATE_GATE, ROW_STATE_GATE_CODE)):
        if (bytes(original[address:address + len(code)]) != bytes(len(code)) or
                bytes(rom[address:address + len(code)]) != bytes(len(code))):
            raise AssertionError('record map gate allocation is not pristine')
    for address, payload in WRITES:
        rom[address:address + len(payload)] = payload
    return {'states': ['0x03000F20', '0x03000EC0', '0x030010A0', '0x03001040', '0x03001220', '0x03001280'], 'hidden_state_rejected': '0x03000F80',
            'record_tiles': ['0x280', '0x2EF'],
            'single_link_tiles': ['0x0D0', '0x13F'],
            'writes': [{'offset': hex(a), 'size': len(raw),
                        'sha256': hashlib.sha256(raw).hexdigest()} for a, raw in WRITES]}


def verify(rom, overlays=None):
    overlays = overlays or {}
    for address, expected in WRITES:
        actual_expected = bytearray(expected)
        for overlay_address, overlay in overlays.items():
            if address <= overlay_address and overlay_address + len(overlay) <= address + len(expected):
                at = overlay_address - address
                actual_expected[at:at + len(overlay)] = overlay
        if bytes(rom[address:address + len(expected)]) != actual_expected:
            raise AssertionError(f'record map gate overwritten at {address:#x}')
