"""Final-ROM guard for attributed parser/pair payloads, with native controls."""
import argparse
import json
from pathlib import Path
from qa_dialogue_jamming import validate_manifest, verify_provenance
from repoint_source_rows import row_bytes
from renderer_text import renderer_for_address, halfwidth_violations, final_text_spans, single_bytes

ROOT = Path(__file__).resolve().parents[1]


def payloads(rom, original, writes, manifest):
    mapped, ranges = validate_manifest(rom, manifest, original, writes)
    for addr, m in mapped.items():
        profile = renderer_for_address(addr)
        if profile:
            key = f'0x{addr:06X}'
            yield addr, profile, row_bytes(rom, m, key), original[addr:addr + m['source_spans'][key]]
    for addr, size, owner, owner_size in final_text_spans(writes, len(rom)):
        profile = renderer_for_address(owner)
        if not profile or any(lo <= addr < hi or dst <= addr < end for lo, hi, dst, end in ranges):
            continue
        # A later writer may not leave half of an older glyph behind.
        if addr != owner or size != owner_size:
            singles = dict(single_bytes(rom[owner:owner + owner_size]))
            boundaries, cursor = {owner}, owner
            while cursor < owner + owner_size:
                cursor += 1 if cursor - owner in singles else 2
                boundaries.add(cursor)
            if addr not in boundaries or addr + size not in boundaries:
                raise ValueError(f'partial text owner splits glyph at {addr:#x}')
        yield addr, profile, rom[addr:addr + size], original[addr:addr + size]


def check(rom, original, writes, manifest):
    checked, errors = 0, []
    ranges = {0xB818B4, 0xB819B8, 0xB819DC}
    range_owners = set()
    layout = {int(key, 16): bytes.fromhex(value)
              for record in manifest if record.get('status') == 'relocated'
              for key, value in record.get('layout_controls', {}).items()}
    for addr, renderer, payload, native in payloads(rom, original, writes, manifest):
        checked += 1
        range_owners.update(a for a in ranges if a <= addr < a + 10)
        try:
            bad = halfwidth_violations(payload, renderer, native,
                                       added_controls=layout.get(addr, b''))
        except ValueError as exc:
            errors.append((hex(addr), renderer, str(exc)))
            continue
        if bad:
            errors.append((hex(addr), renderer, [(hex(off), hex(b)) for off, b in bad]))
    if range_owners:
        from part1_compact_ui_strings import loaded_codes, UNIT_INFO
        loaded = loaded_codes(rom, UNIT_INFO)
        for addr in sorted(range_owners):
            raw = rom[addr:addr + 10]
            singles = dict(single_bytes(raw))
            missing = []
            i = 0
            while i < len(raw):
                if i in singles:
                    i += 1
                    continue
                code = bytes(raw[i:i + 2])
                if code != b'\x81\x40' and code not in loaded:
                    missing.append(code.hex())
                i += 2
            if missing:
                errors.append((hex(addr), 'p1_b1311c', ['missing UNIT_INFO preload', missing]))
    return checked, errors


def main():
    ap = argparse.ArgumentParser()
    for key in ('rom', 'map', 'manifest'):
        ap.add_argument('--' + key, type=Path, required=True)
    args = ap.parse_args()
    verify_provenance(args.rom, args.map, args.manifest)
    count, errors = check(args.rom.read_bytes(), (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes(),
                          json.loads(args.map.read_text()), json.loads(args.manifest.read_text()))
    for row in errors:
        print('FAIL', *row)
    print(f'renderer payloads checked: {count}; unsafe halfwidth payloads: {len(errors)}')
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
