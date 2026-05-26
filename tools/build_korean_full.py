#!/usr/bin/env python3
"""Session 3: 전체 번역문을 예약코드로 인코딩한 풀게임 한글 ROM 빌드.

build_korean_poc.stage_b 의 메커니즘(FONT_BASE repoint + 한글 글리프 주입 + 한자 테이블 확장)을
재사용하고, hajimemashite 1행 대신 **translation_for_import.csv 전체**를 인코딩한다.

인코딩 규칙 (per char):
- 한글 음절(가~힣): 예약 SJIS 코드 2바이트 (syllable_to_code.json).
- ASCII(0x20~0x7E): 1바이트 (게임 단일바이트 경로).
- 그 외(일본어 가나/한자/전각 구두점): shift_jis 2바이트 passthrough — 원본 글리프(복사본)로 렌더.
- shift_jis 실패: fallback 맵(·→・ 등), 그래도 실패면 ？(0x8148)로 치환 + 리포트.

안전:
- 슬롯 길이 = game_wars_found_texts.csv 의 length (권위). 인코딩 길이 > 슬롯이면 **skip**(원문 유지)+리포트.
- address < SAFE_MIN_ADDR(0x800000) 코드영역 skip.
- 빌드 후 헤더 체크섬(0xBD)·크기 검증.

재현: python tools/build_korean_full.py [--out output/game_wars_korean_full.gba]
"""
import argparse, csv, json, os, struct, sys, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_korean_poc as P

BASE = P.BASE
TRANS = os.path.join(BASE, 'data', 'translation_for_import.csv')
FOUND = os.path.join(BASE, 'data', 'game_wars_found_texts.csv')
SYLCODE = os.path.join(BASE, 'data', 'syllable_to_code.json')
SAFE_MIN_ADDR = 0x800000
FILL_BYTE = 0x20  # 슬롯 빈 공간 패딩(공백). 0x00은 메시지 조기종료 버그.

# 0x800000 위의 '텍스트로 오추출된' 중요 데이터 테이블 — 덮어쓰면 그리드/폰트/렌더 깨짐.
# (extraction noise가 SJIS-유사 바이트의 데이터 테이블을 텍스트로 잡음)
DENY_REGIONS = [
    ('sjis_slot_table', 0xBE717A, 0xBE717A + 5498 * 2),   # 그리드/UI SJIS→슬롯 테이블 (cell_slots 의존)
    ('font_region',     0xB974D0, 0xBAF338),              # FONT_BASE 글리프
    ('baseptr_tables',  0xB80270, 0xB80B7C),              # 가나/기호 인덱스 테이블
    ('orig_kanji_table',0xB80B7C, 0xB8180C),              # 원본 한자 테이블
    ('korean_data',     0xF00000, 0x1000000),             # 내가 주입한 글리프/테이블 영역
]

FALLBACK = {'·': '・', '∪': '∩'}  # 일부 유니코드 → SJIS 인코딩 가능 등가
# 전각 구두점 → 반각(1바이트 절약, overflow 시에만 적용). 한국어 가독성 영향 적음.
HALFWIDTH = {'！': '!', '？': '?', '，': ',', '．': '.', '：': ':', '；': ';',
             '（': '(', '）': ')', '　': ' ', '〜': '~', '～': '~'}


# 이름 입력 그리드 charset/레이아웃 데이터 (가나 시퀀스 = 그리드 글자집합 정의).
# 텍스트로 오추출됨 — 인코딩하면 그리드 셀↔글자 매핑 깨짐(글자 누락/미리보기 불가). 원본 유지 필수.
NAME_GRID_DATA = {0x805A24, 0xDA4337}
NAME_GRID_RANGES = [
    (0x83FAF0, 0x83FF00),   # 그리드 charset 클러스터(2세트: 0x83FAF6~0x83FC41, 0x83FE41~0x83FEDD)
    (0xDF8C00, 0xDF8E00),   # DF8C charset(0xDF8C62/CB2), 대화(0xDF8E16+) 앞
    (0xDF9F00, 0xDF9FF0),   # DF9F charset(0xDF9FB0)
]


def in_deny(a, end):
    if a in NAME_GRID_DATA:
        return 'name_grid_data'
    for cs, ce in NAME_GRID_RANGES:
        if a < ce and end > cs:
            return 'name_grid_data'
    for name, cs, ce in DENY_REGIONS:
        if a < ce and end > cs:
            return name
    return None


def patch_name_grid(rom):
    """이름 입력 그리드를 영문 3구역으로 교체 (정확한 구역 매핑 + 하단정렬).

    그리드 셀 idx(SJIS 테이블 0xBE717A 순서) → FONT_BASE 슬롯(공식 직접계산, sjis 검색 회피).
    구역 (RE 확정): 좌(A-Z) idx 9-34, 중(a-z) idx 41-66, 우(0-9) idx 199-208.
    모든 글자 baseline 하단정렬(top_pad = CELL_BASE - 글리프높이) → 소문자가 대문자와 같은 바닥선.
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from render_galmuri_8x16 import render_char
    from bdf import load_bdf, glyph_grid
    FONT_BASE = 0x08B974D0
    BLANK = bytes(32)
    CELL_BASE = 14  # 글리프 바닥(마지막 행)을 셀 row 13에 맞춤 → 하단정렬

    font, _ = load_bdf(os.path.join(BASE, 'reference/fonts/Galmuri11-Condensed.bdf'))

    def slots_from_idx(idx):
        page = (idx - 9) // 16
        chip = (idx - 9) % 16
        top = 128 + page * 32 + chip
        return top, top + 16  # top, bottom

    # cleanup: 그리드 폰트 슬롯 0-1023 비움 (잔여 가나/v56 글리프 제거 → 깔끔한 3구역)
    for slot in range(1024):
        off = (FONT_BASE + slot * 32) - 0x08000000
        rom[off:off + 32] = BLANK

    def inject(idx, ch):
        # 글리프 높이로 하단정렬 top_pad 계산
        h = glyph_grid(font[ord(ch)])[2] if ord(ch) in font else 11
        top_pad = max(0, CELL_BASE - h)
        top, bot = render_char(ch, top_pad=top_pad)
        ts, bs = slots_from_idx(idx)
        rom[(FONT_BASE + ts * 32) - 0x08000000:(FONT_BASE + ts * 32) - 0x08000000 + 32] = top
        rom[(FONT_BASE + bs * 32) - 0x08000000:(FONT_BASE + bs * 32) - 0x08000000 + 32] = bot

    plan = [(9 + i, c) for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")]   # 좌 A-Z
    plan += [(41 + i, c) for i, c in enumerate("abcdefghijklmnopqrstuvwxyz")]  # 중 a-z
    plan += [(199 + i, c) for i, c in enumerate("0123456789")]                 # 우 0-9
    for idx, ch in plan:
        inject(idx, ch)
    return len(plan)


def load_slots():
    slots = {}
    with open(FOUND, encoding='utf-8', errors='ignore') as f:
        for r in csv.DictReader(f):
            try:
                a = int((r.get('address') or '').strip(), 16)
            except (ValueError, TypeError):
                continue
            try:
                ln = int(r.get('length') or 0)
            except ValueError:
                ln = 0
            slots[a] = ln
    return slots


def encode_text(ko, syl_to_code, unmapped):
    out = bytearray()
    for ch in ko:
        if '가' <= ch <= '힣':
            c = syl_to_code[ch]
            out += bytes([c >> 8, c & 0xFF])
        elif 0x20 <= ord(ch) <= 0x7E:
            out += bytes([ord(ch)])
        else:
            src = FALLBACK.get(ch, ch)
            try:
                out += src.encode('shift_jis')
            except Exception:
                unmapped[ch] += 1
                out += b'\x81\x48'  # ？
    return bytes(out)


def encode_fit(ko, slot, syl_to_code, unmapped):
    """슬롯에 맞도록 단계적 압축 인코딩. 맞으면 (bytes, level), 안 맞으면 (None, level).
    level 0=원본 1=반각구두점 2=반각+공백제거 (가독성 순). 번역 의미는 보존."""
    cand = [ko,
            ''.join(HALFWIDTH.get(c, c) for c in ko),
            ''.join(HALFWIDTH.get(c, c) for c in ko).replace(' ', '')]
    for level, s in enumerate(cand):
        enc = encode_text(s, syl_to_code, unmapped)
        if len(enc) <= slot:
            return enc, level
    return None, len(cand)


# v56 훅이 직접 처리하는 대화 본문 주소(중복 렌더 방지 위해 내 인코딩에서 제외) + 네임플레이트
V56_HOOKED_ADDRS = [0xDF8E16, 0xDF8DB2, 0xDF8E3E]
V56_NAMEPLATES = [0x9292A8, 0x961F30, 0x99A7D4, 0x9D3078]
V56_SKIP = set(V56_HOOKED_ADDRS + V56_NAMEPLATES)

# --- ASM hook 방식 (repoint 폐기, 원본 FONT_BASE 보존 → 그리드+대화 양립) ---
KOR_GLYPH_FILE = 0xF00000          # 한글 글리프 블롭 (KOR_BASE=0x08F00000)
KOR_BASE_RT = 0x08F00000
HOOK_FILE = 0xF30000               # ASM hook 코드 (runtime 0x08F30000)
HOOK_RT = 0x08F30000
# hook(Thumb): 입력 r0=idx. if(idx&0x8000) r7=KOR_BASE+(idx&0x7FFF)*0x20 else r7=FONT_BASE+idx*0x20.
# ⚠️ GBA(ARMv4T)는 BLX 없음 → 변환루틴(IWRAM 0x030065E0)에서 bx r3로 hook 호출, hook은 하드코딩된
#   IWRAM 복귀주소(0x030066C9 = 0xEFE870 등가)로 bx r0 복귀. r0,r3만 clobber(이후 dead). r2 보존.
#   설계 상세: docs/research.md(2026-05-26).
# 변환루틴은 글리프소스를 2번 계산: TOP(0xEFE86E, 복귀 0xEFE870) + BOT(0xEFE8EA, 복귀 0xEFE8EC).
# 둘 다 0xEFE97C에서 base 로드 → 둘 다 hook 필요. hook_top/hook_bot은 복귀주소만 다름.
# IWRAM 매핑 선형: ROM 0xEFE788=IWRAM 0x030065E0. 0xEFE870→0x030066C8, 0xEFE8EC→0x03006744.
HOOK_RET_TOP = 0x030066C9          # 0xEFE870 | 1
HOOK_RET_BOT = 0x03006745          # 0xEFE8EC | 1

def _hook(ret):
    return bytes.fromhex(
        '0304'  # lsls r3,r0,#16   (bit15 of idx -> N flag)
        '04d4'  # bmi  +0x0E       (korean)
        '054b'  # ldr  r3,[pc,#0x14] -> FONT_BASE
        '4001'  # lsls r0,r0,#5
        'c718'  # adds r7,r0,r3
        '0648'  # ldr  r0,[pc,#0x18] -> RET
        '0047'  # bx   r0
        '044b'  # ldr  r3,[pc,#0x10] -> KOR_BASE  (kor:)
        '4004'  # lsls r0,r0,#17
        '400c'  # lsrs r0,r0,#17
        '4001'  # lsls r0,r0,#5
        'c718'  # adds r7,r0,r3
        '0248'  # ldr  r0,[pc,#0x08] -> RET
        '0047'  # bx   r0
    ) + (0x08B974D0).to_bytes(4, 'little') + (0x08F00000).to_bytes(4, 'little') + (ret).to_bytes(4, 'little')

HOOK_TOP_BYTES = _hook(HOOK_RET_TOP)
HOOK_BOT_BYTES = _hook(HOOK_RET_BOT)
HOOK_BOT_FILE = HOOK_FILE + 0x30    # 0xF30030 (hook_top|1 + 0x30 = hook_bot|1)
LIT_TRAMP = 0xEFE86C               # TOP: (lsls r0,#5; adds r7,r0,r3) → bx r3; nop
TRAMP_BYTES = bytes.fromhex('1847c046')          # bx r3 ; mov r8,r8
LIT_TRAMP_BOT = 0xEFE8E8           # BOT: (lsls r0,#5; adds r7,r0,r1) → adds r1,#0x30; bx r1
TRAMP_BOT_BYTES = bytes.fromhex('30310847')      # adds r1,#0x30 (0x3130) ; bx r1 (0x4708)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(BASE, 'output', 'game_wars_korean_full.gba'))
    ap.add_argument('--report', default=os.path.join(BASE, 'temp', 'encode_report.csv'))
    ap.add_argument('--base', default=os.path.join(BASE, 'output', 'v56_polished.gba'),
                    help='base ROM. 기본=v56_polished(영문그리드+훅). ASM hook으로 대화 한글 + 그리드 양립.')
    args = ap.parse_args()

    orig = bytes(open(P.ROM, 'rb').read())   # 원본 (테이블 소스)
    use_v56 = os.path.abspath(args.base) != os.path.abspath(P.ROM) and os.path.exists(args.base)
    rom = bytearray(open(args.base, 'rb').read()) if use_v56 else bytearray(orig)
    skip_addrs = V56_SKIP if use_v56 else set()

    # === ASM hook 방식: repoint/폰트복사 없음. 원본 FONT_BASE 보존(그리드+대화 가나/한자). ===
    # 1) 한글 글리프 블롭 → KOR_BASE(0xF00000)
    blob = open(P.BLOB, 'rb').read()
    rom[KOR_GLYPH_FILE:KOR_GLYPH_FILE + len(blob)] = blob
    # 2) ASM hook 코드 → hook_top@0xF30000, hook_bot@0xF30030
    rom[HOOK_FILE:HOOK_FILE + len(HOOK_TOP_BYTES)] = HOOK_TOP_BYTES
    rom[HOOK_BOT_FILE:HOOK_BOT_FILE + len(HOOK_BOT_BYTES)] = HOOK_BOT_BYTES
    # 3) FONT_BASE 리터럴(0xEFE97C)을 hook_top|1 로 교체 (top·bot 둘 다 이 리터럴로 base 로드)
    assert struct.unpack('<I', rom[P.LIT_FONTBASE:P.LIT_FONTBASE + 4])[0] == 0x08B974D0
    P.patch_word(rom, P.LIT_FONTBASE, HOOK_RT | 1)
    # 4) TOP 트램폴린: 0xEFE86C (lsls r0,#5; adds r7,r0,r3) → bx r3; nop  (r3=hook_top|1)
    assert bytes(rom[LIT_TRAMP:LIT_TRAMP + 4]) == bytes.fromhex('4001c718')
    rom[LIT_TRAMP:LIT_TRAMP + 4] = TRAMP_BYTES
    # 5) BOT 트램폴린: 0xEFE8E8 (lsls r0,#5; adds r7,r0,r1) → adds r1,#0x30; bx r1  (r1=hook_top|1→hook_bot|1)
    assert bytes(rom[LIT_TRAMP_BOT:LIT_TRAMP_BOT + 4]) == bytes.fromhex('40014718')
    rom[LIT_TRAMP_BOT:LIT_TRAMP_BOT + 4] = TRAMP_BOT_BYTES

    sylmap = json.load(open(P.SYLMAP, encoding='utf-8'))['map']
    syl_to_code = {s: int(c, 16) for s, c in json.load(open(SYLCODE, encoding='utf-8')).items()}

    # 5) 테이블 확장 — 원본 한자 테이블 + 한글 엔트리(idx에 bit15 마커 → hook이 KOR_BASE 사용)
    syllables = sorted(sylmap.keys())
    orig_tbl = bytes(orig[P.KTAB_FILE:P.KTAB_END_FILE])
    new_tbl = bytearray(orig_tbl)
    for s in syllables:
        code = syl_to_code[s]
        top = sylmap[s]['top'] | 0x8000
        bot = sylmap[s]['bot'] | 0x8000
        new_tbl += bytes([code >> 8, code & 0xFF]) + struct.pack('<H', top) + struct.pack('<H', bot)
    rom[P.NEW_TBL_FILE:P.NEW_TBL_FILE + len(new_tbl)] = new_tbl
    P.patch_word(rom, P.LIT_TBL_START, P.NEW_TBL_RT)
    P.patch_word(rom, P.LIT_TBL_END, P.NEW_TBL_RT + len(new_tbl))

    # 2) 전체 텍스트 인코딩
    slots = load_slots()
    st = collections.Counter()
    unmapped = collections.Counter()
    report = []
    with open(TRANS, newline='') as f:
        for row in csv.DictReader(f):
            ko = (row.get('korean') or '').strip()
            st['rows'] += 1
            if not ko:
                st['no_ko'] += 1; continue
            try:
                a = int(row['address'], 16)
            except (ValueError, TypeError):
                st['bad_addr'] += 1; continue
            if a < SAFE_MIN_ADDR:
                st['code_region'] += 1; continue
            slot = slots.get(a, 0)
            if slot <= 0:
                st['no_slot'] += 1; continue
            if a in skip_addrs:
                st['skip_v56'] += 1; continue   # v56 훅/네임플레이트가 처리 — 중복 렌더 방지
            deny = in_deny(a, a + slot)
            if deny:
                st['deny'] += 1; continue   # 중요 데이터 테이블 — 덮어쓰지 않음
            enc, level = encode_fit(ko, slot, syl_to_code, unmapped)
            if enc is None:
                st['overflow'] += 1
                report.append((row['address'], ko, encode_text(ko, syl_to_code, unmapped).__len__(), slot))
                continue
            st[f'level{level}'] += 1   # 0=원본 1=반각 2=반각+공백제거
            if a + slot > len(rom):
                st['oob'] += 1; continue
            # 빈 공간은 0x00(메시지 조기종료→자동넘어감 버그) 대신 공백(FILL_BYTE)으로 패딩
            # → 렌더러가 슬롯 뒤 제어코드(6B=▼입력대기)에 정상 도달.
            rom[a:a + slot] = bytes([FILL_BYTE]) * slot
            rom[a:a + len(enc)] = enc
            st['written'] += 1

    # 이름 입력 영문 그리드 재주입 (v56 그리드를 정확한 3구역 매핑으로 덮어씀).
    # 그리드는 원본 FONT_BASE(bulk-DMA)를 쓰므로 per-char 대화(0x08F00000)와 독립.
    st['grid_glyphs'] = patch_name_grid(rom)

    # 3) 검증 + 저장 (헤더 무변경이면 0xBD 유효, base가 v56여도 재계산해 설정)
    rom[0xBD] = (-(0x19 + sum(rom[0xA0:0xBD]))) & 0xFF
    assert len(rom) == 0x1000000
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    open(args.out, 'wb').write(rom)

    with open(args.report, 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['address', 'korean', 'encoded_len', 'slot_len'])
        for r in report:
            w.writerow(r)

    print(f'=== 인코딩 통계 (base={"v56_polished" if use_v56 else "original"}) ===')
    for k in ['rows', 'written', 'level0', 'level1', 'level2', 'overflow', 'deny', 'skip_v56', 'no_ko', 'code_region', 'no_slot', 'bad_addr', 'oob']:
        print(f'  {k}: {st[k]}')
    if unmapped:
        print(f'  unmapped chars ({len(unmapped)}): {dict(unmapped.most_common(10))}')
    print(f'→ {args.out} (16MB, chk recomputed), overflow 리포트 {args.report}')


if __name__ == '__main__':
    main()
