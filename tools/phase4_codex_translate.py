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
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('address') and row.get('korean'):
                    translated.add(row['address'].strip())

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

    prompt = f"""You are a professional Game Wars game translator. Translate these Japanese game texts to Korean.

Rules:
1. Keep translations concise - match or shorten the original length
2. Use appropriate gaming terminology
3. Maintain consistency with existing translations
4. Use natural Korean expressions, not literal translation
5. Output format: number|korean_translation

Texts to translate:
{text_lines}

Provide translations in the same format (number|korean_translation):"""

    try:
        # Use full path to codex
        codex_path = Path(r'C:\Users\taro1\AppData\Roaming\npm\codex.cmd')

        result = subprocess.run(
            [str(codex_path), 'exec', prompt],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=60,
            shell=True
        )

        if result.returncode == 0:
            return result.stdout
        else:
            print(f"  Codex error: {result.stderr}")
            return ""

    except subprocess.TimeoutExpired:
        print(f"  Codex timeout on batch {batch_num}")
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
                    'japanese': original.get('japanese', ''),
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

    # Load existing
    existing = {}
    if output_file.exists():
        with open(output_file, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('address'):
                    existing[row['address']] = row

    # Add new translations
    count_new = 0
    for trans in translations:
        addr = trans.get('address')
        if addr and addr not in existing:
            existing[addr] = trans
            count_new += 1

    # Write all
    if existing:
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['address', 'japanese', 'korean', 'length'])
            writer.writeheader()
            for addr in sorted(existing.keys()):
                writer.writerow(existing[addr])

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
    batch_size = 10
    total_translated = 0
    failed_batches = 0

    print(f"\n[Step 3] Processing batches (size={batch_size})...")
    print(f"  Total batches: {(len(untranslated) + batch_size - 1) // batch_size}")

    for batch_num in range(0, min(len(untranslated), 50), batch_size):  # Start with 50 texts
        batch = untranslated[batch_num:batch_num + batch_size]
        batch_id = (batch_num // batch_size) + 1

        print(f"\n  [Batch {batch_id}] Processing {len(batch)} texts...")

        # Extract Japanese texts
        japanese_texts = [item.get('japanese', '') for item in batch]

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
    print(f"  Batches processed: {(min(len(untranslated), 50) + batch_size - 1) // batch_size}")
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
