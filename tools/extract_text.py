#!/usr/bin/env python3
"""
Game Wars GBA 게임에서 텍스트 데이터를 추출합니다.

사용법:
    python extract_text.py <rom_file> <tbl_file> <output_csv>

예:
    python extract_text.py original/game_wars_1.gba tools/game_wars.tbl data/game_wars_1_text.csv
"""

import sys
import csv
import struct
from pathlib import Path


def load_tbl(tbl_path):
    """
    .tbl 파일을 로드하여 바이트-문자 맵핑을 생성합니다.

    .tbl 파일 형식:
    00=あ
    01=い
    FF=끝
    """
    mapping = {}
    with open(tbl_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split('=', 1)
            if len(parts) == 2:
                byte_val = int(parts[0], 16)
                char = parts[1]
                mapping[byte_val] = char
    return mapping


def extract_text_from_rom(rom_path, tbl_mapping, min_length=2):
    """
    ROM에서 텍스트 문자열을 추출합니다.

    Args:
        rom_path: ROM 파일 경로
        tbl_mapping: 바이트-문자 맵핑
        min_length: 최소 문자열 길이 (이 길이 이상의 문자열만 추출)

    Returns:
        추출된 텍스트 리스트 [(address, text, bytes), ...]
    """
    texts = []

    with open(rom_path, 'rb') as f:
        rom_data = f.read()

    # ROM 전체를 스캔하며 텍스트 문자열 찾기
    current_text = []
    current_addr = 0
    start_addr = 0

    for i, byte_val in enumerate(rom_data):
        if byte_val in tbl_mapping:
            if not current_text:
                start_addr = i
            current_text.append(tbl_mapping[byte_val])
        else:
            # 현재 문자열이 끝남
            if len(current_text) >= min_length:
                text = ''.join(current_text)
                texts.append((start_addr, text, len(current_text)))
            current_text = []

    # 마지막 문자열 처리
    if len(current_text) >= min_length:
        text = ''.join(current_text)
        texts.append((start_addr, text, len(current_text)))

    return texts


def save_to_csv(texts, output_path):
    """추출된 텍스트를 CSV 파일로 저장합니다."""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['address', 'text', 'length', 'context', 'notes'])

        for addr, text, length in texts:
            writer.writerow([
                f'0x{addr:08X}',
                text,
                length,
                '',  # context (수동으로 채우기)
                ''   # notes (수동으로 채우기)
            ])


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        return 1

    rom_path = sys.argv[1]
    tbl_path = sys.argv[2]
    output_path = sys.argv[3]

    if not Path(rom_path).exists():
        print(f"오류: ROM 파일을 찾을 수 없습니다: {rom_path}")
        return 1

    if not Path(tbl_path).exists():
        print(f"오류: .tbl 파일을 찾을 수 없습니다: {tbl_path}")
        return 1

    print(f"ROM 로드 중: {rom_path}")
    print(f".tbl 파일 로드 중: {tbl_path}")

    # .tbl 맵핑 로드
    tbl_mapping = load_tbl(tbl_path)
    print(f"  → {len(tbl_mapping)}개 문자 맵핑 로드됨")

    # 텍스트 추출
    print("텍스트 추출 중...")
    texts = extract_text_from_rom(rom_path, tbl_mapping)
    print(f"  → {len(texts)}개 텍스트 문자열 발견")

    # CSV 저장
    print(f"결과 저장 중: {output_path}")
    save_to_csv(texts, output_path)

    print("완료!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
