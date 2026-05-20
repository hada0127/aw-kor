#!/usr/bin/env python3
"""Claude-based batch translation for Game Wars Korean localization"""

import csv
import json
import sys
from pathlib import Path
from anthropic import Anthropic

def load_texts():
    """Load untranslated texts"""
    texts = []
    translated_addrs = set()

    # Load all texts
    with open('data/game_wars_found_texts.csv', 'r', encoding='utf-8', errors='ignore') as f:
        texts = list(csv.DictReader(f))

    # Load already translated
    try:
        with open('data/translation_for_import.csv', 'r', encoding='utf-8', errors='ignore') as f:
            for row in csv.DictReader(f):
                if row.get('address'):
                    translated_addrs.add(row['address'].strip())
    except:
        pass

    untranslated = [t for t in texts if t.get('address') and t['address'].strip() not in translated_addrs]
    return untranslated

def translate_batch(client, japanese_texts, batch_num=1):
    """Translate batch using Claude"""
    if not japanese_texts:
        return {}

    # Format for Claude
    text_list = "\n".join([f"{i+1}. {t.get('japanese', '')}" for i, t in enumerate(japanese_texts)])

    prompt = f"""Translate these Japanese game texts to natural Korean.

Rules:
1. Keep translations short (3-5 chars preferred)
2. Use military terminology in sino-Korean
3. Match or shorten original length
4. Output format: number|korean

Japanese texts:
{text_list}

Provide Korean translations in format (number|korean):"""

    try:
        response = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        result = {}
        for line in response.content[0].text.strip().split('\n'):
            if '|' in line:
                try:
                    parts = line.split('|', 1)
                    num = int(parts[0].strip())
                    korean = parts[1].strip()
                    if 1 <= num <= len(japanese_texts) and korean:
                        result[num-1] = korean
                except:
                    pass

        return result
    except Exception as e:
        print(f"Translation error: {e}")
        return {}

def save_translations(translations, original_texts):
    """Save translations to CSV"""
    output_file = Path('data/translation_for_import.csv')

    # Load existing
    existing = {}
    if output_file.exists():
        with open(output_file, 'r', encoding='utf-8', errors='ignore') as f:
            for row in csv.DictReader(f):
                if row.get('address'):
                    existing[row['address']] = row

    # Add new translations
    for idx, korean in translations.items():
        if idx < len(original_texts):
            orig = original_texts[idx]
            addr = orig.get('address', '')
            if addr and addr not in existing:
                existing[addr] = {
                    'address': addr,
                    'japanese': orig.get('japanese', ''),
                    'korean': korean,
                    'length': str(len(korean.encode('utf-8')))
                }

    # Write all
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['address', 'japanese', 'korean', 'length'])
        writer.writeheader()
        for row in existing.values():
            writer.writerow(row)

    return len([v for v in existing.values() if v.get('korean')]) - len([v for v in (existing or {}).values() if v.get('korean')])

def main():
    client = Anthropic()
    batch_size = 100

    print("Loading texts...")
    untranslated = load_texts()

    if not untranslated:
        print("All texts translated!")
        return

    print(f"Translating {len(untranslated)} texts in batches of {batch_size}...")

    for batch_num in range(0, len(untranslated), batch_size):
        batch = untranslated[batch_num:batch_num+batch_size]
        print(f"\n[Batch {batch_num//batch_size + 1}] Translating {len(batch)} texts...")

        translations = translate_batch(client, batch, batch_num//batch_size + 1)

        if translations:
            saved = save_translations(translations, batch)
            print(f"  ✅ {len(translations)} translations added")
        else:
            print(f"  ❌ No translations generated")

if __name__ == "__main__":
    main()
