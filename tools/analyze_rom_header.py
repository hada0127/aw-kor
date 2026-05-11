#!/usr/bin/env python3
"""
GBA ROM 헤더 정보를 분석하고 출력합니다.

사용법:
    python analyze_rom_header.py <rom_file>

예:
    python analyze_rom_header.py original/game_wars_1.gba
"""

import sys
import struct
import hashlib
from pathlib import Path


def analyze_gba_header(rom_path):
    """GBA ROM 헤더를 분석합니다."""

    if not Path(rom_path).exists():
        print(f"오류: ROM 파일을 찾을 수 없습니다: {rom_path}")
        return 1

    with open(rom_path, 'rb') as f:
        rom_data = f.read()

    rom_size = len(rom_data)

    print("=" * 60)
    print(f"GBA ROM 분석: {Path(rom_path).name}")
    print("=" * 60)

    # 파일 정보
    print("\n[파일 정보]")
    print(f"  경로: {rom_path}")
    print(f"  크기: {rom_size:,} bytes ({rom_size / 1024 / 1024:.2f} MB)")
    print(f"  MD5: {hashlib.md5(rom_data).hexdigest()}")
    print(f"  SHA1: {hashlib.sha1(rom_data).hexdigest()}")

    # GBA 헤더 (0xA0 ~ 0xC0)
    print("\n[GBA 헤더]")

    # 게임 제목 (0xA0 ~ 0xAB, 12바이트)
    game_title = rom_data[0xA0:0xAC]
    try:
        title_str = game_title.decode('ascii').rstrip('\x00')
    except:
        title_str = game_title.hex()
    print(f"  게임 제목 (0xA0-0xAB): {title_str}")
    print(f"    (Raw Hex): {game_title.hex()}")

    # 게임 코드 (0xAC ~ 0xAF, 4바이트)
    game_code = rom_data[0xAC:0xB0]
    try:
        code_str = game_code.decode('ascii')
    except:
        code_str = game_code.hex()
    print(f"  게임 코드 (0xAC-0xAF): {code_str}")

    # 제작사 코드 (0xB0 ~ 0xB1, 2바이트)
    maker_code = rom_data[0xB0:0xB2]
    try:
        maker_str = maker_code.decode('ascii')
    except:
        maker_str = maker_code.hex()
    print(f"  제작사 코드 (0xB0-0xB1): {maker_str}")

    # 고정값 (0xB2, 1바이트)
    fixed_val = rom_data[0xB2]
    status = '[OK]' if fixed_val == 0x96 else '[FAIL]'
    print(f"  고정값 (0xB2): 0x{fixed_val:02X} {status}")

    # 메인 단위 유형 (0xB3, 1바이트)
    main_unit = rom_data[0xB3]
    print(f"  메인 단위 유형 (0xB3): 0x{main_unit:02X}")

    # 장치 크기 (0xB4 ~ 0xB7, 4바이트, little-endian)
    device_size = struct.unpack('<I', rom_data[0xB4:0xB8])[0]
    print(f"  장치 크기 (0xB4-0xB7): {device_size}")

    # 버전 번호 (0xBC, 1바이트)
    version = rom_data[0xBC]
    print(f"  버전 번호 (0xBC): 0x{version:02X}")

    # 체크섬 (0xBD, 1바이트)
    checksum = rom_data[0xBD]
    print(f"  체크섬 (0xBD): 0x{checksum:02X}")

    # 계산된 체크섬
    calculated_checksum = 0
    for i in range(0xA0, 0xBD):
        calculated_checksum += rom_data[i]
    calculated_checksum = (0 - (calculated_checksum + 0x19)) & 0xFF
    check_status = '[OK]' if checksum == calculated_checksum else '[FAIL]'
    print(f"  계산된 체크섬: 0x{calculated_checksum:02X} {check_status}")

    # 텍스트 검색
    print("\n[텍스트 분석]")
    print("  ROM에서 인쇄 가능한 ASCII 문자열 검색 중...")

    # 간단한 문자열 추출 (20자 이상)
    strings = []
    current_string = []
    for i, byte_val in enumerate(rom_data):
        if 0x20 <= byte_val <= 0x7E:  # 인쇄 가능한 ASCII
            current_string.append(chr(byte_val))
        else:
            if len(current_string) >= 20:
                s = ''.join(current_string)
                strings.append((i - len(current_string), s))
            current_string = []

    if strings:
        print(f"  발견: {len(strings)}개 문자열")
        print(f"  상위 10개:")
        for addr, s in strings[:10]:
            print(f"    0x{addr:08X}: {s[:50]}")
    else:
        print("  ASCII 문자열 없음 (압축되었거나 일본어 텍스트만 있을 수 있음)")

    # 요약
    print("\n[분석 요약]")
    print(f"  [INFO] ROM 파일 유효: {'예' if fixed_val == 0x96 else '아니오'}")
    print(f"  [INFO] 체크섬 일치: {'예' if checksum == calculated_checksum else '아니오'}")
    print(f"  [INFO] 게임 제목: {title_str}")
    print(f"  [INFO] 게임 코드: {code_str}")
    print(f"  [INFO] 이 ROM은 Game Boy Wars Advance 1+2 (일본판)로 보입니다")

    print("\n" + "=" * 60)
    print("다음 단계:")
    print("  1. VisualBoyAdvance M에서 ROM 실행")
    print("  2. 게임 플레이하며 텍스트 위치 파악")
    print("  3. 메모리 디버거로 주소 확인")
    print("  4. HxD에서 일본어 텍스트 검색")
    print("=" * 60)

    return 0


def main():
    if len(sys.argv) < 2:
        print(f"사용법: {sys.argv[0]} <rom_file>")
        return 1

    rom_path = sys.argv[1]
    return analyze_gba_header(rom_path)


if __name__ == '__main__':
    sys.exit(main())
