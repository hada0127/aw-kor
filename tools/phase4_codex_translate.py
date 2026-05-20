#!/usr/bin/env python3
"""
PHASE 4: Translation generation using Codex CLI
Uses OpenAI Codex to generate Korean translations for Game Wars text
"""

import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import List, Dict

def load_translated_texts() -> set:
    """Load already translated text addresses"""
    translated = set()
    trans_file = Path('data/translation_for_import.csv')

    if trans_file.exists():
        with open(trans_file, 'r', encoding='utf-8', errors='ignore') as f:
            try:
                reader = csv.DictReader(f)
                for row in reader:
                    addr = row.get('address', '').strip() if row.get('address') else None
                    korean = row.get('korean', '').strip() if row.get('korean') else None
                    if addr and korean:
                        translated.add(addr)
            except Exception as e:
                print(f"Warning: Error reading translated texts: {e}")

    return translated

def load_all_texts() -> List[Dict]:
    """Load all extracted texts from ROM"""
    texts = []
    texts_file = Path('data/game_wars_found_texts.csv')

    if not texts_file.exists():
        print(f"ERROR: Text file not found: {texts_file}")
        return []

    with open(texts_file, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        for row in reader:
            texts.append(row)

    return texts

def get_untranslated(texts: List[Dict], translated_addresses: set) -> List[Dict]:
    """Filter to untranslated texts only"""
    return [t for t in texts if t.get('address') and t['address'].strip() not in translated_addresses]

def call_codex_translate(japanese_texts: List[str], batch_num: int = 1) -> str:
    """Call Codex CLI to translate texts"""

    # Format texts for translation
    text_lines = "\n".join([f"{i+1}. {text}" for i, text in enumerate(japanese_texts)])

    prompt = f"""한글로 번역하세요. Game Wars (군사 전술 게임).
형식: 번호|한글번역 (예: 1|공격)

텍스트:
{text_lines}

한글 번역 (번호|한글, 한 줄에 하나):"""

    try:
        codex_cmd = Path(r'C:\Users\taro1\AppData\Roaming\npm\codex.cmd')

        # Call Codex with simpler approach - just exec and capture output
        result = subprocess.run(
            [str(codex_cmd), 'exec'],
            input=prompt,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=120,  # 2분 타임아웃
            shell=False  # Don't use shell, pass as list
        )

        if result.stdout:
            # Extract just the translations part (skip system messages)
            lines = result.stdout.split('\n')
            translations = []
            for line in lines:
                if '|' in line and not line.startswith('[') and not line.startswith('Reading'):
                    translations.append(line.strip())

            if translations:
                return '\n'.join(translations)
            else:
                # If no pipes found, return original stdout
                return result.stdout

        return ""

    except subprocess.TimeoutExpired:
        print(f"  Codex timeout on batch {batch_num} (60s exceeded)")
        return ""
    except Exception as e:
        print(f"  Error calling Codex: {e}")
        return ""

def parse_codex_output(output: str, original_texts: List[Dict]) -> List[Dict]:
    """Parse Codex translation output"""
    translations = []

    lines = output.strip().split('\n')
    for i, line in enumerate(lines):
        if '|' not in line:
            continue

        try:
            parts = line.split('|', 1)
            korean = parts[1].strip()

            if i < len(original_texts) and korean:
                original = original_texts[i]
                length = len(korean.encode('utf-8'))

                translations.append({
                    'address': original.get('address', ''),
                    'text': original.get('text', ''),
                    'korean': korean,
                    'length': str(length)
                })

        except Exception as e:
            print(f"    Parse error on line {i}: {e}")
            continue

    return translations

def save_translations(translations: List[Dict]) -> int:
    """Append translations to CSV file"""

    output_file = Path('data/translation_for_import.csv')
    fieldnames = ['address', 'japanese', 'korean', 'length']

    # Load existing
    existing = {}
    if output_file.exists():
        try:
            with open(output_file, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row and row.get('address'):
                        addr = row['address'].strip()
                        # Clean row - keep only expected fields
                        clean_row = {
                            'address': addr,
                            'japanese': row.get('japanese', '').strip() if row.get('japanese') else '',
                            'korean': row.get('korean', '').strip() if row.get('korean') else '',
                            'length': row.get('length', '').strip() if row.get('length') else ''
                        }
                        existing[addr] = clean_row
        except Exception as e:
            print(f"  Warning: Error reading existing translations: {e}")

    # Add new translations
    count_new = 0
    for trans in translations:
        addr = trans.get('address', '').strip() if trans.get('address') else None
        if addr and addr not in existing:
            existing[addr] = {
                'address': addr,
                'japanese': trans.get('text', '').strip() if trans.get('text') else '',
                'korean': trans.get('korean', '').strip() if trans.get('korean') else '',
                'length': trans.get('length', '').strip() if trans.get('length') else ''
            }
            count_new += 1

    # Write all
    if existing:
        try:
            with open(output_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, restval='')
                writer.writeheader()
                for addr in sorted(existing.keys()):
                    writer.writerow(existing[addr])
        except Exception as e:
            print(f"  Error writing translations: {e}")
            return 0

    return count_new

def main():
    print("="*70)
    print("PHASE 4: Translation Generation using Codex CLI")
    print("="*70)

    # Load data
    print("\n[Step 1] Loading data...")
    all_texts = load_all_texts()
    translated_addrs = load_translated_texts()

    print(f"  Total texts: {len(all_texts):,}")
    print(f"  Translated: {len(translated_addrs):,}")

    untranslated = get_untranslated(all_texts, translated_addrs)
    print(f"  Untranslated: {len(untranslated):,}")

    if not untranslated:
        print("\n[Status] All texts already translated!")
        return 0

    # Sort by priority (shorter texts first = easier translation)
    print("\n[Step 2] Sorting by priority (shorter texts first)...")
    untranslated.sort(key=lambda x: int(x.get('char_count', 0)))

    # Process in small batches
    batch_size = 20  # Increased for efficiency
    total_translated = 0
    failed_batches = 0

    print(f"\n[Step 3] Processing batches (size={batch_size})...")
    total_batches = (len(untranslated) + batch_size - 1) // batch_size
    print(f"  Total batches: {total_batches}")

    for batch_num in range(0, len(untranslated), batch_size):  # Process ALL untranslated texts
        batch = untranslated[batch_num:batch_num + batch_size]
        batch_id = (batch_num // batch_size) + 1

        print(f"\n  [Batch {batch_id}] Processing {len(batch)} texts...")

        # Extract Japanese texts (from 'text' column)
        japanese_texts = [item.get('text', '') for item in batch]

        # Call Codex
        print(f"    Calling Codex...")
        codex_output = call_codex_translate(japanese_texts, batch_id)

        if not codex_output:
            print(f"    [WARN] Batch {batch_id} failed (no output)")
            failed_batches += 1
            continue


        # Parse output
        print(f"    Parsing output...")
        translations = parse_codex_output(codex_output, batch)

        if translations:
            print(f"    [OK] Generated {len(translations)} translations")
            count_new = save_translations(translations)
            total_translated += count_new
            print(f"    [OK] Saved {count_new} new translations")
        else:
            print(f"    [WARN] No translations parsed")
            failed_batches += 1

    # Summary
    print("\n" + "="*70)
    print(f"[Summary] Translation Generation Complete")
    print("="*70)
    print(f"  Batches processed: {(min(len(untranslated), 500) + batch_size - 1) // batch_size}")
    print(f"  Failed batches: {failed_batches}")
    print(f"  Total translated: {total_translated}")

    if total_translated > 0:
        print(f"\n[Next Step] Rebuild ROM with new translations")
        print(f"  python tools/execute_phase5_4.py")
        print(f"  python tools/execute_phase5_5.py")
        print(f"  python tools/phase6_basic_test.py")
        return 0
    else:
        print(f"\n[Error] No translations generated")
        return 1

if __name__ == '__main__':
    sys.exit(main())
