#!/usr/bin/env python3
"""
Game Wars Translation - Interactive mode
Allows user to provide API key interactively
"""

import os
import sys
import csv
from pathlib import Path
from typing import List, Dict
from anthropic import Anthropic

def get_api_key_interactive() -> str:
    """Get API key from user"""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if api_key:
        print(f"[Found] ANTHROPIC_API_KEY in environment")
        return api_key

    print("\n[REQUIRED] ANTHROPIC_API_KEY not found in environment")
    print("Please enter your Anthropic API key (starts with 'sk-'):")
    api_key = input("> ").strip()

    if not api_key or not api_key.startswith('sk-'):
        print("[ERROR] Invalid API key format")
        sys.exit(1)

    # Set in environment for this session
    os.environ['ANTHROPIC_API_KEY'] = api_key
    return api_key

def load_all_texts() -> List[Dict]:
    """Load all texts"""
    texts = []
    with open('data/game_wars_found_texts.csv', 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        for row in reader:
            texts.append(row)
    return texts

def load_translated_addresses() -> set:
    """Load already translated addresses"""
    translated = set()
    output_file = Path('data/translation_for_import.csv')
    if output_file.exists():
        with open(output_file, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('korean') and row['korean'].strip():
                    translated.add(row.get('address', ''))
    return translated

def get_untranslated() -> List[Dict]:
    """Get untranslated texts"""
    all_texts = load_all_texts()
    translated = load_translated_addresses()

    untranslated = [
        t for t in all_texts
        if t.get('address') and t['address'].strip() not in translated
    ]

    untranslated.sort(key=lambda x: int(x.get('char_count', 999)))
    return untranslated

def translate_batch_simple(client: Anthropic, batch: List[Dict]) -> List[tuple]:
    """Simple batch translation"""
    if not batch:
        return []

    text_list = "\n".join([f"{i+1}. {t.get('text', '')}" for i, t in enumerate(batch)])

    prompt = f"""Translate to Korean (military game context).
Rules: 1) Keep SHORT  2) Military terms (대대,보병,기갑)  3) Natural Korean  4) Format: number|korean

Texts:
{text_list}

Output (number|korean):"""

    try:
        response = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )

        translations = []
        for line in response.content[0].text.strip().split('\n'):
            line = line.strip()
            if not line or '|' not in line:
                continue

            try:
                parts = line.split('|', 1)
                num = int(parts[0].strip())
                korean = parts[1].strip()

                if 1 <= num <= len(batch) and korean:
                    japanese = batch[num - 1].get('text', '')
                    translations.append((japanese, korean))
            except (ValueError, IndexError):
                continue

        return translations

    except Exception as e:
        print(f"  [ERROR] {e}")
        return []

def save_translations(new_translations: List[tuple], texts: List[Dict]):
    """Save translations"""
    existing = {}
    output_file = Path('data/translation_for_import.csv')

    if output_file.exists():
        with open(output_file, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('address'):
                    existing[row['address']] = row

    # Map translations back to addresses
    count_new = 0
    for japanese, korean in new_translations:
        for text_obj in texts:
            if text_obj.get('text') == japanese and text_obj['address'] not in existing:
                addr = text_obj['address']
                existing[addr] = {
                    'address': addr,
                    'japanese': japanese,
                    'korean': korean,
                    'length': str(len(korean.encode('utf-8')))
                }
                count_new += 1
                break

    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['address', 'japanese', 'korean', 'length'])
        writer.writeheader()
        for addr in sorted(existing.keys()):
            writer.writerow(existing[addr])

    return count_new

def main():
    print("="*70)
    print("Game Wars Translation - Interactive Mode")
    print("="*70)

    # Get API key
    api_key = get_api_key_interactive()
    client = Anthropic(api_key=api_key)

    # Load data
    print("\n[1] Loading texts...")
    untranslated = get_untranslated()
    print(f"  Untranslated: {len(untranslated):,} / 28,347")

    if not untranslated:
        print("\n[OK] All texts translated!")
        return 0

    # Translate in batches
    batch_size = 15
    total_batches = (len(untranslated) + batch_size - 1) // batch_size
    total_translated = 0

    print(f"\n[2] Processing {total_batches} batches...")

    for i in range(0, len(untranslated), batch_size):
        batch = untranslated[i:i+batch_size]
        batch_num = (i // batch_size) + 1

        progress = f"  [Batch {batch_num}/{total_batches}] {i+len(batch):,}/{len(untranslated):,} ({100*(i+len(batch))/len(untranslated):.1f}%)"
        print(progress)

        translations = translate_batch_simple(client, batch)
        if translations:
            count = save_translations(translations, batch)
            total_translated += count
            print(f"    [OK] {len(translations)} translated, {count} saved")
        else:
            print(f"    [SKIP] Failed")

    print(f"\n[DONE] Total: {total_translated:,} new translations")
    return 0

if __name__ == '__main__':
    sys.exit(main())
