#!/usr/bin/env python3
"""
PHASE 5-4: Execute text insertion with safety checks
Inserts Korean translations into ROM with backup and validation
"""

import sys
import shutil
import struct
from pathlib import Path
import csv


def create_backup(rom_path: str) -> str:
    """Create a backup of the original ROM before modification"""
    rom_file = Path(rom_path)
    backup_path = rom_file.parent / f"{rom_file.stem}_backup{rom_file.suffix}"

    if not backup_path.exists():
        print(f"Creating backup: {backup_path}")
        shutil.copy2(rom_path, backup_path)
        print(f"  Size: {backup_path.stat().st_size:,} bytes")
    else:
        print(f"Backup already exists: {backup_path}")

    return str(backup_path)


def load_rom(rom_path: str) -> bytes:
    """Load ROM into memory"""
    with open(rom_path, 'rb') as f:
        return bytearray(f.read())


def save_rom(rom_data: bytearray, output_path: str) -> None:
    """Save modified ROM"""
    with open(output_path, 'wb') as f:
        f.write(rom_data)
    size_mb = len(rom_data) / 1024 / 1024
    print(f"Saved: {output_path} ({len(rom_data):,} bytes, {size_mb:.1f}MB)")


# Only insert into the game's text/data region. Addresses below this are code /
# critical data; extraction produced false-positive "text" there, and writing to
# them corrupts executable code -> ROM fails to boot (white screen).
SAFE_MIN_ADDR = 0x800000


def load_original_slots(found_csv: str = 'data/game_wars_found_texts.csv') -> dict:
    """Map address(int) -> (orig_byte_length, orig_hex_bytes) from the source extraction."""
    slots = {}
    with open(found_csv, 'r', encoding='utf-8', errors='ignore') as f:
        for row in csv.DictReader(f):
            a = (row.get('address') or '').strip()
            try:
                ai = int(a, 16)
            except (ValueError, TypeError):
                continue
            try:
                ln = int(row.get('length') or 0)
            except ValueError:
                ln = 0
            slots[ai] = (ln, (row.get('hex_bytes') or '').strip().lower())
    return slots


def insert_translations(rom_data: bytearray, csv_path: str) -> dict:
    """Insert Korean translations into ROM, safely bounded to original text slots."""
    stats = {
        'total_translations': 0,
        'successful_insertions': 0,
        'failed_insertions': 0,
        'skipped': 0,
        'skipped_code_region': 0,
        'skipped_not_found': 0,
        'skipped_too_long': 0,
        'errors': []
    }

    slots = load_original_slots()

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            stats['total_translations'] += 1

            try:
                korean_text = (row.get('korean') or '').strip()
                if not korean_text:
                    stats['skipped'] += 1
                    continue

                # Parse address
                try:
                    address = int(row['address'], 16)
                except (ValueError, TypeError):
                    stats['skipped_not_found'] += 1
                    continue

                # Must be a known extracted-text address (bounds the slot length)
                if address not in slots:
                    stats['skipped_not_found'] += 1
                    continue
                orig_len, _orig_hex = slots[address]
                if orig_len <= 0:
                    stats['skipped_not_found'] += 1
                    continue

                # Skip code / critical-data region (avoid corrupting boot)
                if address < SAFE_MIN_ADDR:
                    stats['skipped_code_region'] += 1
                    continue

                # Encode to EUC-KR and require it to fit the ORIGINAL slot exactly
                korean_bytes = korean_text.encode('euc-kr', errors='ignore')
                if len(korean_bytes) > orig_len:
                    stats['skipped_too_long'] += 1
                    continue
                if address + orig_len > len(rom_data):
                    stats['failed_insertions'] += 1
                    stats['errors'].append(f"Slot exceeds ROM at 0x{address:X}")
                    continue

                # Clear exactly the original slot, then write Korean (null-padded)
                for i in range(address, address + orig_len):
                    rom_data[i] = 0x00
                for i, byte in enumerate(korean_bytes):
                    rom_data[address + i] = byte

                stats['successful_insertions'] += 1

            except Exception as e:
                stats['failed_insertions'] += 1
                stats['errors'].append(f"Error at address {row.get('address', '?')}: {e}")

    return stats


def validate_rom(rom_data: bytearray) -> dict:
    """Validate ROM integrity"""
    result = {
        'valid': False,
        'size': len(rom_data),
        'header': '',
        'errors': []
    }

    # Check size (should be 16MB)
    if len(rom_data) != 16777216:
        result['errors'].append(f"Invalid ROM size: {len(rom_data):,} (expected 16,777,216)")

    # Check header
    try:
        # GBA header is at 0xA0-0xC0
        header_bytes = rom_data[0xA0:0xB0]
        result['header'] = header_bytes.decode('ascii', errors='ignore').strip()

        if 'GBWARS' not in result['header']:
            result['errors'].append(f"Invalid header: {result['header']}")
        else:
            result['valid'] = len(result['errors']) == 0

    except Exception as e:
        result['errors'].append(f"Header read error: {e}")

    return result


def main():
    print("="*60)
    print("PHASE 5-4: Execute Text Insertion")
    print("="*60)

    rom_path = 'original/Game Boy Wars Advance 1+2 (Japan).gba'
    output_path = 'output/game_wars_korean_v1.gba'
    csv_path = 'data/translation_for_import.csv'

    # Create output directory
    Path('output').mkdir(exist_ok=True)

    # Create backup
    print("\n[Step 1] Creating backup...")
    backup_path = create_backup(rom_path)

    # Load ROM
    print("\n[Step 2] Loading ROM...")
    rom_data = load_rom(rom_path)
    print(f"  Loaded: {len(rom_data):,} bytes")

    # Validate original ROM
    print("\n[Step 3] Validating original ROM...")
    original_validation = validate_rom(rom_data)
    print(f"  Header: {original_validation['header']}")
    print(f"  Valid: {original_validation['valid']}")

    if not original_validation['valid']:
        print("  ERROR: ROM validation failed")
        for err in original_validation['errors']:
            print(f"    - {err}")
        return 1

    # Insert translations
    print("\n[Step 4] Inserting Korean translations...")
    insert_stats = insert_translations(rom_data, csv_path)

    print(f"  Total translations: {insert_stats['total_translations']}")
    print(f"  Successful: {insert_stats['successful_insertions']}")
    print(f"  Failed: {insert_stats['failed_insertions']}")
    print(f"  Skipped (no korean): {insert_stats['skipped']}")
    print(f"  Skipped (code region <0x{SAFE_MIN_ADDR:X}): {insert_stats['skipped_code_region']}")
    print(f"  Skipped (addr not in source): {insert_stats['skipped_not_found']}")
    print(f"  Skipped (EUC-KR too long for slot): {insert_stats['skipped_too_long']}")

    if insert_stats['errors']:
        print(f"\n  First 5 errors:")
        for err in insert_stats['errors'][:5]:
            print(f"    - {err}")

    # Save modified ROM
    print("\n[Step 5] Saving modified ROM...")
    save_rom(rom_data, output_path)

    # Validate modified ROM
    print("\n[Step 6] Validating modified ROM...")
    modified_validation = validate_rom(rom_data)
    print(f"  Header: {modified_validation['header']}")
    print(f"  Size: {modified_validation['size']:,} bytes")
    print(f"  Valid: {modified_validation['valid']}")

    # Summary
    print("\n" + "="*60)
    print("PHASE 5-4: Summary")
    print("="*60)

    if modified_validation['valid'] and insert_stats['successful_insertions'] > 0:
        print(f"\n[SUCCESS] Korean translation inserted")
        print(f"  - {insert_stats['successful_insertions']} translations applied")
        print(f"  - Output: {output_path}")
        print(f"  - Backup: {backup_path}")
        print("\nNext: PHASE 5-5 (ROM finalization and checksum)")
        return 0
    else:
        print(f"\n[ERROR] Text insertion failed")
        print(f"  - Successful insertions: {insert_stats['successful_insertions']}")
        print(f"  - Failed insertions: {insert_stats['failed_insertions']}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
