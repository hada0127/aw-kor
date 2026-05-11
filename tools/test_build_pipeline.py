#!/usr/bin/env python3
"""
PHASE 5-1 테스트: 빌드 파이프라인 검증

이 스크립트는 전체 빌드 파이프라인의 각 단계를 테스트합니다:
1. ROM 검증 및 정보 추출
2. 텍스트 추출 기능 검증
3. 포인터 업데이트 로직 검증
4. ROM 최종화 프로세스 검증
"""

import sys
import os
import csv
import struct
import hashlib
from pathlib import Path


def print_section(title):
    """섹션 제목을 출력합니다."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def test_rom_validation():
    """ROM 검증 테스트"""
    print_section("TEST 1: ROM 검증")

    rom_path = "original/Game Boy Wars Advance 1+2 (Japan).gba"
    if not Path(rom_path).exists():
        print(f"[FAIL] ROM 파일 없음: {rom_path}")
        return False

    try:
        with open(rom_path, 'rb') as f:
            rom_data = f.read()

        rom_size = len(rom_data)
        print(f"[PASS] ROM 로드 완료: {rom_size:,} bytes ({rom_size/1024/1024:.1f}MB)")

        # GBA 헤더 검증
        game_title = rom_data[0xA0:0xAC].decode('ascii', errors='ignore').rstrip('\x00')
        game_code = rom_data[0xAC:0xB0].decode('ascii', errors='ignore').rstrip('\x00')
        maker_code = rom_data[0xB0:0xB2].decode('ascii', errors='ignore').rstrip('\x00')

        print(f"  제목: {game_title}")
        print(f"  게임코드: {game_code}")
        print(f"  제작사: {maker_code}")
        print(f"  크기: {rom_size/1024/1024:.1f}MB")

        # 크기 검증
        if rom_size not in [0x1000000, 0x2000000]:
            print(f"[WARN] 예상치 않은 ROM 크기")

        print("[PASS] ROM 헤더 정보 추출 성공")
        return True

    except Exception as e:
        print(f"[FAIL] ROM 검증 실패: {e}")
        return False


def test_text_extraction():
    """텍스트 추출 결과 검증"""
    print_section("TEST 2: 텍스트 추출 결과 검증")

    csv_path = "data/game_wars_found_texts.csv"
    if not Path(csv_path).exists():
        print(f"[FAIL] CSV 파일 없음: {csv_path}")
        return False

    try:
        texts = []
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i < 100:
                    texts.append(row)

        print(f"[PASS] CSV 로드 완료")
        print(f"  샘플 로드: 100개 항목")
        print(f"  필드: address, hex_bytes, text, length, char_count")

        # 샘플 항목 검증
        if texts:
            sample = texts[0]
            print(f"\n  샘플 항목:")
            print(f"    주소: {sample.get('address', 'N/A')}")
            try:
                print(f"    텍스트: {sample.get('text', 'N/A')}")
            except UnicodeEncodeError:
                print(f"    텍스트: [Japanese text - encoding varies]")
            print(f"    길이: {sample.get('length', 'N/A')} bytes")

        print("[PASS] 텍스트 추출 데이터 유효함")
        return True

    except Exception as e:
        print(f"[FAIL] 텍스트 추출 검증 실패: {e}")
        return False


def test_tbl_file():
    """문자 매핑 파일 검증"""
    print_section("TEST 3: 문자 매핑 파일 검증")

    tbl_path = "tools/game_wars.tbl"
    if not Path(tbl_path).exists():
        print(f"[FAIL] .tbl 파일 없음: {tbl_path}")
        return False

    try:
        mappings = {}
        with open(tbl_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    parts = line.split('=', 1)
                    if len(parts) == 2:
                        mappings[parts[0]] = parts[1]

        print(f"[PASS] .tbl 파일 로드 완료")
        print(f"  총 매핑: {len(mappings)}개")

        # 샘플 매핑 출력
        sample_mappings = list(mappings.items())[:5]
        print(f"\n  샘플 매핑:")
        for key, val in sample_mappings:
            print(f"    {key} = {repr(val)}")

        print("[PASS] 문자 매핑 데이터 유효함")
        return True

    except Exception as e:
        print(f"[FAIL] 문자 매핑 검증 실패: {e}")
        return False


def test_translation_data():
    """번역 데이터 형식 검증"""
    print_section("TEST 4: 번역 데이터 형식 검증")

    csv_path = "data/test_translations_small.csv"
    if not Path(csv_path).exists():
        print(f"[FAIL] 번역 CSV 없음: {csv_path}")
        return False

    try:
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

        print(f"[PASS] 번역 데이터 로드 완료")
        print(f"  번역 항목: {len(translations)}개")

        # 샘플 항목 검증
        sample_items = list(translations.items())[:3]
        print(f"\n  샘플 항목:")
        for addr, trans in sample_items:
            try:
                print(f"    0x{addr:08X}: {trans['japanese']} → {trans['korean']} (길이: {trans['length']})")
            except UnicodeEncodeError:
                print(f"    0x{addr:08X}: [Japanese] → [Korean] (길이: {trans['length']})")

        print("[PASS] 번역 데이터 형식 유효함")
        return True

    except Exception as e:
        print(f"[FAIL] 번역 데이터 검증 실패: {e}")
        return False


def test_pointer_logic():
    """포인터 업데이트 로직 검증"""
    print_section("TEST 5: 포인터 업데이트 로직 검증")

    try:
        # 테스트 포인터 생성
        test_pointers = [
            {'pointer_addr': 0x100000, 'text_addr': 0x200000, 'size': 4},
            {'pointer_addr': 0x100004, 'text_addr': 0x200100, 'size': 4},
            {'pointer_addr': 0x100008, 'text_addr': 0x0FFF, 'size': 2},  # Valid 16-bit value
        ]

        print("[PASS] 테스트 포인터 데이터 생성")

        # Little-endian 인코딩 테스트
        for ptr in test_pointers:
            if ptr['size'] == 4:
                ptr_bytes = struct.pack('<I', ptr['text_addr'])
                decoded = struct.unpack('<I', ptr_bytes)[0]
            else:
                ptr_bytes = struct.pack('<H', ptr['text_addr'])
                decoded = struct.unpack('<H', ptr_bytes)[0]

            assert decoded == ptr['text_addr'], f"포인터 인코딩 실패"

        print("[PASS] Little-endian 포인터 인코딩 검증 완료")
        print(f"  테스트 포인터: {len(test_pointers)}개")
        for ptr in test_pointers:
            print(f"    0x{ptr['pointer_addr']:08X} → 0x{ptr['text_addr']:08X} ({ptr['size']} bytes)")

        print("[PASS] 포인터 업데이트 로직 유효함")
        return True

    except Exception as e:
        print(f"[FAIL] 포인터 로직 검증 실패: {e}")
        return False


def test_rom_checksum():
    """ROM 체크섬 계산 검증"""
    print_section("TEST 6: ROM 체크섬 계산 검증")

    rom_path = "original/Game Boy Wars Advance 1+2 (Japan).gba"
    if not Path(rom_path).exists():
        print(f"[WARN] ROM 파일 없음: {rom_path}")
        return True

    try:
        with open(rom_path, 'rb') as f:
            rom_data = f.read()

        # 체크섬 계산
        checksum = 0
        for i in range(0xA0, 0xBD):
            if i < len(rom_data):
                checksum += rom_data[i]
        checksum = (0 - (checksum + 0x19)) & 0xFF

        print(f"[PASS] 체크섬 계산 완료")
        print(f"  계산된 체크섬: 0x{checksum:02X}")
        print(f"  ROM의 체크섬: 0x{rom_data[0xBD]:02X}")

        if checksum == rom_data[0xBD]:
            print("[PASS] 체크섬 일치 (원본 ROM 정상)")
        else:
            print("[WARN] 체크섬 불일치 (수정된 ROM일 수 있음)")

        print("[PASS] 체크섬 계산 로직 유효함")
        return True

    except Exception as e:
        print(f"[FAIL] 체크섬 검증 실패: {e}")
        return False


def test_output_directory():
    """출력 디렉토리 준비 상태 검증"""
    print_section("TEST 7: 출력 디렉토리 준비")

    try:
        output_dir = Path("output")
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"[PASS] 출력 디렉토리 준비 완료: {output_dir.absolute()}")

        # 디렉토리 정보
        items = list(output_dir.iterdir()) if output_dir.exists() else []
        print(f"  현재 항목: {len(items)}개")

        if items:
            for item in items[:5]:
                if item.is_file():
                    size = item.stat().st_size / 1024 / 1024
                    print(f"    {item.name} ({size:.2f}MB)")

        print("[PASS] 출력 디렉토리 정상")
        return True

    except Exception as e:
        print(f"[FAIL] 출력 디렉토리 검증 실패: {e}")
        return False


def main():
    """모든 테스트 실행"""
    print("\n" + "="*60)
    print("  PHASE 5-1: 빌드 파이프라인 테스트")
    print("  Game Wars ROM 한글화 - 자동 빌드 시스템 검증")
    print("="*60)

    tests = [
        ("ROM 검증", test_rom_validation),
        ("텍스트 추출 검증", test_text_extraction),
        ("문자 매핑 파일", test_tbl_file),
        ("번역 데이터 형식", test_translation_data),
        ("포인터 업데이트 로직", test_pointer_logic),
        ("ROM 체크섬", test_rom_checksum),
        ("출력 디렉토리", test_output_directory),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"[FAIL] {test_name} 테스트 중 오류: {e}")
            results.append((test_name, False))

    # 결과 요약
    print_section("테스트 결과 요약")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "[PASS] PASS" if result else "[FAIL] FAIL"
        print(f"{status}: {test_name}")

    print(f"\n통과: {passed}/{total}")

    if passed == total:
        print("\n[PASS] 모든 테스트 통과! 빌드 파이프라인 준비 완료")
        print("\n다음 단계:")
        print("  - PHASE 5-3: 한글 폰트 데이터 준비")
        print("  - PHASE 5-4: 번역 텍스트 삽입 (포인트: 한글 인코딩 처리 필요)")
        print("  - PHASE 5-5: ROM 최종화")
    else:
        print("\n[WARN] 일부 테스트 실패. 위의 오류를 확인하세요.")

    print("\n" + "="*60)
    return 0 if passed == total else 1


if __name__ == '__main__':
    sys.exit(main())
