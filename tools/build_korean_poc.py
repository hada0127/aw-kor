#!/usr/bin/env python3
"""Session 2 PoC 빌더: FONT_BASE repoint + 한글 글리프 주입 + 한자 테이블 확장.

Stage A (--stage a): per-char 경로 FONT_BASE 리터럴(0xEFE97C)을 0x08F00000으로 repoint +
  원본 폰트 idx 0..0x5FF(48KB)를 파일 0xF00000으로 복사. 다른 변경 없음.
  → hajimemashite 대화가 (일본어로) 동일 렌더되면 repoint 메커니즘 검증.

Stage B (--stage b): A에 더해 한글 800타일 주입(0xF0C000, idx 0x600~) + 예약코드 할당 +
  한자 테이블 확장(0xF20000) + start/end 리터럴 패치 + hajimemashite를 한글로 인코딩.
  → 대화가 한글로 렌더되면 풀게임 경로 검증.

재현: python tools/build_korean_poc.py --stage a   (또는 b)
"""
import argparse, csv, json, os, struct

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROM = os.path.join(BASE, 'original', 'Game Boy Wars Advance 1+2 (Japan).gba')
BLOB = os.path.join(BASE, 'data', 'korean_glyph_blob.bin')
SYLMAP = os.path.join(BASE, 'data', 'syllable_to_glyph.json')
FOUND = os.path.join(BASE, 'data', 'game_wars_found_texts.csv')

# --- 확정 파라미터 (docs/research.md SESSION 1 RE) ---
FONT_FILE = 0xB974D0          # 원본 FONT_BASE 파일오프셋
FONT_COPY_TILES = 0x600       # per-char 경로 max idx 0x5FF → 0..0x5FF 복사
FONT_COPY_LEN = FONT_COPY_TILES * 0x20   # 0xC000 = 48KB
NEW_FONT_FILE = 0xF00000      # 새 FONT_BASE 파일오프셋 (896KB 빈공간)
NEW_FONT_RT = 0x08F00000
KOR_BLOB_FILE = NEW_FONT_FILE + FONT_COPY_LEN   # 0xF0C000
KOR_IDX_BASE = FONT_COPY_TILES                  # 한글 글리프 글로벌 idx 시작 = 0x600

LIT_FONTBASE = 0xEFE97C       # 변환루틴 FONT_BASE 리터럴 (파일)
LIT_TBL_START = 0xEFE970      # 테이블 start 리터럴
LIT_TBL_END = 0xEFE974        # 테이블 end 리터럴

KTAB_FILE = 0xB80B7C          # 원본 한자 테이블 파일오프셋
KTAB_END_FILE = 0xB8180C
NEW_TBL_FILE = 0xF20000       # 새 테이블 위치
NEW_TBL_RT = 0x08F20000

HAJI_FILE = 0xDF8E3E          # "はじめまして" 첫 글자 は(0x82CD) 위치
HAJI_KANA = [0x82CD, 0x82B6, 0x82DF, 0x82DC, 0x82B5, 0x82C4]  # は じ め ま し て
HAJI_KOREAN = "안녕하십니까"   # 6음절 등길이 치환


def valid_sjis(code):
    lead, trail = code >> 8, code & 0xFF
    if not (0x81 <= lead <= 0x9F or 0xE0 <= lead <= 0xFC):
        return False
    return 0x40 <= trail <= 0x7E or 0x80 <= trail <= 0xFC


def used_codes_in_text():
    used = set()
    with open(FOUND, encoding='utf-8', errors='ignore') as f:
        for r in csv.DictReader(f):
            ja = r.get('japanese') or r.get('text') or ''
            try:
                b = ja.encode('shift_jis', errors='ignore')
            except Exception:
                continue
            i = 0
            while i < len(b) - 1:
                lead = b[i]
                if 0x81 <= lead <= 0x9F or 0xE0 <= lead <= 0xFC:
                    used.add((lead << 8) | b[i + 1]); i += 2
                else:
                    i += 1
    return used


def kanji_table_codes(rom):
    codes = set()
    for a in range(KTAB_FILE, KTAB_END_FILE, 6):
        sjis_le = struct.unpack('<H', rom[a:a + 2])[0]
        codes.add(((sjis_le & 0xFF) << 8) | (sjis_le >> 8))
    return codes


def extend_pool(rom):
    used = used_codes_in_text()
    table = kanji_table_codes(rom)
    pool = []
    for lead in range(0x88, 0xEB):
        for trail in range(0x40, 0xFD):
            code = (lead << 8) | trail
            if not valid_sjis(code):
                continue
            if code in used or code in table:
                continue
            pool.append(code)
    return pool


def patch_word(rom, file_off, value):
    rom[file_off:file_off + 4] = struct.pack('<I', value)


def stage_a(rom):
    # 1) 폰트 48KB 복사
    rom[NEW_FONT_FILE:NEW_FONT_FILE + FONT_COPY_LEN] = rom[FONT_FILE:FONT_FILE + FONT_COPY_LEN]
    # 2) FONT_BASE 리터럴 repoint
    assert struct.unpack('<I', rom[LIT_FONTBASE:LIT_FONTBASE + 4])[0] == 0x08B974D0, 'FONT_BASE literal mismatch'
    patch_word(rom, LIT_FONTBASE, NEW_FONT_RT)
    print(f'[A] 폰트 {FONT_COPY_LEN}B 복사 {FONT_FILE:#x}->{NEW_FONT_FILE:#x}, 리터럴 0x{LIT_FONTBASE:X} -> {NEW_FONT_RT:#x}')


def stage_b(rom):
    stage_a(rom)
    # 3) 한글 글리프 블롭 주입
    blob = open(BLOB, 'rb').read()
    rom[KOR_BLOB_FILE:KOR_BLOB_FILE + len(blob)] = blob
    print(f'[B] 한글 블롭 {len(blob)}B @ {KOR_BLOB_FILE:#x} (글로벌 idx {KOR_IDX_BASE:#x}~)')

    # 4) 예약 코드 할당 (음절 -> SJIS code)
    sylmap = json.load(open(SYLMAP, encoding='utf-8'))['map']
    syllables = sorted(sylmap.keys())  # 결정적 순서 (build_korean_glyph_blob와 동일)
    pool = extend_pool(rom)
    assert len(pool) >= len(syllables), f'pool {len(pool)} < syllables {len(syllables)}'
    syl_to_code = {s: pool[i] for i, s in enumerate(syllables)}
    json.dump({s: f'0x{c:04X}' for s, c in syl_to_code.items()},
              open(os.path.join(BASE, 'data', 'syllable_to_code.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=0)

    # 5) 새 테이블 구성: 원본 536엔트리 + 한글 엔트리
    orig_tbl = bytes(rom[KTAB_FILE:KTAB_END_FILE])
    new_tbl = bytearray(orig_tbl)
    for s in syllables:
        code = syl_to_code[s]
        lead, trail = code >> 8, code & 0xFF
        top = KOR_IDX_BASE + sylmap[s]['top']
        bot = KOR_IDX_BASE + sylmap[s]['bot']
        assert top <= 0xFFFF and bot <= 0xFFFF
        new_tbl += bytes([lead, trail]) + struct.pack('<H', top) + struct.pack('<H', bot)
    rom[NEW_TBL_FILE:NEW_TBL_FILE + len(new_tbl)] = new_tbl
    print(f'[B] 테이블 {len(orig_tbl)//6}+{len(syllables)}={len(new_tbl)//6}엔트리 ({len(new_tbl)}B) @ {NEW_TBL_FILE:#x}')

    # 6) 테이블 start/end 리터럴 패치
    assert struct.unpack('<I', rom[LIT_TBL_START:LIT_TBL_START + 4])[0] == 0x08B80B7C
    assert struct.unpack('<I', rom[LIT_TBL_END:LIT_TBL_END + 4])[0] == 0x08B8180C
    patch_word(rom, LIT_TBL_START, NEW_TBL_RT)
    patch_word(rom, LIT_TBL_END, NEW_TBL_RT + len(new_tbl))
    print(f'[B] 리터럴 start->{NEW_TBL_RT:#x} end->{NEW_TBL_RT + len(new_tbl):#x}')

    # 7) hajimemashite 한글 인코딩
    assert len(HAJI_KOREAN) == len(HAJI_KANA)
    # 원본 가나 확인
    for i, kana in enumerate(HAJI_KANA):
        cur = (rom[HAJI_FILE + i*2] << 8) | rom[HAJI_FILE + i*2 + 1]
        assert cur == kana, f'kana mismatch @{HAJI_FILE+i*2:#x}: {cur:#x} != {kana:#x}'
    enc = bytearray()
    for ch in HAJI_KOREAN:
        code = syl_to_code[ch]
        enc += bytes([code >> 8, code & 0xFF])
    rom[HAJI_FILE:HAJI_FILE + len(enc)] = enc
    print(f'[B] hajimemashite -> "{HAJI_KOREAN}" 인코딩 @ {HAJI_FILE:#x}: ' +
          ' '.join(f'{syl_to_code[c]:04X}' for c in HAJI_KOREAN))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', choices=['a', 'b'], required=True)
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    rom = bytearray(open(ROM, 'rb').read())
    if args.stage == 'a':
        stage_a(rom)
        out = args.out or os.path.join(BASE, 'temp', 'poc_s2a_repoint.gba')
    else:
        stage_b(rom)
        out = args.out or os.path.join(BASE, 'temp', 'poc_s2b_korean.gba')

    # 체크섬: 헤더(0xA0..0xBC) 무변경이므로 0xBD 유지. 검증.
    chk = (-(0x19 + sum(rom[0xA0:0xBD]))) & 0xFF
    assert chk == rom[0xBD], f'header checksum 0xBD={rom[0xBD]:#x} != computed {chk:#x}'
    assert len(rom) == 0x1000000, f'rom size changed: {len(rom):#x}'
    open(out, 'wb').write(rom)
    print(f'→ {out} (size {len(rom):#x}, header chk OK)')


if __name__ == '__main__':
    main()
