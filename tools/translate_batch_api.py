#!/usr/bin/env python3
"""
PHASE 4: Translation using Anthropic Batch API
Processes all remaining untranslated texts efficiently in batch mode.
Avoids rate limiting by using asynchronous batch processing.
"""

import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Dict
from anthropic import Anthropic

def load_all_texts() -> List[Dict]:
    """Load all extracted texts from ROM"""
    texts = []
    texts_file = Path('data/game_wars_found_texts.csv')

    with open(texts_file, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        for row in reader:
            texts.append(row)
    return texts

def load_translated_addresses() -> set:
    """Load addresses of already translated texts"""
    translated = set()
    output_file = Path('data/translation_for_import.csv')

    if output_file.exists():
        with open(output_file, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('korean') and row['korean'].strip():
                    translated.add(row.get('address', ''))
    return translated

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

def get_untranslated_texts() -> List[Dict]:
    """Get list of untranslated texts"""
    all_texts = load_all_texts()
    translated_addrs = load_translated_addresses()

    untranslated = [
        t for t in all_texts
        if t.get('address') and t['address'].strip() not in translated_addrs
    ]

    untranslated.sort(key=lambda x: int(x.get('char_count', 999)))
    return untranslated

def build_batch_requests(texts: List[Dict], batch_size: int = 20) -> List[Dict]:
    """Build batch request payloads for Anthropic Batch API"""
    requests = []
    request_id = 1

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        text_list = "\n".join([f"{j+1}. {t.get('text', '')}" for j, t in enumerate(batch)])

        prompt = f"""Translate these Japanese game texts to natural Korean.

Rules:
1. Keep translations SHORT - match or shorten original length
2. Use military/tactical terminology (대대, 보병, 기갑, etc.)
3. Prefer sino-Korean words for formal terms
4. Use natural Korean, NOT literal translation
5. Output ONLY: number|korean (one per line, no extra text)

Texts:
{text_list}

Translations (number|korean):"""

        request = {
            "custom_id": f"batch_{request_id}",
            "params": {
                "model": "claude-opus-4-7",
                "max_tokens": 4000,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
        }
        requests.append(request)
        request_id += 1

    return requests

def submit_batch_job(client: Anthropic, requests: List[Dict]) -> str:
    """Submit batch job and return batch ID"""

    # Write requests to JSONL file
    batch_input_file = Path('data/batch_input.jsonl')
    with open(batch_input_file, 'w', encoding='utf-8') as f:
        for req in requests:
            f.write(json.dumps(req) + '\n')

    # Upload file to Anthropic
    print(f"[Step 1] Uploading {len(requests)} batch requests...")
    with open(batch_input_file, 'rb') as f:
        file_response = client.beta.files.upload(
            file=('batch_input.jsonl', f, 'application/jsonl'),
        )
    file_id = file_response.id
    print(f"  [OK] File uploaded: {file_id}")

    # Submit batch job
    print(f"[Step 2] Submitting batch job...")
    batch_response = client.beta.messages.batches.create(
        model="claude-opus-4-7",
        requests=requests
    )
    batch_id = batch_response.id
    print(f"  [OK] Batch submitted: {batch_id}")
    print(f"  Processing requests: {batch_response.processing_count}")
    print(f"  Estimated time: {batch_response.request_counts.processing} requests remaining")

    return batch_id

def check_batch_status(client: Anthropic, batch_id: str) -> tuple:
    """Check batch job status and return (status, result_count)"""
    batch = client.beta.messages.batches.retrieve(batch_id)

    print(f"\n[Status] Batch {batch_id}")
    print(f"  State: {batch.processing_count > 0 and 'PROCESSING' or 'COMPLETED'}")
    print(f"  Succeeded: {batch.request_counts.succeeded}")
    print(f"  Processing: {batch.request_counts.processing}")
    print(f"  Failed: {batch.request_counts.failed}")

    return batch.processing_count > 0, batch.request_counts.succeeded

def process_batch_results(client: Anthropic, batch_id: str, texts: List[Dict]) -> int:
    """Process completed batch results and save translations"""

    batch = client.beta.messages.batches.retrieve(batch_id)

    if batch.request_counts.processing > 0:
        print(f"\n[WAIT] Batch still processing ({batch.request_counts.processing} remaining)")
        return 0

    print(f"\n[Step 3] Processing results...")

    # Load existing translations
    existing = load_existing_translations()

    # Build mapping from batch IDs to text batches
    batch_id_to_texts = {}
    for i in range(0, len(texts), 20):
        batch_num = (i // 20) + 1
        batch_id_str = f"batch_{batch_num}"
        batch_id_to_texts[batch_id_str] = texts[i:i+20]

    # Process results
    total_new = 0
    for result in client.beta.messages.batches.results(batch_id):
        custom_id = result.custom_id

        if result.result.type == "succeeded":
            batch_texts = batch_id_to_texts.get(custom_id, [])
            if not batch_texts:
                continue

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
                        if 1 <= num <= len(batch_texts) and korean:
                            text_obj = batch_texts[num - 1]
                            address = text_obj.get('address', '')
                            japanese = text_obj.get('text', '')

                            if address not in existing and korean:
                                existing[address] = {
                                    'address': address,
                                    'japanese': japanese,
                                    'korean': korean,
                                    'length': str(len(korean.encode('utf-8')))
                                }
                                total_new += 1
                    except ValueError:
                        continue
                except Exception:
                    continue

        elif result.result.type == "error":
            print(f"  [ERROR] {custom_id}: {result.result.error.message}")

    # Save all translations
    output_file = Path('data/translation_for_import.csv')
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['address', 'japanese', 'korean', 'length'])
        writer.writeheader()
        for addr in sorted(existing.keys()):
            writer.writerow(existing[addr])

    return total_new

def main():
    # API key will be loaded from environment or .env file by Anthropic SDK
    client = Anthropic()

    print("="*70)
    print("PHASE 4: Batch API Translation (Efficient Mode)")
    print("="*70)

    # Load untranslated texts
    print("\n[Step 0] Loading data...")
    untranslated = get_untranslated_texts()
    print(f"  Total untranslated: {len(untranslated):,}")

    if not untranslated:
        print("\n[OK] All texts already translated!")
        return 0

    # Build batch requests
    print(f"\n[Prep] Building batch requests...")
    requests = build_batch_requests(untranslated, batch_size=20)
    print(f"  Total batches: {len(requests)}")

    # Submit batch job
    batch_id = submit_batch_job(client, requests)

    # Monitor batch job
    print(f"\n[Step 3] Monitoring batch job {batch_id}...")
    print(f"  Check status with: python tools/check_batch_status.py {batch_id}")

    # Save batch ID for later reference
    with open(Path('data/batch_id.txt'), 'w') as f:
        f.write(batch_id)

    print(f"\n[NEXT] When batch completes, run:")
    print(f"  python tools/check_batch_status.py {batch_id}")

    return 0

if __name__ == '__main__':
    sys.exit(main())
