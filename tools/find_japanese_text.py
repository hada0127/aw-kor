#!/usr/bin/env python3
"""
GBA ROM에서 일본어 (Shift-JIS) 텍스트를 찾습니다.

사용법:
    python find_japanese_text.py <rom_file> [output_csv]

예:
    python find_japanese_text.py original/game_wars_1.gba data/found_texts.csv
"""

import sys
import csv
from pathlib import Path


# Shift-JIS 일본어 바이트 범위
SJIS_RANGES = [
    (0x81, 0x9F),  # 첫 바이트 범위 1
    (0xE0, 0xEF),  # 첫 바이트 범위 2
]

SJIS_SECOND_BYTE = set(range(0x40, 0x7F)) | set(range(0x80, 0xFC))


def is_sjis_start(byte_val):
    """Shift-JIS 문자의 첫 바이트인지 확인"""
    for start, end in SJIS_RANGES:
        if start <= byte_val <= end:
            return True
    return False


def is_sjis_second(byte_val):
    """Shift-JIS 문자의 두 번째 바이트인지 확인"""
    return byte_val in SJIS_SECOND_BYTE


def extract_japanese_text(rom_path, min_chars=2, sample_every=1):
    """
    ROM에서 일본어 텍스트 구간을 추출합니다 (최적화 버전).

    Args:
        rom_path: ROM 파일 경로
        min_chars: 최소 일본어 문자 개수 (단어로)
        sample_every: 몇 바이트마다 샘플링할지 (메모리 절약)

    Returns:
        (주소, 바이트 데이터, 길이) 튜플의 리스트
    """
    with open(rom_path, 'rb') as f:
        rom_data = f.read()

    texts = []
    i = 0
    total = len(rom_data)

    print("진행률: ", end='', flush=True)
    last_percent = -1

    while i < total - 1:
        # 진행률 표시
        percent = (i * 100) // total
        if percent % 10 == 0 and percent != last_percent:
            print(f"{percent}% ", end='', flush=True)
            last_percent = percent

        # Shift-JIS 문자 찾기
        if is_sjis_start(rom_data[i]):
            start_addr = i
            text_bytes = bytearray()
            char_count = 0

            # 연속된 일본어 문자 추출
            while i < total - 1:
                byte1 = rom_data[i]

                if is_sjis_start(byte1):
                    if i + 1 < total and is_sjis_second(rom_data[i + 1]):
                        # 2바이트 문자
                        text_bytes.append(byte1)
                        text_bytes.append(rom_data[i + 1])
                        i += 2
                        char_count += 1
                    else:
                        # 잘못된 Shift-JIS 시퀀스
                        break
                elif byte1 == 0x00 or byte1 > 0x7F:
                    # 널 바이트 또는 다른 범위
                    break
                else:
                    # ASCII (공백, 기호 등) - 계속 포함
                    text_bytes.append(byte1)
                    i += 1

            # 충분한 일본어 문자가 있는 경우만 추가
            if char_count >= min_chars:
                texts.append({
                    'address': start_addr,
                    'bytes': bytes(text_bytes),
                    'length': len(text_bytes),
                    'char_count': char_count,
                })
        else:
            i += 1

    print("100%")
    return texts


def try_decode_sjis(data):
    """Shift-JIS 바이트를 문자열로 변환 시도"""
    try:
        return data.decode('shift_jis')
    except:
        # 실패 시 16진수 표시
        return '[DECODE_ERROR]' + data.hex()


def find_japanese_text(rom_path):
    """ROM에서 일본어 텍스트를 찾고 분석"""

    if not Path(rom_path).exists():
        print(f"오류: ROM 파일을 찾을 수 없습니다: {rom_path}")
        return None

    print(f"ROM 분석 중: {Path(rom_path).name}")
    print("=" * 70)

    texts = extract_japanese_text(rom_path, min_chars=2)

    print(f"\n발견된 일본어 텍스트: {len(texts)}개\n")

    # 상위 30개 출력
    print(f"{'주소':<12} {'문자수':<6} {'크기':<6} {'텍스트 미리보기':<40}")
    print("-" * 70)

    for i, text in enumerate(texts[:30]):
        addr = text['address']
        chars = text['char_count']
        size = text['length']
        decoded = try_decode_sjis(text['bytes'])
        preview = decoded[:38] if len(decoded) <= 38 else decoded[:35] + "..."

        print(f"0x{addr:08X}  {chars:<6} {size:<6} {preview:<40}")

    if len(texts) > 30:
        print(f"\n... 외 {len(texts) - 30}개")

    print("\n" + "=" * 70)
    return texts


def save_to_csv(texts, output_path):
    """추출된 텍스트를 CSV로 저장"""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['address', 'hex_bytes', 'text', 'length', 'char_count', 'context', 'notes'])

        for text in texts:
            addr = f"0x{text['address']:08X}"
            hex_str = text['bytes'].hex()
            try:
                decoded = text['bytes'].decode('shift_jis')
            except:
                decoded = '[ERROR]'
            length = text['length']
            chars = text['char_count']

            writer.writerow([addr, hex_str, decoded, length, chars, '', ''])

    print(f"\n저장 완료: {output_path}")
    print(f"총 {len(texts)}개 텍스트 항목")


def main():
    if len(sys.argv) < 2:
        print("사용법:")
        print(f"  {sys.argv[0]} <rom_file> [output_csv]")
        print("\n예:")
        print(f"  {sys.argv[0]} original/game_wars_1.gba data/found_texts.csv")
        return 1

    rom_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "data/found_texts.csv"

    texts = find_japanese_text(rom_path)

    if texts:
        save_to_csv(texts, output_path)
        print("\n다음 단계:")
        print("  1. CSV 파일에서 텍스트 검토")
        print("  2. 게임 내 메뉴/대사와 비교하여 컨텍스트 확인")
        print("  3. ROM 분석 결과 정리")
        return 0
    else:
        print("일본어 텍스트를 찾을 수 없습니다")
        return 1


if __name__ == '__main__':
    sys.exit(main())
