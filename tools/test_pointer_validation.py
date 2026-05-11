#!/usr/bin/env python3
"""
PHASE 5-2 테스트: 포인터 검증 로직

포인터 업데이트 시스템의 자동 검증 기능을 테스트합니다.
"""

import sys
import struct
from pathlib import Path

# update_pointers.py에서 PointerValidator 클래스 임포트
sys.path.insert(0, str(Path(__file__).parent))
from update_pointers import PointerValidator


def test_valid_pointers():
    """유효한 포인터 검증 테스트"""
    print("\n[TEST 1] 유효한 포인터 검증")
    print("-" * 50)

    rom_size = 0x1000000  # 16MB
    validator = PointerValidator(rom_size)

    test_cases = [
        (0x100000, 0x200000, 4, True, "정상 4바이트 포인터"),
        (0x100004, 0x200100, 4, True, "정상 4바이트 포인터 (다른 주소)"),
        (0x100008, 0x2000, 2, True, "정상 2바이트 포인터"),
    ]

    passed = 0
    for pointer_addr, text_addr, size, expected, description in test_cases:
        result = (
            validator.validate_pointer_address(pointer_addr, size) and
            validator.validate_text_address(text_addr) and
            validator.validate_pointer_size(size)
        )
        status = "PASS" if result == expected else "FAIL"
        print(f"  [{status}] {description}")
        print(f"        -> 포인터: 0x{pointer_addr:08X}, 텍스트: 0x{text_addr:08X}, 크기: {size}")
        if result == expected:
            passed += 1

    return passed == len(test_cases)


def test_out_of_bounds():
    """범위 초과 포인터 검증 테스트"""
    print("\n[TEST 2] ROM 범위 초과 감지")
    print("-" * 50)

    rom_size = 0x1000000  # 16MB
    validator = PointerValidator(rom_size)

    test_cases = [
        (0xFFFFFE, 0x200000, 4, False, "포인터가 ROM 범위 초과"),
        (0x100000, 0x1000000, 4, False, "텍스트 주소가 ROM 경계"),
        (-1, 0x200000, 4, False, "음수 포인터 주소"),
        (0x100000, -1, 4, False, "음수 텍스트 주소"),
    ]

    passed = 0
    for pointer_addr, text_addr, size, expected, description in test_cases:
        validator_test = PointerValidator(rom_size)

        # pointer_addr이 음수인 경우 validate_pointer_address가 False 반환
        if pointer_addr < 0:
            result = not validator_test.validate_pointer_address(pointer_addr, size)
        # text_addr이 음수인 경우 validate_text_address가 False 반환
        elif text_addr < 0:
            result = not validator_test.validate_text_address(text_addr)
        else:
            result = (
                not validator_test.validate_pointer_address(pointer_addr, size) or
                not validator_test.validate_text_address(text_addr)
            )

        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {description}")
        print(f"        -> 포인터: 0x{pointer_addr:08X}, 텍스트: 0x{text_addr:08X}")
        if result:
            passed += 1

    return passed == len(test_cases)


def test_pointer_overlap():
    """포인터 범위 겹침 감지 테스트"""
    print("\n[TEST 3] 포인터 범위 겹침 감지")
    print("-" * 50)

    rom_size = 0x1000000
    validator = PointerValidator(rom_size)

    # 첫 번째 포인터 추가
    result1 = validator.validate_pointer_address(0x100000, 4)
    print(f"  [PASS] 첫 번째 포인터 추가 (0x100000-0x100003)")

    # 겹치는 포인터 추가 시도
    result2 = validator.validate_pointer_address(0x100002, 4)
    status = "PASS" if not result2 else "FAIL"
    print(f"  [{status}] 겹치는 포인터 감지 (0x100002-0x100005)")

    # 인접한 포인터 추가
    result3 = validator.validate_pointer_address(0x100004, 4)
    print(f"  [PASS] 인접한 포인터 추가 (0x100004-0x100007)")

    return result1 and (not result2) and result3


def test_pointer_size_validation():
    """포인터 크기 검증 테스트"""
    print("\n[TEST 4] 포인터 크기 검증")
    print("-" * 50)

    rom_size = 0x1000000
    validator = PointerValidator(rom_size)

    test_cases = [
        (2, True, "2바이트 포인터 (유효)"),
        (4, True, "4바이트 포인터 (유효)"),
        (1, False, "1바이트 포인터 (무효)"),
        (8, False, "8바이트 포인터 (무효)"),
        (3, False, "3바이트 포인터 (무효)"),
    ]

    passed = 0
    for size, expected, description in test_cases:
        result = validator.validate_pointer_size(size)
        status = "PASS" if result == expected else "FAIL"
        print(f"  [{status}] {description}")
        if result == expected:
            passed += 1

    return passed == len(test_cases)


def test_validation_report():
    """검증 보고서 생성 테스트"""
    print("\n[TEST 5] 검증 보고서 생성")
    print("-" * 50)

    rom_size = 0x1000000
    validator = PointerValidator(rom_size)

    # 유효한 포인터 몇 개 추가
    validator.validate_pointer_address(0x100000, 4)
    validator.validate_text_address(0x200000)
    validator.validate_pointer_size(4)

    report = validator.get_validation_report()

    print(f"  검증 상태: {'유효' if report['valid'] else '무효'}")
    print(f"  에러: {len(report['errors'])}개")
    print(f"  경고: {len(report['warnings'])}개")
    print(f"  포인터 범위: {report['pointer_ranges']}개")

    return report['valid'] and len(report['errors']) == 0


def main():
    """모든 검증 테스트 실행"""
    print("\n" + "=" * 60)
    print("  PHASE 5-2: 포인터 자동 검증 로직 테스트")
    print("  Game Wars ROM - 포인터 및 메모리 범위 검증")
    print("=" * 60)

    tests = [
        ("유효한 포인터 검증", test_valid_pointers),
        ("범위 초과 감지", test_out_of_bounds),
        ("포인터 겹침 감지", test_pointer_overlap),
        ("크기 검증", test_pointer_size_validation),
        ("보고서 생성", test_validation_report),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n  [FAIL] {test_name} 실행 중 오류: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # 결과 요약
    print("\n" + "=" * 60)
    print("  테스트 결과 요약")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} {test_name}")

    print(f"\n  통과: {passed}/{total}")

    if passed == total:
        print("\n  [SUCCESS] 모든 검증 로직 테스트 통과!")
        print("\n  PHASE 5-2 완료:")
        print("  - 포인터 범위 검증")
        print("  - ROM 범위 검증")
        print("  - 겹침 감지")
        print("  - 자동 오류 보고")
    else:
        print(f"\n  [FAIL] 일부 테스트 실패")

    print("\n" + "=" * 60)
    return 0 if passed == total else 1


if __name__ == '__main__':
    sys.exit(main())
