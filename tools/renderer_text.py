"""Renderer-attributed text encoding; never normalize command streams.

Native dispatch evidence: B12074/B120F4 and 31424C/314270. B1311C
reads glyph pairs. These profiles exclude the EWRAM link-client images.
"""
from collections import Counter
from dialogue_regions import is_part1_dialog_address, is_part2_story_address

P1_SCRIPT = 'p1_b12074'
P2_SCRIPT = 'p2_31424c'
P1_PAIRS = 'p1_b1311c'
P2_PAIRS = 'p2_pairs'
PRELOAD = 'p2_preload'
COMMANDS = {
    P1_SCRIPT: frozenset(b'>CHKMPQRSWikpqrsw0123\x09\x0a\x0d\x19'),
    P2_SCRIPT: frozenset(b'KPQRSWchmkpqrsw0123\x09\x0a\x0d\x19'),
}


def renderer_for_address(address):
    if address is None:
        return None
    if is_part1_dialog_address(address):
        return P1_SCRIPT
    if is_part2_story_address(address):
        return P2_SCRIPT
    if 0xA29AB0 <= address < 0xA2A244 or 0xA31444 <= address < 0xA3408C or 0xA34E58 <= address < 0xA352B4:
        # Master-table help/link messages contain native r/k/style commands.
        return P2_SCRIPT
    if 0xB82F54 <= address < 0xB831D0 or 0xB83A3C <= address < 0xB842F0:
        # 0x19 message users, including DEBA18/DEBA28/DEBB00.
        return P1_SCRIPT
    if 0xB8180C <= address < 0xB81F00 or 0xB827D0 <= address < 0xB82800 or 0xB8457C <= address < 0xB84600:
        # Unit, map category and menu records; see B43C71 and B47035.
        return P1_PAIRS
    if 0xA352B4 <= address < 0xA357B4:
        return P2_SCRIPT  # Ghidra 0836FAB0 -> 08314A50 -> 0831423C
    if address in (0xA2C8D8, 0xA2C8EC, 0xA2C900):
        return P2_PAIRS
    if 0xA2C5F0 <= address < 0xA2C708 or address == 0xA2C9D4:
        return P2_SCRIPT  # editor master-table messages, native r/k controls
    if address == 0x804FD4:
        return PRELOAD
    if address in (0xE104B6, 0xE104CA, 0xE104DA, 0xEC328E):
        return P1_SCRIPT
    return None


def normalize_text(text, renderer):
    """Authored visible text only. Spaces retain the caller's layout policy."""
    if renderer is None:
        return text
    # Keep the established dialogue ellipsis instead of three sentence stops.
    text = text.replace('...', '・・・')
    import re
    text = re.sub(r'(?<=[0-9０-９])\.(?=[0-9０-９])', '・', text)
    punct = {'.': '。', ',': '、', '-': 'ー' if renderer in (P2_SCRIPT, P2_PAIRS, PRELOAD) else '―',
             '~': '〜', '"': '”', "'": '”', '[': '（', ']': '）', '{': '（', '}': '）',
             ':': '；', '*': '＋', '=': '―', '@': '＃', '\\': '＼'}
    return ''.join(punct.get(ch, chr(ord(ch) + 0xFEE0)) if 0x21 <= ord(ch) <= 0x7e else ch for ch in text)


def single_bytes(payload):
    """Token boundaries, not raw-byte grep (Hangul trails include opcodes)."""
    i = 0
    while i < len(payload):
        b = payload[i]
        if 0x81 <= b <= 0x9f or 0xe0 <= b <= 0xef:
            if i + 1 >= len(payload):
                raise ValueError('truncated two-byte glyph')
            i += 2
        else:
            yield i, b
            i += 1


def halfwidth_violations(payload, renderer, native=b'', *, added_controls=b''):
    """Commands are allowed only up to their native source multiplicity.

    Added row/page controls require an explicit recorded layout operation.
    Padding spaces are not visible glyphs and do not grant letters/digits a pass.
    """
    allowed = COMMANDS.get(renderer, frozenset())
    counts = Counter(b for _, b in single_bytes(native) if b in allowed)
    additions = Counter(added_controls)
    if additions.keys() - set(b'rk\x09\x0a'):
        raise ValueError('unrecognized recorded layout control')
    bad = []
    for offset, byte in single_bytes(payload):
        if byte in (0, 0x20):
            continue
        if byte in allowed and (counts[byte] or additions[byte]):
            if counts[byte]:
                counts[byte] -= 1
            else:
                additions[byte] -= 1
            continue
        if byte < 0x80:
            bad.append((offset, byte))
    return bad


def final_text_spans(writes, rom_size):
    """Final text byte owners, including surviving parts of merged writers.

    Spacing comparisons require a complete sentence, but an unsafe byte in a
    partially superseded writer must still fail the renderer guard.
    """
    occupied = bytearray(rom_size)
    for entry in reversed(writes):
        address, size = entry[:2]
        if address < 0 or size < 0 or address + size > rom_size:
            raise ValueError('invalid text owner bounds')
        if (len(entry) >= 8 and renderer_for_address(address)
                and (str(entry[7]).startswith('script:') or entry[5])):
            begin = None
            for i in range(size + 1):
                live = i < size and not occupied[address + i]
                if live and begin is None:
                    begin = i
                elif not live and begin is not None:
                    yield address + begin, i - begin, address, size
                    begin = None
        occupied[address:address + size] = b'\1' * size


def normalize_final_inplace(rom, original, writes, manifest):
    """Normalize last text owners within their existing capacity; never truncate.

    Relocated owners use the encoder before allocation. Native control tokens
    are retained by the same source-bound allowlist used by the final guard.
    """
    from qa_dialogue_jamming import final_owner_spans
    ranges = [(int(m['msg'], 16), int(m['msg'], 16) + m['old_len'])
              for m in manifest if m.get('status') == 'relocated']
    owners, _ = final_owner_spans(writes, len(rom), hangul_only=False)
    changed = []
    for addr, entry in sorted(owners.items()):
        profile = renderer_for_address(addr)
        if not profile or any(lo <= addr < hi for lo, hi in ranges):
            continue
        raw = bytes(rom[addr:addr + entry[1]])
        bad = dict(halfwidth_violations(raw, profile, original[addr:addr + entry[1]]))
        if not bad:
            continue
        out = bytearray()
        for i, byte in enumerate(raw.rstrip(b' ')):
            if i in bad:
                if not 0x21 <= byte <= 0x7e:
                    raise AssertionError(f'unknown renderer control at {addr+i:#x}: {byte:#x}')
                out.extend(normalize_text(chr(byte), profile).encode('shift_jis'))
            else:
                out.append(byte)
        if len(out) > entry[1]:
            raise AssertionError(f'renderer normalization needs relocation: {addr:#x}, {len(out)} > {entry[1]}')
        n = len(out)
        out += b' ' * (entry[1] - n)
        rom[addr:addr + entry[1]] = out
        writes.append([addr, entry[1], n, out[:n].hex(), 0x20, entry[5], entry[6], 'renderer-normalization'])
        changed.append(addr)
    return changed


def supply_a3_glyphs(rom, original, writes, manifest):
    """Supply missing fullwidth Latin glyphs in the native linked A3 cache.

    A node is next:u32, high:u8, width:u8, pixels:64, alignment:2. Only
    zero-filled, unreferenced original storage after the decimal node is used.
    """
    import struct
    from qa_renderer_text import payloads
    from render_galmuri_8x16 import render_char
    needed = set()
    for _, profile, raw, _ in payloads(rom, original, writes, manifest):
        if profile not in (P2_SCRIPT, P2_PAIRS, PRELOAD):
            continue
        i = 0
        while i + 1 < len(raw):
            b = raw[i]
            if 0x81 <= b <= 0x9f or 0xe0 <= b <= 0xef:
                if b in (0x81, 0x82):
                    needed.add(bytes(raw[i:i+2]))
                i += 2
            else:
                i += 1
    free, end = 0xFD0100, 0xFD1000
    added = []
    for code in sorted(needed):
        bucket = 0x807680 + code[1] * 4
        head = pointer = struct.unpack_from('<I', rom, bucket)[0]
        seen = set()
        while pointer:
            node = pointer - 0x08000000
            if node in seen or not 0 <= node <= len(rom) - 72:
                raise AssertionError('invalid A3 glyph chain')
            seen.add(node)
            if rom[node+4] == code[0]:
                break
            pointer = struct.unpack_from('<I', rom, node)[0]
        if pointer:
            continue
        ch = code.decode('shift_jis')
        ascii_ch = chr(ord(ch) - 0xFEE0) if 0xff01 <= ord(ch) <= 0xff5e else {'”': '"'}.get(ch)
        if ascii_ch is None:
            raise AssertionError(f'no native A3 glyph and no approved Galmuri mapping: {code.hex()} {ch}')
        pixels = b''.join(render_char(ascii_ch, ink=10))
        if not any(pixels) or free + 72 > end or any(rom[free:free+72]) or any(original[free:free+72]):
            raise AssertionError('A3 additional glyph storage/ink contract failed')
        destination = struct.pack('<I', 0x08000000 + free)
        # Pointers are word-aligned; unaligned byte coincidences are not refs.
        _at = original.find(destination)
        while _at != -1:
            if _at % 4 == 0:
                raise AssertionError('A3 additional glyph storage is referenced')
            _at = original.find(destination, _at + 1)
        node = struct.pack('<I', head) + bytes([code[0], 8]) + pixels + bytes(2)
        rom[free:free+72] = node
        rom[bucket:bucket+4] = destination
        writes.extend([[free,72,72,node.hex(),None,None,None,'a3-fullwidth-glyph'],
                       [bucket,4,4,destination.hex(),None,None,None,'a3-fullwidth-bucket']])
        added.append((code.hex(), free))
        free += 72
    return added
