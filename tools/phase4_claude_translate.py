#!/usr/bin/env python3
"""
PHASE 4: Direct translation generation using Claude
Generates Korean translations for Game Wars text
"""

import csv
import json
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
        return []

    with open(texts_file, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        for row in reader:
            texts.append(row)

    return texts

def get_untranslated(texts: List[Dict], translated_addresses: set) -> List[Dict]:
    """Filter to untranslated texts only"""
    return [t for t in texts if t.get('address') and t['address'].strip() not in translated_addresses]

def generate_batch_translations(batch: List[Dict]) -> List[Dict]:
    """
    Placeholder for generating translations
    In real implementation, would call Claude API or use other service
    """

    # Sample manual translations for demonstration
    # This shows what the output format should be
    sample_translations = {
        # Common UI terms
        'ゲーム': '게임',
        'スタート': '시작',
        'ニューゲーム': '새 게임',
        'コンティニュー': '계속',
        'セーブ': '저장',
        'ロード': '로드',
        '終了': '종료',
        '難易度': '난이도',
        'かんたん': '쉬움',
        'ふつう': '보통',
        'むずかしい': '어려움',

        # Combat terms
        '攻撃': '공격',
        '防御': '방어',
        '移動': '이동',
        '技能': '기술',
        'アイテム': '아이템',
        'HP': 'HP',
        'MP': 'MP',
        '経験値': '경험치',
        'レベル': '레벨',
        'ダメージ': '데미지',

        # Unit names
        '歩兵': '보병',
        '戦車': '전차',
        '砲兵': '포병',
        'ロケット砲': '로켓포',
        '自走砲': '자주포',
        '軽戦車': '경전차',
        '重戦車': '중전차',
        '対空戦車': '대공전차',
    }

    translations = []
    for item in batch:
        address = item.get('address', '').strip()
        japanese = item.get('japanese', '').strip()

        if not address or not japanese:
            continue

        # Try exact match first
        korean = sample_translations.get(japanese)

        if korean:
            length = len(korean.encode('utf-8'))
            translations.append({
                'address': address,
                'japanese': japanese,
                'korean': korean,
                'length': str(length)
            })

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
    print("PHASE 4: Translation Generation (Batch Mode)")
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

    # Sort by length (shorter = easier)
    untranslated.sort(key=lambda x: int(x.get('char_count', 0)))

    # Process in batches
    batch_size = 50
    total_translated = 0

    print(f"\n[Step 2] Processing first batch ({batch_size} texts)...")
    batch = untranslated[:batch_size]

    print(f"  Generating translations...")
    translations = generate_batch_translations(batch)

    if translations:
        print(f"  Generated: {len(translations)} translations")
        count_new = save_translations(translations)
        total_translated += count_new
        print(f"  Saved: {count_new} new translations")

    # Summary
    print("\n" + "="*70)
    print(f"[Summary] Translation Processing Complete")
    print("="*70)
    print(f"  Total translated: {total_translated}")
    print(f"  Remaining: {len(untranslated) - total_translated:,}")

    if total_translated > 0:
        print(f"\n[Next] Rebuild ROM with new translations")
        return 0
    else:
        print(f"\n[Status] No new translations generated (demo mode)")
        return 1

if __name__ == '__main__':
    sys.exit(main())
