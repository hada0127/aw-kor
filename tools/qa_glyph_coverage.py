#!/usr/bin/env python3
"""글리프 커버리지 QA 게이트 — "비트맵 깨짐 0"의 폰트측 보증.

한글 음절은 예약 SJIS 코드(data/syllable_to_code_2350.json)로 인코딩되고, 빌드가 그 코드에
2350자 galmuri 글리프(data/syllable_to_glyph_2350.json['map'] + kor_glyphs_2350.bin)를 주입한다.

**렌더 보증의 두 축**
1) 대칭성: code 집합 == glyph 집합 이어야 한다. code에만 있고 glyph에 없는 음절은 코드는
   배정됐으나 글리프 미주입 → 인게임에서 예약코드가 빼앗은 SJIS 슬롯의 본래 글자(예 0x9868→鷲)나
   공백으로 깨져 보인다. (이 게이트의 1차 FAIL 조건)
2) 빌드 자체 보증: build_korean_full.encode_text는 한글 음절을 `syl_to_code[ch]`로 직접 조회한다.
   2350에 없는 음절이 어느 write 경로(import/override/raw_replace/script 리터럴 등)에든 들어오면
   KeyError로 **빌드가 크래시**한다. 빌드가 ROM을 성공 생성했다는 사실 자체가 "출하된 모든 한글
   음절 ∈ 2350"의 증거다.

이 게이트는 위 두 축을 정면 검증한다:
- code/glyph 대칭성(FAIL 조건),
- temp/integrity_map.json의 **enc_hex(출하 바이트)** 를 전 행·전 경로에서 역디코드해(=ko 필드가
  None인 script/raw_replace까지 포함) 실제 쓰인 예약-한글 코드가 전부 glyph 보유 음절로 해석되는지.
  (qa_integrity_map의 reverse-decode와 달리 ko 필드가 아니라 enc_hex 기준이라 전 경로 커버.)

주의(과대해석 금지): 이 게이트는 "음절↔코드↔글리프 매핑"과 "출하 바이트의 코드 해석"을 보증한다.
글리프 비트맵 내용·테이블 주입·렌더 훅 경로의 시각적 정확성은 fresh-boot 캡처로 별도 검증한다.

exit 0=PASS, 1=FAIL.
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP = os.path.join(BASE, "temp", "integrity_map.json")
CODE = os.path.join(BASE, "data", "syllable_to_code_2350.json")
GLYPH = os.path.join(BASE, "data", "syllable_to_glyph_2350.json")


def parse_code(c):
    return int(c, 0) if isinstance(c, str) else int(c)


def decode_korean_codes(enc_hex, code2syl):
    """enc_hex를 2바이트 SJIS-lead 단위로 훑어 (예약-한글 코드→음절) 목록과
    '미해석 예약-범위 코드' 목록을 돌려준다."""
    if not enc_hex:
        return [], []
    enc = bytes.fromhex(enc_hex)
    syllables = []
    unresolved = []  # (code) — 예약 lead 범위인데 2350에 없는 코드
    i, n = 0, len(enc)
    while i < n:
        b = enc[i]
        if i + 1 < n and ((0x81 <= b <= 0x9F) or (0xE0 <= b <= 0xEF)):
            code = (b << 8) | enc[i + 1]
            if code in code2syl:
                syllables.append(code2syl[code])
            elif code != 0x8140:
                # 예약-한글 lead 범위(0x88-0x9F,0xE0-0xE2)인데 미배정 → 잠재 깨짐 후보
                if (0x88 <= b <= 0x9F) or (0xE0 <= b <= 0xE2):
                    unresolved.append(code)
            i += 2
            continue
        i += 1
    return syllables, unresolved


def main():
    code_map = {s: parse_code(c) for s, c in json.load(open(CODE, encoding="utf-8")).items()}
    glyph = set(json.load(open(GLYPH, encoding="utf-8"))["map"].keys())
    code = set(code_map.keys())
    code2syl = {v: s for s, v in code_map.items()}
    renderable = code & glyph
    print(f"=== 글리프 커버리지 게이트: code={len(code)} glyph={len(glyph)} 교집합={len(renderable)} ===")

    fail = False
    # 1축: 대칭성
    only_code = sorted(code - glyph)
    only_glyph = sorted(glyph - code)
    if only_code:
        fail = True
        print(f"[FAIL] code-only {len(only_code)}종 (코드는 있으나 글리프 없음 → 쓰이면 깨짐): {''.join(only_code[:60])}")
    if only_glyph:
        print(f"[정보] glyph-only {len(only_glyph)}종 (글리프만 존재, 무해): {''.join(only_glyph[:60])}")
    if not only_code and not only_glyph:
        print("[OK] code 집합 == glyph 집합 (대칭) — 코드 배정 음절은 모두 글리프 보유")

    # 2축: enc_hex(출하 바이트) 전 경로 스캔
    if not os.path.exists(MAP):
        print("integrity_map.json 없음 — 대칭성만 검사")
        print("=== 결과:", "FAIL" if fail else "PASS (대칭 OK, enc_hex 미검사)", "===")
        return 1 if fail else 0
    im = json.load(open(MAP, encoding="utf-8"))
    rows = 0
    kor_syllable_hits = 0
    distinct = set()
    not_renderable = {}  # syllable -> count (대칭 깨졌을 때만 발생 가능)
    unresolved_codes = {}  # code -> count
    src_seen = set()
    for row in im:
        enc_hex = row[3] if len(row) > 3 else ""
        src = row[7] if len(row) > 7 else "?"
        src_seen.add(src.split(":")[0] if isinstance(src, str) else "?")
        syl, unres = decode_korean_codes(enc_hex, code2syl)
        if enc_hex:
            rows += 1
        for s in syl:
            kor_syllable_hits += 1
            distinct.add(s)
            if s not in glyph:
                not_renderable[s] = not_renderable.get(s, 0) + 1
        for c in unres:
            unresolved_codes[c] = unresolved_codes.get(c, 0) + 1

    print(f"\nenc_hex 스캔: {rows}행(전 경로: {','.join(sorted(src_seen))}) / 예약-한글 코드 {kor_syllable_hits}회 / 고유 음절 {len(distinct)}종")
    if not_renderable:
        fail = True
        print(f"[FAIL] 출하 enc_hex에 글리프 없는 음절 {len(not_renderable)}종:")
        for s, c in sorted(not_renderable.items(), key=lambda kv: -kv[1])[:30]:
            print(f"  {s!r} U+{ord(s):04X} x{c}")
    else:
        print("[OK] 출하 enc_hex의 모든 예약-한글 코드가 glyph 보유 음절로 해석됨 — 미렌더 0")
    if unresolved_codes:
        # 예약 lead 범위인데 2350 미배정 코드 — 대개 미번역 일본어 한자(정상 잔존)지만 surface
        print(f"[정보] 2350 미배정 SJIS-lead 코드 {len(unresolved_codes)}종 {sum(unresolved_codes.values())}회 "
              f"(미번역 일본어 한자 등 — 한글 의도면 terms/잔존 게이트가 별도 검출)")

    print("\n=== 결과:", "FAIL" if fail else "PASS (대칭 OK / 미렌더 0)", "===")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
