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


def in_deny(a, end):
    for name, cs, ce in DENY_REGIONS:
        if a < ce and end > cs:
            return name
    return None


def patch_name_grid(rom):
    """이름 입력 그리드를 영문 A-Z / a-z / 0-9 로 교체 (이전 build_grid v56 로직 통합).

    SJIS→슬롯 테이블(0xBE717A, 보존됨)로 그리드 셀의 FONT_BASE 슬롯을 찾아 영문 글리프 주입.
    이 경로는 bulk-DMA 폰트(원본 FONT_BASE)를 쓰므로 per-char 대화 경로(0x08F00000)와 독립.
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from cell_to_slots import cell_slots, FONT_BASE
    from render_galmuri_8x16 import render_char
    SJIS_TBL = 0x08BE717A
    BLANK = bytes(32)

    def get_sjis(idx):
        o = (SJIS_TBL - 0x08000000) + idx * 2
        return (rom[o] << 8) | rom[o + 1]

    # cleanup: 그리드 폰트 슬롯 0-1023 비움 (잔여 가나 제거 → 깔끔한 영문 그리드)
    for slot in range(1024):
        off = (FONT_BASE + slot * 32) - 0x08000000
        rom[off:off + 32] = BLANK

    def valid_idxs(s, e):
        return [i for i in range(s, e + 1) if get_sjis(i) != 0]

    plan = list(zip(valid_idxs(9, 34), "ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
    plan += list(zip(valid_idxs(35, 60)[:26], "abcdefghijklmnopqrstuvwxyz"))
    plan += list(zip(valid_idxs(61, 72)[:10], "0123456789"))

    count = 0
    for idx, ch in plan:
        sjis = get_sjis(idx)
        if sjis == 0:
            continue
        sl = cell_slots(sjis)
        if not sl:
            continue
        top, bot = render_char(ch)
        for name, tile in (('top', top), ('bottom', bot)):
            off = (FONT_BASE + sl[name] * 32) - 0x08000000
            rom[off:off + 32] = tile
        count += 1
    return count


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


# v56 훅이 직접 처리하는 대화 본문 주소(중복 렌더 방지 위해 내 인코딩에서 제외) + 네임플레이트
V56_HOOKED_ADDRS = [0xDF8E16, 0xDF8DB2, 0xDF8E3E]
V56_NAMEPLATES = [0x9292A8, 0x961F30, 0x99A7D4, 0x9D3078]
V56_SKIP = set(V56_HOOKED_ADDRS + V56_NAMEPLATES)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(BASE, 'output', 'game_wars_korean_full.gba'))
    ap.add_argument('--report', default=os.path.join(BASE, 'temp', 'encode_report.csv'))
    ap.add_argument('--base', default=os.path.join(BASE, 'original', 'Game Boy Wars Advance 1+2 (Japan).gba'),
                    help='base ROM. 기본=원본. v56_polished 지정 시 영문그리드 시도(단 repoint와 충돌해 미작동 — ASM hook 필요)')
    args = ap.parse_args()

    orig = bytes(open(P.ROM, 'rb').read())   # 대화 폰트/테이블 복사 소스(원본)
    use_v56 = os.path.abspath(args.base) != os.path.abspath(P.ROM) and os.path.exists(args.base)
    rom = bytearray(open(args.base, 'rb').read()) if use_v56 else bytearray(orig)
    skip_addrs = V56_SKIP if use_v56 else set()

    # 1) 대화 per-char 폰트는 **원본**에서 0xF00000으로 복사 (base가 v56면 FONT_BASE에 영문그리드가
    #    섞여 있으므로 반드시 원본 폰트를 복사해야 대화 가나/한자가 정상)
    rom[P.NEW_FONT_FILE:P.NEW_FONT_FILE + P.FONT_COPY_LEN] = orig[P.FONT_FILE:P.FONT_FILE + P.FONT_COPY_LEN]
    assert struct.unpack('<I', rom[P.LIT_FONTBASE:P.LIT_FONTBASE + 4])[0] == 0x08B974D0
    P.patch_word(rom, P.LIT_FONTBASE, P.NEW_FONT_RT)
    blob = open(P.BLOB, 'rb').read()
    rom[P.KOR_BLOB_FILE:P.KOR_BLOB_FILE + len(blob)] = blob

    sylmap = json.load(open(P.SYLMAP, encoding='utf-8'))['map']
    syl_to_code = {s: int(c, 16) for s, c in json.load(open(SYLCODE, encoding='utf-8')).items()}

    # 테이블 확장 — 원본 한자 테이블 기반(base가 v56여도 원본 테이블 사용)
    syllables = sorted(sylmap.keys())
    orig_tbl = bytes(orig[P.KTAB_FILE:P.KTAB_END_FILE])
    new_tbl = bytearray(orig_tbl)
    for s in syllables:
        code = syl_to_code[s]
        top = P.KOR_IDX_BASE + sylmap[s]['top']
        bot = P.KOR_IDX_BASE + sylmap[s]['bot']
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
            enc = encode_text(ko, syl_to_code, unmapped)
            if len(enc) > slot:
                st['overflow'] += 1
                report.append((row['address'], ko, len(enc), slot))
                continue
            if a + slot > len(rom):
                st['oob'] += 1; continue
            # 빈 공간은 0x00(메시지 조기종료→자동넘어감 버그) 대신 공백(FILL_BYTE)으로 패딩
            # → 렌더러가 슬롯 뒤 제어코드(6B=▼입력대기)에 정상 도달.
            rom[a:a + slot] = bytes([FILL_BYTE]) * slot
            rom[a:a + len(enc)] = enc
            st['written'] += 1

    # 이름 입력 영문 그리드는 base(v56_polished)에 이미 포함됨(훅+글리프). per-char 대화 폰트는
    # 위에서 원본을 0xF00000으로 복사했으므로 그리드(FONT_BASE)와 독립.

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
    for k in ['rows', 'written', 'overflow', 'deny', 'skip_v56', 'no_ko', 'code_region', 'no_slot', 'bad_addr', 'oob']:
        print(f'  {k}: {st[k]}')
    if unmapped:
        print(f'  unmapped chars ({len(unmapped)}): {dict(unmapped.most_common(10))}')
    print(f'→ {args.out} (16MB, chk recomputed), overflow 리포트 {args.report}')


if __name__ == '__main__':
    main()
