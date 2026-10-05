"""Allow the observed record-menu live state through the compact map hook.

The single/link list renders with state 0x03000F20; map records use 0x03001220
initially and 0x03001280 when scrolling.
Both initialize a hidden 0x03000F80 buffer first. Keep rejecting that hidden
buffer. Single/link retains its six-cell/page allocation. Records use seven
cells in an eight-row EWRAM ring and a separate 112-tile BG character window.
"""
import hashlib
import struct

HOOK = 0xF30600
HOOK_SIZE = 0x118
TABLE_END_OFFSET = 0x100
HOOK_LAYOUT_SHA256 = 'ed86defba6b50126789e61ed249b275db1fd827ecf160d477ed763a9d85181c0'
SITE = 0xF30614
EXPECTED = bytes.fromhex('3548874260d13548')
GATE = 0xF30720
# tools/asm/part1_record_map_gate.s. All targets preserve Thumb state.
CODE = bytes.fromhex(
    '0648874207d00648874204d06030874201d0044800470448044b1847'
    '200f000320120003dd06f308a01cb8081d06f308'
)
TRAMPOLINE = bytes.fromhex('00480047') + struct.pack('<I', 0x08000000 + GATE + 1)
ROW_SITE = 0xF3065E
ROW_EXPECTED = bytes.fromhex('06293cd2301cc009072528400628')
ROW_GATE = 0xF307A8
ROW_CODE = bytes.fromhex(
    '039f0f48874211d0b00a114da84291d107298fd2301cc00907252840c5002d1a68184000'
    '0749091807480047062981d2301cc009072528400628044f3847c046'
    '200f0003800200009506f3086d06f30800800000'
)
# This site is only halfword-aligned: NOP first, then an aligned literal load.
ROW_TRAMPOLINE = (bytes.fromhex('c04600480047') + struct.pack('<I', 0x08000000 + ROW_GATE + 1)
                  + bytes.fromhex('c046c046'))
WRITES = ((SITE, TRAMPOLINE), (GATE, CODE), (ROW_SITE, ROW_TRAMPOLINE), (ROW_GATE, ROW_CODE))


def patch(rom, original):
    """Validate every writer before mutating, including the complete old hook."""
    if len(rom) != len(original) or len(rom) < ROW_GATE + len(ROW_CODE):
        raise AssertionError('record map gate requires matching complete ROMs')
    layout = bytearray(rom[HOOK:HOOK + HOOK_SIZE])
    table_end = struct.unpack_from('<I', layout, TABLE_END_OFFSET)[0]
    if not 0x08F30800 < table_end <= 0x08F32000 or (table_end - 0x08F30800) % 8:
        raise AssertionError('record map gate requires a valid glyph table extent')
    layout[TABLE_END_OFFSET:TABLE_END_OFFSET + 4] = bytes(4)
    if hashlib.sha256(layout).hexdigest() != HOOK_LAYOUT_SHA256:
        raise AssertionError('existing compact map hook layout changed')
    if bytes(rom[SITE:SITE + len(EXPECTED)]) != EXPECTED:
        raise AssertionError('compact map state gate changed')
    if bytes(rom[ROW_SITE:ROW_SITE + len(ROW_EXPECTED)]) != ROW_EXPECTED:
        raise AssertionError('compact map row gate changed')
    # The gap is between the old hook ending F30718 and inactive B84 slot F30780.
    if GATE < HOOK + HOOK_SIZE or GATE + len(CODE) > 0xF30780:
        raise AssertionError('record map gate overlaps a neighboring hook')
    if not 0xF307A8 <= ROW_GATE < ROW_GATE + len(ROW_CODE) <= 0xF30800:
        raise AssertionError('record map row gate overlaps a neighboring hook')
    for address, code in ((GATE, CODE), (ROW_GATE, ROW_CODE)):
        if (bytes(original[address:address + len(code)]) != bytes(len(code)) or
                bytes(rom[address:address + len(code)]) != bytes(len(code))):
            raise AssertionError('record map gate allocation is not pristine')
    for address, payload in WRITES:
        rom[address:address + len(payload)] = payload
    return {'states': ['0x03000F20', '0x03001220', '0x03001280'], 'hidden_state_rejected': '0x03000F80',
            'record_tiles': ['0x280', '0x2EF'], 'single_link_tiles_unchanged': ['0x3A8', '0x3FB'],
            'writes': [{'offset': hex(a), 'size': len(raw),
                        'sha256': hashlib.sha256(raw).hexdigest()} for a, raw in WRITES]}


def verify(rom):
    for address, expected in WRITES:
        if bytes(rom[address:address + len(expected)]) != expected:
            raise AssertionError(f'record map gate overwritten at {address:#x}')
