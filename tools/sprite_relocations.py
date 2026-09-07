"""Declared compressed sprite relocations shared by the build and editor."""
import struct

from lz77_scan import lz77_decompress

# The original ROM contains FF padding here. Keep dialogue allocations below it.
SPRITE_STORAGE_START = 0xAFF000
SPRITE_STORAGE_END = 0xB00000
RELOCATIONS = {
    0xC1A81C: {'pointer': 0xDFAD0C, 'destination': SPRITE_STORAGE_START,
               'capacity': SPRITE_STORAGE_END - SPRITE_STORAGE_START, 'decoded_size': 1280},
}


def resolve_sprite_offset(rom, source):
    spec = RELOCATIONS.get(source)
    if spec is None:
        return source
    pointer = struct.unpack_from('<I', rom, spec['pointer'])[0]
    if pointer not in (0x08000000 + source, 0x08000000 + spec['destination']):
        raise ValueError(f'unexpected sprite pointer at {spec["pointer"]:#x}: {pointer:#x}')
    return pointer - 0x08000000


def write_relocated_sprite(rom, source, compressed):
    spec = RELOCATIONS[source]
    destination, capacity = spec['destination'], spec['capacity']
    decoded = lz77_decompress(compressed, 0)
    if len(compressed) > capacity or decoded is None or len(decoded[0]) != spec['decoded_size']:
        raise ValueError(f'invalid relocated sprite payload for {source:#x}')
    current = resolve_sprite_offset(rom, source)
    if current == source:
        if rom[destination:destination + capacity] != b'\xff' * capacity:
            raise ValueError('sprite storage is not unused FF padding')
        needle = struct.pack('<I', source + 0x08000000)
        references, position = [], 0
        while (position := rom.find(needle, position)) >= 0:
            references.append(position)
            position += 1
        if references != [spec['pointer']]:
            raise ValueError(f'unexpected sprite reference set: {references}')
    elif lz77_decompress(rom, destination) is None:
        raise ValueError('existing relocated sprite is invalid')
    rom[destination:destination + capacity] = compressed + b'\xff' * (capacity - len(compressed))
    struct.pack_into('<I', rom, spec['pointer'], destination + 0x08000000)
    return len(compressed), capacity
