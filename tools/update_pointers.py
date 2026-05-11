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


class PointerValidator:
    """포인터 및 메모리 범위 검증"""

    def __init__(self, rom_size):
        self.rom_size = rom_size
        self.pointer_ranges = []  # (start, end) 튜플 리스트
        self.text_ranges = []     # (start, end) 튜플 리스트
        self.errors = []
        self.warnings = []

    def validate_pointer_address(self, addr, size):
        """포인터 주소가 유효한지 검증"""
        if addr < 0:
            self.errors.append(f"포인터 주소가 음수: 0x{addr:08X}")
            return False
        if addr + size > self.rom_size:
            self.errors.append(f"포인터 주소가 ROM 범위 초과: 0x{addr:08X} + {size} > 0x{self.rom_size:08X}")
            return False

        # 기존 포인터 범위와 겹침 확인
        for existing_start, existing_end in self.pointer_ranges:
            if not (addr + size <= existing_start or addr >= existing_end):
                self.errors.append(f"포인터 범위 겹침 감지: 0x{addr:08X}-0x{addr+size:08X} 과 0x{existing_start:08X}-0x{existing_end:08X}")
                return False

        self.pointer_ranges.append((addr, addr + size))
        return True

    def validate_text_address(self, addr):
        """텍스트 주소가 유효한지 검증"""
        if addr < 0:
            self.errors.append(f"텍스트 주소가 음수: 0x{addr:08X}")
            return False
        if addr >= self.rom_size:
            self.errors.append(f"텍스트 주소가 ROM 범위 초과: 0x{addr:08X} > 0x{self.rom_size:08X}")
            return False
        return True

    def validate_pointer_size(self, size):
        """포인터 크기가 유효한지 검증"""
        if size not in [2, 4]:
            self.errors.append(f"지원하지 않는 포인터 크기: {size} (2 또는 4만 지원)")
            return False
        return True

    def check_for_overlaps(self):
        """모든 범위 겹침 확인"""
        # 포인터 범위 겹침 (이미 위에서 확인됨)
        # 텍스트 범위 겹침 (텍스트 길이 정보가 있을 때만 가능)
        pass

    def get_validation_report(self):
        """검증 결과 보고서 반환"""
        return {
            'valid': len(self.errors) == 0,
            'errors': self.errors,
            'warnings': self.warnings,
            'pointer_ranges': len(self.pointer_ranges),
            'text_ranges': len(self.text_ranges)
        }


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


def update_pointers_in_rom(rom_path, pointers, output_path, validator=None):
    """
    ROM의 포인터들을 업데이트합니다.

    GBA는 little-endian 포인터를 사용합니다.
    """
    with open(rom_path, 'rb') as f:
        rom_data = bytearray(f.read())

    updated = 0
    skipped = 0

    for ptr_info in pointers:
        pointer_addr = ptr_info['pointer_addr']
        text_addr = ptr_info['text_addr']
        size = ptr_info['size']

        if pointer_addr is None or text_addr is None:
            skipped += 1
            continue

        # 검증 실행 (validator가 있으면)
        if validator:
            if not validator.validate_pointer_address(pointer_addr, size):
                skipped += 1
                continue
            if not validator.validate_text_address(text_addr):
                skipped += 1
                continue
            if not validator.validate_pointer_size(size):
                skipped += 1
                continue

        # 포인터를 little-endian으로 인코딩
        try:
            if size == 4:
                pointer_bytes = struct.pack('<I', text_addr)
            elif size == 2:
                pointer_bytes = struct.pack('<H', text_addr)
            else:
                print(f"경고: 지원하지 않는 포인터 크기 {size}")
                skipped += 1
                continue

            # ROM에 삽입
            rom_data[pointer_addr:pointer_addr + size] = pointer_bytes
            updated += 1

        except struct.error as e:
            print(f"오류: 포인터 0x{pointer_addr:08X} 인코딩 실패: {e}")
            skipped += 1

    # 수정된 ROM 저장
    with open(output_path, 'wb') as f:
        f.write(rom_data)

    print(f"{updated}개 포인터가 업데이트되었습니다.")
    if skipped > 0:
        print(f"{skipped}개 포인터가 건너뛰어졌습니다.")


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
    rom_size = Path(rom_path).stat().st_size
    print(f"ROM 크기: {rom_size:,} bytes ({rom_size/1024/1024:.1f}MB)")

    print(f"포인터 테이블 로드 중: {csv_path}")

    pointers = load_pointer_table(csv_path)
    print(f"포인터 항목: {len(pointers)}개")

    # 검증기 초기화
    validator = PointerValidator(rom_size)

    print("\n[검증 시작]")
    print("포인터와 텍스트 주소를 검증 중...")

    valid_count = 0
    for i, ptr_info in enumerate(pointers):
        pointer_addr = ptr_info['pointer_addr']
        text_addr = ptr_info['text_addr']
        size = ptr_info['size']

        if pointer_addr is None or text_addr is None:
            continue

        # 각 포인터 검증
        is_valid = (
            validator.validate_pointer_address(pointer_addr, size) and
            validator.validate_text_address(text_addr) and
            validator.validate_pointer_size(size)
        )
        if is_valid:
            valid_count += 1

    report = validator.get_validation_report()

    print(f"\n[검증 결과]")
    print(f"유효한 포인터: {valid_count}/{len(pointers)}")

    if report['errors']:
        print(f"\n오류 ({len(report['errors'])}개):")
        for i, error in enumerate(report['errors'][:10], 1):
            print(f"  {i}. {error}")
        if len(report['errors']) > 10:
            print(f"  ... 외 {len(report['errors']) - 10}개")
        print("\n업데이트를 중단합니다.")
        return 1

    if report['warnings']:
        print(f"\n경고 ({len(report['warnings'])}개):")
        for warning in report['warnings'][:5]:
            print(f"  - {warning}")

    print("\n포인터 업데이트 중...")
    update_pointers_in_rom(rom_path, pointers, output_path, validator)

    print(f"결과 저장됨: {output_path}")
    print("완료!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
