# Game Boy Wars Advance 1+2 한글화 — 진척 상태

## 사용자 목표 달성

| 목표 | 상태 | 증거 |
|------|------|------|
| 두줄 출력 성공 | ✅ 완료 | `output/welcome_2line_v16.gba` |
| 남는 텍스쳐 없음 | ✅ 완료 | `docs/screenshots/SUCCESS_v16_FINAL_clean_2line_2026-05-23.png` |
| 폰트 통일 (Galmuri11) | ✅ 완료 | v16 화면 |
| 시작 위치 정렬 | ✅ 완료 | col 7, line 1+2 정확히 정렬 |
| 원래 번역 출력 | ✅ 완료 | "게임보이 워즈에 / 어서 와! ▼" |
| 마커 라인 2 끝 | ✅ 완료 | ▼ |
| 전체 대사 한글화 | ⏳ 진행중 (multi-day) | welcome scene 29 dialogs 빌드됨 |

## 검증된 ROM 산출물

| 파일 | 설명 |
|------|------|
| `output/welcome_2line_v16.gba` | 단일 welcome dialog — 완벽 깨끗 2-line 한글 |
| `output/multi_dialog_v3.gba` | 10 dialogs multi-dispatch — 디스패치 검증 |
| `output/multi_dialog_v5_dynamic.gba` | 29 dialogs (welcome scene) — dynamic layout |

## 자동 빌드 도구

| 도구 | 기능 |
|------|------|
| `tools/build_multi_dialog_v2.py` | N개 dialog 자동 빌드 (CSV 입력 → 패치 ROM) |
| `tools/mgba_harness.c` | libmgba 디버거 (w16 명령 추가) |
| `tools/bdf.py` | Galmuri11 BDF 파서 |

## 핵심 기술적 발견

### 엔진 패치
- **1바이트 ROM 패치 (0xB175AA: 0x06→0x02)**: dialog clear height 6→2 → line 2 영역 영구 활성화
- **Dual hook architecture** (init + loop exit): per-dialog dispatch with flag

### Code cave 사용
- 0x08A3CF14+ (798 KB 가용)
- 29 dialogs: ~68 KB 사용
- 100 dialogs: ~234 KB 사용 (intro 영향 문제 발견 — 추후 디버그)
- 18K dialogs: ~700 KB 예상 (binary search + master glyph 아키텍처 필요)

### Font Galmuri11
- Top tile: glyph rows 0-7 → tile rows 0-7
- Bot tile: glyph rows 8-10 → tile rows 0-2 (no overlap = 깨끗한 표시)
- 1028 unique Korean 음절 (`data/korean_glyphs_8px.json`)

## 18K 확장 단계 (남은 작업)

1. **Binary search dispatch**: linear if/else 540 KB → 144 KB
2. **Master glyph table**: per-dialog full 42 MB → 64 KB shared
3. **Per-dialog syllable indices**: 24 bytes/dialog × 18K = 430 KB
4. **시스템 dialog 필터링**: 메뉴/UI 텍스트 제외 (intro 영향 회피)
5. **테스트 자동화**: 18K dialog 모두 navigate + visual check

## 작업 시간 추정
- Welcome 1 dialog: ✅ 완료 (수 시간)
- 29 dialogs (welcome scene): ✅ 완료 (1 iteration)
- 18K dialog 전체: **multi-day engineering** (binary search + master glyph + testing)

---
2026-05-23
