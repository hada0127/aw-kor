# 무라마사 한글화 프로젝트에서 가져온 자산 (2026-05-25)

`~/project/muramasa-kor` — **오보로 무라마사(PS Vita) 한글화**가 v1.0.0으로 성공 종료.
플랫폼은 다르지만(Vita CPK/GPU 텍스처 ↔ GBA 타일폰트), **번역 QA·용어 일관화·작업 규율**
방법론은 그대로 전이 가능하다. 이 문서는 무엇을 가져왔고 어떻게 적응했는지 정리한다.

---

## 1. 실제 이식한 도구 (aw-kor CSV 포맷에 맞게 재작성)

무라마사는 `translations/jp_messages.json`(중첩 `ja`/`ko`), aw-kor는
`data/translation_for_import.csv`(`address,japanese,korean,length`). 핵심 로직(한국어
텍스트 처리)은 플랫폼 무관이라 입출력 어댑터만 새로 짰다.

| aw-kor 도구 | 원본 | 핵심 적응 |
|---|---|---|
| `tools/lint_translation.py` | `lint_dialogs.py` | 박스 폭 검사(Vita) → **바이트 예산 검사**(GBA 삽입 손상 방지). 인코딩 검사 글리프 소스를 Galmuri11-Condensed BDF로. **hex 토큰 누출** 검사 신규(aw-kor 추출 손상 특화). 추출 노이즈 휴리스틱. |
| `tools/export_proper_nouns.py` | 동명 | 섹션별 추출(Vita) → 평면 CSV에서 **같은 일본어 → 다른 한국어 불일치 탐지** + 반복 고유명사 후보. |
| `tools/apply_proper_nouns.py` | 동명 | `proper_nouns.json` 편집(ja 정확치환 + 부분문자열 치환)을 CSV에 역적용. dry-run 기본. |
| `tools/fix_punctuation.py` | 동명(919줄) | 한국어 종결어미 분류표 이식 + **aw-kor 안전 게이트**: 일본어 원문이 종결부호로 끝날 때만 미러링. (메뉴 라벨 과잉부호 방지) |
| `tools/repair_hex_corruption.py` | (신규) | 추출 손상(포인터 주소 누출) 행 복구. lint hex_token 해소용. |
| `tools/reflow_dialogs.py` | 동명(DP) | 박스 폭/줄 수 맞춰 줄바꿈 재배치. **현재 미적용**(aw-kor는 단일행+게임 자동 줄바꿈) — 향후 박스 폭 보정 후 사용. `--test`로 동작 시연 가능. condense의 greedy-fill보다 나은 DP 균형 분배라 condense는 별도 이식 안 함. |

### 워크플로
```bash
# 1) 번역 품질 스캔 (회귀 추적·삽입 손상 사전 차단)
python tools/lint_translation.py                 # 전체 요약
python tools/lint_translation.py --hide-noise     # 추출 노이즈 제외(실작업 대상)
python tools/lint_translation.py --rule hex_token --limit 30   # 손상 행 보기

# 2) 용어 일관화
python tools/export_proper_nouns.py               # data/proper_nouns.json 생성
#   → proper_nouns.json의 inconsistencies/recurring_terms의 edit 칸을 채운다
python tools/apply_proper_nouns.py                # 미리보기
python tools/apply_proper_nouns.py --apply        # CSV 반영

# 3) 문장부호 자동 보정
python tools/fix_punctuation.py                   # 미리보기
python tools/fix_punctuation.py --apply
```

> ⚠️ 모든 적용형 도구(`apply_proper_nouns`, `fix_punctuation`)는 **dry-run이 기본**.
> CSV는 git으로 관리되므로 적용 전 `git diff data/translation_for_import.csv`로 확인.

---

## 2. 참고 문서 (원본 그대로 보관)

| 파일 | 내용 | aw-kor 활용 |
|---|---|---|
| `translation-style-guide.md` | 화자별 말투 표(간결 포맷) | aw-kor `docs/TRANSLATION_TONE_AND_STORY_GUIDE.md`를 이 표 형식으로 정리하면 일관성↑ |
| `font_patch_methods_research.md` | 폰트 패치 6가지 방법 비교(Vita 기준) | GBA엔 GPU 텍스처 교체가 없어 직접 적용 불가. **방법론적 사고**(매핑 테이블 추출·시각 분석)만 참고 |
| `AGENTS_example.md` | Codex용 작업 핸드북 | aw-kor도 codex 번역을 쓰므로 `AGENTS.md` 신설 시 템플릿 |

---

## 3. 전이 가능한 방법론 교훈 (무라마사 success.md/fail.md에서 추출)

### (a) Fixed-point 수렴 루프 — 텍스트 가공의 정석
부호 추가가 글자 길이를 바꾸면 줄바꿈이 깨진다. 그래서 **여러 도구를 0건 수렴까지 반복**한다:
```
reflow/condense → fix_punctuation → reflow/condense → ... (변경 0건 될 때까지)
```
무라마사는 보통 2~3회차에 fixed-point 도달. aw-kor에서 부호 보정 후 lint가
새 경고를 만들면 같은 방식으로 수렴시킨다.

### (b) 용어 불일치는 자동 탐지 가능 — 사람은 결정만
같은 원문이 여러 번역으로 갈리는 건 기계가 다 찾는다(`export_proper_nouns`). 사람은
표준 표기 하나만 정하고 `apply`로 일괄 반영. 무라마사는 인명 독법(켄지→켄모치 등),
용어(掟 규율, 髑髏谷 해골 골짜기)를 이렇게 통일.
→ aw-kor 첫 실행에서 **813개 불일치** 발견. 예: `「もぐる」`(잠수 능력)이 잠수/잠복/잠항 혼용.

### (c) 손상은 데이터 레벨에서 잡는다
무라마사는 `+OSS`(BOSS 오역)·`럴럴`(`##` 토큰 미치환)을 NMS 바이트 검색으로 확정 수정.
aw-kor는 추출 시 **포인터 주소가 번역에 새어든 손상**(`유0x00D9991D`)이 250행 — lint
`hex_token` 규칙이 잡는다. ROM 삽입 전 반드시 0으로 만들 것.

### (d) "폰트 페이지를 늘리지 말고, 있는 페이지를 더 써라" (개념)
무라마사 핵심 반전: 한 폰트 페이지(아틀라스)를 세로로 늘리는 건 게임이 1024 하드코딩
UV로 무시 → 실패. 하지만 **이미 존재하는 다른 한자 페이지**(重/隼)에 한글을 얹으니 성공.
→ GBA aw-kor에 직역 불가하나, "엔진이 가정하는 레이아웃을 거스르지 말고 빈/여유 슬롯을
재활용하라"는 사고는 aw-kor 슬롯 매핑(카타카나 그리드 42+idx)에도 통한다.

### (e) RUNTIME_OVERLAY 충돌 — 한 셀을 두 스킴이 읽는다
무라마사: 게임이 ASCII를 `192+code`와 `960+(code-0x20)` 두 스킴으로 읽어, 한글을 그 셀에
넣으면 ASCII 렌더가 덮어써 깨짐. → aw-kor도 슬롯 매핑 시 **같은 슬롯이 다른 화면/코드에서
다르게 해석되는지** 항상 확인(success.md의 카타카나 그리드 vs dialog overlay 분리와 동일 교훈).

### (f) 작업 규율
- `.claude/` 또는 `docs/`에 **success.md / fail.md / todo(plan).md** 3종을 항상 갱신.
  fail.md는 "다시 시도하지 마라" 조건까지 명시(무라마사는 이게 dead-end 반복을 막음).
- 자동 검증 불가(macOS)일 때는 **데이터/픽셀 레벨 검증으로 갈음**하고 그 사실을 명시.
- 적용형 변경은 빌드 산출물 해시(md5)를 기록해 재현·동일성 확인.

---

## 4. 가져오지 않은 것 (참고만)

- Vita 전용 파이프라인: `cpk_extract/patch`, `ftx_extract`, `auto_font_import`(GPU 텍스처),
  `vita3k_*`, `texture_localize`, `ui_editor` — GBA와 무관.
- `condense_dialogs.py`(greedy-fill): `reflow_dialogs.py`의 DP 균형 분배가 상위호환이라
  별도 이식 안 함. (reflow는 이식 완료 — 위 표 참조)
- `score_candidates.py`/`verify_batch.py`/`retranslate_batch.py`: gemini 배치 재번역·검증.
  aw-kor는 Claude 에이전트 병렬 번역을 쓰므로 패턴만 참고(`~/project/muramasa-kor/tools/`).
