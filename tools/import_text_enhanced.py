#!/usr/bin/env python3
"""
PHASE 5-4: 번역 텍스트 삽입 (개선 버전)

번역된 한글 텍스트를 ROM에 삽입합니다.

사용법:
    python import_text_enhanced.py <rom_file> <translation_csv> <output_rom> [--encoding euc-kr|shift-jis|custom]

예:
    python import_text_enhanced.py output/game_wars_kor.gba data/translations.csv output/game_wars_final.gba --encoding euc-kr
"""

import sys
import csv
import struct
from pathlib import Path
from typing import Dict, List, Tuple


class TextEncodingHandler:
    """텍스트 인코딩 처리"""

    SUPPORTED_ENCODINGS = {
        'shift-jis': 'shift_jis',
        'euc-kr': 'euc_kr',
        'utf-8': 'utf_8',
        'custom': None,
    }

    def __init__(self, encoding: str):
        """
        인코딩 설정

        Args:
            encoding: 'shift-jis', 'euc-kr', 'utf-8', 또는 'custom'
        """
        if encoding not in self.SUPPORTED_ENCODINGS:
            raise ValueError(f"지원하지 않는 인코딩: {encoding}")

        self.encoding_name = encoding
        self.encoding = self.SUPPORTED_ENCODINGS[encoding]

    def encode_text(self, text: str, tbl_mapping: Dict = None) -> bytes:
        """
        텍스트를 바이트로 인코딩

        Args:
            text: 인코딩할 텍스트
            tbl_mapping: 커스텀 인코딩용 .tbl 매핑

        Returns:
            인코딩된 바이트
        """
        if self.encoding_name == 'custom':
            return self._encode_custom(text, tbl_mapping)
        else:
            try:
                return text.encode(self.encoding)
            except UnicodeEncodeError as e:
                print(f"[경고] 인코딩 실패 ({self.encoding_name}): {text}")
                print(f"  오류: {e}")
                return b''

    def _encode_custom(self, text: str, tbl_mapping: Dict) -> bytes:
        """
        .tbl 매핑을 사용하여 커스텀 인코딩

        주의: 이 함수는 프레임워크입니다.
        실제 구현은 게임의 인코딩 방식에 따라 달라집니다.
        """
        if not tbl_mapping:
            print("[오류] 커스텀 인코딩을 위해 tbl_mapping이 필요합니다.")
            return b''

        result = bytearray()
        for char in text:
            if char in tbl_mapping:
                result.append(tbl_mapping[char])
            else:
                print(f"[경고] 매핑되지 않은 문자: '{char}'")
                result.append(ord('?'))

        return bytes(result)


class TranslationLoader:
    """번역 데이터 로드"""

    @staticmethod
    def load_translations(csv_path: str) -> Dict[int, Dict]:
        """
        번역 CSV 파일 로드

        CSV 형식:
            address,japanese,korean,length
            0x009294D0,潜水艦,잠수함,6

        Returns:
            {주소: {'korean': 한글, 'japanese': 일본어, 'length': 길이}, ...}
        """
        translations = {}

        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    try:
                        # 주소 파싱
                        addr_str = row['address'].strip()
                        if addr_str.startswith('0x') or addr_str.startswith('0X'):
                            addr = int(addr_str, 16)
                        else:
                            addr = int(addr_str)

                        translations[addr] = {
                            'korean': row.get('korean', '').strip(),
                            'japanese': row.get('japanese', '').strip(),
                            'length': int(row.get('length', 0))
                        }
                    except (ValueError, KeyError) as e:
                        print(f"[경고] 행 파싱 실패: {row}")
                        print(f"  오류: {e}")

            print(f"[정보] {len(translations)}개 번역 항목 로드 완료")
            return translations

        except FileNotFoundError:
            print(f"[오류] 파일을 찾을 수 없습니다: {csv_path}")
            return {}
        except Exception as e:
            print(f"[오류] 파일 로드 실패: {e}")
            return {}


class TBLCharacterMapper:
    """TBL 파일 문자 매핑"""

    @staticmethod
    def load_tbl(tbl_path: str) -> Dict[str, int]:
        """
        .tbl 파일 로드하여 문자->바이트 매핑 생성

        .tbl 형식:
            40=@
            41=A
            ...

        Returns:
            {'@': 0x40, 'A': 0x41, ...}
        """
        mapping = {}

        try:
            with open(tbl_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    if '=' not in line:
                        continue

                    parts = line.split('=', 1)
                    if len(parts) != 2:
                        continue

                    try:
                        byte_val = int(parts[0], 16)
                        char = parts[1]
                        mapping[char] = byte_val
                    except ValueError:
                        continue

            print(f"[정보] TBL 파일 로드: {len(mapping)}개 매핑")
            return mapping

        except FileNotFoundError:
            print(f"[오류] TBL 파일을 찾을 수 없습니다: {tbl_path}")
            return {}
        except Exception as e:
            print(f"[오류] TBL 로드 실패: {e}")
            return {}


class TextInsertionValidator:
    """텍스트 삽입 검증"""

    @staticmethod
    def validate_insertion(rom_size: int, address: int,
                           korean_bytes: bytes,
                           original_length: int) -> Tuple[bool, str]:
        """
        텍스트 삽입 가능 여부 검증

        Args:
            rom_size: ROM 크기
            address: 삽입 주소
            korean_bytes: 한글 바이트 데이터
            original_length: 원래 텍스트 길이

        Returns:
            (가능 여부, 메시지)
        """
        # 주소 검증
        if address < 0:
            return False, f"주소가 음수: 0x{address:08X}"

        if address >= rom_size:
            return False, f"주소가 ROM 범위 초과: 0x{address:08X} >= 0x{rom_size:08X}"

        # 길이 검증
        if len(korean_bytes) > original_length:
            return False, f"한글 텍스트가 너무 깁니다: {len(korean_bytes)} > {original_length} bytes"

        if address + original_length > rom_size:
            return False, f"삽입 범위가 ROM 초과: 0x{address:08X} + {original_length} > 0x{rom_size:08X}"

        return True, "검증 통과"

    @staticmethod
    def validate_all_insertions(rom_size: int,
                               translations: Dict[int, Dict]) -> Tuple[int, List[str]]:
        """
        모든 번역에 대해 삽입 가능 여부 검증

        Returns:
            (검증 통과 항목 수, 오류 목록)
        """
        valid_count = 0
        errors = []

        for addr, trans_data in translations.items():
            # 여기서는 실제 바이트 길이를 알 수 없으므로
            # 간단한 검증만 수행
            is_valid, msg = TextInsertionValidator.validate_insertion(
                rom_size,
                addr,
                b'',  # 빈 바이트 (실제로는 인코딩 후 길이 확인)
                trans_data.get('length', 0)
            )

            if is_valid:
                valid_count += 1
            else:
                errors.append(f"0x{addr:08X}: {msg}")

        return valid_count, errors


class TextInserter:
    """ROM에 텍스트 삽입"""

    def __init__(self, encoding: str = 'euc-kr'):
        self.encoding_handler = TextEncodingHandler(encoding)
        self.inserted = 0
        self.failed = 0

    def insert_translations(self, rom_path: str, translations: Dict[int, Dict],
                           output_path: str, tbl_mapping: Dict = None) -> bool:
        """
        ROM에 번역 텍스트 삽입

        Args:
            rom_path: 원본 ROM 경로
            translations: 번역 데이터
            output_path: 출력 ROM 경로
            tbl_mapping: 커스텀 인코딩용 매핑

        Returns:
            성공 여부
        """
        try:
            # ROM 로드
            with open(rom_path, 'rb') as f:
                rom_data = bytearray(f.read())

            rom_size = len(rom_data)
            print(f"[정보] ROM 로드: {rom_size:,} bytes")

            # 검증
            valid_count, errors = TextInsertionValidator.validate_all_insertions(
                rom_size, translations
            )

            if errors:
                print(f"\n[경고] {len(errors)}개 오류 발견:")
                for error in errors[:10]:
                    print(f"  - {error}")
                if len(errors) > 10:
                    print(f"  ... 외 {len(errors) - 10}개")

            # 텍스트 삽입
            print(f"\n[진행] 텍스트 삽입 시작...")

            for addr, trans_data in translations.items():
                korean_text = trans_data['korean']
                korean_bytes = self.encoding_handler.encode_text(korean_text, tbl_mapping)
                original_length = trans_data.get('length', 0)

                # 길이 검증
                if len(korean_bytes) > original_length:
                    print(f"[경고] 0x{addr:08X}: 텍스트가 너무 깁니다 ({len(korean_bytes)} > {original_length})")
                    korean_bytes = korean_bytes[:original_length]

                # 패딩
                if len(korean_bytes) < original_length:
                    korean_bytes = korean_bytes + b'\x00' * (original_length - len(korean_bytes))

                # 삽입
                try:
                    rom_data[addr:addr + original_length] = korean_bytes
                    self.inserted += 1
                except Exception as e:
                    print(f"[오류] 0x{addr:08X}: 삽입 실패 - {e}")
                    self.failed += 1

            # ROM 저장
            with open(output_path, 'wb') as f:
                f.write(rom_data)

            print(f"\n[결과]")
            print(f"  삽입: {self.inserted}개")
            print(f"  실패: {self.failed}개")
            print(f"  저장: {output_path}")

            return self.failed == 0

        except Exception as e:
            print(f"[오류] 텍스트 삽입 실패: {e}")
            return False


def main():
    """메인 프로그램"""
    if len(sys.argv) < 4:
        print(__doc__)
        return 1

    rom_path = sys.argv[1]
    csv_path = sys.argv[2]
    output_path = sys.argv[3]

    # 인코딩 파라미터 파싱
    encoding = 'euc-kr'  # 기본값
    if len(sys.argv) > 4 and sys.argv[4] == '--encoding' and len(sys.argv) > 5:
        encoding = sys.argv[5]

    # 파일 존재 확인
    if not Path(rom_path).exists():
        print(f"[오류] ROM 파일 없음: {rom_path}")
        return 1

    if not Path(csv_path).exists():
        print(f"[오류] 번역 CSV 없음: {csv_path}")
        return 1

    print("=" * 60)
    print("PHASE 5-4: 번역 텍스트 삽입")
    print("=" * 60)

    # 번역 로드
    translations = TranslationLoader.load_translations(csv_path)
    if not translations:
        print("[오류] 번역 데이터 없음")
        return 1

    # TBL 로드 (선택사항)
    tbl_mapping = None
    tbl_path = 'tools/game_wars.tbl'
    if Path(tbl_path).exists():
        tbl_mapping = TBLCharacterMapper.load_tbl(tbl_path)

    # 텍스트 삽입
    inserter = TextInserter(encoding)
    success = inserter.insert_translations(rom_path, translations, output_path, tbl_mapping)

    print("=" * 60)
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
