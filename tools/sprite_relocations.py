"""Declared compressed sprite relocations shared by the build and editor."""
import struct
import hashlib

from lz77_scan import lz77_decompress

# The original ROM contains FF padding here. Keep dialogue allocations below it.
SPRITE_STORAGE_START = 0xAFF000
SPRITE_STORAGE_END = 0xB00000
RELOCATIONS = {
    0xC1A81C: {'pointer': 0xDFAD0C, 'destination': SPRITE_STORAGE_START,
               'capacity': SPRITE_STORAGE_END - SPRITE_STORAGE_START, 'decoded_size': 1280},
}


def resolve_sprite_offset(rom, source):
    return resolve_sprite_allocation(rom, source)[0]


def resolve_sprite_allocation(rom, source, native_capacity=None):
    """Return the consumer's live stream and its bounded writable allocation."""
    import part1_mission_titles as missions
    import part1_m19_title as m19
    import part1_m20_title as m20
    import part2_power_title_glyphs as power
    from hangul_pixel_fit import PLATE_LOADERS, plate_address

    blocks = {row[0]: row for row in missions._all_blocks()}
    if source in blocks:
        row = blocks[source]
        address = missions.stream_address(rom, source)
        moved = missions.relocations()
        expected = moved.get(source, (source,))[0]
        if address == source and source in moved:
            if hashlib.sha256(rom).hexdigest() != power.ORIGINAL_SHA256:
                raise ValueError(f'relocated mission title pointer reverted: {source:#x}')
            return address, row[2]
        if address != expected:
            raise ValueError(f'unexpected mission title pointer: {source:#x} -> {address:#x}')
        if address == source:
            return address, row[2]
        destinations = sorted([dest for dest, _ in moved.values()] + [missions.RELOCATION_END])
        return address, destinations[destinations.index(address) + 1] - address
    for module in (m19, m20):
        if source == module.SOURCE:
            address = struct.unpack_from('<I', rom, module.POINTER)[0] - 0x08000000
            if address not in (source, module.RELOCATION):
                raise ValueError(f'unexpected mission title pointer: {source:#x} -> {address:#x}')
            if address == source and hashlib.sha256(rom).hexdigest() != power.ORIGINAL_SHA256:
                raise ValueError(f'relocated mission title pointer reverted: {source:#x}')
            return (address, module.CAPACITY if address == source else
                    module.RELOCATION_LIMIT - module.RELOCATION)
    if source in PLATE_LOADERS:
        address = plate_address(rom, source)
        if address == source:
            return address, native_capacity
        moved = sorted({plate_address(rom, off) for off in PLATE_LOADERS
                        if plate_address(rom, off) != off} | {0xFDB000})
        return address, moved[moved.index(address) + 1] - address
    if source == power.OFFSET:
        addresses = {struct.unpack_from('<I', rom, loc)[0] - 0x08000000
                     for loc in power.ATLAS_POINTERS}
        if len(addresses) != 1 or next(iter(addresses)) not in (source, power.ATLAS):
            raise ValueError('unexpected power title atlas pointers')
        address = addresses.pop()
        return address, native_capacity if address == source else power.ATLAS_CAPACITY
    spec = RELOCATIONS.get(source)
    if spec is None:
        return source, native_capacity
    pointer = struct.unpack_from('<I', rom, spec['pointer'])[0]
    if pointer not in (0x08000000 + source, 0x08000000 + spec['destination']):
        raise ValueError(f'unexpected sprite pointer at {spec["pointer"]:#x}: {pointer:#x}')
    address = pointer - 0x08000000
    return address, native_capacity if address == source else spec['capacity']


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
