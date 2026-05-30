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
    # Part 2 tutorial intro slots with strict byte budgets.
    0xDF5D81: '하는 법 설명이야',
    0xDF5D9A: '뵙겠습니다',
    0xDF5DB4: '코스모랜드에 어서 와',
    0xDF619E: '부대라 볼 수 있어',
    0xDF68F6: '지금까지 실력을 시험해 봐',
    0xDF6A47: '나중에 골치 아파져',
    0xDF6D92: '을 중심으로 한 부대라',
    0xDF6E29: '내가 너무 깊이 생각했나',
    0xDF6EFA: '를 준비한다고',
    0xDF70AE: '님은 며칠 걸릴까?',
    0xDF71DE: '해상 유닛 설명이야',
    0xDF7346: '지난 작전에 쓴,',
    0xDF7382: '필요한 유닛을 골라',
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
    # Later Part 2 tutorial battle lines that otherwise remain Japanese because
    # the natural Korean sentence is a few bytes over the original slot.
    0xD9000C: '유리하니까',
    0xD9028B: '이제 남은 적은 하나야',
    0xD904A7: '버려',
    0xD90945: '도 쓰러뜨려',
    0xD90D26: '이번엔',
    0xD90EC1: '이번엔',
    0xD910C6: '여기 안가면',
    0xD91DA1: '겁내지 말고',
    0xD91DC4: '하는거야',
    0xD91DF4: '수로 밀면 될 거야',
    0xD920DE: '이번엔',
    0xD9226D: '점령지에붙여둬',
    0xD92366: '실수로움직이지마',
    0xD925A6: '다른목표없으면도시근처',
    0xD925D5: '이동하는게좋아',
    0xD925F6: '지금은여기로보내줘',
    0xD92647: '가까운곳으로둬',
    0xD92745: '부대를배치했을거야',
    0xD9287C: '잊기쉬운법이야',
    0xD928C6: '턴시작때먼저행동시켜',
    0xD92A76: '다시얘기할게',
    0xD92C2E: '이번엔',
    0xD92CB2: '이동범위에점령지가둘이나',
    0xD92D0D: '어느쪽을고를래',
    0xD92DDB: '어느쪽',
    0xD92F4A: '얼마나더',
    0xD9307B: '공격피해만큼',
    0xD9316E: '적전멸로도',
    0xD931B8: '부대는강적',
    0xD931CB: '정면승부는좋은작전아냐',
    0xD93265: '는정면상대말고',
    0xD937C8: '쓸모없는놈들',
    0xD93A36: '을도망치게해줘',
    0xD93B75: '는다음날HP2만',
    0xD93CC5: '다음날수리되게도시근처로',
    0xD93E20: '빨간범위가',
    0xD93E3A: '가능범위야',
    0xD93FE3: '못지나가게해야겠지',
    0xD94006: '이번엔',
    0xD94198: '싸우는법이야',
    0xD94266: '는앞으로나머지는',
    0xD94539: '여기서Ａ버튼',
    0xD9470B: '상황따라유닛둘이면편해',
    0xD9497F: '이제거의승리야',
    0xD94A13: '적전멸쪽이빠를거야',
    0xD94B2A: '저정도소부대에애먹다니',
    0xD94C9A: '최대치까지회복',
    0xD94D4B: '사용할수있어',
    0xD94E7D: '할수밖에',
    0xD94FBE: '탄약과연료가',
    0xD95020: '할수있어',
    0xD95032: '이번엔',
    0xD951EE: '능력을시험해봐',
    0xD95601: '을보내고싶네',
    0xD958C1: '가능범위보는법',
    0xD958E9: '아군도같아',
    0xD95AEE: '이번엔',
    0xD9617E: '을다리앞도시에둬',
    0xD96203: '말깜빡했어',
    0xD96220: '는간접공격가능한강유닛',
    0xD963B0: '은간접공격가능해도',
    0xD966CE: '공격범위에들지마',
    0xD96701: '공격범위보는법기억해',
    0xD9672E: '공격범위볼유닛에커서',
    0xD96782: '다시얘기할게',
    0xD96806: '아래중립도시는',
    0xD96975: '눈치못채고나타났구나',
    0xD96BD4: '까지쓸수있어',
    0xD96CF3: '을쓸수있을땐',
    0xD96E06: '그래도공중유닛은없을줄알았는데',
    # Part 2 tutorial rows with empty or shifted CSV translations. The normal
    # import would leave these as Japanese or write the wrong neighboring line.
    0xD919BE: '작전처음부터다시하게돼',
    0xD92458: '을이동',
    0xD939B6: '먼저두유닛을이쪽으로불러와',
    0xD9500C: '아군유닛에',
    0xD952B2: '의능력',
    0xD95D0A: '그럼이동해보자',
    0xD9603D: '의능력이야',
    0xD9703A: '일단육지는이어졌지만못가',
    0xD975CC: '의능력',
    0xD9767C: '의이동은',
    0xD97A5D: '는매일연료',
    0xD97F73: '두어도HP보충보급안돼',
    0xD97FC9: '지형이면가능해',
    0xD983F2: '폭격기',
    0xD98611: '대공전차',
    0xD987DE: '의능력이야',
    0xD98F21: '산위에',
    0xD990C6: '산위에',
    0xD995E4: '는공중유닛',
    0xD99BAA: '의이동은',
    0xD99C14: '평지를이동하면차이가나',
    0xD9AAAC: '는공격받지않아',
    0xD9AD89: '공중유닛과',
    0xD9AED4: '가공격',
    0xD9B169: '전함',
    0xD9DCAE: '이지형숲은옆에갈때까지',
    0xD9EC2E: '곧장이동하면조우해서',
    0xD9EFE5: '이동할곳',
    0xD9F276: '유닛정보야',
    0xD9FFF4: '여긴모드따라메뉴가늘거나',
    0xDA01D7: '하지만이걸고르면내가맵을클리어해',
    0xDA0652: '공중유닛을생산할수있는곳',
    0xDA1B9A: '중립도시',
    0xDA1D2B: '이동범위안',
    0xDA1D4E: '적군도시',
    0xDA1D5E: '중립도시',
    0xDA3AF2: '전차계와차량계이동비용은2',
    0xDA3C83: '이동할때는써도좋지만멈출땐',
    0xDA4000: '도시',
    0xDA4010: '공장',
    0xDA401E: '공항',
    0xDA402C: '항',
    # Late Part 2 tutorial battle fragments. These stay in very tight original
    # slots, so keep them short enough for the fixed-width script records.
    0xD97020: '는바다이동불가',
    0xD9709A: '여기서쓸모있는게',
    0xD970CE: '기억하지',
    0xD971B4: '의능력시험하자',
    0xD97284: '을시험하자',
    0xD972EE: '가못가는',
    0xD972FF: '바다도이동가능',
    0xD97336: '같은비용으로이동가능',
    0xD974A1: '가능위치는',
    0xD974B5: '가갈수있는지형뿐',
    0xD974E5: '어느지형',
    0xD97608: '의능력시험하자',
    0xD97648: '의능력시험하자',
    0xD977C7: '능력시험위해',
    0xD97BCE: '맞서싸울건',
    0xD97C68: '내일부터잊지마',
    0xD97D6F: '가라내부하들',
    0xD98136: '그병력을전멸',
    0xD9833D: '하지만늦었어',
    0xD986B8: '는이름대로하늘을날아',
    0xD98A79: '는매일연료2소모',
    0xD98C86: '연료바닥',
    0xD98F0E: '로쳐도좋고',
    0xD991BB: '힘내',
    0xD99216: '휩은보급생각없고',
    0xD99516: '여기서쓸모있는게',
    0xD9958E: '의능력시험',
    0xD996C8: '의능력시험',
    0xD996E3: '그러니여긴',
    0xD99714: '상자는예를들어',
    0xD997F6: '공격범위로유인해쓰는',
    0xD999D9: '있을땐어쩌는지기억해',
    0xD99D13: '적공중유닛을해치워',
    0xD99E15: '천천히공략해도좋아',
    0xD99E5A: '역시',
    0xD99E69: '이젠내말이필요없겠네',
    0xD9A117: '을끝까지지켜',
    0xD9A2E4: '혹시모르니확인',
    0xD9A327: '을해',
    0xD9A469: '지금부대만으로해내라',
    0xD9AA62: '위에겹쳐이동해',
    0xD9AE4D: '움직여야',
    0xD9B233: '여기서움직이지마',
    0xD9B27C: '을골라',
    0xD9B45A: '의능력시험해',
    0xD9B581: '여기로이동해야',
    0xD9B605: '그러니여긴',
    0xD9B69C: '만큼능력이',
    0xD9B70F: '마지막이야',
    0xD9B747: '기억하지',
    0xD9B95B: '그저가능할뿐이면',
    0xD9BC44: '얕은여울뿐',
    0xD9BD74: '하지마',
    0xD9BDA0: '를시험하자',
    0xD9BDE4: '갈수있는곳은여울항구뿐',
    0xD9C166: '가는곳은여울항구뿐',
    0xD9C390: '연료보급하려면',
    0xD9C4C9: '캐서린에게공중유닛안잃었으면',
    0xD9C550: '막상막하야',
    0xD9C5D2: '의또다른능력시험',
    0xD9C66A: '는적공격범위안이어도',
    0xD9C881: '가능',
    0xD9CC06: '매복했나봐',
    0xD9D27E: '비가온다',
    0xD9D418: '휘프는눈에강하고비에약해',
    0xD9D9CC: '이야기계속할게',
    0xD9DDB6: '다시얘기할게',
    0xD9E039: '여기나여기',
    0xD9E10C: '아무것도못하고끝날뿐아니라',
    0xD9E7B1: '잘해나갈수있어',
    0xD9EB86: '여기로보내고싶어',
    0xD9EDB6: '예를들어커서를이렇게',
    0xD9EE90: '기억하면편리할지도',
    0xD9F5FE: '거점이면수입',
    0xD9F642: '이동비용이어느정도인지',
    0xD9F927: '가능해',
    0xD9FD5A: '그럼다음',
    0xD9FF54: '설명듣고싶어',
    0xD9FFC5: '항복지도나가기등을고르는곳',
    0xDA025E: '이지만',
    0xDA04C5: '처음엔무엇을생산할지망설이면',
    0xDA0AA3: '기본부분을가르치는수업',
    0xDA0B0D: '가능한곳은지형',
    0xDA0BFC: '하고파',
    0xDA0D08: '소지금이하유닛은생산가능',
    0xDA0D90: '은맨위라여기서',
    0xDA0E17: '되었어',
    0xDA0E48: '상태가돼',
    0xDA0EDB: '다음은여기',
    0xDA0FB7: '이걸로이번턴할일은',
    0xDA105D: '을내려면움직일유닛',
    0xDA111F: '행동이돼',
    0xDA14C1: '를골라줘',
    0xDA1639: '을움직여',
    0xDA1995: '를파악해',
    0xDA1B71: '은누구도',
    0xDA1BB3: '자다시얘기할게',
    0xDA1DF7: '어느쪽',
    0xDA1E05: '해도수입자체는',
    0xDA1E81: '돈없으면생산도못해',
    0xDA2092: '수입줄면유닛도제대로못만들어',
    0xDA2341: '방법과간단전략의',
    0xDA237F: '승리조건은',
    0xDA24DB: '지금은여기',
    0xDA25C9: '지금은이',
    0xDA26C0: '같은유닛끼린이정도',
    0xDA27D3: '지금움직일유닛은이',
    0xDA2867: '그러니여기',
    0xDA28BB: '그러니',
    0xDA2909: '수많은쪽이이겨',
    0xDA2C89: '이동력3인데2칸뿐',
    0xDA2E17: '에들어가',
    0xDA3358: '그러니여긴',
    0xDA3820: '조건같으면공격쪽이',
    0xDA389C: '공격력은현재유닛수로증감',
    0xDA3AC3: '보병계는이동비용1이매력',
    0xDA3B20: '색적땐붙어야상황이',
    0xDA3DC6: '강은보병계외지상유닛불가',
    0xDA3EB2: '공중유닛은갈수있다고',
    0xDA3ED2: '공중유닛은지형방어추가없어',
    0xDA3F79: '지상유닛은보병만이동가능하고',
    0xDA4093: '이수업은전투진행에필요한',
    0xDA43C9: '움직일유닛없으면이야기가',
    0xDA43F9: '안되니생산이가장중요해',
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
    seen_import_addrs = set()
    with open(TRANS, newline='') as f:
        for row in csv.DictReader(f):
            ko = (row.get('korean') or '').strip()
            st['rows'] += 1
            try:
                a = int(row['address'], 16)
            except (ValueError, TypeError):
                st['bad_addr'] += 1; continue
            seen_import_addrs.add(a)
            if a in ADDRESS_TEXT_OVERRIDES:
                ko = ADDRESS_TEXT_OVERRIDES[a]
            if not ko:
                st['no_ko'] += 1; continue
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

    # Some extracted text rows are missing from translation_for_import.csv or
    # have malformed rows there. Address overrides are authoritative for those
    # tight tutorial fragments, so write them directly from found-text slots.
    for a, ko in sorted(ADDRESS_TEXT_OVERRIDES.items()):
        if a in seen_import_addrs:
            continue
        if a < SAFE_MIN_ADDR:
            continue
        slot = slots.get(a, 0)
        if slot <= 0:
            continue
        deny = in_deny(a, a + slot)
        if deny:
            continue
        enc, level = encode_fit(ko, slot, syl_to_code, unmapped)
        if enc is None:
            st['overflow'] += 1
            report.append((f'0x{a:08X}', ko, len(encode_text(ko, syl_to_code, unmapped)), slot))
            continue
        st[f'level{level}'] += 1
        if a + slot > len(rom):
            st['oob'] += 1
            continue
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
        (b'\x32\x8C\x79\x90\xED\x8E\xD4\x30', b'\x32' + encode_text('경전차', syl_to_code, unmapped) + b'\x30'),
        (b'\x32\x90\xED\x93\xAC\x83\x77\x83\x8A\x30', b'\x32' + encode_text('전투헬기', syl_to_code, unmapped) + b'\x30'),
        (b'\x32\x97\x41\x91\x97\x83\x77\x83\x8A\x30', b'\x32' + encode_text('수송헬기', syl_to_code, unmapped) + b'\x30'),
        (b'\x32\x90\xED\x93\xAC\x8B\x40\x30', b'\x32' + encode_text('전투기', syl_to_code, unmapped) + b'\x30'),
        (b'\x32\x94\x9A\x8C\x82\x8B\x40\x30', b'\x32' + encode_text('폭격기', syl_to_code, unmapped) + b'\x30'),
        (b'\x32\x97\x41\x91\x97\x8E\xD4\x30', b'\x32' + encode_text('수송차', syl_to_code, unmapped) + b'\x30'),
        (b'\x32\x92\xE3\x8E\x40\x8E\xD4\x30', b'\x32' + encode_text('정찰차', syl_to_code, unmapped) + b'\x30'),
        (b'\x32\x91\xCE\x8B\xF3\x90\xED\x8E\xD4\x30', b'\x32' + encode_text('대공전차', syl_to_code, unmapped) + b'\x30'),
        (b'\x32\x8E\xA9\x91\x96\x96\x43\x30', b'\x32' + encode_text('자주포', syl_to_code, unmapped) + b'\x30'),
        (b'\x32\x90\xED\x8A\xCD\x30', b'\x32' + encode_text('전함', syl_to_code, unmapped) + b'\x30'),
        (b'\x32\x90\xF6\x90\x85\x8A\xCD\x30', b'\x32' + encode_text('잠수함', syl_to_code, unmapped) + b'\x30'),
        (b'\x33\x90\xED\x93\xAC\x30', b'\x33' + encode_text('전투', syl_to_code, unmapped) + b'\x30'),
        (b'\x33\x88\xDA\x93\xAE\x30', b'\x33' + encode_text('이동', syl_to_code, unmapped) + b'\x30'),
        (b'\x33\x8D\x55\x8C\x82\x30', b'\x33' + encode_text('공격', syl_to_code, unmapped) + b'\x30'),
        (b'\x33\x90\xB6\x8E\x59\x30', b'\x33' + encode_text('생산', syl_to_code, unmapped) + b'\x30'),
        (b'\x32\x91\xD2\x8B\x40\x30', b'\x32' + encode_text('대기', syl_to_code, unmapped) + b'\x30'),
        (b'\x33\x91\xD2\x8B\x40\x30', b'\x33' + encode_text('대기', syl_to_code, unmapped) + b'\x30'),
        (b'\x33\x8F\x49\x97\xB9\x30', b'\x33' + encode_text('종료', syl_to_code, unmapped) + b'\x30'),
        (b'\x33\x90\xE8\x97\xCC\x30', b'\x33' + encode_text('점령', syl_to_code, unmapped) + b'\x30'),
        (b'\x33\x95\xE2\x8B\x8B\x30', b'\x33' + encode_text('보급', syl_to_code, unmapped) + b'\x30'),
        (b'\x33\x93\x8B\x8D\xDA\x30', b'\x33' + encode_text('탑재', syl_to_code, unmapped) + b'\x30'),
        (b'\x32\x93\x73\x8E\x73\x30', b'\x32' + encode_text('도시', syl_to_code, unmapped) + b'\x30'),
        (b'\x32\x8D\x48\x8F\xEA\x30', b'\x32' + encode_text('공장', syl_to_code, unmapped) + b'\x30'),
        (b'\x32\x8B\xF3\x8D\x60\x30', b'\x32' + encode_text('공항', syl_to_code, unmapped) + b'\x30'),
        (b'\x32\x95\xBD\x92\x6E\x30', b'\x32' + encode_text('평지', syl_to_code, unmapped) + b'\x30'),
        (b'\x32\x8E\x52\x30', b'\x32' + encode_text('산', syl_to_code, unmapped) + b'\x30'),
        (b'\x32\x90\x58\x30', b'\x32' + encode_text('숲', syl_to_code, unmapped) + b'\x30'),
        (b'\x32\x93\xB9\x98\x48\x30', b'\x32' + encode_text('도로', syl_to_code, unmapped) + b'\x30'),
        (b'\x32\x8D\x60\x30', b'\x32' + encode_text('항', syl_to_code, unmapped) + b'\x30'),
    ]
    for old, new in raw_replacements:
        if len(old) != len(new):
            raise AssertionError('raw tutorial replacement length mismatch')
        start, end = 0xD8F300, 0xDA5000
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
