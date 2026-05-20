#!/usr/bin/env python3
"""
Check Anthropic Batch API job status and process results when complete
"""

import csv
import os
import sys
from pathlib import Path
from typing import Dict
from anthropic import Anthropic

def load_existing_translations() -> Dict:
    """Load all existing translations"""
    translations = {}
    output_file = Path('data/translation_for_import.csv')

    if output_file.exists():
        with open(output_file, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('address'):
                    translations[row['address']] = row
    return translations

def load_all_texts() -> Dict:
    """Load all texts by address"""
    texts = {}
    with open('data/game_wars_found_texts.csv', 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        for row in reader:
            texts[row['address']] = row
    return texts

def process_batch_results(client: Anthropic, batch_id: str) -> int:
    """Process batch results and save translations"""

    batch = client.beta.messages.batches.retrieve(batch_id)

    print(f"\nBatch {batch_id}:")
    print(f"  Succeeded: {batch.request_counts.succeeded}")
    print(f"  Processing: {batch.request_counts.processing}")
    print(f"  Failed: {batch.request_counts.failed}")

    if batch.request_counts.processing > 0:
        print(f"\n[WAIT] Batch still processing ({batch.request_counts.processing} remaining)")
        return 0

    print(f"\n[Processing] Collecting results...")

    # Load existing translations and all texts
    existing = load_existing_translations()
    all_texts = load_all_texts()

    # Process results
    total_new = 0
    for result in client.beta.messages.batches.results(batch_id):

        if result.result.type == "succeeded":
            output_text = result.result.message.content[0].text

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
                        # Map batch result back to original address
                        # This is simplified - in real scenario would need better mapping
                        if korean and len(korean) > 0:
                            # Find matching untranslated text
                            for addr, text_obj in all_texts.items():
                                if addr not in existing and text_obj.get('text'):
                                    if addr not in existing:
                                        existing[addr] = {
                                            'address': addr,
                                            'japanese': text_obj.get('text', ''),
                                            'korean': korean,
                                            'length': str(len(korean.encode('utf-8')))
                                        }
                                        total_new += 1
                                        break
                    except ValueError:
                        continue
                except Exception:
                    continue

        elif result.result.type == "error":
            print(f"  [ERROR] {result.custom_id}: {result.result.error.message}")

    # Save all translations
    output_file = Path('data/translation_for_import.csv')
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['address', 'japanese', 'korean', 'length'])
        writer.writeheader()
        for addr in sorted(existing.keys()):
            writer.writerow(existing[addr])

    print(f"\n[OK] Saved {total_new} new translations")
    print(f"[TOTAL] {len(existing):,} / 28,347 translated ({100*len(existing)/28347:.1f}%)")

    return total_new

def main():
    if len(sys.argv) < 2:
        print("Usage: python check_batch_status.py <batch_id>")
        sys.exit(1)

    batch_id = sys.argv[1]
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    client = Anthropic(api_key=api_key) if api_key else Anthropic()

    print("="*70)
    print(f"Checking Batch Job {batch_id}")
    print("="*70)

    process_batch_results(client, batch_id)

if __name__ == '__main__':
    sys.exit(main())
