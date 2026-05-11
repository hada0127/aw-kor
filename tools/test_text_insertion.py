#!/usr/bin/env python3
"""
Test text insertion before full ROM modification
Validates translation data and tests insertion logic
"""

import sys
import csv
from pathlib import Path


def validate_translation_csv(csv_path: str) -> dict:
    """Validate translation CSV structure"""
    result = {
        'valid': False,
        'rows': 0,
        'columns': 0,
        'headers': [],
        'errors': [],
        'warnings': []
    }

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            result['headers'] = reader.fieldnames

            rows = list(reader)
            result['rows'] = len(rows)

            # Validate rows
            for i, row in enumerate(rows):
                # Check required fields
                for field in ['address', 'japanese', 'korean', 'length']:
                    if field not in row:
                        result['errors'].append(f"Row {i}: Missing field '{field}'")

                # Validate address format
                try:
                    addr = int(row.get('address', '0'), 16)
                    if addr < 0 or addr > 0x1000000:  # 16MB max
                        result['warnings'].append(f"Row {i}: Address out of range: {row['address']}")
                except:
                    result['errors'].append(f"Row {i}: Invalid address format: {row['address']}")

                # Check Korean text
                korean = row.get('korean', '')
                if not korean:
                    result['warnings'].append(f"Row {i}: Missing Korean translation")

                # Check length
                try:
                    length = int(row.get('length', '0'))
                    if length <= 0:
                        result['errors'].append(f"Row {i}: Invalid length: {length}")
                except:
                    result['errors'].append(f"Row {i}: Invalid length format")

        result['valid'] = len(result['errors']) == 0
        return result

    except Exception as e:
        result['errors'].append(f"File read error: {e}")
        return result


def analyze_translation_data(csv_path: str) -> None:
    """Analyze translation data statistics"""
    stats = {
        'total': 0,
        'total_korean_bytes': 0,
        'total_japanese_bytes': 0,
        'length_increases': 0,
        'length_decreases': 0,
        'length_same': 0,
        'sample_texts': []
    }

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            stats['total'] += 1

            japanese = row.get('japanese', '')
            korean = row.get('korean', '')
            target_length = int(row.get('length', '0'))

            jp_bytes = len(japanese.encode('shift_jis', errors='ignore'))
            kr_bytes = len(korean.encode('euc-kr', errors='ignore'))

            stats['total_japanese_bytes'] += jp_bytes
            stats['total_korean_bytes'] += kr_bytes

            if kr_bytes > jp_bytes:
                stats['length_increases'] += 1
            elif kr_bytes < jp_bytes:
                stats['length_decreases'] += 1
            else:
                stats['length_same'] += 1

            if len(stats['sample_texts']) < 5:
                stats['sample_texts'].append({
                    'japanese': japanese[:50],
                    'korean': korean[:50],
                    'jp_bytes': jp_bytes,
                    'kr_bytes': kr_bytes
                })

    return stats


def main():
    csv_path = 'data/translation_for_import.csv'

    print("="*60)
    print("PHASE 5-4: Text Insertion Validation")
    print("="*60)

    # Validate CSV
    print("\n[Step 1] Validating CSV structure...")
    validation = validate_translation_csv(csv_path)

    print(f"  CSV Headers: {validation['headers']}")
    print(f"  Total Rows: {validation['rows']}")
    print(f"  Valid: {validation['valid']}")

    if validation['errors']:
        print(f"\n  ERRORS ({len(validation['errors'])}):")
        for err in validation['errors'][:5]:
            print(f"    - {err}")

    if validation['warnings']:
        print(f"\n  WARNINGS ({len(validation['warnings'])}):")
        for warn in validation['warnings'][:5]:
            print(f"    - {warn}")

    # Analyze data
    print("\n[Step 2] Analyzing translation data...")
    stats = analyze_translation_data(csv_path)

    print(f"  Total translations: {stats['total']}")
    print(f"  Total Japanese bytes: {stats['total_japanese_bytes']:,}")
    print(f"  Total Korean bytes: {stats['total_korean_bytes']:,}")
    print(f"  Byte length increase: {stats['total_korean_bytes'] - stats['total_japanese_bytes']:,}")
    print(f"  Increase ratio: {stats['length_increases']} texts need more space")
    print(f"  Decrease ratio: {stats['length_decreases']} texts need less space")
    print(f"  Same length: {stats['length_same']} texts")

    print("\n[Sample Translations]")
    for i, sample in enumerate(stats['sample_texts'], 1):
        try:
            jp_text = sample['japanese']
            kr_text = sample['korean']
        except:
            jp_text = "[encoding varies]"
            kr_text = "[encoding varies]"
        print(f"  {i}. ({sample['jp_bytes']}B) -> ({sample['kr_bytes']}B)")

    # Readiness assessment
    print("\n" + "="*60)
    print("[Assessment] Ready for PHASE 5-4?")
    print("="*60)

    if validation['valid'] and stats['total'] > 0:
        print("\n[OK] Translation data is valid and ready for insertion")
        print(f"  - {stats['total']} translations available")
        print(f"  - {stats['length_increases']} will require space reallocation")
        print("\nNext: Run import_text_enhanced.py with this CSV")
        return 0
    else:
        print("\n[ERROR] Translation data has issues that need fixing")
        return 1


if __name__ == '__main__':
    sys.exit(main())
