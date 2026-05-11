#!/usr/bin/env python3
"""
번역된 텍스트를 ROM에 삽입합니다.

사용법:
    python import_text.py <rom_file> <translation_csv> <tbl_file> <output_rom>

예:
    python import_text.py original/game_wars_1.gba data/game_wars_1_translation.csv tools/game_wars.tbl output/game_wars_1_kor.gba
"""

import sys
import csv
from pathlib import Path


def load_tbl(tbl_path):
    """
    .tbl 파일을 로드하여 문자-바이트 맵핑을 생성합니다.
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
                mapping[char] = byte_val
    return mapping


def load_translations(csv_path):
    """
    번역 CSV 파일을 로드합니다.

    형식:
    address,japanese,korean,length
    0x100000,あなたの名前,당신의 이름,6
    """
    translations = {}
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            addr = int(row['address'], 16) if row['address'].startswith('0x') else int(row['address'])
            translations[addr] = {
                'korean': row['korean'],
                'japanese': row.get('japanese', ''),
                'length': int(row.get('length', 0))
            }
    return translations


def text_to_bytes(text, tbl_mapping):
    """
    텍스트를 .tbl 맵핑을 사용하여 바이트로 변환합니다.
    """
    result = bytearray()
    for char in text:
        if char in tbl_mapping:
            result.append(tbl_mapping[char])
        else:
            # 맵핑되지 않은 문자는 스킵 또는 경고
            print(f"경고: 맵핑되지 않은 문자 '{char}'")
    return bytes(result)


def import_text_to_rom(rom_path, translations, tbl_mapping, output_path):
    """
    번역된 텍스트를 ROM에 삽입합니다.
    """
    with open(rom_path, 'rb') as f:
        rom_data = bytearray(f.read())

    inserted = 0
    for addr, trans_data in translations.items():
        korean_text = trans_data['korean']
        korean_bytes = text_to_bytes(korean_text, tbl_mapping)

        # 원래 텍스트 길이와 비교
        original_length = trans_data.get('length', 0)

        if len(korean_bytes) <= original_length:
            # 원본 길이보다 짧으면 패딩 추가
            korean_bytes = korean_bytes + b'\x00' * (original_length - len(korean_bytes))
        else:
            # 원본 길이보다 길면 경고
            print(f"경고: 주소 0x{addr:08X}에서 텍스트가 너무 깁니다 ({len(korean_bytes)} > {original_length})")
            # 원래 길이로 자르기
            korean_bytes = korean_bytes[:original_length]

        # ROM에 삽입
        rom_data[addr:addr + original_length] = korean_bytes
        inserted += 1

    # 수정된 ROM 저장
    with open(output_path, 'wb') as f:
        f.write(rom_data)

    print(f"{inserted}개 텍스트 항목이 ROM에 삽입되었습니다.")


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        return 1

    rom_path = sys.argv[1]
    csv_path = sys.argv[2]
    tbl_path = sys.argv[3]
    output_path = sys.argv[4]

    if not Path(rom_path).exists():
        print(f"오류: ROM 파일을 찾을 수 없습니다: {rom_path}")
        return 1

    if not Path(csv_path).exists():
        print(f"오류: 번역 CSV를 찾을 수 없습니다: {csv_path}")
        return 1

    if not Path(tbl_path).exists():
        print(f"오류: .tbl 파일을 찾을 수 없습니다: {tbl_path}")
        return 1

    print(f"ROM 로드 중: {rom_path}")
    print(f"번역 CSV 로드 중: {csv_path}")
    print(f".tbl 파일 로드 중: {tbl_path}")

    tbl_mapping = load_tbl(tbl_path)
    translations = load_translations(csv_path)

    print(f"번역 항목: {len(translations)}개")
    print("텍스트 삽입 중...")

    import_text_to_rom(rom_path, translations, tbl_mapping, output_path)

    print(f"결과 저장됨: {output_path}")
    print("완료!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
