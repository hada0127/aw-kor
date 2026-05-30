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
    ('tilemap_renderer',0xB11B00, 0xB11E40),              # 2편/공용 타일맵 렌더러 코드
    # UI dictionary/list tables rendered by non-dialogue paths. Korean reserved
    # SJIS codes here can corrupt mode/operation/battle UI before the Hangul
    # renderer hooks see them; localize these later via their own UI path.
    ('part1_ui_text_table', 0x805100, 0x805A00),
    ('part2_ui_text_table', 0xD82740, 0xD83100),
    ('korean_data',     0xF00000, 0x1000000),             # 내가 주입한 글리프/테이블 영역
]

FALLBACK = {'·': '・', '∪': '∩'}  # 일부 유니코드 → SJIS 인코딩 가능 등가
# 전각 구두점 → 반각(1바이트 절약, overflow 시에만 적용). 한국어 가독성 영향 적음.
HALFWIDTH = {'！': '!', '？': '?', '，': ',', '．': '.', '：': ':', '；': ';',
             '（': '(', '）': ')', '　': ' ', '〜': '~', '～': '~'}

SHORTEN = [
    ('할수있', '가능'), ('할수없', '불가'), ('수있', '가능'), ('수없', '불가'),
    ('있습니다', '있음'), ('없습니다', '없음'), ('했습니다', '했음'), ('합니다', '함'),
    ('됩니다', '됨'), ('입니다', '임'), ('하십시오', '하라'), ('주세요', '줘'),
    ('하세요', '해'), ('하려면', '려면'), ('위해서', '위해'), ('때문에', '탓'),
    ('그러나', '단'), ('하지만', '단'), ('그리고', '또'), ('이번에는', '이번엔'),
    ('처음부터', '처음'), ('지금부터', '지금'), ('아군의', '아군'), ('적군의', '적군'),
    ('있는', '있'), ('없는', '없'), ('에게', '에'), ('에서', '서'), ('부터', '서'),
    ('것이다', '거다'), ('것은', '건'), ('것을', '걸'), ('것이', '게'),
]

TEXT_OVERRIDES = {
    # These 8-byte yes/no slots are not rendered as normal dialogue. The menu
    # routine samples a compact path; renderer advance hooks proved unstable, so
    # keep the original four-syllable Korean text and avoid code hooks here.
    '예아니오▼': '예아니오',
    '예아니오': '예아니오',
    '예 아니오 ▼': '예아니오',
    '예 아니오': '예아니오',
    '예　　아니오': '예  아니오',
}

ADDRESS_TEXT_OVERRIDES = {
    # Name-confirm prompt. The original translation used a long phrase whose
    # final syllables rendered poorly in this compact UI.
    0xDF8DFA: '맞습니까',
    # Name-variable dialogue. 0xDF8E3E is followed by byte 0x69 (player name)
    # and then the 0xDF8E4D suffix slot, so it must fit the original 14 bytes.
    0xDF8E3E: '뵙겠습니다.　',
    # translation_for_import.csv has a malformed row at this address whose
    # Korean field is another Japanese line. Keep the actual script line Korean.
    0xDF5E56: '우리가 지금 있는 곳은 레드스타국',
    # ASCII quotes render as symbol debris in this text engine path.
    0xDF9024: '다음 「모드선택」에서 「작전실」',
    # The original translation is one byte too long for the 14-byte fragment.
    0xDF91D0: '포함해서.',
    # Part 2 tutorial battle fragments. These slots are short and run inside
    # scripted battle text; leaving them as Japanese falls through the remapped
    # name-grid kana glyphs and produces garbage on screen.
    0xD8F33D: '그래서 휩도 병력이 적어',
    0xD8F4CD: '십자키로 움직여',
    0xD8F4FE: '에게 명령하자',
    0xD8F525: '에　Ａ버튼을',
    0xD8F53C: '눌러 봐',
    0xD8F571: '여기서　Ａ버튼이야',
    0xD8F58A: '지금 한 건',
    0xD8F5D2: '앞으로 자주 나올 말이야',
    0xD8F60C: '유닛을 잡으면 이렇게',
    0xD8F62F: '주변 색이 바뀌어',
    0xD8F677: '먼저 적에게 다가가자',
    0xD8F6CF: '여기 두고　Ａ로 이동해',
    0xD8F713: '지금은 여기로 이동해',
    0xD8F738: '여기 두고　Ａ버튼',
    0xD8F78F: '여기서',
    0xD8F7A7: '를 고르면 이동',
    0xD8F7EE: '색이 바뀌었지',
    0xD8F838: '뜻이야',
    0xD8F84B: '나중에 또 쓸 수 있어',
    0xD8F86C: '안심해',
    0xD8F882: '그럼 이 기세로 이쪽의',
    0xD8F8A7: '이동해 보자',
    0xD8F909: '여기서　Ａ버튼이야',
    0xD8F92C: '가 적에게 가까운 곳은 여기야',
    0xD8FBA5: '가 오고 있어',
    0xD8FE6C: 'Ａ버튼 전투시작',
}

POST_TEXT_RESTORE = {
    # v56 blanked 0xDF8DB2..0xDF8DCE, two bytes past the 26-byte prompt slot.
    # Restore the original wait/newline terminator or the parser runs into the
    # following name-grid data and corrupts the prompt/subsequent dialogue.
    0xDF8DCC: bytes.fromhex('6b0a0000'),
}

INTRO_DIRECT_TEXT = {
    # Part 2 first intro uses the same name-control layout as the Part 1 intro:
    # text fragment, byte 0x69 for the entered player name, then さん/さん！.
    0xDF5D9A: ('뵙겠습니다。　', 14),
    # These fragments surround the runtime player-name control byte. The generic
    # slot fitter removes punctuation to save bytes, but this intro has enough
    # room and needs the period/spacing to read naturally.
    0xDF8E3E: ('뵙겠습니다。', 14),
    0xDF8E58: ('나는　캐서린。', 16),
}

RESTORE_SYMBOL_CODES = [
    0x8142,  # 。
    0x8148,  # ？
    0x8149,  # ！
]


# 이름 입력 그리드 charset/레이아웃 데이터 (가나 시퀀스 = 그리드 글자집합 정의).
# 텍스트로 오추출됨 — 인코딩하면 그리드 셀↔글자 매핑 깨짐(글자 누락/미리보기 불가). 원본 유지 필수.
NAME_GRID_DATA = {0x805A24, 0xDA4337}
NAME_GRID_RANGES = [
    (0x83FAF0, 0x83FF00),   # 그리드 charset 클러스터(2세트: 0x83FAF6~0x83FC41, 0x83FE41~0x83FEDD)
    (0xDF8C00, 0xDF8E00),   # DF8C charset(0xDF8C62/CB2), 대화(0xDF8E16+) 앞
    (0xDF9F00, 0xDF9FF0),   # DF9F charset(0xDF9FB0)
]

TEXT_ALLOW_ADDRS = {0xDF8DB2, 0xDF8DD2, 0xDF8DFA}


def in_deny(a, end):
    if a in TEXT_ALLOW_ADDRS:
        return None
    if a in NAME_GRID_DATA:
        return 'name_grid_data'
    for cs, ce in NAME_GRID_RANGES:
        if a < ce and end > cs:
            return 'name_grid_data'
    for name, cs, ce in DENY_REGIONS:
        if a < ce and end > cs:
            return name
    return None


# ── 이름 그리드 ground-truth 슬롯맵 (2026-05-26 RE 확정) ──────────────────────────
# 신규 원본 이름화면 VRAM 덤프 → BG0(screenblock14, charblock0) 타일맵에서 각 셀의 타일ID →
# charblock0 VRAM 타일을 ROM FONT_BASE 슬롯과 exact-byte 역매칭(팔레트 리맵 없음 확인) →
# 셀→슬롯 ground-truth 도출. 관계 top_slot = bottom_slot - 16 (전 셀 일관 검증).
# 좌(A-Z): 카타카나 ア~ハ 슬롯(우연히 slots_from_idx와 일치). 중(a-z): マ~ー 슬롯(불연속 — 작은가나
#   ァィゥェォ/ッャュョー은 별도 블록). 우(0-9): 전각숫자 ０-９ 전용 슬롯(291-300/307-316).
# ※ 이전 코드 버그: 중간 a-z는 slots_from_idx(41+)=192부터로 어긋났고(참값 174부터), 숫자는
#   idx9-18 extra(완전 오류, 참값 291-300). 또 슬롯 0-1023 블랭크가 원본 숫자글리프(291-300)를 지움.
# (검증 스크립트: temp/grid_slotmap.json, temp/sim_render.py)
# 가나 슬롯 테이블 RE (2026-05-26, codex 검증):
#   변환루틴 0x08EFE788. 가나(0x8340-0x8397)는 base8=*(0x08B80278)=0x08B8087C 테이블 사용.
#   kidx = ((SJIS-0x8140)&0xFFF8)*2 + (SJIS&7) - 0x400.   top=base8[kidx], bottom=base8[kidx+8].
#   → 이 테이블을 패치하면 각 가나 셀의 top/bottom 슬롯을 자유 지정 가능(그리드+대화 공유 주의).
KANA_TBL = 0x08B8087C
def _kidx(sjis):
    return (((sjis - 0x8140) & 0xFFF8) * 2 + (sjis & 7)) - 0x400

# 작은가나(q-y)·ン(p) 슬롯 재배치: 원본은 일부 top/bottom 슬롯을 공유한다.
# base8 테이블에서 q-y top/bottom + p bottom 을 미사용 빈 슬롯으로 옮겨
# 이름 미리보기와 이후 대화에서도 26자 전부 고유 슬롯을 쓰게 한다.
# (미사용 빈 슬롯: temp 스캔으로 확인, base8 미참조 + all-zero)
KANA_REMAP = {
    # SJIS : [(which, new_slot), ...] where which is "top" or "bot".
    0x8340: [('top', 328), ('bot', 349)],  # q ァ
    0x8342: [('top', 329), ('bot', 350)],  # r ィ
    0x8344: [('top', 330), ('bot', 351)],  # s ゥ
    0x8346: [('top', 332), ('bot', 352)],  # t ェ
    0x8348: [('top', 333), ('bot', 353)],  # u ォ
    0x8362: [('top', 334), ('bot', 354)],  # v ッ
    0x8383: [('top', 344), ('bot', 355)],  # w ャ
    0x8385: [('top', 345), ('bot', 356)],  # x ュ
    0x8387: [('top', 346), ('bot', 357)],  # y ョ
    0x8393: [('bot', 348)],                # p ン (bottom 220→348, n=ワ는 220 유지)
}

# 셀 → (top_slot, bot_slot). 슬롯 프로브(니블1-9 마커)로 ground-truth 확정 + KANA_REMAP 반영.
NAME_GRID_SLOTS = {
    # 좌 A-Z
    'A': (128, 144), 'B': (129, 145), 'C': (130, 146), 'D': (131, 147), 'E': (132, 148),
    'F': (133, 149), 'G': (134, 150), 'H': (135, 151), 'I': (136, 152), 'J': (137, 153),
    'K': (138, 154), 'L': (139, 155), 'M': (140, 156), 'N': (141, 157), 'O': (142, 158),
    'P': (143, 159), 'Q': (160, 176), 'R': (161, 177), 'S': (162, 178), 'T': (163, 179),
    'U': (164, 180), 'V': (165, 181), 'W': (166, 182), 'X': (167, 183), 'Y': (168, 184),
    'Z': (169, 185),
    # 중 a-z (q-y top·p bottom 은 KANA_REMAP으로 fresh 슬롯 재배치 → 26자 전부 고유)
    'a': (174, 190), 'b': (175, 191), 'c': (192, 208), 'd': (193, 209), 'e': (194, 210),
    'f': (195, 211), 'g': (196, 212), 'h': (197, 213), 'i': (198, 214), 'j': (199, 215),
    'k': (200, 216), 'l': (201, 217), 'm': (202, 218), 'n': (203, 220), 'o': (1508, 1524),
    'p': (204, 348), 'q': (328, 349), 'r': (329, 350), 's': (330, 351), 't': (332, 352),
    'u': (333, 353), 'v': (334, 354), 'w': (344, 355), 'x': (345, 356), 'y': (346, 357),
    'z': (290, 306),
    # 우 0-9 (전각숫자 슬롯)
    '0': (291, 307), '1': (292, 308), '2': (293, 309), '3': (294, 310), '4': (295, 311),
    '5': (296, 312), '6': (297, 313), '7': (298, 314), '8': (299, 315), '9': (300, 316),
}
# Some name renderers bypass the remapped kana table and keep using the original
# small-kana bottom slots. Mirror the same Latin glyphs there so grid, preview,
# and later player-name insertion agree.
NAME_GRID_MIRROR_SLOTS = {
    'q': [(328, 252)], 'r': [(329, 253)], 's': [(330, 254)],
    't': [(332, 256)], 'u': [(333, 257)], 'v': [(334, 259)],
    'w': [(344, 258)], 'x': [(345, 260)], 'y': [(346, 261)],
}
# 영문 그리드 미사용 셀(좌영역 Z 뒤 ヒフヘホ) top 슬롯 → 블랭크.
NAME_GRID_BLANK_TOPSLOTS = [170, 171, 172, 173]

NAME_GRID_ROW_LAYOUTS = {
    # Live row strings drawn by 0x08B48910..0x08B48960 via 0x08B1311C.
    # Encoding is raw Shift-JIS bytes, with 0A 09 prefix and 0A 00 00 00 row terminator.
    # Middle area keeps the original selectable gaps. Removing those gaps makes
    # visual cells disagree with the input/preview lookup (for example k -> i).
    # The right-side symbol row is blanked.
    0x08DF8C38: [0x8341, 0x8343, 0x8345, 0x8347, 0x8349, 0x8140,
                 0x837D, 0x837E, 0x8380, 0x8381, 0x8382, 0x8140,
                 0x824F, 0x8250, 0x8251, 0x8252, 0x8253],
    0x08DF8C60: [0x834A, 0x834C, 0x834E, 0x8350, 0x8352, 0x8140,
                 0x8384, 0x8140, 0x8386, 0x8140, 0x8388, 0x8140,
                 0x8254, 0x8255, 0x8256, 0x8257, 0x8258],
    0x08DF8C88: [0x8354, 0x8356, 0x8358, 0x835A, 0x835C, 0x8140,
                 0x8389, 0x838A, 0x838B, 0x838C, 0x838D, 0x8140,
                 0x8140, 0x8140, 0x8140, 0x8140, 0x8140],
    0x08DF8CB0: [0x835E, 0x8360, 0x8363, 0x8365, 0x8367, 0x8140,
                 0x838F, 0x8140, 0x8392, 0x8140, 0x8393],
    0x08DF8CCC: [0x8369, 0x836A, 0x836B, 0x836C, 0x836D, 0x8140,
                 0x8340, 0x8342, 0x8344, 0x8346, 0x8348],
    0x08DF8CE8: [0x836E, 0x8371, 0x8374, 0x8377, 0x837A, 0x8140,
                 0x8362, 0x8383, 0x8385, 0x8387, 0x815B],
}

def _name_grid_row_bytes(codes):
    return b'\x0A\x09' + b''.join(struct.pack('>H', c) for c in codes) + b'\x0A\x00\x00\x00'


def patch_name_grid(rom):
    """이름 입력 그리드를 영문 3구역(좌 A-Z / 중 a-z / 우 0-9)으로 교체.

    ① base8 가나 슬롯 테이블 패치(KANA_REMAP): q-y top·p bottom 을 fresh 슬롯으로 → 26자 전부 고유.
    ② NAME_GRID_SLOTS 슬롯에 영문 글리프 주입(하단정렬). 미사용 셀 블랭크.
    ③ live 행 문자열(0x08DF8C38 계열)을 패치하되, 선택 로직과 맞는 원본 중간 갭은 유지.
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from render_galmuri_8x16 import render_char
    from bdf import load_bdf, glyph_grid
    FONT_BASE = 0x08B974D0
    BLANK = bytes(32)
    CELL_BASE = 14  # 글리프 바닥(마지막 행)을 셀 row 13에 맞춤 → 하단정렬

    font, _ = load_bdf(os.path.join(BASE, 'reference/fonts/Galmuri11-Condensed.bdf'))

    # ① base8 가나 테이블 패치
    for sjis, remaps in KANA_REMAP.items():
        for which, newslot in remaps:
            kidx = _kidx(sjis) + (8 if which == 'bot' else 0)
            off = (KANA_TBL + kidx * 2) - 0x08000000
            rom[off:off + 2] = struct.pack('<H', newslot)

    def write_slot(slot, data):
        off = (FONT_BASE + slot * 32) - 0x08000000
        rom[off:off + 32] = data

    def inject(ch):
        top_slot, bot_slot = NAME_GRID_SLOTS[ch]
        h = glyph_grid(font[ord(ch)])[2] if ord(ch) in font else 11
        top_pad = max(0, CELL_BASE - h)
        top, bot = render_char(ch, top_pad=top_pad)
        write_slot(top_slot, top)
        write_slot(bot_slot, bot)

    for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789":
        inject(ch)
        for top_slot, bot_slot in NAME_GRID_MIRROR_SLOTS.get(ch, []):
            h = glyph_grid(font[ord(ch)])[2] if ord(ch) in font else 11
            top_pad = max(0, CELL_BASE - h)
            top, bot = render_char(ch, top_pad=top_pad)
            write_slot(top_slot, top)
            write_slot(bot_slot, bot)
    for top_slot in NAME_GRID_BLANK_TOPSLOTS:   # 미사용 좌영역 셀 비움
        write_slot(top_slot, BLANK)
        write_slot(top_slot + 16, BLANK)

    for addr, codes in NAME_GRID_ROW_LAYOUTS.items():
        new = _name_grid_row_bytes(codes)
        off = addr - 0x08000000
        old = rom[off:off + len(new)]
        assert old[:2] == b'\x0A\x09' and old[-4:] == b'\x0A\x00\x00\x00'
        rom[off:off + len(new)] = new
    return len(NAME_GRID_SLOTS)


def _symbol_table_index(sjis):
    return (((sjis + 0xFFFF7EC0) & 0xFFF8) << 1) + (sjis & 7)


def restore_symbol_glyphs(rom, orig):
    """Recover punctuation tiles that the v56/name-grid base leaves blank."""
    font_file = 0xB974D0
    symbol_tbl = 0xB8027C
    restored = set()
    for sjis in RESTORE_SYMBOL_CODES:
        idx = _symbol_table_index(sjis)
        for table_delta in (0, 8):
            slot = struct.unpack_from('<H', orig, symbol_tbl + (idx + table_delta) * 2)[0]
            if slot == 95 or slot in restored:
                continue
            off = font_file + slot * 32
            rom[off:off + 32] = orig[off:off + 32]
            restored.add(slot)
    return len(restored)


def patch_part2_battle_obj_labels(rom):
    """Patch small OBJ-tile labels used by the Part 2 battle terrain popup."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from bdf import load_bdf, glyph_grid

    font, _ = load_bdf(os.path.join(BASE, 'reference/fonts/Galmuri11-Condensed.bdf'))

    def render_tiles(text, width, height=16, x=0, y=2, ink=1, shadow=15):
        pixels = [[0] * width for _ in range(height)]
        cursor = x
        for ch in text:
            if ord(ch) not in font:
                cursor += 8
                continue
            grid, w, h, xo, _yo = glyph_grid(font[ord(ch)])
            for row in range(h):
                for col in range(w):
                    if not grid[row][col]:
                        continue
                    px = cursor + col + xo
                    py = y + row
                    if 0 <= px + 1 < width and 0 <= py + 1 < height and pixels[py + 1][px + 1] == 0:
                        pixels[py + 1][px + 1] = shadow
                    if 0 <= px < width and 0 <= py < height:
                        pixels[py][px] = ink
            cursor += 8

        tiles = []
        for ty in range(height // 8):
            for tx in range(width // 8):
                tile = bytearray(32)
                for row in range(8):
                    for col in range(8):
                        value = pixels[ty * 8 + row][tx * 8 + col]
                        bi = row * 4 + col // 2
                        if col & 1:
                            tile[bi] = (tile[bi] & 0x0F) | (value << 4)
                        else:
                            tile[bi] = (tile[bi] & 0xF0) | value
                tiles.append(bytes(tile))
        return tiles

    def write_tiles(start, tiles):
        for idx, tile in enumerate(tiles):
            rom[start + idx * 32:start + idx * 32 + 32] = tile

    # The terrain name is drawn as a 16x16 OBJ followed by an 8x16 OBJ. The
    # source tiles are stored sequentially, but the first OBJ expects its two
    # rows before the second OBJ's top/bottom tiles.
    terrain = render_tiles('평지', 24, x=3, y=2)
    write_tiles(0xB93CD0, [terrain[i] for i in (0, 1, 3, 4, 2, 5)])
    write_tiles(0xB93BD0, render_tiles('육', 16, x=4, y=2))
    return 2


def patch_part2_mission_start_obj(rom):
    """Replace the Part 2 battle-start OBJ label sheet with Korean text."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from bdf import load_bdf, glyph_grid
    from lz77_compress import lz77_compress
    from lz77_scan import lz77_decompress

    off = 0xC10B34
    dec = lz77_decompress(rom, off)
    if dec is None:
        raise AssertionError(f'invalid mission-start LZ77 block at 0x{off:X}')
    tile_data, consumed = dec
    width, height = 128, 32
    pixels = [[0] * width for _ in range(height)]
    font, _ = load_bdf(os.path.join(BASE, 'reference/fonts/Galmuri11-Condensed.bdf'))

    def draw_scaled(text, x, y, scale=2, ink=10, shadow=14):
        cursor = x
        for ch in text:
            if ord(ch) not in font:
                cursor += 4 * scale
                continue
            grid, w, h, xo, _yo = glyph_grid(font[ord(ch)])
            for row in range(h):
                for col in range(w):
                    if not grid[row][col]:
                        continue
                    for sy in range(scale):
                        for sx in range(scale):
                            px = cursor + (col + xo) * scale + sx
                            py = y + row * scale + sy
                            if 0 <= px + 1 < width and 0 <= py + 1 < height and pixels[py + 1][px + 1] == 0:
                                pixels[py + 1][px + 1] = shadow
                            if 0 <= px < width and 0 <= py < height:
                                pixels[py][px] = ink
            cursor += (w + 1) * scale if ch != '!' else 4 * scale

    # The original block packs several Japanese labels. On the battle-start
    # screen the unused labels can bleed in around the main banner, so clear the
    # sheet and redraw only the active battle-start text.
    draw_scaled('전투개시!', 14, 4)

    out = bytearray(len(tile_data))
    # The banner is displayed as two 64x32 OBJs: tile 0x00 for the left half
    # and tile 0x20 for the right half. Pack the 128x32 canvas into that layout.
    for ty in range(4):
        for tx in range(16):
            tile_idx = ty * 8 + tx if tx < 8 else 0x20 + ty * 8 + (tx - 8)
            for row in range(8):
                for col in range(8):
                    value = pixels[ty * 8 + row][tx * 8 + col] & 0x0F
                    bi = tile_idx * 32 + row * 4 + col // 2
                    if col & 1:
                        out[bi] |= value << 4
                    else:
                        out[bi] |= value

    comp = lz77_compress(bytes(out), vram_safe=True)
    if len(comp) > consumed:
        raise AssertionError(f'mission-start LZ77 overflow: {len(comp)} > {consumed}')
    rom[off:off + consumed] = comp + bytes(consumed - len(comp))
    return 1


def patch_part2_companion_hud_name(rom):
    """Patch the fixed Part 2 battle HUD OBJ name label for Catherine."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from bdf import load_bdf, glyph_grid

    font, _ = load_bdf(os.path.join(BASE, 'reference/fonts/Galmuri7.bdf'))
    width, height = 32, 8
    pixels = [[0] * width for _ in range(height)]
    cursor = 5
    for ch in '캐서린':
        grid, w, h, xo, _yo = glyph_grid(font[ord(ch)])
        for row in range(h):
            for col in range(w):
                if not grid[row][col]:
                    continue
                px = cursor + col + xo
                py = row
                if 0 <= px + 1 < width and 0 <= py + 1 < height and pixels[py + 1][px + 1] == 0:
                    pixels[py + 1][px + 1] = 3
                if 0 <= px < width and 0 <= py < height:
                    pixels[py][px] = 1
        cursor += w + 1

    out = bytearray()
    for tx in range(width // 8):
        tile = bytearray(32)
        for row in range(8):
            for col in range(8):
                value = pixels[row][tx * 8 + col] & 0x0F
                bi = row * 4 + col // 2
                if col & 1:
                    tile[bi] |= value << 4
                else:
                    tile[bi] |= value
        out += tile

    off = 0xBD00B0
    rom[off:off + len(out)] = out
    return 1


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
        elif ch == '　':
            out += b'\x81\x40'
        elif ch == ' ':
            out += b'\x20'
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


def patch_name_honorific_fragments(rom, syl_to_code, unmapped):
    """Localize name-control suffix fragments like <0x69>さん in scripts."""
    honorific = encode_text('　님', syl_to_code, unmapped)
    replacements = [
        (b'\x69\x82\xB3\x82\xF1\x82\xCD', b'\x69' + honorific + encode_text('은', syl_to_code, unmapped)),
        (b'\x69\x82\xB3\x82\xF1\x82\xAA', b'\x69' + honorific + encode_text('이', syl_to_code, unmapped)),
        (b'\x69\x82\xB3\x82\xF1\x81\x41', b'\x69' + honorific + b'\x81\x41'),
        (b'\x69\x82\xB3\x82\xF1\x81\x49', b'\x69' + honorific + b'\x81\x49'),
        (b'\x69\x82\xB3\x82\xF1\x72', b'\x69' + honorific + b'\x72'),
        (b'\x69\x82\xB3\x82\xF1', b'\x69' + honorific),
    ]
    patched = 0
    for old, new in replacements:
        if len(old) != len(new):
            raise AssertionError('name honorific replacement length mismatch')
        pos = 0
        while True:
            idx = rom.find(old, pos)
            if idx < 0:
                break
            rom[idx:idx + len(old)] = new
            patched += 1
            pos = idx + len(new)
    return patched


def encode_fit(ko, slot, syl_to_code, unmapped):
    """슬롯에 맞도록 단계적 압축 인코딩.

    맞으면 (bytes, level), 안 맞으면 None을 돌려 원문을 유지한다.
    level 0=정규화 1=축약규칙.
    """
    normalized = ''.join(HALFWIDTH.get(c, c) for c in ko)
    normalized = ''.join(c for c in normalized if c not in ',.!?:;()[]{}"\'‘’“”・…。、「」『』▼')
    spaced = normalized.replace(' ', '　')
    cand = [spaced]
    shortened = spaced
    for src, dst in SHORTEN:
        shortened = shortened.replace(src, dst)
    cand.append(shortened)
    # Fallback: keep Korean coverage when full-width spaces do not fit.
    # ASCII spaces are ignored by the Part 1 renderer, but this is still better
    # than dropping many more translated lines back to Japanese.
    cand.append(normalized)
    shortened_ascii = normalized
    for src, dst in SHORTEN:
        shortened_ascii = shortened_ascii.replace(src, dst)
    cand.append(shortened_ascii)
    for level, s in enumerate(cand):
        if any('가' <= ch <= '힣' and ch not in syl_to_code for ch in s):
            continue
        enc = encode_text(s, syl_to_code, unmapped)
        if len(enc) <= slot:
            return enc, level

    return None, 5


# v56 base has a Galmuri11 overlay hook for early dialogues. Keep the name-grid
# base ROM, but disable that overlay in main() so all dialogue, including
# welcome, uses the same per-character Korean glyph path.
V56_HOOKED_ADDRS = []
V56_NAMEPLATES = [0x9292A8, 0x961F30, 0x99A7D4, 0x9D3078]
V56_SKIP = set(V56_HOOKED_ADDRS + V56_NAMEPLATES)

V56_OVERLAY_ADDR_TABLE = 0xA3CF48
V56_OVERLAY_ADDR_TABLE_LEN = 12

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

# --- Advance 2 tilemap renderers ---
# 0x08B11Cxx and 0x08313xxx do not copy glyph pixels per character. They read table top/bot
# tile entries and write them directly to a BG tilemap. Korean entries therefore keep the
# bit15 marker in the relocated tables, but the tilemap hooks below consume the marker:
# copy KOR_BASE[local tile] to a dynamic VRAM tile (0x300 + screen-entry-position)
# and write that real tile id instead. The marker is never allowed to reach the BG
# screen entry.
PART2_HOOK_TOP_313_FILE = HOOK_FILE + 0x100
PART2_HOOK_BOT_313_FILE = HOOK_FILE + 0x160
PART2_HOOK_TOP_B11_FILE = HOOK_FILE + 0x1C0
PART2_HOOK_BOT_B11_FILE = HOOK_FILE + 0x220
PART2_HOOK_A3_FILE = HOOK_FILE + 0x280
PART2_HOOK_A3_SPACE_FILE = HOOK_FILE + 0x340
PART2_HOOK_SPACE_313_FILE = HOOK_FILE + 0x360
PART2_HOOK_SPACE_B11_FILE = HOOK_FILE + 0x3A0
PART1_YESNO_HOOK_FILE = 0xF10000
PART2_HOOK_TOP_313_RT = 0x08F30100
PART2_HOOK_BOT_313_RT = 0x08F30160
PART2_HOOK_TOP_B11_RT = 0x08F301C0
PART2_HOOK_BOT_B11_RT = 0x08F30220
PART2_HOOK_A3_RT = 0x08F30280
PART2_HOOK_A3_SPACE_RT = 0x08F30340
PART2_HOOK_SPACE_313_RT = 0x08F30360
PART2_HOOK_SPACE_B11_RT = 0x08F303A0
PART1_YESNO_HOOK_RT = 0x08F10000
PART1_YESNO_CALL_SITE = 0xB18D2C
PART1_YESNO_CALL_EXPECT = bytes.fromhex('fff7c8ff')  # bl 0x08B18CC0
PART1_YESNO_ORIG_FN = 0x08B18CC0

def _thumb_bl(src_rt, dst_rt):
    off = dst_rt - (src_rt + 4)
    if off < -(1 << 22) or off >= (1 << 22) or (off & 1):
        raise ValueError(f'Thumb BL out of range: {src_rt:#x}->{dst_rt:#x}')
    hi = 0xF000 | ((off >> 12) & 0x7FF)
    lo = 0xF800 | ((off >> 1) & 0x7FF)
    return struct.pack('<HH', hi, lo)

def _part1_yesno_hook():
    # Called around part1's compact choice cursor update. The original compact
    # renderer writes "아 니 오" for the name-confirm yes/no buffer, then clears
    # the middle cell, so the final row becomes "아 오". Saved states can also
    # carry the older two-syllable buffer that only leaves "아". Run the original
    # update first, refresh the needed glyph-cache tiles, and rewrite only those
    # exact tilemap-buffer signatures to "예 아니오".
    b = bytearray(bytes.fromhex(
        'ffb5'      # push {r0-r7,lr}
        '00000000'  # bl original compact-choice update (patched below)
        '2b4801882b4a914202d02a4a91422bd1'
        '2a482a4900f029f82a482a4900f025f82a482a4900f021f8'
        '2a482a4900f01df82a482a4900f019f82a482a4900f015f8'
        '2a482a4900f011f82a482a4900f00df8174800f012f8'
        '284800f01cf8284800f00cf8274800f016f8'
        'ffbd'
        '082203680b6004300431013af9d17047'
        '22490180224941800c4981800a49c180204901811e4941817047'
        '1f4901801c4941801e4981801e49c1801e490181184941817047'
        '184e0102'  # 0x02014E18, source top row x10
        'e6800000'  # fresh-route signature tile: 0x80E6
        'e4800000'  # saved-state signature tile: 0x80E4
        '0046f008401c00062046f008601c0006'  # 예 top/bot -> tiles E2/E3
        'c03ff008801c0006e03ff008a01c0006'  # 아 top/bot -> tiles E4/E5
        '4018f008c01c00062015f008e01c0006'  # 니 top/bot -> tiles E6/E7
        'a046f008001d0006c046f008201d0006'  # 오 top/bot -> tiles E8/E9
        '584e0102'  # 0x02014E58, source bottom row x10
        'd4600006'  # 0x060060D4, visible top row x10
        '14610006'  # 0x06006114, visible bottom row x10
        'e2800000'  # 예 top tile
        '64010000'  # blank tile
        'e8800000'  # 니 top tile
        'e3800000'  # 예 bottom tile
        'e5800000'  # 아 bottom tile
        'e7800000'  # 니 bottom tile
        'e9800000'  # 오 bottom tile
    ))
    b[2:6] = _thumb_bl(PART1_YESNO_HOOK_RT + 2, PART1_YESNO_ORIG_FN)
    return bytes(b)

PART1_YESNO_HOOK = _part1_yesno_hook()

# Assembled for ARM7TDMI Thumb. Patch offset 0x4c with the Thumb return address.
PART2_HOOK_TOP_TEMPLATE = bytes.fromhex(
    '1188080404d40698084318800f480047'
    'fcb44904490c7f20c0461c1c64080440c020800024180a4d49016d18094e6701f619'
    '83cd83c683cd83c603cd03c60c9820431880fcbc014800470000'
    '00000000'  # return literal
    '0000f008'  # KOR_BASE_RT
    '00000006'  # VRAM base 0x06000000
)
PART2_HOOK_BOT_TEMPLATE = bytes.fromhex(
    '01880a0404d4069a0a431a800f490847'
    'ffb44904490c7f20c0461c1c64080440c020800024180a4d49016d18094e6701f619'
    '83cd83c683cd83c603cd03c60e9820431880ffbc014908470000'
    '00000000'  # return literal
    '0000f008'  # KOR_BASE_RT
    '00000006'  # VRAM base 0x06000000
)

# Hook for the IWRAM-copied glyph-cache renderer sourced at 0x08A3C7C0.
# The original fallback is at 0x08A3C820: linked glyph miss rewrites the current
# code as 0x8148 ('?') and restarts lookup. We hook immediately after the
# prologue/source byte load site, before fallback can run. Korean reserved SJIS
# codes are resolved through the relocated 6-byte table and copied from KOR_BASE
# into the two destination VRAM tiles that this renderer would normally fill.
PART2_HOOK_A3 = bytes.fromhex(
    '0478417804911d4a3f2932d923020b431b4eb3422dd31b4eb3422ad81a4e1b4fbe4226d2'
    '32781202707802439a4201d00636f5e7708802041bd5b188144b1840194040014901134a80'
    '1889180c1c6d01114aad18061c2f1c0fce0fc70fce0fc7261c20352f1c0fce0fc70fce0f'
    'c70b4800470498014a3f28094b1847'
    '60f95208'  # glyph-cache page pointer table literal: 0x0852F960
    '40880000'  # min Korean reserved SJIS: 0x8840
    '69930000'  # max Korean reserved SJIS: 0x9369
    '0000f208'  # relocated table start: 0x08F20000
    'b424f208'  # relocated table end: 0x08F224B4
    'ff7f0000'  # strip bit15 marker
    '0000f008'  # KOR_BASE_RT
    '00000006'  # VRAM base 0x06000000
    'c1610003'  # Korean handled return: IWRAM epilogue 0x030061C1
    '8d600003'  # non-Korean return: IWRAM 0x0300608D
)

# The Advance 2 tilemap renderers are SJIS-oriented: at their main loop they only
# branch on NUL/newline, then treat every other byte as a two-byte code. Korean
# prose keeps ASCII 0x20 spaces, so add a one-byte space path that advances the
# tile cursor by one cell and consumes exactly one input byte.
PART2_HOOK_SPACE_313 = bytes.fromhex(
    '307800280fd00a280bd0202801d007480047404601300004000c80460136044800470448004704480047c046'
    'c33d3108'  # non-control: 0x08313DC2|1
    'd73f3108'  # loop:        0x08313FD6|1
    'e33f3108'  # newline:     0x08313FE2|1
    'ed3f3108'  # exit:        0x08313FEC|1
)
PART2_HOOK_SPACE_B11 = bytes.fromhex(
    '307800280fd00a280bd0202801d007480047404601300004000c80460136044800470448004704480047c046'
    'e31bb108'  # non-control: 0x08B11BE2|1
    'ff1db108'  # loop:        0x08B11DFE|1
    '0b1eb108'  # newline:     0x08B11E0A|1
    '151eb108'  # exit:        0x08B11E14|1
)

# MODE SELECT's A3 glyph-cache function is reached after the text parser has
# already classified the byte. ASCII space never reaches 0x08A3C7E8: the first
# parser jump-table entry consumes one byte at 0x0831431C without touching x.
# Patch the 0x20 table entry to consume one byte and advance state[0x32] by one
# 8px BG column, then return like a normal handled char.
PART2_HOOK_A3_SPACE = bytes.fromhex(
    '286a01302862291c3231087801300870032001490847c046'
    'f7473108'  # parser handled return: 0x083147F6|1
)

def _assert_relocated_korean_indices(new_tbl, sylmap, syl_to_code):
    by_code = {}
    for off in range(0, len(new_tbl), 6):
        code = (new_tbl[off] << 8) | new_tbl[off + 1]
        top, bot = struct.unpack_from('<HH', new_tbl, off + 2)
        by_code[code] = (top, bot)
    for ch in ('매', '플', '할', '즐', '혈'):
        code = syl_to_code[ch]
        top, bot = by_code[code]
        expected_top = sylmap[ch]['top'] | 0x8000
        expected_bot = sylmap[ch]['bot'] | 0x8000
        if (top, bot) != (expected_top, expected_bot):
            raise AssertionError(
                f'{ch} table idx mismatch: got {top & 0x7fff}/{bot & 0x7fff}, '
                f'expected {expected_top & 0x7fff}/{expected_bot & 0x7fff}'
            )

def _part2_hook(template, ret):
    b = bytearray(template)
    struct.pack_into('<I', b, 0x4C, ret)
    return bytes(b)

def _abs_tramp(reg, hook_rt):
    # 8-byte far Thumb trampoline: ldr reg,[pc,#0]; bx reg; .word hook|1
    if reg == 0:
        return bytes.fromhex('00480047') + struct.pack('<I', hook_rt | 1)
    if reg == 1:
        return bytes.fromhex('00490847') + struct.pack('<I', hook_rt | 1)
    if reg == 2:
        return bytes.fromhex('004a1047') + struct.pack('<I', hook_rt | 1)
    raise ValueError(reg)

PART2_HOOK_TOP_313 = _part2_hook(PART2_HOOK_TOP_TEMPLATE, 0x08313FC1)
PART2_HOOK_BOT_313 = _part2_hook(PART2_HOOK_BOT_TEMPLATE, 0x08313FD1)
PART2_HOOK_TOP_B11 = _part2_hook(PART2_HOOK_TOP_TEMPLATE, 0x08B11DE9)
PART2_HOOK_BOT_B11 = _part2_hook(PART2_HOOK_BOT_TEMPLATE, 0x08B11DF9)

PART2_PATCHES = [
    # name, table_start_lit, table_end_lit, top_site, bottom_site, top_hook_rt, bottom_hook_rt
    ('part2_313', 0x313FFC, 0x314000, 0x313FB8, 0x313FC8, PART2_HOOK_TOP_313_RT, PART2_HOOK_BOT_313_RT),
    ('tilemap_B11', 0xB11E24, 0xB11E28, 0xB11DE0, 0xB11DF0, PART2_HOOK_TOP_B11_RT, PART2_HOOK_BOT_B11_RT),
]

PART2_A3_TRAMP_SITE = 0xA3C7E8
PART2_A3_TRAMP_EXPECT = bytes.fromhex('047840780e4a3f28')
PART2_A3_SPACE_TABLE_ENTRY = 0x3142CC  # first jump table entry for byte 0x20: 0x08314270 + (0x20 - 0x09) * 4
PART2_A3_SPACE_TABLE_EXPECT = 0x0831431C
PART2_SPACE_313_SITE = 0x313FD6
PART2_SPACE_B11_SITE = 0xB11DFE
PART2_SPACE_313_EXPECT = bytes.fromhex('3078002807d00a28')
PART2_SPACE_B11_EXPECT = bytes.fromhex('3078002807d00a28')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(BASE, 'output', 'game_wars_korean_full.gba'))
    ap.add_argument('--report', default=os.path.join(BASE, 'temp', 'encode_report.csv'))
    ap.add_argument('--base', default=P.ROM,
                    help='base ROM. 기본=원본 ROM. v56_polished는 전투 튜토리얼 진입 후 충돌하는 구버전 베이스라 명시 지정할 때만 사용.')
    args = ap.parse_args()

    orig = bytes(open(P.ROM, 'rb').read())   # 원본 (테이블 소스)
    use_v56 = os.path.abspath(args.base) != os.path.abspath(P.ROM) and os.path.exists(args.base)
    rom = bytearray(open(args.base, 'rb').read()) if use_v56 else bytearray(orig)
    skip_addrs = V56_SKIP if use_v56 else set()

    if use_v56:
        # v56's overlay uses wider pre-rendered welcome glyphs. Disable only
        # its address matches; the rest of v56, especially name-grid work,
        # remains the base for this build.
        rom[V56_OVERLAY_ADDR_TABLE:V56_OVERLAY_ADDR_TABLE + V56_OVERLAY_ADDR_TABLE_LEN] = b'\xFF' * V56_OVERLAY_ADDR_TABLE_LEN

    # === ASM hook 방식: repoint/폰트복사 없음. 원본 FONT_BASE 보존(그리드+대화 가나/한자). ===
    # 1) 한글 글리프 블롭 → KOR_BASE(0xF00000)
    blob = open(P.BLOB, 'rb').read()
    rom[KOR_GLYPH_FILE:KOR_GLYPH_FILE + len(blob)] = blob
    # 2) ASM hook 코드 → hook_top@0xF30000, hook_bot@0xF30030
    rom[HOOK_FILE:HOOK_FILE + len(HOOK_TOP_BYTES)] = HOOK_TOP_BYTES
    rom[HOOK_BOT_FILE:HOOK_BOT_FILE + len(HOOK_BOT_BYTES)] = HOOK_BOT_BYTES
    rom[PART2_HOOK_TOP_313_FILE:PART2_HOOK_TOP_313_FILE + len(PART2_HOOK_TOP_313)] = PART2_HOOK_TOP_313
    rom[PART2_HOOK_BOT_313_FILE:PART2_HOOK_BOT_313_FILE + len(PART2_HOOK_BOT_313)] = PART2_HOOK_BOT_313
    rom[PART2_HOOK_TOP_B11_FILE:PART2_HOOK_TOP_B11_FILE + len(PART2_HOOK_TOP_B11)] = PART2_HOOK_TOP_B11
    rom[PART2_HOOK_BOT_B11_FILE:PART2_HOOK_BOT_B11_FILE + len(PART2_HOOK_BOT_B11)] = PART2_HOOK_BOT_B11
    rom[PART2_HOOK_A3_FILE:PART2_HOOK_A3_FILE + len(PART2_HOOK_A3)] = PART2_HOOK_A3
    rom[PART2_HOOK_A3_SPACE_FILE:PART2_HOOK_A3_SPACE_FILE + len(PART2_HOOK_A3_SPACE)] = PART2_HOOK_A3_SPACE
    rom[PART2_HOOK_SPACE_313_FILE:PART2_HOOK_SPACE_313_FILE + len(PART2_HOOK_SPACE_313)] = PART2_HOOK_SPACE_313
    rom[PART2_HOOK_SPACE_B11_FILE:PART2_HOOK_SPACE_B11_FILE + len(PART2_HOOK_SPACE_B11)] = PART2_HOOK_SPACE_B11
    rom[PART1_YESNO_HOOK_FILE:PART1_YESNO_HOOK_FILE + len(PART1_YESNO_HOOK)] = PART1_YESNO_HOOK
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
    _assert_relocated_korean_indices(new_tbl, sylmap, syl_to_code)
    rom[P.NEW_TBL_FILE:P.NEW_TBL_FILE + len(new_tbl)] = new_tbl
    P.patch_word(rom, P.LIT_TBL_START, P.NEW_TBL_RT)
    P.patch_word(rom, P.LIT_TBL_END, P.NEW_TBL_RT + len(new_tbl))

    # 2편/tilemap 계열도 같은 relocated table을 보게 한다. 이 루틴들은 table idx를
    # BG tilemap에 직접 쓰므로 write-site hook이 bit15 Korean marker를 VRAM tile id로 변환한다.
    for _name, start_lit, end_lit, top_site, bot_site, top_hook_rt, bot_hook_rt in PART2_PATCHES:
        P.patch_word(rom, start_lit, P.NEW_TBL_RT)
        P.patch_word(rom, end_lit, P.NEW_TBL_RT + len(new_tbl))
        assert bytes(rom[top_site:top_site + 8]) == bytes.fromhex('1188069808431880')
        assert bytes(rom[bot_site:bot_site + 8]) == bytes.fromhex('0188069808431880')
        rom[top_site:top_site + 8] = _abs_tramp(0, top_hook_rt)
        rom[bot_site:bot_site + 8] = _abs_tramp(1, bot_hook_rt)
    assert bytes(rom[PART2_A3_TRAMP_SITE:PART2_A3_TRAMP_SITE + 8]) == PART2_A3_TRAMP_EXPECT
    rom[PART2_A3_TRAMP_SITE:PART2_A3_TRAMP_SITE + 8] = _abs_tramp(2, PART2_HOOK_A3_RT)
    assert struct.unpack('<I', rom[PART2_A3_SPACE_TABLE_ENTRY:PART2_A3_SPACE_TABLE_ENTRY + 4])[0] == PART2_A3_SPACE_TABLE_EXPECT
    P.patch_word(rom, PART2_A3_SPACE_TABLE_ENTRY, PART2_HOOK_A3_SPACE_RT)
    assert bytes(rom[PART2_SPACE_313_SITE:PART2_SPACE_313_SITE + 8]) == PART2_SPACE_313_EXPECT
    assert bytes(rom[PART2_SPACE_B11_SITE:PART2_SPACE_B11_SITE + 8]) == PART2_SPACE_B11_EXPECT
    rom[PART2_SPACE_313_SITE:PART2_SPACE_313_SITE + 8] = _abs_tramp(0, PART2_HOOK_SPACE_313_RT)
    rom[PART2_SPACE_B11_SITE:PART2_SPACE_B11_SITE + 8] = _abs_tramp(0, PART2_HOOK_SPACE_B11_RT)
    assert bytes(rom[PART1_YESNO_CALL_SITE:PART1_YESNO_CALL_SITE + 4]) == PART1_YESNO_CALL_EXPECT
    rom[PART1_YESNO_CALL_SITE:PART1_YESNO_CALL_SITE + 4] = _thumb_bl(0x08000000 + PART1_YESNO_CALL_SITE, PART1_YESNO_HOOK_RT)

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
            ko = ADDRESS_TEXT_OVERRIDES.get(a, TEXT_OVERRIDES.get(ko, ko))
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
    st['symbol_glyphs'] = restore_symbol_glyphs(rom, orig)
    st['part2_obj_labels'] = patch_part2_battle_obj_labels(rom)
    st['part2_mission_obj'] = patch_part2_mission_start_obj(rom)
    st['part2_companion_hud'] = patch_part2_companion_hud_name(rom)

    # 2편 프롤로그 낱 한자 정리: 추출이 놓친 제어바이트(0x77) 사이 프래그먼트 "今、"(0xA019B6, 슬롯 밖 갭)
    #   → 한글 "지금"(예약코드)로 직접 덮어씀. (CSV 라인이 아니라 ROM 갭이라 여기서 패치.)
    #   "この地に、今、侵略者…" 의 今 = "이 땅에, 지금 침략자…"
    # {ROM주소: 한글} — 추출이 놓친 선두 감탄사 프래그먼트(제어바이트 사이 갭, CSV 라인 아님)를 직접 패치.
    #   각 한글은 원래 JP 바이트수와 같게(가나 1자=2B=한글 1음절 2B). 뒤 구두점(、)은 유지.
    for faddr, text in {
        0xA019B6: '지금',   # この地に[今]、 → 이 땅에 [지금]…  (今、4B→지금4B)
        0xA0E3D0: '아',     # [あ]、료 맥스… → [아]、료…       (あ2B→아2B, 、유지)
    }.items():
        enc = b''.join(struct.pack('>H', syl_to_code[ch]) for ch in text)
        rom[faddr:faddr + len(enc)] = enc
    for faddr, data in POST_TEXT_RESTORE.items():
        rom[faddr:faddr + len(data)] = data
    for faddr, (text, slot_len) in INTRO_DIRECT_TEXT.items():
        enc = encode_text(text, syl_to_code, unmapped)
        if len(enc) > slot_len:
            raise AssertionError(f'intro text overflow at 0x{faddr:X}: {len(enc)} > {slot_len}')
        rom[faddr:faddr + slot_len] = enc + bytes([FILL_BYTE]) * (slot_len - len(enc))
    st['name_honorifics'] = patch_name_honorific_fragments(rom, syl_to_code, unmapped)

    # Part 2 tutorial scripts embed small control bytes around object names.
    # Keep those control bytes in place, but replace the Japanese label payloads.
    def fixed_text_patch(faddr, slot_len, text):
        enc = encode_text(text, syl_to_code, unmapped)
        if len(enc) > slot_len:
            raise AssertionError(f'tutorial text overflow at 0x{faddr:X}: {len(enc)} > {slot_len}')
        rom[faddr:faddr + slot_len] = enc + bytes([FILL_BYTE]) * (slot_len - len(enc))

    fixed_text_patch(0xD8F384, 14, '보병')
    fixed_text_patch(0xD8F798, 14, '대기')

    raw_replacements = [
        (b'\x32\x95\xE0\x95\xBA\x30\x82\xE0', b'\x32' + encode_text('보병', syl_to_code, unmapped) + b'\x30' + encode_text('도', syl_to_code, unmapped)),
        (b'\x82\xB1\x82\xCC\x32\x95\xE0\x95\xBA\x30', encode_text('이', syl_to_code, unmapped) + b'\x81\x40\x32' + encode_text('보병', syl_to_code, unmapped) + b'\x30'),
        (b'\x32\x95\xE0\x95\xBA\x30', b'\x32' + encode_text('보병', syl_to_code, unmapped) + b'\x30'),
        (b'\x33\x8D\x55\x8C\x82\x30', b'\x33' + encode_text('공격', syl_to_code, unmapped) + b'\x30'),
        (b'\x33\x91\xD2\x8B\x40\x30', b'\x33' + encode_text('대기', syl_to_code, unmapped) + b'\x30'),
        (b'\x33\x8F\x49\x97\xB9\x30', b'\x33' + encode_text('종료', syl_to_code, unmapped) + b'\x30'),
    ]
    for old, new in raw_replacements:
        if len(old) != len(new):
            raise AssertionError('raw tutorial replacement length mismatch')
        start, end = 0xD8F300, 0xD97000
        pos = start
        while True:
            idx = rom.find(old, pos, end)
            if idx < 0:
                break
            rom[idx:idx + len(old)] = new
            pos = idx + len(new)

    # Name-confirm compact choices are not part of the normal CSV path because
    # nearby UI tables are deny-listed. This order loads 예/오/아/니 tiles; the
    # tiny tilemap hook above rewrites the visible row to "예 아니오".
    yesno_name_confirm = encode_text('예오아니', syl_to_code, unmapped)
    rom[0xD8273C:0xD8273C + 8] = yesno_name_confirm

    suffix = encode_text('　님', syl_to_code, unmapped)
    rom[0xDF8E4D:0xDF8E4D + 6] = suffix + bytes([FILL_BYTE]) * (6 - len(suffix))

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
    for k in ['rows', 'written', 'level0', 'level1', 'level2', 'level3', 'level4', 'level5', 'overflow', 'deny', 'skip_v56', 'no_ko', 'code_region', 'no_slot', 'bad_addr', 'oob', 'grid_glyphs', 'symbol_glyphs', 'part2_obj_labels', 'part2_mission_obj', 'part2_companion_hud', 'name_honorifics']:
        print(f'  {k}: {st[k]}')
    if unmapped:
        print(f'  unmapped chars ({len(unmapped)}): {dict(unmapped.most_common(10))}')
    print(f'→ {args.out} (16MB, chk recomputed), overflow 리포트 {args.report}')


if __name__ == '__main__':
    main()
