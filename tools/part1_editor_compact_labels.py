"""Bounded Part 1 editor caption consumer gate."""
import hashlib
import struct

CODE_OFFSET = 0xF31E00
# Assembled from tools/asm/part1_editor_compact_gate.s (ARM7TDMI Thumb).
# The linked code and literal pool exactly fill the owned F31E00..F31EEC allocation.
CODE = bytes.fromhex(
    '02b5380000f049f802bc01bc864640d03248281a10280cd03c280ad03e2802d3'
    '4c38042805d204360c2801d0382800d104362d4800472948281a62282cd20398'
    '02b500f02af802bc01bc864621d02548301a224fef1b282f00d24038c709052f'
    '17d28c1e062c14d24006400e4c00a0420fd1812000026430341f208030804034'
    '208004342080f8004018d830164f543738471548a230004792e006b402001049'
    '401a010a0f2915d26038fdd2603011d1106800280ed1906a0a49c639884209d1'
    '0649681a622805d2a91c106a884201d1012000e0002006bc7047c0464c24d808'
    '000e00030a2e01023b06f308'
)
assert len(CODE) == 0xEC
assert hashlib.sha256(CODE).hexdigest() == 'e0d0d47078282b8fbbd3c627f52d09ac377133b1364ec06385c05cc5943454d1'

# Record-map stage predecessors. F31FE4 stays at its original record-map target.
REPLACES = {
    0xF3075C: (0x08F306DD, 0x08F31E01),
    0xF31FB4: (0x08F306DD, 0x08F31E01),
    0xF30664: (0x08F31FC1, 0x08F31E37),
}
LEGACY_ROW_SITE = 0xF31FE4
LEGACY_ROW_TARGET = 0x08F307A9
RETURN_SITE = 0xB0469A
RETURN_OLD = bytes.fromhex('15f05ffd662039f0bafe034801680320888000f0d8f9')


def _checked(rom, original):
    if len(rom) != len(original) or len(rom) < CODE_OFFSET + len(CODE):
        raise AssertionError('editor gate requires matching complete ROMs')
    if (bytes(original[CODE_OFFSET:CODE_OFFSET + len(CODE)]) != bytes(len(CODE)) or
            bytes(rom[CODE_OFFSET:CODE_OFFSET + len(CODE)]) != bytes(len(CODE))):
        raise AssertionError('editor helper allocation occupied')
    for address, (old, _) in REPLACES.items():
        if struct.unpack_from('<I', rom, address)[0] != old:
            raise AssertionError(f'editor gate predecessor changed at {address:#x}')
    if struct.unpack_from('<I', rom, LEGACY_ROW_SITE)[0] != LEGACY_ROW_TARGET:
        raise AssertionError('legacy row predecessor changed')
    if bytes(original[RETURN_SITE:RETURN_SITE + 22]) != RETURN_OLD:
        raise AssertionError('B-return original source changed')
    if bytes(rom[RETURN_SITE:RETURN_SITE + 22]) != RETURN_OLD:
        raise AssertionError('B-return source changed')


def patch(rom, original):
    # Validate every site before the first write so a failed install is atomic.
    _checked(rom, original)
    rom[CODE_OFFSET:CODE_OFFSET + len(CODE)] = CODE
    for address, (_, new) in REPLACES.items():
        struct.pack_into('<I', rom, address, new)
    return {'code': hex(CODE_OFFSET), 'size': len(CODE),
            'sha256': hashlib.sha256(CODE).hexdigest(),
            'source_range': ['0x08D8244C', '0x08D824AE'],
            'pool': ['0x03000E00', '0x03001D00']}


def verify(rom):
    if bytes(rom[CODE_OFFSET:CODE_OFFSET + len(CODE)]) != CODE:
        raise AssertionError('editor helper overwritten')
    for address, (_, new) in REPLACES.items():
        if struct.unpack_from('<I', rom, address)[0] != new:
            raise AssertionError(f'editor gate overwritten at {address:#x}')
    if struct.unpack_from('<I', rom, LEGACY_ROW_SITE)[0] != LEGACY_ROW_TARGET:
        raise AssertionError('legacy row overwritten')
    if bytes(rom[RETURN_SITE:RETURN_SITE + 22]) != RETURN_OLD:
        raise AssertionError('B-return source overwritten')
