#!/usr/bin/env python3
"""
PHASE 5-3: ROM 폰트 구조 자동 분석

Game Wars ROM에서 폰트 데이터 위치와 구조를 자동으로 분석합니다.
HxD 없이 Python만으로 폰트 정보를 추출합니다.

사용법:
    python analyze_rom_font_structure.py <rom_file>

예:
    python analyze_rom_font_structure.py "original/Game Boy Wars Advance 1+2 (Japan).gba"
"""

import sys
import struct
from pathlib import Path
from collections import Counter, defaultdict
from typing import List, Tuple, Dict


class ROMFontAnalyzer:
    """GBA ROM 폰트 구조 분석기"""

    def __init__(self, rom_path: str):
        self.rom_path = rom_path
        self.rom_data = None
        self.rom_size = 0
        self.findings = {
            'potential_font_regions': [],
            'repeated_patterns': [],
            'bitmap_regions': [],
            'pointer_patterns': [],
            'text_clusters': []
        }

    def load_rom(self) -> bool:
        """ROM 파일 로드"""
        try:
            with open(self.rom_path, 'rb') as f:
                self.rom_data = f.read()
            self.rom_size = len(self.rom_data)
            print(f"[정보] ROM 로드 완료: {self.rom_size:,} bytes ({self.rom_size/1024/1024:.1f}MB)")
            return True
        except Exception as e:
            print(f"[오류] ROM 로드 실패: {e}")
            return False

    def find_repeated_patterns(self, min_size=16, min_count=50) -> List[Tuple]:
        """반복되는 패턴 찾기 (비트맵 글리프 가능성)"""
        print("\n[분석 1] 반복되는 패턴 탐색 (비트맵 글리프 후보)...")

        patterns = defaultdict(list)
        chunk_size = 8  # 8바이트 청크

        for i in range(0, len(self.rom_data) - chunk_size, chunk_size):
            chunk = self.rom_data[i:i+chunk_size]
            patterns[chunk].append(i)

        # 충분히 반복되는 패턴만 필터
        repeated = []
        for pattern, addresses in patterns.items():
            if len(addresses) >= min_count:
                # 패턴의 특성 분석
                entropy = self._calculate_entropy(pattern)
                if entropy > 2:  # 어느 정도 변화가 있는 패턴
                    repeated.append({
                        'pattern': pattern.hex(),
                        'count': len(addresses),
                        'first_address': hex(addresses[0]),
                        'entropy': entropy
                    })

        # 빈도순 정렬
        repeated.sort(key=lambda x: x['count'], reverse=True)

        print(f"[결과] {len(repeated)}개 반복 패턴 발견")
        for i, item in enumerate(repeated[:10], 1):
            print(f"  {i}. 패턴: {item['pattern'][:16]}... 빈도: {item['count']}회 엔트로피: {item['entropy']:.2f}")

        self.findings['repeated_patterns'] = repeated
        return repeated

    def find_bitmap_regions(self) -> List[Dict]:
        """비트맵 데이터 영역 찾기"""
        print("\n[분석 2] 비트맵 데이터 영역 탐색...")

        regions = []
        region_start = None
        region_entropy = 0

        # 슬라이딩 윈도우로 엔트로피 계산
        window_size = 128

        for i in range(0, len(self.rom_data) - window_size, window_size):
            window = self.rom_data[i:i+window_size]
            entropy = self._calculate_entropy(window)

            # 엔트로피가 높은 영역 = 비트맵 가능성
            if entropy > 5:  # 높은 엔트로피
                if region_start is None:
                    region_start = i
                    region_entropy = entropy
            else:
                if region_start is not None:
                    regions.append({
                        'start': hex(region_start),
                        'end': hex(i),
                        'size': i - region_start,
                        'avg_entropy': region_entropy
                    })
                    region_start = None

        print(f"[결과] {len(regions)}개 비트맵 가능 영역 발견")
        for i, region in enumerate(regions[:5], 1):
            size_kb = region['size'] / 1024
            print(f"  {i}. {region['start']} ~ {region['end']} ({size_kb:.1f}KB, 엔트로피: {region['avg_entropy']:.2f})")

        self.findings['bitmap_regions'] = regions
        return regions

    def find_shift_jis_patterns(self) -> List[Dict]:
        """Shift-JIS 문자 패턴 탐색 (텍스트 클러스터)"""
        try:
            print("\n[분석 3] Shift-JIS 텍스트 클러스터 탐색...")
        except:
            print("\n[Analysis 3] Shift-JIS text cluster search...")

        clusters = []
        i = 0

        while i < len(self.rom_data) - 1:
            b1 = self.rom_data[i]

            # Shift-JIS 첫 바이트 확인
            if (0x81 <= b1 <= 0x9F) or (0xE0 <= b1 <= 0xEF):
                if i + 1 < len(self.rom_data):
                    b2 = self.rom_data[i + 1]

                    # Shift-JIS 둘째 바이트 확인
                    if (0x40 <= b2 <= 0x7E) or (0x80 <= b2 <= 0xFC):
                        cluster_start = i
                        cluster_data = bytearray()
                        char_count = 0

                        # 연속된 Shift-JIS 문자 수집
                        while i < len(self.rom_data) - 1:
                            b1 = self.rom_data[i]
                            if (0x81 <= b1 <= 0x9F) or (0xE0 <= b1 <= 0xEF):
                                if i + 1 < len(self.rom_data):
                                    b2 = self.rom_data[i + 1]
                                    if (0x40 <= b2 <= 0x7E) or (0x80 <= b2 <= 0xFC):
                                        cluster_data.append(b1)
                                        cluster_data.append(b2)
                                        i += 2
                                        char_count += 1
                                    else:
                                        break
                                else:
                                    break
                            else:
                                break

                        # 충분히 긴 클러스터만 기록
                        if char_count >= 5:
                            try:
                                decoded = cluster_data.decode('shift_jis', errors='ignore')
                                clusters.append({
                                    'address': hex(cluster_start),
                                    'length': len(cluster_data),
                                    'char_count': char_count,
                                    'text': decoded[:50] if len(decoded) > 50 else decoded
                                })
                            except:
                                pass
                        continue

            i += 1

        # 크기순 정렬
        clusters.sort(key=lambda x: x['length'], reverse=True)

        print(f"[결과] {len(clusters)}개 텍스트 클러스터 발견")
        for i, cluster in enumerate(clusters[:10], 1):
            try:
                text_preview = repr(cluster['text'][:30])
            except:
                text_preview = "[encoding varies]"
            print(f"  {i}. {cluster['address']}: {cluster['char_count']}자 ({cluster['length']}bytes) - {text_preview}")

        self.findings['text_clusters'] = clusters
        return clusters

    def find_pointer_arrays(self) -> List[Dict]:
        """포인터 배열 찾기 (문자별 폰트 오프셋)"""
        print("\n[분석 4] 포인터 배열 탐색...")

        pointer_regions = []

        # 4바이트 단위로 잠재적 포인터 찾기
        for i in range(0, len(self.rom_data) - 4, 4):
            # Little-endian 포인터로 해석
            ptr_value = struct.unpack('<I', self.rom_data[i:i+4])[0]

            # 유효한 ROM 범위 내인지 확인
            if ptr_value < self.rom_size and ptr_value > 0x8000:  # 의미있는 범위
                # 여러 포인터가 연속으로 나타나는지 확인
                consecutive_pointers = 0
                start_addr = i

                j = i
                while j < len(self.rom_data) - 4:
                    ptr = struct.unpack('<I', self.rom_data[j:j+4])[0]
                    if ptr < self.rom_size and ptr > 0x8000:
                        consecutive_pointers += 1
                        j += 4
                    else:
                        break

                # 포인터 배열 조건: 최소 10개 이상 연속 포인터
                if consecutive_pointers >= 10:
                    pointer_regions.append({
                        'address': hex(start_addr),
                        'pointer_count': consecutive_pointers,
                        'range': f"{hex(start_addr)} - {hex(start_addr + consecutive_pointers * 4)}",
                        'first_target': hex(struct.unpack('<I', self.rom_data[start_addr:start_addr+4])[0])
                    })

                    # 이미 처리한 영역 스킵
                    i = j - 1

        print(f"[결과] {len(pointer_regions)}개 포인터 배열 발견")
        for i, region in enumerate(pointer_regions[:10], 1):
            print(f"  {i}. {region['address']}: {region['pointer_count']}개 포인터 → {region['first_target']}")

        self.findings['pointer_patterns'] = pointer_regions
        return pointer_regions

    def estimate_glyph_size(self) -> Dict:
        """글리프 크기 추정"""
        print("\n[분석 5] 글리프 크기 추정...")

        # 반복 패턴에서 크기 추정
        if self.findings['repeated_patterns']:
            pattern_size = len(bytes.fromhex(self.findings['repeated_patterns'][0]['pattern']))
            print(f"[추정] 반복 패턴 크기: {pattern_size} bytes")

            # 일반적인 GBA 글리프 크기
            # 8x8: 8bytes, 16x16: 32bytes, 8x16: 16bytes
            possible_sizes = {
                8: "8x8 글리프 (1bpp 비트맵)",
                16: "8x16 또는 16x8 글리프 (1bpp)",
                32: "16x16 글리프 (1bpp)",
                64: "16x16 글리프 (2bpp) 또는 32x8"
            }

            for size_bytes, description in possible_sizes.items():
                if pattern_size == size_bytes:
                    print(f"[추정] {description}")

            return {'estimated_glyph_bytes': pattern_size, 'description': possible_sizes.get(pattern_size, "알 수 없음")}

        return {}

    def generate_analysis_report(self) -> str:
        """분석 보고서 생성"""
        print("\n" + "="*60)
        print("PHASE 5-3: ROM 폰트 구조 분석 보고서")
        print("="*60)

        report = f"""
ROM 분석 결과
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ROM 정보:
  파일: {self.rom_path}
  크기: {self.rom_size:,} bytes ({self.rom_size/1024/1024:.1f}MB)

발견 사항:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[1] 반복 패턴 (비트맵 글리프 가능성)
    발견: {len(self.findings['repeated_patterns'])}개
    {self._format_patterns()}

[2] 비트맵 영역
    발견: {len(self.findings['bitmap_regions'])}개
    {self._format_regions()}

[3] Shift-JIS 텍스트 클러스터
    발견: {len(self.findings['text_clusters'])}개
    {self._format_clusters()}

[4] 포인터 배열
    발견: {len(self.findings['pointer_patterns'])}개
    {self._format_pointers()}

다음 단계:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 위의 분석 결과에서 폰트 후보 선택
2. HxD에서 해당 주소 확인하여 폰트 구조 검증
3. 다음 정보를 font_preparation_framework.py에 입력:
   - font_start_address: 폰트 데이터 시작 주소
   - font_end_address: 폰트 데이터 끝 주소
   - glyph_width, glyph_height: 글리프 픽셀 크기
   - glyph_size_bytes: 글리프당 바이트 크기
   - encoding_type: 문자 인코딩 (Shift-JIS 확인됨)
   - num_chars: 폰트에 포함된 문자 수

권장:
  - 포인터 배열 주소에서 글리프 데이터 시작 위치 확인
  - 텍스트 클러스터는 게임 데이터, 폰트 영역은 별도
"""
        return report

    def _format_patterns(self) -> str:
        if self.findings['repeated_patterns']:
            lines = []
            for i, item in enumerate(self.findings['repeated_patterns'][:3], 1):
                lines.append(f"    {i}. 패턴: {item['pattern'][:16]}... 빈도: {item['count']}")
            return "\n".join(lines)
        return "    없음"

    def _format_regions(self) -> str:
        if self.findings['bitmap_regions']:
            lines = []
            for i, region in enumerate(self.findings['bitmap_regions'][:3], 1):
                size_kb = region['size'] / 1024
                lines.append(f"    {i}. {region['start']} ~ {region['end']} ({size_kb:.1f}KB)")
            return "\n".join(lines)
        return "    없음"

    def _format_clusters(self) -> str:
        if self.findings['text_clusters']:
            lines = []
            for i, cluster in enumerate(self.findings['text_clusters'][:3], 1):
                lines.append(f"    {i}. {cluster['address']}: {cluster['char_count']}자")
            return "\n".join(lines)
        return "    없음"

    def _format_pointers(self) -> str:
        if self.findings['pointer_patterns']:
            lines = []
            for i, ptr in enumerate(self.findings['pointer_patterns'][:3], 1):
                lines.append(f"    {i}. {ptr['address']}: {ptr['pointer_count']}개 포인터")
            return "\n".join(lines)
        return "    없음"

    @staticmethod
    def _calculate_entropy(data: bytes) -> float:
        """데이터의 엔트로피 계산 (무작위성 측정)"""
        if not data:
            return 0
        counter = Counter(data)
        entropy = 0
        for count in counter.values():
            p = count / len(data)
            entropy -= p * (p and __import__('math').log2(p))
        return entropy

    def run_analysis(self):
        """전체 분석 실행"""
        if not self.load_rom():
            return False

        print("\n" + "="*60)
        print("Game Wars ROM 폰트 구조 분석 시작")
        print("="*60)

        self.find_repeated_patterns()
        self.find_bitmap_regions()
        self.find_shift_jis_patterns()
        self.find_pointer_arrays()
        self.estimate_glyph_size()

        report = self.generate_analysis_report()
        print(report)

        # 보고서 저장
        report_path = Path(self.rom_path).parent.parent / "docs" / "PHASE5_3_ROM_FONT_ANALYSIS.md"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"\n[정보] 분석 보고서 저장: {report_path}")
        return True


def main():
    """메인 프로그램"""
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    rom_path = sys.argv[1]

    if not Path(rom_path).exists():
        print(f"[오류] ROM 파일 없음: {rom_path}")
        return 1

    analyzer = ROMFontAnalyzer(rom_path)
    success = analyzer.run_analysis()

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
