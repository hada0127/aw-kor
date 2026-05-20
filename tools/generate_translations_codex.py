#!/usr/bin/env python3
"""
PHASE 4: Automated translation generation using Claude
Generates Korean translations for untranslated Game Wars text
"""

import csv
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

def categorize_texts(texts: List[Dict]) -> Dict[str, List[Dict]]:
    """Categorize texts by priority and type"""
    categories = {
        'ui_short': [],      # UI texts 3-10 chars
        'ui_medium': [],     # UI texts 11-30 chars
        'story': [],         # Story/dialogue
        'descriptive': [],   # Long descriptions
        'other': []
    }

    for text in texts:
        if not text.get('japanese'):
            continue

        char_count = int(text.get('char_count', 0))
        japanese = text.get('japanese', '')

        # Classify by content and length
        if any(keyword in japanese for keyword in ['ゲーム', 'スタート', 'コンティニュー', 'セーブ', 'ロード', '難易度']):
            # UI keywords
            if char_count <= 10:
                categories['ui_short'].append(text)
            else:
                categories['ui_medium'].append(text)
        elif any(keyword in japanese for keyword in ['。', '「', '」', '…']):
            # Story/dialogue (has Japanese punctuation)
            categories['story'].append(text)
        elif char_count > 30:
            categories['descriptive'].append(text)
        else:
            categories['other'].append(text)

    return categories

def get_untranslated(texts: List[Dict], translated_addresses: set) -> List[Dict]:
    """Filter to untranslated texts only"""
    return [t for t in texts if t.get('address') and t['address'].strip() not in translated_addresses]

def create_translation_batch(texts: List[Dict], batch_size: int = 50) -> List[List[Dict]]:
    """Create batches for translation"""
    batches = []
    for i in range(0, len(texts), batch_size):
        batches.append(texts[i:i+batch_size])
    return batches

def format_batch_for_translation(batch: List[Dict]) -> str:
    """Format a batch of texts for Claude to translate"""
    lines = ["Translate the following Game Wars Japanese texts to Korean. Keep translations concise (match or shorten original length when possible). Output CSV format: address,japanese,korean,length\n"]

    for item in batch:
        address = item.get('address', '').strip()
        japanese = item.get('japanese', '').replace('"', '""')
        char_count = item.get('char_count', '0')

        if address and japanese:
            lines.append(f'{address},"{japanese}"')

    return "\n".join(lines)

def parse_translation_output(output: str, original_batch: List[Dict]) -> List[Dict]:
    """Parse Claude's translation output"""
    translations = []

    try:
        # Skip header line and parse CSV output
        lines = output.strip().split('\n')
        for line in lines[1:]:  # Skip prompt line
            if not line.strip() or line.startswith('address'):
                continue

            # Parse CSV line
            parts = [p.strip() for p in line.split(',', 3)]
            if len(parts) >= 3:
                address = parts[0]
                korean = parts[2].strip('"')
                length = len(korean.encode('utf-8'))

                if address and korean:
                    translations.append({
                        'address': address,
                        'korean': korean,
                        'length': str(length)
                    })
    except Exception as e:
        print(f"  Warning: Parse error - {e}")

    return translations

def save_translations(translations: List[Dict], output_file: str = 'data/translation_for_import.csv'):
    """Append translations to translation file"""

    # Load existing translations
    existing = {}
    if Path(output_file).exists():
        with open(output_file, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('address'):
                    existing[row['address']] = row

    # Load original texts
    texts_by_addr = {}
    with open('data/game_wars_found_texts.csv', 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('address'):
                texts_by_addr[row['address']] = row

    # Update with new translations
    count_new = 0
    for trans in translations:
        addr = trans.get('address')
        if addr and addr not in existing:
            # Add original Japanese text
            if addr in texts_by_addr:
                existing[addr] = {
                    'address': addr,
                    'japanese': texts_by_addr[addr].get('japanese', ''),
                    'korean': trans.get('korean', ''),
                    'length': trans.get('length', '0')
                }
                count_new += 1

    # Write all translations
    if existing:
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['address', 'japanese', 'korean', 'length'])
            writer.writeheader()
            for addr in sorted(existing.keys()):
                writer.writerow(existing[addr])

    return count_new

def main():
    print("="*70)
    print("PHASE 4: Automated Translation Generation")
    print("="*70)

    # Load data
    print("\n[Step 1] Loading text data...")
    all_texts = load_all_texts()
    translated_addrs = load_translated_texts()

    print(f"  Total texts: {len(all_texts):,}")
    print(f"  Already translated: {len(translated_addrs):,}")

    # Get untranslated
    untranslated = get_untranslated(all_texts, translated_addrs)
    print(f"  Untranslated: {len(untranslated):,}")

    if not untranslated:
        print("\n[Status] All texts are already translated!")
        return 0

    # Categorize
    print("\n[Step 2] Categorizing texts by priority...")
    categories = categorize_texts(untranslated)

    for cat, texts_list in categories.items():
        print(f"  {cat}: {len(texts_list):,}")

    # Prioritize UI texts first (most important for gameplay)
    priority_texts = categories['ui_short'] + categories['ui_medium'] + categories['story'][:500]

    print(f"\n[Step 3] Preparing first batch for translation...")
    print(f"  Prioritized texts: {len(priority_texts):,}")

    # Create batches (smaller batches for better quality)
    batches = create_translation_batch(priority_texts[:100], batch_size=20)  # Start with 100
    print(f"  Batches: {len(batches)}")

    print(f"\n[Step 4] STATUS - Ready for translation")
    print(f"  Next step: Use Claude/Codex to translate batches")
    print(f"  Tool: Not directly callable - requires external translation service")
    print(f"  Manual process:")
    print(f"    1. Copy text batch to ChatGPT/Claude")
    print(f"    2. Paste translation output")
    print(f"    3. Save to data/new_translations_batch1.csv")
    print(f"    4. Run: python tools/merge_translations.py")

    # Show sample for first batch
    if batches:
        print(f"\n[Sample] First batch (showing first 5 items):")
        for item in batches[0][:5]:
            addr = item.get('address', '')
            jp = item.get('japanese', '')[:30]
            print(f"  {addr}: {jp}")

    print("\n" + "="*70)
    print("NOTE: Claude translation requires manual prompting")
    print("This tool prepares batches for human/Claude translation")
    print("="*70)

    return 0

if __name__ == '__main__':
    sys.exit(main())
