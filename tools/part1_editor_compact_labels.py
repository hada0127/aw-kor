"""Bounded Part 1 editor caption consumer gate."""
import hashlib
import struct

CODE_OFFSET = 0xF31E00
# Assembled from tools/asm/part1_editor_compact_gate.s (ARM7TDMI Thumb).
# Keep the zero padding in the owned F31E00..F31EEC allocation explicit.
CODE = bytes.fromhex(
    '02b5380000f037f8002802bc01bc864609d02a48281a282802d34c38042800d2'
    '04362a4800472a4800472448281a62281fd2039802b500f01ef8002802bc01bc'
    '8646f0d080b42048301ac709052f0ed208290cd24006400e4f00b84207d11a48'
    '301ac009c000401880bc1b4f384780bcd9e71848004706b402001149401af021'
    '0901884216d2602801d36038fbe7002810d1106800280dd1906a0a49884209d1'
    '0649681a622805d2a91c106a884201d1012000e0002006bc7047c0464c24d808'
    '000e0003442d01020a2e01023b06f308dd06f308c11ff3088f06f308'
    '00000000000000000000000000000000'
)
assert len(CODE) == 0xEC
assert hashlib.sha256(CODE).hexdigest() == '9219a1c3eae0a83bb1c41319b6ba21b4b540412d557523a1d4443dade399aa78'

# Record-map stage predecessors. F31FE4 stays at its original record-map target.
REPLACES = {
    0xF3075C: (0x08F306DD, 0x08F31E01),
    0xF31FB4: (0x08F306DD, 0x08F31E01),
    0xF30664: (0x08F31FC1, 0x08F31E2B),
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
