#!/usr/bin/env python3
"""
Complete translation of all Game Wars texts using Claude API
Processes untranslated texts in efficient batches with priority sorting
"""

import csv
import sys
import time
import os
from pathlib import Path
from anthropic import Anthropic
from typing import List, Dict, Tuple

class TranslationManager:
    def __init__(self):
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if api_key:
            self.client = Anthropic(api_key=api_key)
        else:
            self.client = Anthropic()
        self.batch_size = 20  # Reduced from 50 to reduce API call frequency
        self.checkpoint_interval = 500  # Save after N texts
        self.texts_file = Path('data/game_wars_found_texts.csv')
        self.output_file = Path('data/translation_for_import.csv')

    def load_all_texts(self) -> List[Dict]:
        """Load all extracted texts from ROM"""
        texts = []
        with open(self.texts_file, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                texts.append(row)
        return texts

    def load_translated_addresses(self) -> set:
        """Load addresses of already translated texts"""
        translated = set()
        if self.output_file.exists():
            with open(self.output_file, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('korean') and row['korean'].strip():
                        translated.add(row.get('address', ''))
        return translated

    def load_existing_translations(self) -> Dict:
        """Load all existing translations"""
        translations = {}
        if self.output_file.exists():
            with open(self.output_file, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('address'):
                        translations[row['address']] = row
        return translations

    def get_untranslated_texts(self) -> List[Dict]:
        """Get list of untranslated texts"""
        all_texts = self.load_all_texts()
        translated_addrs = self.load_translated_addresses()

        untranslated = [
            t for t in all_texts
            if t.get('address') and t['address'].strip() not in translated_addrs
        ]

        # Sort by character count (shorter first = easier to translate)
        untranslated.sort(key=lambda x: int(x.get('char_count', 999)))

        return untranslated

    def translate_batch(self, batch: List[Dict]) -> List[Tuple[str, str]]:
        """
        Translate a batch of texts using Claude
        Returns list of (japanese_original, korean_translation) tuples
        """
        if not batch:
            return []

        # Build prompt with context about Game Wars
        text_list = "\n".join([f"{i+1}. {t.get('text', '')}" for i, t in enumerate(batch)])

        prompt = f"""You are translating Game Wars, a turn-based tactical RPG for Game Boy Advance.

Translate these Japanese game texts to natural Korean. Follow these rules:
1. Keep translations SHORT - match or shorten original length (crucial for UI display)
2. Use military/tactical terminology (battalion, infantry, armor, etc.)
3. Prefer sino-Korean words for formal/military terms
4. Use natural Korean expressions, NOT literal word-for-word translation
5. Maintain consistency with existing translations
6. For unit names: use 대대 (battalion), 보병 (infantry), 기갑 (armor) etc.
7. Output ONLY the translations in format: number|korean (one per line, no extra text)

Texts to translate:
{text_list}

Provide translations (number|korean):"""

        import time
        max_retries = 15
        retry_count = 0
        response = None

        while retry_count < max_retries:
            try:
                response = self.client.messages.create(
                    model="claude-opus-4-7",
                    max_tokens=4000,
                    messages=[{"role": "user", "content": prompt}]
                )
                break
            except Exception as e:
                if "429" in str(e) or "rate_limit" in str(e).lower():
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = min(3 ** retry_count, 300)  # Exponential with longer cap
                        print(f"  Rate limit, waiting {wait_time}s (retry {retry_count}/{max_retries})...")
                        time.sleep(wait_time)
                        continue
                print(f"  Translation error: {e}")
                return []

        if not response:
            return []

        try:
            translations = []
            output_text = response.content[0].text

            for line in output_text.strip().split('\n'):
                line = line.strip()
                if not line or '|' not in line:
                    continue

                try:
                    parts = line.split('|', 1)
                    num_str = parts[0].strip()
                    korean = parts[1].strip()

                    try:
                        num = int(num_str)
                        if 1 <= num <= len(batch) and korean:
                            japanese = batch[num - 1].get('text', '')
                            translations.append((japanese, korean))
                    except ValueError:
                        continue

                except Exception:
                    continue

            return translations

        except Exception as e:
            print(f"  Parse error: {e}")
            return []

    def save_translations_batch(self, new_translations: List[Tuple[str, str, str, str]]) -> int:
        """
        Save new translations to file
        new_translations: list of (address, japanese, korean, length)
        """
        if not new_translations:
            return 0

        # Load existing
        existing = self.load_existing_translations()

        # Add new translations
        count_new = 0
        for address, japanese, korean, length in new_translations:
            if address not in existing:
                existing[address] = {
                    'address': address,
                    'japanese': japanese,
                    'korean': korean,
                    'length': length
                }
                count_new += 1

        # Write back
        with open(self.output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['address', 'japanese', 'korean', 'length'])
            writer.writeheader()
            for addr in sorted(existing.keys()):
                writer.writerow(existing[addr])

        return count_new

    def run(self):
        """Main translation loop"""
        print("="*70)
        print("PHASE 4: Complete Game Wars Translation")
        print("="*70)

        # Load data
        print("\n[Step 1] Loading texts...")
        untranslated = self.get_untranslated_texts()
        total = len(untranslated)

        print(f"  Total untranslated: {total:,}")
        print(f"  Batch size: {self.batch_size}")
        print(f"  Est. batches: {(total + self.batch_size - 1) // self.batch_size}")

        if total == 0:
            print("\n[OK] All texts already translated!")
            return 0

        # Process in batches
        print(f"\n[Step 2] Processing batches...")
        total_translated = 0
        failed_batches = 0

        for batch_start in range(0, total, self.batch_size):
            batch_end = min(batch_start + self.batch_size, total)
            batch = untranslated[batch_start:batch_end]
            batch_num = (batch_start // self.batch_size) + 1
            total_batches = (total + self.batch_size - 1) // self.batch_size

            progress = f"{batch_start + len(batch)}/{total}"
            percentage = 100 * (batch_start + len(batch)) / total

            print(f"\n  [Batch {batch_num}/{total_batches}] {progress} ({percentage:.1f}%)")
            print(f"    Translating {len(batch)} texts...")

            # Translate batch
            translations = self.translate_batch(batch)

            if not translations:
                print(f"    [FAIL] Failed")
                failed_batches += 1
                continue

            # Prepare data for saving
            save_data = []
            for japanese, korean in translations:
                # Find original text in batch
                for text_obj in batch:
                    if text_obj.get('text') == japanese:
                        address = text_obj.get('address', '')
                        length = str(len(korean.encode('utf-8')))
                        save_data.append((address, japanese, korean, length))
                        break

            # Save
            count_new = self.save_translations_batch(save_data)
            if count_new > 0:
                print(f"    [OK] Saved {count_new} translations")
                total_translated += count_new
            else:
                print(f"    ⚠️  Translations parsed but not saved (duplicates?)")

            # Aggressive delay between batches to respect strict rate limits
            print(f"    Batch delay: 10 seconds...")
            time.sleep(10)

        # Summary
        print("\n" + "="*70)
        print("Translation Complete")
        print("="*70)
        print(f"  Total translated: {total_translated:,}")
        print(f"  Failed batches: {failed_batches}")

        # Check final status
        translated_addrs = self.load_translated_addresses()
        remaining = len(untranslated) - total_translated
        percentage = 100 * (len(translated_addrs)) / 28347

        print(f"\n  Overall progress: {len(translated_addrs):,} / 28,347 ({percentage:.1f}%)")
        print(f"  Remaining: {remaining:,}")

        if remaining == 0:
            print("\n[OK] All texts translated! Ready for ROM building.")
            return 0
        else:
            print(f"\n[PROGRESS] More translations needed ({remaining:,} texts)")
            return 0

def main():
    manager = TranslationManager()
    return manager.run()

if __name__ == "__main__":
    sys.exit(main())
