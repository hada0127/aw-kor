#!/usr/bin/env python3
"""텍스트 바이트 예산 단일 진실원(SSOT) — Python ↔ JS(scene editor) 동형.

빌드 인코더(build_korean_full.encode_text)의 바이트 길이와 일치한다:
  한글 음절       → 2  (예약 SJIS 2바이트 코드)
  전각 공백 '　'  → 2  (0x8140)
  줄바꿈 '\n'     → 1  (0x0A 제어)
  ASCII 0x20~0x7E → 1
  그 외           → 2  (SJIS 폴백 / ？)
이 모듈을 build/qa/scene_editor가 공통 사용해 "한글=2 추정" 같은 드리프트를 없앤다.
(todo: 공통 text_metrics 추출 + py↔js 일치 테스트 + 2350 미수록 음절 차단)

JS 미러는 _JS_ENCLEN 문자열로 박제하고, tests에서 node로 실행해 동일성을 강제한다.
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYLCODE_2350 = os.path.join(BASE, 'data', 'syllable_to_code_2350.json')
SYLCODE = os.path.join(BASE, 'data', 'syllable_to_code.json')


def encoded_len(text):
    """encode_text 바이트 길이와 동일한 예산. (한글2/전각공백2/줄바꿈1/ASCII1/기타2)"""
    n = 0
    for ch in text or '':
        if '가' <= ch <= '힣':
            n += 2
        elif ch == '　':
            n += 2
        elif ch == '\n':
            n += 1
        elif ch == ' ' or (0x20 <= ord(ch) <= 0x7E):
            n += 1
        else:
            n += 2
    return n


def visual_cells(text):
    """반-셀(half-cell) 단위 시각 폭. 한글/전각=2, ASCII/반각공백=1, 줄바꿈=0.

    고정폭 대사 렌더(per-char 셀 복사) 기준 근사. 박스 폭(셀) 비교용.
    """
    w = 0
    for ch in text or '':
        if ch == '\n':
            continue
        if ch == ' ' or (0x20 <= ord(ch) <= 0x7E):
            w += 1
        else:
            w += 2
    return w


def _load_syllable_set(path=None):
    for p in ([path] if path else [SYLCODE_2350, SYLCODE]):
        if p and os.path.exists(p):
            data = json.load(open(p, encoding='utf-8'))
            return set(data.keys())
    return set()


def unmapped_syllables(text, sylset=None):
    """폰트(2350 완성형)에 없는 한글 음절 목록 — 인코딩 시 ？로 깨질 글자."""
    if sylset is None:
        sylset = _load_syllable_set()
    return [ch for ch in (text or '') if '가' <= ch <= '힣' and ch not in sylset]


def fits(text, slot_bytes):
    """encoded_len이 슬롯(바이트)에 들어가는가 — 빌드의 1차 하드게이트와 동일 의미."""
    return encoded_len(text) <= slot_bytes


# scene editor app.js encLen 정본 미러(파서 동형성 테스트용). app.js를 바꾸면 여기도 함께.
_JS_ENCLEN = r"""
function encLen(t) {
  let n = 0;
  for (const ch of t) {
    const c = ch.codePointAt(0);
    if (c >= 0xAC00 && c <= 0xD7A3) n += 2;        // 완성형 한글
    else if (ch === "　") n += 2;                   // 전각 공백
    else if (ch === "\n") n += 1;                   // 줄바꿈 0x0A
    else if (c >= 0x20 && c <= 0x7E) n += 1;        // ASCII
    else n += 2;
  }
  return n;
}
"""


if __name__ == '__main__':
    import sys
    for t in sys.argv[1:]:
        print(f'{encoded_len(t):3d}B  cells={visual_cells(t):3d}  {t!r}')
