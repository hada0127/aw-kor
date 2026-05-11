#!/usr/bin/env python3
"""
GBA ROM에서 포인터를 찾습니다.

포인터는 보통 4바이트 (little-endian)로 저장된 주소입니다.
특정 주소를 역참조하여 해당 주소를 가리키는 포인터를 찾습니다.

사용법:
    python find_pointers.py <rom_file> <target_address> [output_csv]

예:
    python find_pointers.py original/game_wars_1.gba 0x200000 data/pointers.csv
"""

import sys
import struct
import csv
from pathlib import Path


def find_pointers_to_address(rom_path, target_addr, ptr_size=4):
    """
    특정 주소를 가리키는 포인터를 찾습니다.

    Args:
        rom_path: ROM 파일 경로
        target_addr: 찾을 대상 주소 (정수 또는 16진수 문자열)
        ptr_size: 포인터 크기 (보통 4바이트)

    Returns:
        (포인터_주소, 값, 설명) 튜플의 리스트
    """

    # target_addr 변환
    if isinstance(target_addr, str):
        if target_addr.startswith('0x'):
            target_addr = int(target_addr, 16)
        else:
            target_addr = int(target_addr)

    with open(rom_path, 'rb') as f:
        rom_data = f.read()

    pointers = []
    rom_size = len(rom_data)

    print(f"대상 주소: 0x{target_addr:08X}")
    print(f"찾는 중... (이 작업은 시간이 걸릴 수 있습니다)")

    # Little-endian으로 대상 주소를 찾기
    target_bytes = struct.pack('<I', target_addr & 0xFFFFFFFF)

    # ROM 전체 검색
    for i in range(rom_size - ptr_size + 1):
        if rom_data[i:i+ptr_size] == target_bytes:
            # 포인터 발견
            ptr_addr = i
            ptr_val = struct.unpack('<I', rom_data[i:i+ptr_size])[0]
            pointers.append({
                'pointer_address': ptr_addr,
                'pointer_value': ptr_val,
                'target_address': target_addr,
            })

    return pointers


def find_all_pointer_patterns(rom_path, min_refs=2):
    """
    ROM에서 자주 나타나는 포인터 패턴을 찾습니다.

    Args:
        rom_path: ROM 파일 경로
        min_refs: 최소 참조 횟수

    Returns:
        (주소, 참조_횟수) 튜플의 리스트
    """

    with open(rom_path, 'rb') as f:
        rom_data = f.read()

    rom_size = len(rom_data)
    address_refs = {}

    print("포인터 패턴 검색 중...")
    print(f"ROM 크기: {rom_size:,} bytes")

    # 4바이트 단위로 읽고 유효한 ROM 주소인지 확인
    for i in range(0, rom_size - 3, 4):
        ptr_val = struct.unpack('<I', rom_data[i:i+4])[0]

        # 유효한 ROM 주소 범위인지 확인 (0x8000000 ~ 0x8FFFFFF for GBA)
        # 또는 ROM 내 주소 (0x0 ~ rom_size)
        if (0x08000000 <= ptr_val <= 0x08FFFFFF) or (0 <= ptr_val < rom_size):
            # 상대 주소로 정규화
            if ptr_val >= 0x08000000:
                normalized_addr = ptr_val - 0x08000000
            else:
                normalized_addr = ptr_val

            if 0 <= normalized_addr < rom_size:
                if normalized_addr not in address_refs:
                    address_refs[normalized_addr] = []
                address_refs[normalized_addr].append(i)

    # 참조가 많은 주소 찾기
    patterns = []
    for addr, refs in address_refs.items():
        if len(refs) >= min_refs:
            patterns.append({
                'target_address': addr,
                'reference_count': len(refs),
                'pointer_addresses': refs[:10],  # 처음 10개만 저장
            })

    # 참조 횟수 기준으로 정렬
    patterns.sort(key=lambda x: x['reference_count'], reverse=True)

    return patterns


def main():
    if len(sys.argv) < 3:
        print("사용법:")
        print(f"  {sys.argv[0]} <rom_file> <target_address> [output_csv]")
        print("\n예:")
        print(f"  {sys.argv[0]} original/game_wars_1.gba 0x200000")
        print(f"  {sys.argv[0]} original/game_wars_1.gba 0x200000 data/pointers.csv")
        print("\n참고:")
        print("  - target_address는 16진수 (0x로 시작) 또는 10진수")
        print("  - 포인터는 little-endian 4바이트 주소로 가정")
        return 1

    rom_path = sys.argv[1]
    target_addr = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else None

    if not Path(rom_path).exists():
        print(f"오류: ROM 파일을 찾을 수 없습니다: {rom_path}")
        return 1

    print("=" * 70)
    print("GBA ROM 포인터 분석")
    print("=" * 70 + "\n")

    # 포인터 검색
    pointers = find_pointers_to_address(rom_path, target_addr)

    print(f"\n발견된 포인터: {len(pointers)}개\n")

    if pointers:
        print(f"{'포인터_주소':<15} {'포인터_값':<15} {'설명':<30}")
        print("-" * 70)

        for i, ptr in enumerate(pointers[:20]):
            ptr_addr = ptr['pointer_address']
            ptr_val = ptr['pointer_value']
            print(f"0x{ptr_addr:08X}     0x{ptr_val:08X}     Text at 0x{ptr_val:08X}")

        if len(pointers) > 20:
            print(f"\n... 외 {len(pointers) - 20}개")

        # CSV 저장
        if output_path:
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['pointer_address', 'pointer_value', 'target_address', 'notes'])

                for ptr in pointers:
                    writer.writerow([
                        f"0x{ptr['pointer_address']:08X}",
                        f"0x{ptr['pointer_value']:08X}",
                        f"0x{ptr['target_address']:08X}",
                        ''
                    ])

            print(f"\n저장 완료: {output_path}")
    else:
        print("포인터를 찾을 수 없습니다.")
        print("다른 주소를 시도해보세요.")

    print("\n" + "=" * 70)
    return 0


if __name__ == '__main__':
    sys.exit(main())
