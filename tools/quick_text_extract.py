#!/usr/bin/env python3
"""
ROM에서 연속된 Shift-JIS 바이트를 빠르게 찾습니다 (최소한의 처리).
"""

import sys
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        print(f"사용법: {sys.argv[0]} <rom_file>")
        return 1

    rom_path = sys.argv[1]

    if not Path(rom_path).exists():
        print(f"오류: {rom_path}")
        return 1

    with open(rom_path, 'rb') as f:
        rom_data = f.read()

    print(f"ROM 크기: {len(rom_data):,} bytes")
    print("Shift-JIS 바이트 패턴 검색 중...")

    # 간단한 통계
    sjis_ranges = []
    sjis_count = 0

    # 0x81-0x9F, 0xE0-0xEF는 Shift-JIS 첫 바이트
    for i in range(len(rom_data) - 1):
        b = rom_data[i]
        if (0x81 <= b <= 0x9F) or (0xE0 <= b <= 0xEF):
            sjis_count += 1
            if i < 1000:  # 처음 1000개 위치만 기록
                sjis_ranges.append(i)

    print(f"발견: {sjis_count}개 Shift-JIS 바이트")
    print(f"\n처음 10개 위치:")
    for addr in sjis_ranges[:10]:
        b1 = rom_data[addr]
        b2 = rom_data[addr+1] if addr+1 < len(rom_data) else 0
        print(f"  0x{addr:08X}: {b1:02X} {b2:02X}")

    return 0

if __name__ == '__main__':
    sys.exit(main())
