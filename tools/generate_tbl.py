#!/usr/bin/env python3
"""
추출된 텍스트 데이터에서 .tbl 파일을 자동으로 생성합니다.

사용법:
    python generate_tbl.py <text_csv> [output_tbl]

예:
    python generate_tbl.py data/game_wars_found_texts.csv tools/game_wars_auto.tbl
"""

import sys
import csv
from collections import defaultdict
from pathlib import Path


def generate_tbl_from_csv(csv_path):
    """
    추출된 텍스트 CSV에서 바이트-문자 맵핑을 추출합니다.
    """

    if not Path(csv_path).exists():
        print(f"오류: CSV 파일을 찾을 수 없습니다: {csv_path}")
        return None

    # 바이트 -> 문자 매핑
    byte_to_char = {}
    byte_frequency = defaultdict(int)

    print(f"CSV 파일 읽는 중: {csv_path}")

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get('hex_bytes'):
                continue

            hex_str = row['hex_bytes']
            text = row.get('text', '')

            # 16진수 문자열을 바이트로 변환
            try:
                hex_bytes = bytes.fromhex(hex_str)
            except:
                continue

            # 1바이트 문자 (ASCII)
            for i, byte_val in enumerate(hex_bytes):
                if 0x20 <= byte_val <= 0x7E:  # 인쇄 가능한 ASCII
                    if byte_val not in byte_to_char:
                        byte_to_char[byte_val] = chr(byte_val)
                    byte_frequency[byte_val] += 1

            # 2바이트 일본어 문자 (Shift-JIS)
            # 대략적으로 매핑 (정확한 디코딩은 어려움)
            if len(text) > 0 and len(hex_bytes) > 0:
                for j, char in enumerate(text):
                    if ord(char) >= 0x3040:  # 일본어 문자
                        # 2바이트 단위로 매핑 시도
                        if j * 2 + 1 < len(hex_bytes):
                            byte_pair = hex_bytes[j*2:j*2+2]
                            if len(byte_pair) == 2:
                                # 2바이트 시퀀스 저장
                                key = f"2B_{byte_pair.hex()}"
                                if key not in byte_to_char:
                                    byte_to_char[key] = char
                                byte_frequency[key] += 1

    print(f"\n추출된 매핑: {len(byte_to_char)}개")
    print("\n상위 30개 바이트 (빈도순):")
    print(f"{'바이트':<15} {'문자':<10} {'빈도':<10}")
    print("-" * 35)

    # 빈도 기준으로 정렬
    sorted_bytes = sorted(byte_frequency.items(), key=lambda x: x[1], reverse=True)

    for i, (byte_val, freq) in enumerate(sorted_bytes[:30]):
        if isinstance(byte_val, str):
            byte_str = byte_val
            char = byte_to_char.get(byte_val, '?')
        else:
            byte_str = f"0x{byte_val:02X}"
            char = byte_to_char.get(byte_val, chr(byte_val) if 0x20 <= byte_val <= 0x7E else '?')

        try:
            print(f"{byte_str:<15} {char:<10} {freq:<10}")
        except UnicodeEncodeError:
            print(f"{byte_str:<15} [UNICODE] {freq:<10}")

    return byte_to_char


def save_tbl(byte_to_char, output_path):
    """
    바이트-문자 맵핑을 .tbl 파일로 저장합니다.
    """

    print(f"\n.tbl 파일 저장 중: {output_path}")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# Game Wars GBA - 자동 생성 문자 테이블\n")
        f.write("# 생성 일시: ROM 분석\n")
        f.write("# 참고: 수동으로 검토 및 수정이 필요합니다\n\n")

        # 1바이트 맵핑 (ASCII)
        f.write("# ASCII 및 단일 바이트\n")
        for byte_val in sorted([b for b in byte_to_char.keys() if isinstance(b, int)]):
            char = byte_to_char[byte_val]
            if char == '\n':
                f.write(f"{byte_val:02X}=\\n\n")
            elif char == '\t':
                f.write(f"{byte_val:02X}=\\t\n")
            elif char == '\0':
                f.write(f"{byte_val:02X}=\\0\n")
            else:
                f.write(f"{byte_val:02X}={char}\n")

        # 2바이트 맵핑 (일본어)
        f.write("\n# 2바이트 일본어 (Shift-JIS)\n")
        f.write("# 아래는 자동 생성되었으므로 검증이 필요합니다\n")
        # 문자열 키만 분리하여 정렬
        str_keys = sorted([k for k in byte_to_char.keys() if isinstance(k, str) and k.startswith('2B_')])
        for key in str_keys:
            char = byte_to_char[key]
            hex_part = key[3:]  # "2B_" 제거
            try:
                f.write(f"{hex_part}={char}\n")
            except:
                # 인코딩 오류 무시
                pass

        f.write("\n# 특수 문자\n")
        f.write("FF=\\end\n")

    print(f"저장 완료: {output_path}")


def main():
    if len(sys.argv) < 2:
        print("사용법:")
        print(f"  {sys.argv[0]} <text_csv> [output_tbl]")
        print("\n예:")
        print(f"  {sys.argv[0]} data/game_wars_found_texts.csv tools/game_wars_auto.tbl")
        return 1

    csv_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "tools/game_wars_auto.tbl"

    print("=" * 50)
    print(".tbl 파일 자동 생성")
    print("=" * 50 + "\n")

    byte_to_char = generate_tbl_from_csv(csv_path)

    if byte_to_char:
        save_tbl(byte_to_char, output_path)
        print("\n" + "=" * 50)
        print("주의: 자동 생성된 .tbl 파일은 검증이 필요합니다!")
        print("특히 일본어 문자의 매핑을 확인하세요.")
        print("=" * 50)
        return 0
    else:
        return 1


if __name__ == '__main__':
    sys.exit(main())
