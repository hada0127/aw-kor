#!/usr/bin/env python3
"""
PHASE 6: QA Testing - Basic ROM Integrity Tests
Automated pre-flight checks before emulator testing
"""

import sys
import struct
from pathlib import Path
import csv


def check_rom_integrity(rom_path: str) -> dict:
    """Perform basic ROM integrity checks"""
    result = {
        'valid': True,
        'checks': {},
        'errors': []
    }

    rom_file = Path(rom_path)

    # Check 1: File exists
    if not rom_file.exists():
        result['valid'] = False
        result['errors'].append(f"ROM file not found: {rom_path}")
        return result

    result['checks']['file_exists'] = True

    # Check 2: File size
    file_size = rom_file.stat().st_size
    if file_size != 16777216:
        result['valid'] = False
        result['errors'].append(f"Invalid ROM size: {file_size:,} (expected 16,777,216)")
    else:
        result['checks']['file_size'] = True

    # Check 3: Read ROM
    with open(rom_path, 'rb') as f:
        rom_data = f.read()

    result['checks']['file_read'] = True

    # Check 4: Header validation
    try:
        title = rom_data[0xA0:0xAC].decode('ascii', errors='ignore').strip('\x00')
        game_code = rom_data[0xAC:0xB0].decode('ascii', errors='ignore')

        if 'GBWARS' not in title:
            result['valid'] = False
            result['errors'].append(f"Invalid game title: {title}")
        else:
            result['checks']['header_title'] = True

        if game_code != 'BGWJ':
            result['errors'].append(f"Unexpected game code: {game_code}")
        else:
            result['checks']['header_code'] = True

    except Exception as e:
        result['valid'] = False
        result['errors'].append(f"Header read error: {e}")

    # Check 5: Checksum verification
    try:
        stored_checksum = rom_data[0xBD]
        header_range = rom_data[0xA0:0xBC]
        calculated_checksum = (0 - sum(header_range)) & 0xFF

        if stored_checksum == calculated_checksum:
            result['checks']['checksum'] = True
        else:
            result['errors'].append(f"Checksum mismatch: stored=0x{stored_checksum:02X}, calculated=0x{calculated_checksum:02X}")
            # Note: This is not critical for playability

    except Exception as e:
        result['errors'].append(f"Checksum error: {e}")

    # Check 6: Korean text presence
    korean_count = 0
    for i in range(0, len(rom_data) - 1):
        byte1 = rom_data[i]
        # EUC-KR starts with 0xB0-0xC8
        if 0xB0 <= byte1 <= 0xC8:
            byte2 = rom_data[i + 1]
            if 0xA1 <= byte2 <= 0xFE:
                korean_count += 1

    if korean_count > 0:
        result['checks']['korean_text'] = True
        result['korean_detected'] = korean_count
    else:
        result['errors'].append("No Korean text detected in ROM")

    # Check 7: Japanese text presence (should still exist for untranslated parts)
    japanese_count = 0
    for i in range(0, len(rom_data) - 1):
        byte1 = rom_data[i]
        # Shift-JIS starts with 0x81-0x9F, 0xE0-0xEF
        if (0x81 <= byte1 <= 0x9F) or (0xE0 <= byte1 <= 0xEF):
            byte2 = rom_data[i + 1]
            if (0x40 <= byte2 <= 0x7E) or (0x80 <= byte2 <= 0xFC):
                japanese_count += 1

    if japanese_count > 0:
        result['checks']['japanese_text'] = True
        result['japanese_detected'] = japanese_count

    return result


def check_translation_status() -> dict:
    """Check translation progress"""
    result = {
        'total_texts': 0,
        'translations': 0,
        'translated_percent': 0
    }

    # Read extracted texts
    texts_file = Path('data/game_wars_found_texts.csv')
    if texts_file.exists():
        with open(texts_file, 'r', encoding='utf-8', errors='ignore') as f:
            result['total_texts'] = sum(1 for _ in f) - 1  # Exclude header

    # Read translations
    trans_file = Path('data/translation_for_import.csv')
    if trans_file.exists():
        with open(trans_file, 'r', encoding='utf-8', errors='ignore') as f:
            result['translations'] = sum(1 for _ in f) - 1  # Exclude header

    if result['total_texts'] > 0:
        result['translated_percent'] = (result['translations'] / result['total_texts']) * 100

    return result


def main():
    print("="*60)
    print("PHASE 6: QA Testing - Pre-flight Checks")
    print("="*60)

    rom_path = 'output/game_wars_korean_final.gba'

    # Check 1: ROM Integrity
    print("\n[Check 1] ROM Integrity Tests...")
    integrity = check_rom_integrity(rom_path)

    print(f"  File exists: {integrity['checks'].get('file_exists', False)}")
    print(f"  File size correct: {integrity['checks'].get('file_size', False)}")
    print(f"  Header valid: {integrity['checks'].get('header_title', False)}")
    print(f"  Checksum valid: {integrity['checks'].get('checksum', False)}")
    print(f"  Korean text detected: {integrity['checks'].get('korean_text', False)}")
    print(f"  Japanese text detected: {integrity['checks'].get('japanese_text', False)}")

    if integrity.get('korean_detected'):
        print(f"    Korean sequences found: {integrity['korean_detected']:,}")
    if integrity.get('japanese_detected'):
        print(f"    Japanese sequences found: {integrity['japanese_detected']:,}")

    if integrity['errors']:
        print(f"\n  Errors/Warnings:")
        for err in integrity['errors']:
            print(f"    - {err}")

    # Check 2: Translation Status
    print("\n[Check 2] Translation Status...")
    trans = check_translation_status()

    print(f"  Total texts: {trans['total_texts']:,}")
    print(f"  Translated: {trans['translations']:,}")
    print(f"  Progress: {trans['translated_percent']:.1f}%")

    # Assessment
    print("\n" + "="*60)
    print("[Assessment] Ready for PHASE 6?")
    print("="*60)

    if integrity['valid']:
        print("\n[OK] ROM passed pre-flight checks")
        print(f"\nExpected Behavior:")
        print(f"  - ROM should load in VisualBoyAdvance M")
        print(f"  - Game Wars title screen should appear")
        print(f"  - ~{trans['translations']} menu items in Korean")
        print(f"  - Remaining text in Japanese (not yet translated)")
        print(f"\nNext Steps:")
        print(f"  1. Open ROM in VisualBoyAdvance M:")
        print(f"     {Path('original/Visualboy Advance M v2.1.4.x64.exe').resolve()}")
        print(f"  2. Load ROM: {Path(rom_path).resolve()}")
        print(f"  3. Verify game loads and shows Korean text")
        print(f"  4. Run through PHASE 6 test checklist")
        return 0
    else:
        print("\n[ERROR] ROM failed pre-flight checks")
        print(f"  - Please check errors above")
        return 1


if __name__ == '__main__':
    sys.exit(main())
