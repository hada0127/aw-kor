#!/usr/bin/env python3
"""B팀(짜옹이) 권위 번역 drift 검사(QA).

절대제약: B팀/짜옹이 캠페인 번역 문구는 수정 불가(재배치/복원만). 2026-06-24 codex 적대
리뷰가 작업트리에서 B팀 대사 3건이 슬롯 여유에도 축약·개작된 것을 적발 → 이런 우발적 변형을
영구 자동 검출하기 위한 게이트.

방식: `data/bteam_baseline.json`(B팀 적용 주소의 권위 override 스냅샷)과 현재
`data/dialogue_overrides.json`을 주소별로 비교. 값이 다르면 DRIFT(우발적 변형 의심).

짜옹이 본인이 의도적으로 B팀 문구를 바꾸려면: 편집 후 `--accept`로 baseline을 재생성한다
(의도적 변경만 통과시키고, 그 외 우발 변형은 차단).

사용자 일괄 승인 재작성(2026-11-04)은 `data/bteam_approved_rewrites.json` 원장에
(주소, from=baseline, to=현재 override)로 등재하고 파일 SHA256을
`APPROVED_REWRITE_LEDGER_DIGEST`에 고정한다. baseline은 바꾸지 않으며 `--accept`도
원장 주소의 baseline을 유지한다.

사용:
  python3 tools/qa_bteam_drift.py            # drift 있으면 출력 + 비0 종료
  python3 tools/qa_bteam_drift.py --accept   # 현재 override로 baseline 갱신(의도적 변경 확정)
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import os
import struct
import sys
from pathlib import Path

from qa_integrity_map import decode_enc, fill_pattern, load_syl
from dialogue_regions import is_part1_dialog_address, is_part2_story_address
from repoint_source_rows import fragments as source_fragments, row_bytes as source_row_bytes


def script_format_bytes(payload, address):
    """Drop non-drawing format instructions only for attributed script rows."""
    from renderer_text import renderer_for_address,P1_SCRIPT,P2_SCRIPT,single_bytes
    if renderer_for_address(address) not in (P1_SCRIPT,P2_SCRIPT):return payload
    remove={off for off,b in single_bytes(payload) if b in (9,10,13)}
    return bytes(b for off,b in enumerate(payload) if off not in remove)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def co_breaks_as_spaces(payload):
    """Replace CO row controls without touching SJIS trail bytes."""
    result = bytearray()
    pos = 0
    while pos < len(payload):
        lead = payload[pos]
        if (0x81 <= lead <= 0x9F or 0xE0 <= lead <= 0xFC) and pos + 1 < len(payload):
            result.extend(payload[pos:pos + 2])
            pos += 2
        else:
            result.extend(b'\x81\x40' if lead == 0x72 else bytes((lead,)))
            pos += 1
    return bytes(result)
OVERRIDES = os.path.join(BASE, 'data', 'dialogue_overrides.json')
BASELINE = os.path.join(BASE, 'data', 'bteam_baseline.json')

# Exact B-team source/display exceptions reviewed at script row boundaries.
# Shared with the writer so the final-ROM gate cannot drift from its policy.
BTEAM_SCRIPT_SPACING_REPAIRS = {
    0xDEECDE: ('해상유닛.지상 유닛을', '해상 유닛.지상 유닛을'),
    0xDC3C63: ('사령관님,료!', ' 사령관님, 료!'),
    0xDEDFB6: ('공중유닛에 강한,', '공중 유닛에 강한,'),
    0xDEE15E: ('공중유닛.공중유닛에', '공중 유닛. 공중 유닛에'),
}


def norm(a: str) -> str:
    try:
        return '0x%08X' % int(a, 16)
    except (ValueError, TypeError):
        return a


def load_overrides() -> dict:
    ov = json.load(open(OVERRIDES, encoding='utf-8'))
    return {norm(k): v for k, v in ov.items()}


# SHA-256 of every baseline entry that is NOT a user-approved exception
# (sorted JSON). Hand edits or a broad --accept change it and fail the gate;
# changing B-team wording needs a reviewed code change of this pin.
# The 2026-10-07 consensus re-keys two misaligned entries only; see
# temp/claude_2026-10-07/plan/bteam_final_decisions.tsv.
# 2026-11-04: re-pinned after 0x00DF5E12/0x00A1B469 moved into the user-approved
# exception table (temp/fix_20261104/inputs.md msg3/5); no other core entry changed.
# 2026-11-04: re-pinned after 0x00A2CB8C (shifted ハチ key -> イワン 이반) moved into the
# exception table (inputs.md msg7/8, names_audit 1-1); no other core entry changed.
# 2026-11-04: re-pinned after 0x00DF8EAE (Catherine first question -> banmal) moved into the
# exception table (inputs.md msg7-8); no other core entry changed.
PINNED_CORE_DIGEST = 'a23c220b356433dfdc0465204c3d84d64764645c418d7107166d2604b8a66297'
ALIGNMENT_RESTORE_ADDRESSES = frozenset({0x00A19300, 0x00A1B3C8})
ALIGNMENT_COMPOSITE_NEXT = {0x00A19300: 0x00A1930F}
ALIGNMENT_LEGACY_KEYS = {
    '0x00A19300': '0x00A19324',
    '0x00A1B3C8': '0x00A1B3EC',
}

# Exact round-2 deferrals; previously deferred addresses with a reviewed
# restore decision must no longer be forced to fail after restoration.
ROUND2_MANIFEST = Path(BASE, 'data', 'bteam_round2_decisions.tsv')
ROUND2_RESIDUAL_DIGEST = '7d3c76b92b4d6ce30fd79331d54c65468988daa0e16fed07c4de1fd5261d01e1'
ROUND2_ACTIVE_PINS_DIGEST = 'eab2fa69a949253974305293e28c1ed5952708fed0a2a162b4e619541cf2be4f'
with ROUND2_MANIFEST.open('rb') as _stream:
    if hashlib.sha256(_stream.read()).hexdigest() != 'ae9e9a92530507b01859b57f137650f6fc9b8877add9ee1257feb1452f131a37':
        raise ValueError('B-team round-2 decision manifest digest changed')
with ROUND2_MANIFEST.open(encoding='utf-8', newline='') as _stream:
    _round2_rows = list(csv.DictReader(_stream, delimiter='\t'))
DEFERRED_ADDRESSES = frozenset(int(row['address'], 16) for row in _round2_rows
                                if row['decision'] == 'DEFER')
FIX_GATE_ADDRESSES = frozenset(int(row['address'], 16) for row in _round2_rows
                              if row['decision'] == 'FIX_GATE')
if len(_round2_rows) != 287 or len(DEFERRED_ADDRESSES) != 11:
    raise ValueError('B-team round-2 deferral count changed')
COMPACT_GLYPH_ADDRESSES = frozenset(int(x, 16) for x in '''
B818D0 B818F4 B81900 B81970 B81988 B81994 B819C4 B819E8
B81AC0 B81ACC B82CF6 B82D02 B82D0E B82D76 B82DD6 B82DE2
B84F28 B84F38 B84F4C B84F5C B84F6C
'''.split())
# Newly exposed by preserving punctuation and authored spaces. These were not
# among the 649 consensus rows and need separate review, not silent clearance.
NEW_STRICT_ADDRESSES = frozenset(int(x, 16) for x in '''
A021A0 A02450 A03F0C A15D3C A2C144 A2C5F0 A2C704 A2C8B0
A2C8C4 A2C970 A2C994 A2CA38 A2CA44 A2CA60 A2CA70 A2CA88
A2CBFC A2CC0C A2D55C A2D58C A2D5A0 A2D61C A2D698 A2D6C0
A2D704 A2D7A4 A2D7FC A2D828 A2D838 A2D848 A2D889 A309AC
A30C88 A30E40 A33C3C A33D1C A34F5C A34FC8 A3500C A3506C
A351A4 B8306C B830EC B8310C B83188 B8319C B83254 B83268
B83870 B8387C B838A4 B838B0 B838BC B83A3C B83A98 B83AC8
B83D10 B83DE0 B84128 B84238 D9159E DC3B0E DC495E DC4B2A
DC51AE DC5812 DC5D12 DC7006 DC9662 DCB0BA DCBD36 DD1476
DF3AC3 DF3AD2 E062DE E064B2 E0F7EE
'''.split())


def compact_glyph_map() -> dict[str, str]:
    """Read the actual compact FONT_BASE substitution table from the builder.

    Keep this tied to the writer's literal map, and fail closed if it becomes
    computed or disappears. The same source drives patch_part2_ui_kanji_glyphs.
    """
    source = Path(BASE, 'tools', 'build_korean_full.py').read_text(encoding='utf-8')
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == 'PART2_UI_KANJI_GLYPH_SUBS'
                for t in node.targets):
            result = ast.literal_eval(node.value)
            if not isinstance(result, dict) or not result:
                break
            return result
    raise ValueError('compact UI glyph substitution table unavailable')


def decode_compact(enc: bytes, code2syl: dict, glyphs: dict[str, str]) -> str:
    """Decode bytes through the compact renderer's substituted glyphs."""
    # The compact writer owns fixed-size rows and terminates glyph text with
    # zero bytes; these are not displayed glyphs. Embedded zeros remain errors.
    ordinary = decode_enc(enc.rstrip(b'\x00'), code2syl)
    return ''.join(glyphs.get(ch, ch) for ch in ordinary)


def verify_compact_font(rom: bytes, glyphs: dict[str, str]) -> None:
    """Prove that this ROM, not just builder source, carries the substitute tiles."""
    from build_korean_poc import FONT_FILE, KTAB_FILE, KTAB_END_FILE, ROM
    from render_galmuri_8x16 import render_char
    original = Path(ROM).read_bytes()
    slots = {}
    for pos in range(KTAB_FILE, KTAB_END_FILE, 6):
        try:
            jp = original[pos:pos + 2].decode('shift_jis')
        except UnicodeDecodeError:
            continue
        slots[jp] = struct.unpack_from('<HH', original, pos + 2)
    for jp, ko in glyphs.items():
        if jp not in slots:
            raise ValueError(f'compact glyph has no original font slot: {jp}')
        top, bottom = slots[jp]
        actual = (rom[FONT_FILE + top * 32:FONT_FILE + (top + 1) * 32],
                  rom[FONT_FILE + bottom * 32:FONT_FILE + (bottom + 1) * 32])
        if actual != tuple(render_char(ko)):
            raise ValueError(f'compact glyph tile mismatch in inspected ROM: {jp}->{ko}')


# Round-2 residual restorations (2026-10-07). These consumers are not the
# Part 1/Part 2 dialogue writers, but every one displayed the original Japanese
# with SJIS fullwidth punctuation, digits and 「」 (checked byte-by-byte in the
# original ROM: ！？、。ー２ and 　). Restoring the protected Korean words with
# those same glyph codes is consumer-safe without guessing how ASCII renders:
#   Part 1 mission titles 0xB81D80..0xB82018 (original e.g. 決着！シッコクノモリ！),
#   Part 2 map-editor/link messages 0xA2C6xx..0xA350B4,
#   Part 1 link and CO-quote texts 0xB8301C..0xB84298.
ROUND2_ORIGINAL_GLYPH_ROWS = frozenset(int(x, 16) for x in '''
B81D80 B81D94 B81DD4 B81DF0 B81E08 B81E1C B81E38 B81E50 B81E64 B81E78
B81E98 B81EA8 B81EB8 B81ED0 B81EE0 B81EF4 B81F04 B81F10 B81F5C B81F70
B81F98 B81FAC B81FC4 B81FDC B81FF4
A2C644 A2C720 A2C784 A2C7B4 A2C828 A2C848 A2C868 A2C898 A2C950 A2C9B4
A2CA10 A2CABC A34F98 A34FEC A350B4
B8301C B83044 B83130 B83CC0 B83DB0 B83EB8 B83F74 B84298
'''.split())
ORIGINAL_GLYPH_PUNCTUATION = str.maketrans({'!': '！', '?': '？', ',': '、', '.': '。', '-': 'ー'})

# Per-address punctuation alias table, baseline-derived: each row comes from
# bteam_baseline.json overrides and was observed in the b26/b27 final ROM via
# integrity_map.json and the final-ROM drift gate (not a general rule).
# A35228, B82FAC, B8319C, B83A64, B83FA8 are NOT in this table: they remain
# pinned residual mismatches, not proven punctuation substitutions. No source row contains :[]{}.
# Values list only punctuation present in that row's protected text.
PROFILE_PUNCTUATION_ROWS = {
    0x00A2C614: '.',
    0x00A3353C: '.',
    0x00A33C3C: '.',
    0x00A33D1C: '.,',
    0x00A33D8C: '.',
    0x00A34E58: ',',
    0x00A34F00: ',',
    0x00A34F70: ',',
    0x00A34FC8: '.',
    0x00A3508C: ',',
    0x00A350DC: '.',
    0x00A350F8: '.',
    0x00A3511C: ',',
    0x00A3514C: '.',
    0x00A3517C: '.,',
    0x00A351A4: '.',
    0x00A351CC: '.',
    0x00A351E0: '.',
    0x00A35228: ',',
    0x00B82F54: '.,',
    0x00B82F7C: '.',
    0x00B82FAC: ',',
    0x00B82FDC: '.',
    0x00B83000: '.',
    0x00B8310C: '.',
    0x00B83160: ',',
    0x00B8319C: '-',
    0x00B83A64: ',',
    0x00B83A98: ',',
    0x00B83AF8: ',',
    0x00B83C3C: '-',
    0x00B83C70: '.,',
    0x00B83D10: ',',
    0x00B83D38: '.,',
    0x00B83E08: '.,',
    0x00B83E2C: ',',
    0x00B83E58: '-',
    0x00B83E78: ',-',
    0x00B83E94: '-',
    0x00B83F04: ',',
    0x00B83FA8: '.,-',
    0x00B84034: '-',
    0x00B84104: ',',
    0x00B84128: '.',
    0x00B84154: ',',
    0x00B84224: '-',
    0x00B842B8: ',',
    0x00EC328E: '.',
}


def original_glyph_encoding(value: str) -> str:
    """Expected-side form for ROUND2_ORIGINAL_GLYPH_ROWS (words and order unchanged)."""
    value = value.replace('...', '・・・').replace(' ', '　').translate(ORIGINAL_GLYPH_PUNCTUATION)
    return ''.join(chr(ord(ch) + 0xFEE0) if ch.isascii() and ch.isalnum() else ch for ch in value)


def display_equivalent(value: str, address: int, *, actual: bool = False) -> str:
    """Predict only documented writer glyph substitutions on baseline text.

    The ROM side stays literal: a halfwidth space or punctuation byte in a
    dialogue renderer must not pass as its visible fullwidth counterpart.

    fixB J (2026-11-04, plan_C E3): in dialogue consumers the builder's final
    byte stage turns runs of 3-5 「・」 into one 「…」 (0x8163) and 6+ into two.
    Both sides fold to that form so a row the pass skipped (exact-byte pins)
    and a compacted row compare equal; 1-2 dots stay middle dots.
    """
    from korean_punct_glyphs import compact_ellipsis_text
    from renderer_text import renderer_for_address, P1_SCRIPT, P2_SCRIPT
    # Same scope as build_korean_full.compact_dialogue_ellipsis: both script consumers.
    ellipsis_scope = renderer_for_address(address) in (P1_SCRIPT, P2_SCRIPT)
    if actual:
        if not ellipsis_scope:
            return value
        value = compact_ellipsis_text(value)
        # The compaction pass pads the freed bytes with 0x20 at the end of the
        # row fragment (drawn as nothing by both script consumers).
        return value.replace(' ', '') if '…' in value else value
    from part2_mission_title_fit import is_pair_title
    if is_pair_title(address):
        # Every active native map name is a strict two-byte glyph stream.
        # Preserve each authored character, changing only its width form.
        return ''.join('　' if ch == ' ' else chr(ord(ch)+0xFEE0)
                       if 0x21 <= ord(ch) <= 0x7E else ch for ch in value)
    if address in ROUND2_ORIGINAL_GLYPH_ROWS:
        value = original_glyph_encoding(value)
        return compact_ellipsis_text(value) if ellipsis_scope else value
    dialogue = is_part2_story_address(address) or is_part1_dialog_address(address)
    if dialogue:
        # The dialogue writer promotes authored ASCII to visible SJIS glyphs.
        # Preserve the number and position of punctuation and spaces.
        value = value.replace('...', '・・・').replace(' ', '　')
        value = ''.join(chr(ord(ch) + 0xFEE0) if ch.isascii() and ch.isalnum()
                        else ch for ch in value)
    else:
        # Reviewed aliases only. Builder normalization may grow; the drift
        # oracle must never inherit a new semantic substitution automatically.
        from renderer_text import renderer_for_address
        profile = renderer_for_address(address)
        if profile is not None:
            # Only punctuation observed in this exact protected ROM row may
            # change glyph form; all other ASCII gets pure-width conversion.
            row_chars = PROFILE_PUNCTUATION_ROWS.get(address, '')
            row_aliases = {ch: {'.': '。', ',': '、', '-': '―'}[ch]
                           for ch in row_chars}
            value = ''.join(row_aliases[ch] if ch in row_aliases else
                            chr(ord(ch) + 0xFEE0) if 0x21 <= ord(ch) <= 0x7E
                            and ch not in '*=@' else ch for ch in value)
        value = value.replace(' ', '　')
    # This 36-byte Part 1 link preload now carries the complete protected
    # wording.  Its compact consumer uses the SJIS fullwidth period glyph.
    if address in {0xB8322C, 0xB83254}:
        value = value.replace('.', '。')
    punctuation = {}
    if is_part1_dialog_address(address):
        punctuation.update({'!': '！', '?': '？', ',': '、', '.': '。',
                            '-': '―', '「': '”', '」': '”'})
    elif is_part2_story_address(address):
        punctuation.update({'!': '！', '?': '？', ',': '、', '.': '。', '-': 'ー'})
        from part2_prologue_punctuation import in_prologue
        if in_prologue(address):
            # 2026-10-23 user approval: the Part 2 prologue shows Korean 「，」「．」
            # (builder: part2_prologue_punctuation.patch / patch_rewritten).
            # Expected side only; the ROM side stays literal.
            punctuation.update({',': '，', '.': '．', '、': '，', '。': '．'})
    value = value.translate(str.maketrans(punctuation))
    return compact_ellipsis_text(value) if ellipsis_scope else value


def round2_width_equivalent(baseline: str, actual: str, address: int) -> bool:
    """Accept only reviewed FIX_GATE glyph aliases, with every character retained."""
    if address not in FIX_GATE_ADDRESSES:
        return False
    aliases = str.maketrans({' ': '　', '!': '！', '?': '？', ',': '、',
                             '.': '。', '～': '〜', '-': 'ー', '―': 'ー'})
    def canonical(value: str) -> str:
        value = value.translate(aliases)
        return ''.join(chr(ord(ch) + 0xFEE0) if ch.isascii() and ch.isalnum()
                       else ch for ch in value)
    expected = baseline.translate(aliases)
    if is_part1_dialog_address(address) or is_part2_story_address(address):
        return canonical(baseline) == actual
    return actual in {expected, canonical(baseline)}


ROUND2_PREFIX_GLYPH_ROWS = {0xA2CA88: 2, 0xB83870: 3,
                            0xB8387C: 3, 0xB838A4: 4,
                            0xB838B0: 4, 0xB838BC: 3}
ROUND2_OBJECTIVE_ROWS = {
    0xA01ED0: ('산을 넘어,캣의 연구 기지를공격하라!', '산을　넘어、　캣의　연구　기지를', '공격하라！'),
    0xA021A0: ('캣에게 빼앗긴 국토를되찾아라!', '캣에게　빼앗긴　국토를', '되찾아라！'),
    0xA02450: ('블랙홀 군의 본거지를쳐라!', '블랙홀　군의　본거지를', '쳐라！'),
}


def round2_objective_equivalent(rom: bytes, baseline: str, actual: str,
                                address: int, row_start: int) -> bool:
    """Check both displayed rows of three reviewed objective sentences."""
    if address not in ROUND2_OBJECTIVE_ROWS or address not in FIX_GATE_ADDRESSES:
        return False
    # The first row is already decoded by check_rom. The predicate must be in
    # the immediately following physical row, after exactly one 0x72 break.
    lead_end = rom.find(b'\x72', row_start + 20, row_start + 48)
    if lead_end < 0:
        return False
    tail_end = rom.find(b'\x00', lead_end + 1, lead_end + 40)
    if tail_end < 0:
        return False
    tail_raw = rom[lead_end + 1:tail_end].rstrip(b' ')
    if not tail_raw or b'\x72' in tail_raw:
        return False
    tail = decode_enc(tail_raw, load_syl())
    expected_baseline, expected_first, expected_tail = ROUND2_OBJECTIVE_ROWS[address]
    return (baseline == expected_baseline and actual == expected_first
            and tail == expected_tail)


def reviewed_seam_variants(value: str, msg: int, rows: dict) -> set[str]:
    """Expected side only: add a reviewed seam space; never remove one."""
    variants = {value}
    for prev, next_ in rows.get(msg, ()):
        joined = prev + next_
        spaced = prev + '　' + next_
        variants |= {v.replace(joined, spaced, 1) for v in variants if joined in v}
    return variants


def matches_reviewed_bteam_spacing(address: int, baseline: str, actual: str) -> bool:
    """Accept only an individually reviewed whitespace repair at its source row."""
    if address == 0xA34B6C:
        return baseline == '예　아뇨' and actual == '　예　　　아뇨'
    from dialogue_spacing import reviewed_bteam_match
    if reviewed_bteam_match(address,baseline,actual,restored=True):
        return True
    repair = BTEAM_SCRIPT_SPACING_REPAIRS.get(address)
    return (repair is not None and baseline == repair[0]
            and display_equivalent(actual, address, actual=True)
            == display_equivalent(repair[1], address))


def load_reviewed_seams() -> dict[int, list[tuple[str, str]]]:
    path = Path(BASE, 'data', 'part2_seam_decisions.tsv')
    rows = {}
    with path.open(encoding='utf-8', newline='') as stream:
        for row in csv.DictReader(stream, delimiter='\t'):
            if row['decision'] == 'space':
                rows.setdefault(int(row['msg'], 16), []).append(
                    (row['prev_word'], row['next_word']))
    return rows


def matches_alignment_composite(wanted: str, first: str, second: str,
                                gap: bytes, address: int) -> bool:
    """Only the consensus A19300/A1930F pair may cross its native 0x72 row break."""
    return (address in ALIGNMENT_COMPOSITE_NEXT and gap == b'\x72' and
            bool(first) and bool(second) and
            wanted == display_equivalent(first + second, address, actual=True))


# User-approved B-team wording exceptions, exact (address, from, to). The
# baseline's _user_approved_exceptions must equal this table; adding or editing
# one is a reviewed code change. 0xDD0D1A: じょうでき=上出来, user 「제안대로」 2026-10-07.
APPROVED_EXCEPTIONS = {
    '0x00D82498': ('정보', '채움'),  # display only; source bytes stay protected
    '0x00D8246A': ('이름 입력', '이름'),  # display only; no baseline override at this key
    '0x00A34F70': ('엔트리 중이야,잠시 기다려 줘!!', '엔트리 중이야, 잠시 기다려 줘!!'),
    '0x00A34F98': ('친구가 모이면,스타트를 눌러 줘!!', '친구가 모이면, 스타트를 눌러 줘!!'),
    '0x00A3508C': ('맵을 송신 중이야,잠시 기다려 줘!!', '맵을 송신 중이야, 잠시 기다려 줘!!'),
    '0x00A350B4': ('맵을 수신 중이야,잠시 기다려 줘!!', '맵을 수신 중이야, 잠시 기다려 줘!!'),
    '0x00A350DC': ('종료했어.시작한다!!', '종료했어. 시작한다!!'),
    '0x00A350F8': ('종료했어.메뉴로 돌아갈게.', '종료했어. 메뉴로 돌아갈게.'),
    '0x00A3511C': ('맵을 저장 중이야,전원을 끄지 말아 줘!!', '맵을 저장 중이야, 전원을 끄지 말아 줘!!'),
    '0x00A3514C': ('다운로드 준비 중이야.잠시 기다려 줘!!', '다운로드 준비 중이야. 잠시 기다려 줘!!'),
    '0x00A3517C': ('접속이 안 되네,메뉴로 돌아갈게.', '접속이 안 되네, 메뉴로 돌아갈게.'),
    '0x00DD0D1A': ('뭐,자네치고는,상등품이군.', '뭐, 자네치고는 잘했군.'),
    '0x00A2D814': ('결전 전', '최종결전!'),
    # 2026-11-04 user (inputs.md msg9): title restored to 게임보이 워즈 어드밴스 (supersedes 2026-10-16).
    '0x00DF8E16': ('게임보이 워즈에 오신 걸 환영해요!', '게임보이 워즈 어드밴스에 어서 와!'),
    '0x00DF948E': ('그렇다면, 간단하게 게임보이 워즈에', '그렇다면, 게임보이 워즈 어드밴스에'),
    # 2026-11-04 user (temp/fix_20261104/inputs.md msg3/5): EXT_COMPARE defects.
    '0x00DF5E12': ('당신에게는,코스모 랜드에 대해', '코스모 랜드에 대해'),
    '0x00A1B469': ('그건 안 돼.', '하지만요...'),
    # 2026-11-04 user (inputs.md msg7/8): Part 2 CO name table key shift (names_audit 1-1).
    '0x00A2CB8C': ('하치', '이반'),
    # 2026-11-04 user (inputs.md msg7-8): Catherine first question, banmal; exact 34-byte slot.
    '0x00DF8EAE': ('혹시, 이 게임은 처음이신가요?', '너, 혹시 이 게임은 처음이니?'),
}

# Exact user-approved Part 2 prologue renderer exceptions.  These rows record
# the full visible before/after text; the original protected source baseline
# and the authored dialogue overrides remain unchanged.
PROLOGUE_RENDERER_EXCEPTION_DIGEST = '61a87dcacc53d16ff7b99f107dea74d6cb376ab02e51a2999b823774b06f902b'


def core_digest(base: dict) -> str:
    exceptions = base.get('_user_approved_exceptions', {})
    core = {k: v for k, v in base.get('overrides', {}).items()
            if k not in exceptions or exceptions[k].get('display_only')
            or exceptions[k].get('renderer_only')}
    return hashlib.sha256(json.dumps(core, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def exception_errors(base: dict, overrides: dict) -> list:
    """Each exception is valid only for its exact (address, from, to) tuple."""
    errors = []
    recorded = base.get('_user_approved_exceptions', {})
    ordinary = {a: (e.get('from'), e.get('to')) for a, e in recorded.items()
                if isinstance(e, dict) and not e.get('renderer_only')}
    renderer = {a: (e.get('from'), e.get('to')) for a, e in recorded.items()
                if isinstance(e, dict) and e.get('renderer_only')}
    if ordinary != APPROVED_EXCEPTIONS:
        errors.append('baseline exceptions differ from the approved (address, from, to) table')
    renderer_digest = hashlib.sha256(json.dumps(renderer, ensure_ascii=False,
                                                sort_keys=True).encode()).hexdigest()
    if len(renderer) != 21 or renderer_digest != PROLOGUE_RENDERER_EXCEPTION_DIGEST:
        errors.append('Part 2 prologue renderer exceptions differ from the approved text')
    for addr, exc in recorded.items():
        if isinstance(exc, dict) and bool(exc.get('display_only')) != (addr in ('0x00D82498', '0x00D8246A')):
            errors.append(f'{addr}: display-only status differs from approval')
    for addr, exc in recorded.items():
        if (not isinstance(exc, dict) or not exc.get('approved') or not exc.get('from')
                or not exc.get('to') or exc['from'] == exc['to']):
            errors.append(f'{addr}: malformed user-approved exception')
            continue
        if exc.get('renderer_only'):
            expected = exc['from'].replace('、', '，').replace('。', '．')
            if exc['to'] != expected or exc['from'] == expected or exc.get('display_only'):
                errors.append(f'{addr}: unapproved prologue renderer transformation')
            continue
        if exc.get('display_only'):
            if addr not in ('0x00D82498', '0x00D8246A'):
                errors.append(f'{addr}: unapproved display-only exception')
            if addr in base.get('overrides', {}) and base['overrides'][addr] != exc['from']:
                errors.append(f'{addr}: display-only exception changed baseline source')
            if addr in overrides and addr in base.get('overrides', {}) and overrides[addr] != exc['from']:
                errors.append(f'{addr}: display-only exception changed override source')
            continue
        if base.get('overrides', {}).get(addr) != exc['to']:
            errors.append(f'{addr}: baseline differs from the approved exception text')
        if overrides.get(addr) != exc['to']:
            errors.append(f'{addr}: override differs from the approved exception text')
    return errors


# Bulk user-approved B-team rewrites (2026-11-04 humanizer, plan D3). The
# baseline keeps the original B-team text; each ledger entry approves exactly
# (address, from=baseline, to=current override). The ledger file bytes are
# pinned here, so adding or editing an entry is a reviewed code change.
APPROVED_REWRITE_LEDGER = os.path.join(BASE, 'data', 'bteam_approved_rewrites.json')
APPROVED_REWRITE_LEDGER_DIGEST = '4e1313a7b1a2a29d9868f8b3661772244ff605b661a37670ade6e4154862114e'
LEDGER_REQUIRED_FIELDS = ('from', 'to', 'batch', 'reviewed_by', 'review_ref')


def load_ledger_bytes(path: str = None) -> bytes:
    return Path(path or APPROVED_REWRITE_LEDGER).read_bytes()


def ledger_entries(ledger_bytes: bytes) -> dict:
    """Parsed entries without validation; non-dict content yields {}."""
    try:
        data = json.loads(ledger_bytes.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        return {}
    entries = data.get('entries') if isinstance(data, dict) else None
    return entries if isinstance(entries, dict) else {}


def ledger_errors(base: dict, overrides: dict, ledger_bytes: bytes,
                  pinned: str = None) -> list:
    """Each ledger entry is valid only for its exact (address, from, to) tuple."""
    errors = []
    pinned = APPROVED_REWRITE_LEDGER_DIGEST if pinned is None else pinned
    if hashlib.sha256(ledger_bytes).hexdigest() != pinned:
        errors.append('approved rewrite ledger digest mismatch (APPROVED_REWRITE_LEDGER_DIGEST)')
    try:
        data = json.loads(ledger_bytes.decode('utf-8'))
    except (UnicodeDecodeError, ValueError) as exc:
        return errors + [f'approved rewrite ledger is not valid JSON: {exc}']
    if not isinstance(data, dict) or not isinstance(data.get('entries'), dict):
        return errors + ['approved rewrite ledger needs an "entries" object']
    top_approved = data.get('approved')
    recorded = base.get('_user_approved_exceptions', {})
    expected = base.get('overrides', {})
    for addr, entry in data['entries'].items():
        if norm(addr) != addr:
            errors.append(f'{addr}: ledger key is not a normalized 0x%08X address')
            continue
        if addr in APPROVED_EXCEPTIONS or addr in recorded:
            errors.append(f'{addr}: ledger entry overlaps an individually approved exception')
            continue
        if not isinstance(entry, dict):
            errors.append(f'{addr}: malformed ledger entry')
            continue
        missing = [f for f in LEDGER_REQUIRED_FIELDS
                   if not isinstance(entry.get(f), str) or not entry[f]]
        approved = entry.get('approved', top_approved)
        if not isinstance(approved, str) or not approved:
            missing.append('approved')
        if missing:
            errors.append(f'{addr}: ledger entry missing {", ".join(missing)}')
            continue
        if addr not in expected:
            errors.append(f'{addr}: ledger address is not a B-team baseline address')
            continue
        if entry['from'] != expected[addr]:
            errors.append(f'{addr}: ledger "from" differs from the B-team baseline')
        if entry['from'] == entry['to']:
            errors.append(f'{addr}: ledger entry does not change the text')
        if overrides.get(addr) != entry['to']:
            errors.append(f'{addr}: override differs from the ledger "to" text')
    return errors


def rewrite_owner_texts(rewrites: dict = None, path: str = None) -> tuple[dict, list]:
    """Per-row final text of the W3 overlay (data/dialogue_rewrites.json).

    ``dialogue_rewrite_apply`` owns the format: each accepted message records
    ``owner_texts`` (row key -> rewritten row text), and the same value becomes
    the ledger ``to`` of every B-team row in it. A message without that record
    cannot prove which protected rows it rewrote, so it is an error.
    Returns ({0x%08X address: text}, errors).
    """
    from dialogue_rewrite_apply import REWRITES, key8, load_rewrites
    errors = []
    if rewrites is None:
        try:
            rewrites = load_rewrites(path or REWRITES)
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            return {}, [f'dialogue rewrite overlay unreadable: {exc}']
    texts, owner = {}, {}
    for key, entry in sorted(rewrites.get('messages', {}).items()):
        rows = entry.get('owner_texts') if isinstance(entry, dict) else None
        if not isinstance(rows, dict) or not rows:
            errors.append(f'{key}: dialogue rewrite lacks owner_texts (rewritten rows unproven)')
            continue
        for row, text in rows.items():
            try:
                addr = key8(int(row, 16))
            except (TypeError, ValueError):
                errors.append(f'{key}: invalid owner_texts row key {row!r}')
                continue
            if not isinstance(text, str):
                errors.append(f'{key}: owner_texts {addr} is not text')
                continue
            if addr in owner and owner[addr] != key:
                errors.append(f'{addr}: row owned by two dialogue rewrites ({owner[addr]}, {key})')
                continue
            texts[addr], owner[addr] = text, key
    return texts, errors


def check(base: dict, overrides: dict, pinned: str = None, *,
          ledger_bytes: bytes = None, ledger_pinned: str = None,
          rewrites: dict = None) -> dict:
    """Source gate on the effective final text: overrides, then the W3 overlay.

    W3 rewrites replace whole messages after every override stage, so each
    protected row they own is compared by its rewritten text. An unlisted
    change therefore stays drift; a listed one must match the ledger exactly.
    """
    expected = base.get('overrides', {})
    rewritten, rewrite_errors = rewrite_owner_texts(rewrites)
    overrides = dict(overrides)
    overrides.update({a: t for a, t in rewritten.items() if a in expected})
    if ledger_bytes is None:
        ledger_bytes = load_ledger_bytes()
    approved_rewrites = ledger_entries(ledger_bytes)
    drift = [(a, w, overrides[a]) for a, w in expected.items()
             if a in overrides and overrides[a] != w
             and not (isinstance(approved_rewrites.get(a), dict)
                      and approved_rewrites[a].get('from') == w
                      and approved_rewrites[a].get('to') == overrides[a])
             and not (int(a, 16) == 0xA34B6C
                      and w == '예　아뇨'
                      and overrides[a] == '　예　　　아뇨')]
    # The two consensus re-keys precede the other worker's override migration.
    # Accept only their exact legacy text in the source-data gate; the final
    # ROM gate still protects the corrected source addresses and fails today.
    missing = [(a, w) for a, w in expected.items()
               if a not in overrides and overrides.get(ALIGNMENT_LEGACY_KEYS.get(a)) != w]
    errors = rewrite_errors + exception_errors(base, overrides)
    errors += ledger_errors(base, overrides, ledger_bytes, ledger_pinned)
    pinned = PINNED_CORE_DIGEST if pinned is None else pinned
    if core_digest(base) != pinned:
        errors.append('baseline entries outside the approved exceptions changed (core digest mismatch)')
    return {'drift': drift, 'missing': missing, 'errors': errors}


def authorized_dcf_a8c_reflow(rom: bytes, message: dict) -> bool:
    """Require the two protected rows to be adjacent across the native newline."""
    if message.get('msg') != '0xDCFA8C':
        return False
    spans = message.get('line_spans', {})
    first = spans.get('0xDCFA8E')
    following = spans.get('0xDCFABB')
    if not first or not following:
        return False
    first_off, first_len = first
    next_off, next_len = following
    target, new_len = int(message['new_addr'], 16), int(message['new_len'])
    if (target < 0 or new_len <= 0 or target + new_len > len(rom)
            or first_off < 0 or first_len <= 0 or first_off + first_len > new_len
            or next_off < 0 or next_len <= 0 or next_off + next_len > new_len
            or next_off != first_off + first_len + 3):
        return False
    return rom[target + first_off + first_len:target + next_off] == b'\x72\x0a\x09'


def accept(base: dict, overrides: dict, *, allow_bteam_changes: bool = False, pinned: str = None,
           ledger_bytes: bytes = None) -> dict:
    """New baseline from current overrides. Refuses to widen beyond the exceptions.

    Ledger addresses keep their B-team baseline text: bulk rewrites are
    approved by the pinned ledger, never by re-snapshotting the baseline.
    """
    if ledger_bytes is None:
        ledger_bytes = load_ledger_bytes()
    keep = ledger_entries(ledger_bytes)
    new = dict(base)
    new['overrides'] = {a: (base['overrides'][a] if a in keep else overrides[a])
                        for a in base.get('overrides', {}) if a in overrides}
    new['count'] = len(new['overrides'])
    if exception_errors(new, overrides):
        raise ValueError('approved exceptions do not match the current overrides')
    pinned = PINNED_CORE_DIGEST if pinned is None else pinned
    if core_digest(new) != pinned and not allow_bteam_changes:
        changed = sorted(a for a, v in new['overrides'].items()
                         if a not in base.get('_user_approved_exceptions', {})
                         and base['overrides'].get(a) != v)
        raise ValueError('--accept would change B-team entries outside the approved exceptions: '
                         + ', '.join(changed[:10]) + (' ...' if len(changed) > 10 else '')
                         + ' (needs --allow-bteam-changes and a new PINNED_CORE_DIGEST)')
    return new


def check_rom(base: dict, rom_path: str, map_path: str, manifest_path: str,
              map_rom_path: str | None = None, *, observations=None,
              ledger_bytes: bytes = None, ledger_pinned: str = None) -> list[dict]:
    """Compare protected text with final ROM bytes, including relocated messages.

    Relocation metadata records each original line's final byte span. Reject
    stale write metadata before checking text so a mismatched map cannot pass.
    """
    if ledger_bytes is None:
        ledger_bytes = load_ledger_bytes()
    ledger_pinned = APPROVED_REWRITE_LEDGER_DIGEST if ledger_pinned is None else ledger_pinned
    if hashlib.sha256(ledger_bytes).hexdigest() != ledger_pinned:
        raise ValueError('approved rewrite ledger digest mismatch')
    approved_rewrites = ledger_entries(ledger_bytes)
    # plan_C B-pin (2026-11-04 user): rows of contract-pinned messages whose reviewed
    # wording the builder's B-pin writer ships (tools/bpin_contract.py). They are
    # ledger-owned like W3 rows: only the approved "to" passes, never the baseline.
    from bpin_contract import bteam_approvals
    approved_rewrites = dict(approved_rewrites)
    for _key, _entry in bteam_approvals().items():
        if _key in approved_rewrites:
            raise ValueError(f'{_key}: B-pin approval overlaps the approved rewrite ledger')
        approved_rewrites[_key] = {'from': _entry['baseline'], 'to': _entry['to'],
                                   'batch': _entry['batch'], 'review_ref': _entry['review_ref']}
    rom = Path(rom_path).read_bytes()
    map_rom = Path(map_rom_path).read_bytes() if map_rom_path else rom
    if len(map_rom) != len(rom):
        raise ValueError('ROM and map ROM lengths differ')
    writes = json.loads(Path(map_path).read_text(encoding='utf-8'))
    # plan_C J decision (a): protected rows are read in their exact pre-ellipsis-
    # compaction form; restore_precompaction verifies every logged 「・・・」->「…」
    # transform against the final ROM first (display_equivalent folds stay as is).
    from korean_punct_glyphs import restore_precompaction
    final_rom = rom
    rom, writes = restore_precompaction(rom, writes)
    map_rom = rom if map_rom is final_rom else restore_precompaction(map_rom, json.loads(
        Path(map_path).read_text(encoding='utf-8')))[0]
    manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    by_addr = {int(row[0]): row for row in writes if row[3]}
    protected_addrs = sorted(int(key, 16) for key in base['overrides'])
    import bisect
    covering = {}
    for row in writes:
        start, slot = int(row[0]), int(row[1])
        if slot <= 0:
            continue
        lo = bisect.bisect_left(protected_addrs, start)
        hi = bisect.bisect_left(protected_addrs, start + slot, lo)
        for covered in protected_addrs[lo:hi]:
            covering[covered] = row
    in_place_fragments = {}
    from bpin_contract import NATIVE_WRITER as _bpin_native_writer
    for row in writes:
        if row[7] not in ('part2-prologue-drawn-comma-space', _bpin_native_writer) or len(row) < 9:
            continue
        bpin_owner = row[7] == _bpin_native_writer
        for key, span in row[8].get('source_line_fragments', {}).items():
            address = int(key, 16)
            offset, length = span
            # A later B-pin whole-message owner supersedes the prologue writer's spans.
            if ((address in in_place_fragments and not bpin_owner) or offset < 0 or length <= 0
                    or offset + length > int(row[2])):
                raise ValueError(f'{key}: invalid prologue final source fragment')
            in_place_fragments[address] = (row, offset, length)
    expected = {}
    for addr, slot, _enc_len, enc_hex, fill, *_rest in writes:
        enc = bytes.fromhex(enc_hex)
        if fill is not None:
            pattern = fill_pattern(fill)
            for k in range(len(enc), slot):
                expected[addr + k] = pattern[(k - len(enc)) % len(pattern)]
        for k, byte in enumerate(enc):
            expected[addr + k] = byte
    stale = [addr for addr, byte in expected.items() if addr >= len(map_rom) or map_rom[addr] != byte]
    if stale:
        raise ValueError(f'integrity map does not match ROM ({len(stale)} bytes; first 0x{stale[0]:X})')
    relocated = sorted((int(m['msg'], 16), int(m['msg'], 16) + int(m['old_len']), m)
                       for m in manifest if m.get('status') == 'relocated')
    starts = [x[0] for x in relocated]
    codes = load_syl()
    compact = compact_glyph_map()
    compact_writers = {'part1-unit-compact-name', 'part1-compact-ui',
                       'part1-battle-menu-font', 'bteam-round2-compact-residual'}
    if (set(protected_addrs) & COMPACT_GLYPH_ADDRESSES or
            any(row[3] and row[7] in compact_writers and int(row[0]) in protected_addrs
                for row in writes)):
        verify_compact_font(rom, compact)
    seams = load_reviewed_seams()
    def decode(payload: bytes, address: int, writer: str = '') -> str:
        if address in COMPACT_GLYPH_ADDRESSES and writer not in compact_writers:
            raise ValueError(f'0x{address:08X}: compact renderer writer evidence changed: {writer!r}')
        if writer in compact_writers:
            return decode_compact(payload, codes, compact)
        return decode_enc(payload, codes)

    issues = []
    for key, baseline in base['overrides'].items():
        addr = int(key, 16)
        if addr == 0xD821F0:
            # Neither retained source36 nor stale line spans can prove the display.
            from d821f0_contract import final as check_d821f0_display
            try:
                check_d821f0_display(rom, manifest, writes)
                if map_rom_path:
                    check_d821f0_display(map_rom, manifest, writes)
            except AssertionError as exc:
                issues.append(dict(address=key,baseline=baseline,
                    rom_text='<invalid D821F0 display contract>',
                    cause='repoint line mapping invalid',decision='RESTORE_BASELINE',
                    detail=str(exc)))
                if observations is not None:
                    observations.append(dict(address=key,baseline=baseline,
                        actual='<invalid D821F0 display contract>',matched=False))
                continue
        objective_start = None
        invalid_reflow = False
        i = bisect.bisect_right(starts, addr) - 1
        relocation = relocated[i] if i >= 0 and addr < relocated[i][1] else None
        # Exact writer wins over an earlier padded slot that happens to cover it.
        row = (in_place_fragments[addr][0] if addr in in_place_fragments
               else by_addr.get(addr) or covering.get(addr))
        if relocation:
            m = relocation[2]
            target = int(m['new_addr'], 16)
            sites = m.get('ptr_sites')
            if not sites:
                raise ValueError(f'{key}: relocated message lacks ptr_sites')
            if map_rom_path:
                end = target + int(m['new_len'])
                if rom[target:end] != map_rom[target:end] or any(
                        rom[int(site, 16):int(site, 16) + 4] !=
                        map_rom[int(site, 16):int(site, 16) + 4] for site in sites):
                    raise ValueError(f'{key}: overlay changed protected relocated message or pointer')
            bad_sites = [site for site in sites if int.from_bytes(
                rom[int(site, 16):int(site, 16) + 4], 'little') != 0x08000000 + target]
            span = source_fragments(m, f'0x{addr:06X}')
            payload = None
            if bad_sites:
                actual = '<bad repoint pointer at ' + ', '.join(bad_sites) + '>'
                cause = 'repoint pointer mismatch'
            elif not span:
                actual = '<protected row missing from relocated line spans>'
                cause = 'repoint line mapping missing'
            else:
                off, _length = span[0]
                payload = source_row_bytes(rom, m, f'0x{addr:06X}')
                objective_start = target + off
                # A wrapped row may contain this verified internal control.
                display_payload = payload.replace(b'\x72\x0a\x09', b'\x81\x40')
                display_payload = script_format_bytes(display_payload, addr)
                if addr in (0xA2AA08, 0xA2BC3C):
                    # This protected CO sentence uses a native row break
                    # in place of its authored fullwidth space.
                    display_payload = co_breaks_as_spaces(display_payload)
                actual = decode(display_payload, addr).rstrip(' \u3000')
                cause = 'relocated row differs from protected baseline'
            wanted = display_equivalent(baseline, addr)
            matched = wanted == display_equivalent(actual, addr, actual=True)
            if addr == 0xDCFA8E and m['msg'] == '0xDCFA8C' and payload is not None:
                if authorized_dcf_a8c_reflow(rom, m):
                    next_off, next_len = m['line_spans']['0xDCFABB']
                    first_text = decode(payload, addr).rstrip(' \u3000')
                    second_text = decode(rom[target + next_off:target + next_off + next_len], addr).rstrip(' \u3000')
                    matched = (first_text == '이\u3000싸움의\u3000뒤에\u3000있는\u3000자가\u3000얼마나'
                               and second_text == '강적일지도\u3000모르는\u3000거라고！'
                               and wanted == display_equivalent('이 싸움의 뒤에 있는 자가　얼마나 강적일지도', addr))
                else:
                    matched = False
                    invalid_reflow = True
                    cause = 'repoint line mapping invalid'
                    payload = None
            if not matched and payload is not None and is_part2_story_address(addr):
                message = int(m['msg'], 16)
                matched = display_equivalent(actual, addr, actual=True) in reviewed_seam_variants(wanted, message, seams)
            if not matched and payload is not None:
                # The explicit wrap replaced an authored space; some older
                # baselines had no space at that point. Keep both readings.
                no_wrap_space = decode(payload.replace(b'\x72\x0a\x09', b''), addr)
                matched = wanted == display_equivalent(no_wrap_space, addr, actual=True)
            if not matched and payload is not None and actual:
                # A few authority rows cover consecutive physical rows.
                ordered = sorted(m['line_spans'].items(), key=lambda entry: entry[1][0])
                idx = next((n for n, (key2, _) in enumerate(ordered)
                            if int(key2, 16) == addr), -1)
                if idx >= 0:
                    parts = [actual]
                    prior_end = ordered[idx][1][0] + ordered[idx][1][1]
                    for _next_key, (next_off, next_len) in ordered[idx + 1:idx + 3]:
                        if next_len <= 0 or next_off != prior_end:
                            break
                        parts.append(decode(source_row_bytes(rom, m, _next_key), addr))
                        prior_end = next_off + next_len
                        if wanted in (display_equivalent(''.join(parts), addr, actual=True),
                                      display_equivalent('　'.join(parts), addr, actual=True)):
                            actual = ' | '.join(parts)
                            matched = True
                            break
        elif row:
            row_start = int(row[0])
            objective_start = addr
            enc_end = row_start + int(row[2])
            if map_rom_path and rom[addr:row_start + int(row[1])] != map_rom[addr:row_start + int(row[1])]:
                raise ValueError(f'{key}: overlay changed protected in-place slot')
            if addr in in_place_fragments:
                _owner, offset, length = in_place_fragments[addr]
                objective_start = row_start + offset
                payload = rom[objective_start:objective_start + length]
            else:
                payload = rom[addr:max(addr, enc_end)]
            actual = decode(payload, addr, row[7])
            if addr != 0xD9159E:
                actual = actual.rstrip(' \u3000')
            if row[7] == 'part2-prologue-inline-renderer':
                # The writer owns a whole multi-line script at this address;
                # the B-team authority applies to its first displayed row.
                payload = rom[addr:enc_end].split(b'\x77\x72', 1)[0]
                actual = decode(payload, addr, row[7]).rstrip(' \u3000')
            matched = display_equivalent(actual, addr, actual=True) == display_equivalent(baseline, addr)
            if not matched and row[7]=='dialogue-pixel-layout-source':
                # Native CO Break titles reserve three blank cells for a
                # separately drawn OBJ caption. Validate that exact reservation
                # from the immutable original, then compare the complete title.
                original=Path(BASE,'original','Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
                title_sources={int.from_bytes(original[base+0x18:base+0x1C],'little')-0x08000000+2
                               for base in range(0xDF3B54,0xDF3CD4,0x20)}
                matched=(addr in title_sources and row_start==addr
                         and original[addr:addr+6]==b'\x81\x40'*3
                         and actual.startswith('\u3000'*3)
                         and display_equivalent(actual[3:],addr,actual=True)==display_equivalent(baseline,addr))
            if not matched and addr in seams and is_part2_story_address(addr):
                matched = display_equivalent(actual, addr, actual=True) in reviewed_seam_variants(
                    display_equivalent(baseline, addr), addr, seams)
            if not matched and addr in ALIGNMENT_COMPOSITE_NEXT and row_start == addr:
                next_addr = ALIGNMENT_COMPOSITE_NEXT[addr]
                next_row = by_addr.get(next_addr)
                if next_row and int(next_row[0]) == next_addr and next_addr >= enc_end:
                    next_text = decode(rom[next_addr:next_addr + int(next_row[2])],
                                       next_addr, next_row[7]).rstrip(' \u3000')
                    matched = matches_alignment_composite(
                        display_equivalent(baseline, addr), actual, next_text,
                        rom[enc_end:next_addr], addr)
            cause = (f'final in-place writer {row[7]} level={row[6]}'
                     f' at 0x{row_start:08X}; source={row[5]!r}')
        else:
            # No write evidence is a hard failure; guessing a text boundary
            # would turn unknown controls or binary assets into a false pass.
            actual = '<no text write in integrity map>'
            matched = False
            cause = 'protected address has no final text write evidence'
        ledger_owned = key in approved_rewrites
        if ledger_owned:
            # A ledger-owned row must ship the approved rewrite: once its
            # (address, from=baseline) binding is valid, only the rendered
            # "to" passes. The baseline-equivalence fallbacks below would
            # otherwise accept the old wording that the rewrite replaced.
            rewrite = approved_rewrites[key]
            bound = (isinstance(rewrite, dict) and rewrite.get('from') == baseline
                     and isinstance(rewrite.get('to'), str) and bool(rewrite['to']))
            matched = bound and (display_equivalent(actual, addr, actual=True)
                                 == display_equivalent(rewrite['to'], addr))
            if not matched and not actual.startswith('<'):
                cause = ('ledger-owned row differs from approved rewrite "to"' if bound
                         else 'ledger entry not bound to the B-team baseline')
        if not matched and not ledger_owned:
            matched = matches_reviewed_bteam_spacing(addr, baseline, actual)
        if not matched and not ledger_owned and key in base.get('_user_approved_exceptions', {}):
            exception = base['_user_approved_exceptions'][key]
            if exception.get('renderer_only'):
                matched = actual == exception['to']
        if not matched and not ledger_owned:
            matched = round2_width_equivalent(baseline, actual, addr)
        if not matched and not ledger_owned and key in APPROVED_EXCEPTIONS and 0xA2D55C <= addr <= 0xA2D8A8:
            # The approved M29 pair title is drawn by the strict pair-title
            # writer, which emits the original fullwidth glyphs (！) like the
            # other FIX_GATE mission titles; words and order stay exact.
            matched = actual == original_glyph_encoding(baseline)
        if not matched and not ledger_owned and addr in ROUND2_PREFIX_GLYPH_ROWS and addr in FIX_GATE_ADDRESSES:
            matched = actual == '　' * ROUND2_PREFIX_GLYPH_ROWS[addr] + display_equivalent(baseline, addr)
        if not matched and not ledger_owned and objective_start is not None:
            matched = round2_objective_equivalent(rom, baseline, actual, addr, objective_start)
        if addr in DEFERRED_ADDRESSES:
            matched = False  # Reviewed decision withholds acceptance, even on a later ROM.
        if invalid_reflow:
            matched = False
        if observations is not None:
            observations.append(dict(address=key,baseline=baseline,actual=actual,matched=matched))
        if not matched:
            issues.append({'address': key, 'baseline': baseline, 'rom_text': actual,
                           'cause': cause,
                           'decision': 'DEFER' if addr in DEFERRED_ADDRESSES else
                                       'FIX_GATE_BLOCKED' if addr in COMPACT_GLYPH_ADDRESSES else
                                       'ALIGNMENT_RESTORE' if addr in ALIGNMENT_RESTORE_ADDRESSES else
                                       'NEW_STRICT_MISMATCH' if addr in NEW_STRICT_ADDRESSES else
                                       'APPLY_LEDGER_REWRITE' if ledger_owned else
                                       'RESTORE_BASELINE'})
    return issues


STRUCTURAL_ROUND2_CAUSES = frozenset({
    'repoint pointer mismatch', 'repoint line mapping missing',
    'repoint line mapping invalid', 'protected address has no final text write evidence',
})


def is_structural_round2_issue(issue: dict) -> bool:
    return issue['cause'] in STRUCTURAL_ROUND2_CAUSES


def round2_issue_bucket(issue: dict, listed: set[int]) -> str:
    addr = int(issue['address'], 16)
    if is_structural_round2_issue(issue):
        return 'unlisted'
    if addr in DEFERRED_ADDRESSES:
        return 'deferred'
    if addr in listed and (issue['cause'] == 'relocated row differs from protected baseline'
                           or issue['cause'].startswith('final in-place writer ')):
        return 'residual'
    return 'unlisted'


ROUND2_PIN_RELEASE = Path(BASE, 'data', 'bteam_round2_pin_release.json')


def round2_pin_release() -> dict:
    """Rows released from the round-2 byte pin (lane T, plan_C B, 2026-11-04 user)."""
    if not ROUND2_PIN_RELEASE.exists():
        return {}
    data = json.loads(ROUND2_PIN_RELEASE.read_text(encoding='utf-8'))
    released = {k: v for k, v in data.items() if not k.startswith('_')}
    for key, value in released.items():
        if (not key.startswith('0x') or len(key) != 10 or not isinstance(value, dict)
                or not isinstance(value.get('to'), str) or not value.get('approved')):
            raise ValueError(f'{key}: invalid round-2 pin release entry')
    return released


def classify_round2_issues(issues: list[dict], base: dict, rom_path: str,
                           manifest_path: str, map_path: str = None) -> tuple[list[dict], list[dict], list[dict]]:
    """Count only byte-pinned listed residuals and exact reviewed deferrals as expected."""
    path = Path(BASE, 'data', 'bteam_round2_residuals.tsv')
    if hashlib.sha256(path.read_bytes()).hexdigest() != ROUND2_RESIDUAL_DIGEST:
        raise ValueError('B-team residual manifest digest changed')
    with path.open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    listed = {int(row['address'], 16): row for row in rows}
    if len(rows) != 87 or len(listed) != len(rows):
        raise ValueError('B-team residual list count or addresses changed')
    pins_path = Path(BASE, 'data', 'bteam_round2_active_pins.json')
    if hashlib.sha256(pins_path.read_bytes()).hexdigest() != ROUND2_ACTIVE_PINS_DIGEST:
        raise ValueError('B-team active residual pin digest changed')
    pins = {int(key, 16): value for key, value in json.loads(
        pins_path.read_text(encoding='utf-8')).items()}
    rom = Path(rom_path).read_bytes()
    if map_path:
        # plan_C J decision (a): residual byte pins and reviewed after-hashes are
        # checked on the exact pre-ellipsis-compaction bytes (transform verified).
        from korean_punct_glyphs import restore_precompaction
        rom = restore_precompaction(rom, json.loads(Path(map_path).read_text(encoding='utf-8')))[0]
    manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    spans = {}
    messages = {}
    for message in manifest:
        if message.get('status') == 'relocated':
            for key, (offset, length) in message.get('line_spans', {}).items():
                address = int(key, 16)
                if address in spans:
                    raise ValueError(f'0x{address:08X}: duplicate relocated line mapping')
                spans[address] = (int(message['new_addr'], 16) + offset, length)
                messages[address] = message
    released = round2_pin_release()
    from bpin_contract import bteam_approvals
    bpin_rows = bteam_approvals()
    for addr, row in listed.items():
        key = f'0x{addr:08X}'
        if key in bpin_rows:
            # plan_C B-pin: the builder's B-pin writer owns the row; check_rom
            # treats it as ledger-owned and requires its approved `to`.
            continue
        if key in released:
            # plan_C B (2026-11-04 user): released from the byte pin; the W3
            # overlay owns the row and the ROM must show the release `to`.
            if addr in spans:
                pos, size = spans[addr]
                actual = decode_enc(rom[pos:pos + size].replace(b'\x72\x0a\x09', b'\x81\x40'),
                                    load_syl()).rstrip(' \u3000')
                if (display_equivalent(actual, addr, actual=True).replace('\u3000', ' ').strip()
                        != display_equivalent(released[key]['to'], addr).replace('\u3000', ' ').strip()):
                    raise ValueError(f'{key}: released residual row does not show its approved text')
            continue
        payload = bytes.fromhex(row['payload_hex'])
        if (key not in base['overrides'] or row['expected_baseline'] != base['overrides'][key]
                or not row['reason'] or not payload or rom[addr:addr + len(payload)] != payload):
            raise ValueError(f'{key}: listed residual metadata or source bytes changed')
        message = messages.get(addr)
        pinned_message = pins.get(addr)
        if addr == 0xDCE89A and message and not pinned_message:
            pos, size = spans[addr]
            actual = decode_enc(rom[pos:pos + size].replace(b'\x72\x0a\x09', b'\x81\x40'), load_syl())
            target = int(message['new_addr'], 16)
            sites = message.get('ptr_sites') or []
            if (display_equivalent(row['expected_baseline'], addr) !=
                    display_equivalent(actual, addr)
                    or addr in {int(issue['address'], 16) for issue in issues}
                    or not sites or any(int.from_bytes(rom[int(site, 16):int(site, 16) + 4],
                                                      'little') != 0x08000000 + target for site in sites)):
                raise ValueError(f'{key}: restored relocated baseline or pointer changed')
            continue
        if addr == 0xDCFA8E and message and not pinned_message:
            # This formerly deferred row is now wrapped and fully restored in
            # its live message. The source-slot residual remains byte-pinned.
            if not authorized_dcf_a8c_reflow(rom, message):
                raise ValueError(f'{key}: restored relocated reflow layout changed')
            pos, size = spans[addr]
            actual = decode_enc(rom[pos:pos + size], load_syl()).rstrip(' \u3000')
            next_off, next_len = message['line_spans']['0xDCFABB']
            next_actual = decode_enc(rom[int(message['new_addr'], 16) + next_off:
                                         int(message['new_addr'], 16) + next_off + next_len], load_syl()).rstrip(' \u3000')
            target = int(message['new_addr'], 16)
            sites = message.get('ptr_sites') or []
            if (actual != '이\u3000싸움의\u3000뒤에\u3000있는\u3000자가\u3000얼마나'
                    or next_actual != '강적일지도\u3000모르는\u3000거라고！'
                    or display_equivalent(row['expected_baseline'], addr) !=
                    display_equivalent('이 싸움의 뒤에 있는 자가　얼마나 강적일지도', addr)
                    or addr in {int(issue['address'], 16) for issue in issues}
                    or not sites or any(int.from_bytes(rom[int(site, 16):int(site, 16) + 4],
                                                      'little') != 0x08000000 + target for site in sites)):
                raise ValueError(f'{key}: restored relocated baseline or pointer changed')
            continue
        from dialogue_spacing import reviewed_message_pin, verify_reviewed_owner_bytes
        reviewed = bool(message) and reviewed_message_pin(rom,message,pinned_message)
        if bool(message) != bool(pinned_message) and not reviewed:
            raise ValueError(f'{key}: active residual mapping or byte pin missing')
        if message:
            target = int(message['new_addr'], 16)
            length = int(message['new_len'])
            off, span_length = message['line_spans'][f'0x{addr:06X}']
            if (off < 0 or span_length <= 0 or off + span_length > length
                    or (not reviewed and (len(bytes.fromhex(pinned_message)) != length
                    or rom[target:target + length].hex() != pinned_message))):
                raise ValueError(f'{key}: active residual message bytes or span changed')
            sites = message.get('ptr_sites') or []
            if not sites or any(int.from_bytes(rom[int(site, 16):int(site, 16) + 4],
                                               'little') != 0x08000000 + target for site in sites):
                raise ValueError(f'{key}: active residual pointer changed')
        if row['active_payload_hex']:
            if addr not in spans or not row['active_text']:
                raise ValueError(f'{key}: active residual has no relocated line')
            pos, length = spans[addr]
            active = bytes.fromhex(row['active_payload_hex'])
            pair_title = 0xA2D55C <= addr <= 0xA2D8A8
            padding = (b'\x00' if pair_title else b' ') * (length - len(active))
            if (len(active) > length or rom[pos:pos + length] != active + padding) and not (
                    reviewed and verify_reviewed_owner_bytes(rom,message,addr)):
                raise ValueError(f'{key}: active residual bytes changed')
            if row['active_follow_hex']:
                expected_follow = bytes.fromhex(row['active_follow_hex'])
                from repoint_source_rows import row_bytes
                if addr != 0xA2BC3C or row_bytes(rom,message,'0xA2BC57') != expected_follow:
                    raise ValueError(f'{key}: residual continuation bytes changed')
    expected_residuals, deferred, unlisted = [], [], []
    listed_addresses = set(listed)
    for issue in issues:
        bucket = round2_issue_bucket(issue, listed_addresses)
        if bucket == 'deferred':
            deferred.append(issue)
        elif bucket == 'residual':
            expected_residuals.append(issue)
        else:
            unlisted.append(issue)
    if {int(x['address'], 16) for x in deferred} != DEFERRED_ADDRESSES:
        raise ValueError('B-team deferred issue set changed')
    return expected_residuals, deferred, unlisted


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--accept', action='store_true',
                    help='현재 override로 baseline 갱신(승인된 예외 범위만; 그 밖의 변경은 거부)')
    ap.add_argument('--allow-bteam-changes', action='store_true',
                    help='--accept와 함께: 예외 밖 B팀 문구 변경까지 확정(별도 승인 필요, PINNED_CORE_DIGEST도 갱신해야 게이트 통과)')
    ap.add_argument('--rom', help='최종 ROM 보호 대사 전수 검사')
    ap.add_argument('--map', default=os.path.join(BASE, 'temp', 'integrity_map.json'))
    ap.add_argument('--map-rom', help='overlay 후보일 때 map을 만든 B 빌드 ROM (기본: --rom)')
    ap.add_argument('--repoint-manifest', default=os.path.join(BASE, 'temp', 'repoint_manifest.json'))
    ap.add_argument('--json', help='ROM 불일치 전체 JSON 보고서 경로')
    args = ap.parse_args()

    ovn = load_overrides()

    if args.accept:
        # 우발 drift를 권위본으로 봉인하는 사고 방지: 명시적 환경변수 승인 필요(codex 리뷰).
        if os.environ.get('AW_BTEAM_ACCEPT') != '1':
            print('거부: baseline 갱신은 의도적 B팀 변경 확정 전용. 변경 내역을 git diff로 확인 후\n'
                  '  AW_BTEAM_ACCEPT=1 python3 tools/qa_bteam_drift.py --accept 로 재실행하라.', file=sys.stderr)
            sys.exit(2)
        base = json.load(open(BASELINE, encoding='utf-8'))
        try:
            base = accept(base, ovn, allow_bteam_changes=args.allow_bteam_changes)
        except ValueError as exc:
            print('거부: ' + str(exc), file=sys.stderr)
            sys.exit(2)
        json.dump(base, open(BASELINE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'baseline 갱신: {base["count"]}개 B팀 주소를 현재 override로 확정 (core digest {core_digest(base)})')
        return

    base = json.load(open(BASELINE, encoding='utf-8'))
    absent = (DEFERRED_ADDRESSES | COMPACT_GLYPH_ADDRESSES |
              NEW_STRICT_ADDRESSES | ALIGNMENT_RESTORE_ADDRESSES) - {
        int(key, 16) for key in base['overrides']}
    if absent:
        print('[HARD-FAIL] reviewed gate addresses missing from baseline: ' +
              ', '.join(f'0x{addr:08X}' for addr in sorted(absent)), file=sys.stderr)
        sys.exit(1)
    result = check(base, ovn)
    drift, missing = result['drift'], result['missing']
    for error in result['errors']:
        print(f'[HARD-FAIL] {error}', file=sys.stderr)
    if result['errors']:
        sys.exit(1)
    expected = base.get('overrides', {})
    if args.rom:
        try:
            issues = check_rom(base, args.rom, args.map, args.repoint_manifest, args.map_rom)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f'[HARD-FAIL] ROM 검사 입력 오류: {exc}', file=sys.stderr)
            sys.exit(1)
        if args.json:
            Path(args.json).write_text(json.dumps(issues, ensure_ascii=False, indent=2), encoding='utf-8')
        try:
            residuals, deferred, unlisted = classify_round2_issues(
                issues, base, args.rom, args.repoint_manifest, args.map)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f'[HARD-FAIL] ROM residual classification error: {exc}', file=sys.stderr)
            sys.exit(1)
        print(f'B팀 최종 ROM 검사: {len(expected)}개, mismatch {len(issues)}개 '
              f'(listed residual {len(residuals)}, deferred {len(deferred)}, '
              f'unlisted {len(unlisted)})')
        print('  [DEFERRED] ' + ', '.join(x['address'] for x in deferred))
        for issue in unlisted:
            print(f"  [ROM-DRIFT:{issue['decision']}] {issue['address']} baseline={issue['baseline']!r} "
                  f"ROM={issue['rom_text']!r} cause={issue['cause']}")
        if unlisted:
            sys.exit(1)
    print(f'B팀 보호 주소: {len(expected)}')
    print(f'DRIFT(우발적 변형 의심): {len(drift)}  / MISSING(override 삭제됨): {len(missing)}')
    for addr, want, cur in drift[:40]:
        print(f'  [DRIFT] {addr}')
        print(f'          baseline: {want!r}')
        print(f'          현재:     {cur!r}')
    for addr, want in missing[:20]:
        print(f'  [MISSING] {addr}  baseline={want!r}')

    if drift or missing:
        print('\n[HARD-FAIL] B팀 권위문 변형/삭제 감지. 의도적이면 --accept, 아니면 복원하라.',
              file=sys.stderr)
        sys.exit(1)
    print('[HARD-OK] B팀 권위문 drift 0')


if __name__ == '__main__':
    main()
