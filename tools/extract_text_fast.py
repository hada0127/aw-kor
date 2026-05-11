#!/usr/bin/env python3
"""
ROM에서 연속된 텍스트 블록을 빠르게 추출합니다 (효율적 버전).
"""

import sys
import csv
from pathlib import Path

def extract_texts(rom_path, output_csv):
    """연속된 Shift-JIS 텍스트 블록 추출"""

    with open(rom_path, 'rb') as f:
        rom_data = f.read()

    texts = []
    i = 0
    total = len(rom_data)

    print(f"ROM 분석 중 ({total:,} bytes)...")
    last_percent = -1

    while i < total - 1:
        # 진행률 표시
        percent = (i * 100) // total
        if percent % 5 == 0 and percent != last_percent:
            print(f"  {percent}%", end='', flush=True)
            last_percent = percent

        b = rom_data[i]

        # Shift-JIS 첫 바이트 찾기
        if (0x81 <= b <= 0x9F) or (0xE0 <= b <= 0xEF):
            start = i
            text_data = bytearray()
            char_count = 0

            # 연속된 Shift-JIS 문자 추출
            while i < total - 1:
                b1 = rom_data[i]

                # Shift-JIS 첫 바이트
                if (0x81 <= b1 <= 0x9F) or (0xE0 <= b1 <= 0xEF):
                    b2 = rom_data[i + 1]
                    # Shift-JIS 둘째 바이트 확인
                    if (0x40 <= b2 <= 0x7E) or (0x80 <= b2 <= 0xFC):
                        text_data.append(b1)
                        text_data.append(b2)
                        i += 2
                        char_count += 1
                    else:
                        break
                else:
                    break

            # 충분한 문자가 있는 경우만 저장
            if char_count >= 3:  # 최소 3개 문자
                try:
                    decoded = text_data.decode('shift_jis')
                    texts.append({
                        'address': start,
                        'hex': text_data.hex(),
                        'text': decoded,
                        'length': len(text_data),
                        'chars': char_count,
                    })
                except:
                    pass
        else:
            i += 1

    print("\n완료!\n")
    return texts

def main():
    if len(sys.argv) < 2:
        print(f"사용법: {sys.argv[0]} <rom_file> [output_csv]")
        return 1

    rom_path = sys.argv[1]
    output_csv = sys.argv[2] if len(sys.argv) > 2 else "data/game_wars_found_texts.csv"

    if not Path(rom_path).exists():
        print(f"오류: {rom_path}")
        return 1

    print("=" * 60)
    print("일본어 텍스트 추출 (효율적 버전)")
    print("=" * 60 + "\n")

    texts = extract_texts(rom_path, output_csv)

    print(f"발견된 텍스트: {len(texts)}개\n")
    print(f"{'주소':<12} {'문자':<6} {'길이':<6} {'텍스트':<40}")
    print("-" * 70)

    for text in texts[:20]:
        addr = f"0x{text['address']:08X}"
        chars = text['chars']
        length = text['length']
        preview = text['text'][:37] if len(text['text']) <= 37 else text['text'][:34] + "..."
        print(f"{addr}  {chars:<6} {length:<6} {preview:<40}")

    if len(texts) > 20:
        print(f"\n... 외 {len(texts) - 20}개")

    # CSV 저장
    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['address', 'hex_bytes', 'text', 'length', 'char_count', 'context', 'notes'])
        writer.writeheader()
        for text in texts:
            writer.writerow({
                'address': f"0x{text['address']:08X}",
                'hex_bytes': text['hex'],
                'text': text['text'],
                'length': text['length'],
                'char_count': text['chars'],
                'context': '',
                'notes': '',
            })

    print(f"\n저장 완료: {output_csv}")
    print(f"총 {len(texts)}개 텍스트 항목")
    print("\n다음 단계:")
    print("  1. CSV 파일 검토")
    print("  2. game_wars.tbl 작성")
    print("  3. 포인터 분석")

    return 0

if __name__ == '__main__':
    sys.exit(main())
