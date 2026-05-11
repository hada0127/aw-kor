#!/usr/bin/env python3
"""
ROM에서 텍스트 포인터를 업데이트합니다.

한글화로 인해 텍스트 길이가 변하면 포인터도 재계산하여 업데이트해야 합니다.

사용법:
    python update_pointers.py <rom_file> <pointer_table_csv> <output_rom>

예:
    python update_pointers.py output/game_wars_1_kor.gba data/pointers.csv output/game_wars_1_kor_final.gba
"""

import sys
import csv
import struct
from pathlib import Path


def load_pointer_table(csv_path):
    """
    포인터 테이블 CSV를 로드합니다.

    형식:
    pointer_address,text_address,size,game_wars_index
    0x100010,0x200000,2,0
    0x100014,0x200010,2,1
    """
    pointers = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pointer_addr = int(row['pointer_address'], 16) if 'pointer_address' in row else None
            text_addr = int(row['text_address'], 16) if 'text_address' in row else None
            pointers.append({
                'pointer_addr': pointer_addr,
                'text_addr': text_addr,
                'size': int(row.get('size', 4)),
                'index': int(row.get('game_wars_index', 0))
            })
    return pointers


def update_pointers_in_rom(rom_path, pointers, output_path):
    """
    ROM의 포인터들을 업데이트합니다.

    GBA는 little-endian 포인터를 사용합니다.
    """
    with open(rom_path, 'rb') as f:
        rom_data = bytearray(f.read())

    updated = 0
    for ptr_info in pointers:
        pointer_addr = ptr_info['pointer_addr']
        text_addr = ptr_info['text_addr']
        size = ptr_info['size']

        if pointer_addr is None or text_addr is None:
            continue

        # 포인터를 little-endian으로 인코딩
        if size == 4:
            pointer_bytes = struct.pack('<I', text_addr)
        elif size == 2:
            pointer_bytes = struct.pack('<H', text_addr)
        else:
            print(f"경고: 지원하지 않는 포인터 크기 {size}")
            continue

        # ROM에 삽입
        rom_data[pointer_addr:pointer_addr + size] = pointer_bytes
        updated += 1

    # 수정된 ROM 저장
    with open(output_path, 'wb') as f:
        f.write(rom_data)

    print(f"{updated}개 포인터가 업데이트되었습니다.")


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        return 1

    rom_path = sys.argv[1]
    csv_path = sys.argv[2]
    output_path = sys.argv[3]

    if not Path(rom_path).exists():
        print(f"오류: ROM 파일을 찾을 수 없습니다: {rom_path}")
        return 1

    if not Path(csv_path).exists():
        print(f"오류: 포인터 테이블을 찾을 수 없습니다: {csv_path}")
        return 1

    print(f"ROM 로드 중: {rom_path}")
    print(f"포인터 테이블 로드 중: {csv_path}")

    pointers = load_pointer_table(csv_path)
    print(f"포인터 항목: {len(pointers)}개")

    print("포인터 업데이트 중...")
    update_pointers_in_rom(rom_path, pointers, output_path)

    print(f"결과 저장됨: {output_path}")
    print("완료!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
