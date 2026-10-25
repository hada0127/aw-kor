"""Bounded Part 1 editor caption consumer gate."""
import hashlib
import struct

CODE_OFFSET = 0xF31E00
# Assembled from tools/asm/part1_editor_compact_gate.s (ARM7TDMI Thumb).
# The linked code and literal pool exactly fill the owned F31E00..F31EEC allocation.
CODE = bytes.fromhex(
    '02b5380000f04cf802bc01bc864643d03348281a10280ad03c2802d34c380428'
    '05d204360c2801d0382800d10436624800472b48281a622831d2039802b500f0'
    '2ff802bc01bc864626d02748301a244fef1b282f00d24038c709052f1cd28c1e'
    '062c19d24006400e4c00a04214d1812000026430022f05d0042f03d0341f2080'
    '403420803080340040342080f8004018d830494f543738474748a23000478fe0'
    '06b402000f49401a010a0f2915d26038fdd2603011d1106800280ed1906a0a49'
    'c639884209d10649681a622805d2a91c106a884201d1012000e0002006bc7047'
    '4c24d808000e00030a2e0102'
)
assert len(CODE) == 0xEC
assert hashlib.sha256(CODE).hexdigest() == '9d9662da832257e0b14528f25566ae7a9d846b4d11cb2b7b2bfd800fcd11cc80'

# Record-map stage predecessors. F31FE4 stays at its original record-map target.
REPLACES = {
    0xF3075C: (0x08F306DD, 0x08F31E01),
    0xF31FB4: (0x08F306DD, 0x08F31E01),
    0xF30664: (0x08F31FC1, 0x08F31E33),
}
LEGACY_ROW_SITE = 0xF31FE4
LEGACY_ROW_TARGET = 0x08F307A9
LEGACY_LOOKUP_LITERAL = 0xF31FB8
LEGACY_LOOKUP_TARGET = 0x08F3063B
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
    if struct.unpack_from('<I', rom, LEGACY_LOOKUP_LITERAL)[0] != LEGACY_LOOKUP_TARGET:
        raise AssertionError('legacy lookup literal changed')
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
    if struct.unpack_from('<I', rom, LEGACY_LOOKUP_LITERAL)[0] != LEGACY_LOOKUP_TARGET:
        raise AssertionError('legacy lookup literal overwritten')
    if bytes(rom[RETURN_SITE:RETURN_SITE + 22]) != RETURN_OLD:
        raise AssertionError('B-return source overwritten')
