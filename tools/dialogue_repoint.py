#!/usr/bin/env python3
"""대사 메시지 재배치(repoint) 엔진 — 짜옹이님 문구 불변, 단어붙음/축약 해소.

배경(2026-06-23 RE):
- Part2 캠페인 대사는 **메시지 포인터 테이블**(0x08A357B4, 3315엔트리, 단조 증가)로 참조된다.
  메시지 중간으로 들어오는 포인터는 없다(순차 읽기). 각 메시지는 라인(0x0A/제어로 구분) +
  종단 제어(예 6B 00..)로 구성.
- 빌드는 한글을 **원본 슬롯에 in-place**로 쓴다. 슬롯이 빠듯하면 encode_fit이 공백/부호를 제거
  (단어붙음 level>=10). 504행(거의 전부 짜옹이님 대사)이 이렇게 열화된다.
- 바로 뒤 0x00A3CF14~0x00B00000(799KB)이 미사용(0xFF) 여유공간.

해결(외부 서양판과 동일 기법): 열화가 생기는 메시지를 **스켈레톤(제어코드) 보존 재구성**해
여유공간에 전체로 기록하고, 테이블 포인터만 갱신한다. 라인 텍스트는 짜옹이님 원문을
**완전 충실(level0)** 인코딩 → 단어붙음/축약 없음. 제어 바이트는 한 바이트도 안 바뀐다.

안전장치:
- 각 메시지는 ROM 내 포인터가 정확히 1개(테이블 엔트리)일 때만 재배치(중간참조/다중참조 skip+보고).
- 메시지가 (라인 span + 제어 gap)으로 **정확 분해**될 때만 재배치(분해 불일치 skip+보고).
- 재구성된 메시지의 제어 바이트(라인 외 전부) == 원본 == 보존 검증.
- 여유공간 범위 초과/현재 비어있지 않으면 중단.
"""
import struct, json, os, collections
from dialogue_regions import is_part2_story_address, needs_safe_dialogue_punctuation, renderer_safe_symbol
from pcm_pointer_collisions import classify_pointer_sites

GBA = 0x08000000
PART1_DIALOG_LO = 0xD80000
PART1_DIALOG_HI = 0xE10000
PART1_DIALOG_ASCII_PUNCT = {
    0x21: b'\x81\x49',  # !
    0x22: b'\x81\x68',  # "
    0x23: b'\x81\x94',  # #
    0x24: b'\x81\x90',  # $
    0x25: b'\x81\x93',  # %
    0x26: b'\x81\x95',  # &
    0x27: b'\x81\x68',  # ' -> ” (0x8166 is blank in this font)
    0x28: b'\x81\x69',  # (
    0x29: b'\x81\x6A',  # )
    0x2A: b'\x81\x7B',  # * -> + (0x8196 is blank in this font)
    0x2B: b'\x81\x7B',  # +
    0x2C: b'\x81\x41',  # ,
    0x2D: b'\x81\x5C',  # -
    0x2E: b'\x81\x42',  # . -> 。 (0x8144 is blank in this font)
    0x2F: b'\x81\x5E',  # /
    0x3A: b'\x81\x47',  # : -> ； (0x8146 is blank in this font)
    0x3B: b'\x81\x47',  # ;
    0x3D: b'\x81\x5C',  # = -> ― (0x8181 is blank in this font)
    0x3F: b'\x81\x48',  # ?
    0x40: b'\x81\x94',  # @ -> # (0x8197 is blank in this font)
    0x5B: b'\x81\x69',  # [ -> （
    0x5C: b'\x81\x5F',  # backslash
    0x5D: b'\x81\x6A',  # ] -> ）
    0x7B: b'\x81\x69',  # { -> （
    0x7D: b'\x81\x6A',  # } -> ）
    0x7E: b'\x81\x60',  # ~
}


def is_sjis_lead(value):
    return 0x81 <= value <= 0x9F or 0xE0 <= value <= 0xEF


def has_independently_referenced_overlap(message, lines, texts, targets):
    return any(i != j and len(texts[j]) >= 4 and texts[j] in texts[i]
               and lines[j][0] != message and lines[j][0] in targets
               for i in range(len(texts)) for j in range(len(texts)))


def text_segment_cells(payload):
    """Half-cell width of encoded text; trailing 0x20 padding has no ink."""
    width = 0
    i = 0
    while i < len(payload):
        if is_sjis_lead(payload[i]) and i + 1 < len(payload):
            width += 2
            i += 2
        else:
            width += int(payload[i] != 0x20)
            i += 1
    return width


def normalize_text_segment(payload, part1, address=None):
    """Normalize a proven text span; callers must never pass control gaps."""
    _conv = bytearray(); _i = 0
    while _i < len(payload):
        _b = payload[_i]
        if is_sjis_lead(_b) and _i + 1 < len(payload):
            _conv += renderer_safe_symbol(payload[_i:_i + 2], address); _i += 2
        elif _b == 0x20:
            _nx = payload[_i + 1] if _i + 1 < len(payload) else 0
            if is_sjis_lead(_nx) or 0x21 <= _nx <= 0x7E:   # 다음이 content → interior space
                _conv += b'\x81\x40'
            else:
                _conv += b'\x20'
            _i += 1
        elif part1 and _b == 0x2E and payload[_i:_i + 3] == b'...':
            _conv += b'\x81\x45' * 3
            _i += 3
        elif part1 and _b in PART1_DIALOG_ASCII_PUNCT:
            _conv += renderer_safe_symbol(PART1_DIALOG_ASCII_PUNCT[_b], address); _i += 1
        elif _b == 0x2C:
            _conv += b'\x81\x41'; _i += 1
        else:
            _conv += bytes([_b]); _i += 1
    return bytes(_conv)


# ---------------------------------------------------------------------------
# Fragment seams (2026-10-07). Part 2 story messages join translated fragments
# with the same-row wait control 0x77 ('w'). Japanese needs no space there; the
# Korean fragments do, but the halfwidth 0x20 slot padding before 'w' is not
# rendered (몸에{20}{20}w혹시 -> "몸에혹시"). A seam is
#   [Hangul or ！/？ pair][0x20 * n][0x77 * m >= 1][Hangul pair]
# and is fixed by emitting a fullwidth space 0x8140 right after the last glyph.
# 、。・ are excluded: their fullwidth cells already carry blank space and the
# project style writes no space after them.
SEAM_WAIT = 0x77
SEAM_ROW_CONTINUE = frozenset((0x20, 0x57, 0x77))
SEAM_PREV_PUNCT = frozenset((0x8148, 0x8149))
PORTRAIT_ROW_HALF_CELLS = 44   # verified A3 portrait capacity (qa_part2_physical_rows)


def _tokens(data):
    """(offset, length) tokens; SJIS lead + trail is one token."""
    out = []
    i = 0
    while i < len(data):
        if is_sjis_lead(data[i]) and i + 1 < len(data):
            out.append((i, 2))
            i += 2
        else:
            out.append((i, 1))
            i += 1
    return out


def row_half_cells(data, pos):
    """Half-cell width of the row containing byte offset pos.

    Rows continue across 0x20 padding and the 0x57/0x77 waits; every other
    single byte (newline 72, page 6B, operands, NUL) ends the row. Unknown
    same-row controls would make this an underestimate, so callers treat it
    as a lower bound and report it, never as a pixel verdict.
    """
    toks = _tokens(data)
    idx = next((k for k, (o, n) in enumerate(toks) if o <= pos < o + n), len(toks) - 1)

    def breaks(tok):
        o, n = tok
        return n == 1 and data[o] not in SEAM_ROW_CONTINUE and not (0x21 <= data[o] <= 0x2F)

    lo = idx
    while lo > 0 and not breaks(toks[lo - 1]):
        lo -= 1
    hi = idx
    while hi + 1 < len(toks) and not breaks(toks[hi + 1]):
        hi += 1
    width = 0
    for o, n in toks[lo:hi + 1]:
        if n == 2:
            width += 2
        elif data[o] not in SEAM_ROW_CONTINUE and 0x21 <= data[o] <= 0x7E:
            width += 1
    return width


# The same 0x77 also splits a word from its particle around tutorial keywords
# (主砲の弾wやw燃料wが -> 탄약w과w연료w가, 搭載wして -> 탑승w시켜). Those seams
# must stay joined. A space is inserted only when every check agrees:
#   1. After ！/？ a seam is never bound.
#   2. A next Hangul run that is exactly a particle/ending (KO_BOUND_WORDS) is
#      bound, even where it could also be a word (이 = this): kept as is.
#   3. The Japanese source must be aligned; otherwise the seam is left as is.
#   4. Japanese word char (kanji/katakana/」) before the wait and a particle or
#      auxiliary right after it (燃料wが, 「占領」wという) means bound. This also
#      covers unspaced runs such as 연료w가없다 and restructured Korean, which
#      then stays joined (unfixed, never wrongly spaced).
# The next Hangul run is compared whole; a run that merely starts with a
# particle syllable (이번, 가볍게) is decided by rule 4.
KO_BOUND_WORDS = frozenset(
    '이 가 은 는 을 를 의 에 로 으로 와 과 도 만 께 께서 에서 에게 한테 에서는 에는 에도 '
    '으로는 로는 와는 과는 이나 나 이랑 랑 까지 부터 처럼 보다 마저 조차 밖에 '
    '이야 야 이다 이고 이며 이지 이죠 이요 이에요 예요 입니다 이었다 였다 '
    '라는 이라는 이라고 라고 이란 란 서 요 '
    '시켜 시키고 시킬 시킨 시켰'.split())
JP_BOUND_HEADS = ('が', 'を', 'は', 'の', 'に', 'で', 'と', 'や', 'へ', 'も', 'から', 'まで',
                  'より', 'して', 'させ', 'する', 'した', 'され', 'しな', 'だ', 'です', 'じゃ',
                  'って', 'という', 'とか', 'なら')


def _is_word_char(ch):
    """Kanji, katakana (incl. ー, not the ・ dot) or a closing bracket."""
    return ('\u4e00' <= ch <= '\u9fff' or ('\u30a0' <= ch <= '\u30ff' and ch != '\u30fb')
            or ch in '」』）')


def _decode_sjis_text(raw):
    """Text of a raw original span; controls/padding become separators."""
    out = []
    i = 0
    while i < len(raw):
        if is_sjis_lead(raw[i]) and i + 1 < len(raw):
            try:
                out.append(raw[i:i + 2].decode('shift_jis'))
            except UnicodeDecodeError:
                out.append('\x00')
            i += 2
        else:
            out.append('\x00')
            i += 1
    return ''.join(out)


def seam_is_bound(seam, jp_prev, jp_next):
    """True: keep joined. False: insert a space. None: source unaligned, keep."""
    if seam['prev_punct']:
        return False
    if seam['next_word'] in KO_BOUND_WORDS:
        return True
    if jp_prev is None or jp_next is None:
        return None
    prev = jp_prev.rstrip('\x00')
    nxt = jp_next.lstrip('\x00')
    return bool(prev and nxt and _is_word_char(prev[-1]) and nxt.startswith(JP_BOUND_HEADS))


def inplace_seam_spaces(current, source, hangul, max_row=PORTRAIT_ROW_HALF_CELLS):
    """In-place seam fix for one non-relocated message payload.

    Only padding 0x20 0x20 directly after the last glyph becomes 0x8140 (same
    length). The row width is recomputed on the updated payload before every
    insertion, so several seams in one row share the row budget.
    Returns (new_payload, records); each record has 'action' in
    inserted / bound / unaligned / needs_relocation / row_full.
    """
    data = bytearray(current)
    records = []
    for seam in find_seams(bytes(current), hangul):
        jp = source_context(source, bytes(current), seam)
        bound = seam_is_bound(seam, *jp)
        record = {'glyph_end': seam['glyph_end'], 'pads': seam['pads'], 'next_word': seam['next_word'],
                  'jp_prev': jp[0], 'jp_next': jp[1]}
        if bound is None:
            record['action'] = 'unaligned'
        elif bound:
            record['action'] = 'bound'
        elif seam['pads'] < 2:
            record['action'] = 'needs_relocation'
        else:
            at = seam['glyph_end']
            width = row_half_cells(bytes(data), at - 1)
            if width + 2 > max_row:
                record['action'] = 'row_full'
            else:
                if bytes(data[at:at + 2]) != b'  ':
                    raise AssertionError('seam padding changed')
                data[at:at + 2] = b'\x81\x40'
                record['action'] = 'inserted'
            record['row_half_cells'] = width
        records.append(record)
    return bytes(data), records


def find_seams(data, hangul):
    """Raw scan of one message payload for fragment seams (see above).

    hangul maps reserved Hangul code -> syllable.
    """
    seams = []
    toks = _tokens(data)
    for k, (o, n) in enumerate(toks):
        if n != 2:
            continue
        code = (data[o] << 8) | data[o + 1]
        if code not in hangul and code not in SEAM_PREV_PUNCT:
            continue
        j = o + 2
        pads = 0
        while j < len(data) and data[j] == 0x20:
            pads += 1
            j += 1
        waits = 0
        while j < len(data) and data[j] == SEAM_WAIT:
            waits += 1
            j += 1
        if not waits or j + 1 >= len(data) or not is_sjis_lead(data[j]):
            continue
        if ((data[j] << 8) | data[j + 1]) not in hangul:
            continue
        word = []
        w = j
        while w + 1 < len(data) and ((data[w] << 8) | data[w + 1]) in hangul:
            word.append(hangul[(data[w] << 8) | data[w + 1]])
            w += 2
        seams.append({'glyph_end': o + 2, 'pads': pads, 'waits': waits, 'next': j,
                      'prev_punct': code in SEAM_PREV_PUNCT,
                      'next_word': ''.join(word), 'row_half_cells': row_half_cells(data, o)})
    return seams


def _controls(data):
    return [(o, data[o]) for o, n in _tokens(data) if n == 1 and data[o] != 0x20]


def source_context(original, current, seam):
    """Japanese text around the matching control run of the original message.

    Controls are preserved byte-for-byte by every writer, so the k-th control
    of the current payload is the k-th control of the original. Returns
    (jp_prev, jp_next) or (None, None) when the control sequences differ.
    """
    cur_ctrl = _controls(current)
    org_ctrl = _controls(original)
    if [b for _, b in cur_ctrl] != [b for _, b in org_ctrl]:
        return None, None
    first_wait = seam['next'] - seam['waits']
    k = next((i for i, (o, _) in enumerate(cur_ctrl) if o == first_wait), None)
    if k is None:
        return None, None
    start = org_ctrl[k][0]
    end = org_ctrl[k + seam['waits'] - 1][0] + 1
    prev_ctrl = org_ctrl[k - 1][0] + 1 if k > 0 else 0
    next_ctrl = org_ctrl[k + seam['waits']][0] if k + seam['waits'] < len(org_ctrl) else len(original)
    return _decode_sjis_text(original[prev_ctrl:start]), _decode_sjis_text(original[end:next_ctrl])


def apply_seam_spaces(pieces, hangul, max_row=PORTRAIT_ROW_HALF_CELLS, report=None):
    """Fix seams across ['text', bytes, original] / ['gap', bytes, original] pieces.

    Only text pieces change: trailing 0x20 padding is replaced by one 0x8140.
    Control gaps are never touched. Returns (fixed, skipped_wide).
    """
    fixed = skipped = 0
    for i in range(len(pieces) - 2):
        if pieces[i][0] != 'text' or pieces[i + 1][0] != 'gap' or pieces[i + 2][0] != 'text':
            continue
        prev, gap, nxt = pieces[i][1], pieces[i + 1][1], pieces[i + 2][1]
        if not gap or any(b != SEAM_WAIT for b in gap):
            continue
        probe = prev + gap + nxt
        seam = [s for s in find_seams(probe, hangul) if s['next'] == len(prev) + len(gap)]
        if not seam:
            continue
        stripped = prev.rstrip(b' ')
        if seam[0]['glyph_end'] != len(stripped):
            continue
        jp_prev = _decode_sjis_text(pieces[i][2]) if len(pieces[i]) > 2 else None
        jp_next = _decode_sjis_text(pieces[i + 2][2]) if len(pieces[i + 2]) > 2 else None
        bound = seam_is_bound(seam[0], jp_prev, jp_next)
        if bound is not False:
            continue
        head = b''.join(p[1] for p in pieces[:i])
        joined = head + stripped + b'\x81\x40' + gap + b''.join(p[1] for p in pieces[i + 2:])
        if row_half_cells(joined, len(head) + len(stripped) - 1) > max_row:
            skipped += 1
            continue
        pieces[i][1] = stripped + b'\x81\x40'
        fixed += 1
    return fixed, skipped


def _read_table(orig, tbl_off):
    """단조 증가하며 한 스크립트 영역(상위 바이트 동일대)을 가리키는 포인터 테이블 범위."""
    def ptr(o):
        return struct.unpack_from('<I', orig, o)[0]
    first = ptr(tbl_off)
    if not (GBA <= first < GBA + len(orig)):
        return []
    region_hi = (first - GBA) >> 16
    entries = []
    o = tbl_off
    while o + 4 <= len(orig):
        v = ptr(o)
        if not (GBA <= v < GBA + len(orig)):
            break
        tgt = v - GBA
        # 같은 스크립트 영역(±2개 상위블록 허용: 0xA0~0xA3 등)
        if not (region_hi - 0 <= (tgt >> 16) <= region_hi + 4):
            break
        entries.append((o, tgt))
        o += 4
    return entries


def scan_command_messages(orig, lo=0x08B80000, hi=0x08E10000, opcode=0x19, scan_lo=0xD80000, scan_hi=0xE20000):
    """Part1 커맨드 스트림의 show-message 명령(opcode 0x19) 뒤에 오는 메시지 포인터를 수집.
    (2026-06-23 런타임 트레이싱으로 확증: 캐서린 대사 0xDF5D60 등이 0x19 뒤 포인터로 로드됨.)
    반환: {msg_addr: [ptr_offset...]}. 각 ptr_offset은 ROM 내 4바이트 포인터 워드 위치.
    """
    out = {}
    o = scan_lo
    n = min(len(orig), scan_hi)
    while o + 8 <= n:
        if struct.unpack_from('<I', orig, o)[0] == opcode:
            v = struct.unpack_from('<I', orig, o + 4)[0]
            if lo <= v < hi:
                out.setdefault(v - GBA, []).append(o + 4)
        o += 4
    return out


def _line_index(found_csv):
    import csv
    idx = {}
    with open(found_csv, encoding='utf-8', errors='ignore') as f:
        for r in csv.DictReader(f):
            try:
                a = int((r.get('address') or '').strip(), 16)
                L = int(r.get('length') or 0)
            except (ValueError, TypeError):
                continue
            if L > 0:
                idx[a] = (L, (r.get('text') or '').strip())
    return idx


def apply_script_span_ownership(line_index, writes, rom):
    """Use final script-row writers; reject ambiguous partial overlaps.

    A superseded original fragment may extend into trailing padding, but never
    into another glyph or command. The caller excludes conflicting messages
    from relocation instead of cutting their current payload at old boundaries.
    """
    rows = dict(line_index)
    owners = {}
    conflicts = set()
    import bisect
    final = {}
    ranges = []
    for order, entry in enumerate(writes):
        if len(entry) >= 2 and isinstance(entry[0], int) and isinstance(entry[1], int) and entry[1] > 0:
            ranges.append((entry[0], entry[0] + entry[1], order))
        if len(entry) >= 8 and str(entry[7]).startswith('script:'):
            final[entry[0]] = (order, entry)
    ranges.sort()
    starts = [r[0] for r in ranges]
    max_ends = []
    for _, end, _ in ranges:
        max_ends.append(max(end, max_ends[-1] if max_ends else end))
    for start, (order, entry) in sorted(final.items()):
        size, text = entry[1], entry[5]
        end = start + size
        other = bisect.bisect_left(starts, end) - 1
        superseded = False
        while other >= 0 and max_ends[other] > start:
            _, other_end, other_order = ranges[other]
            if other_end > start and other_order > order:
                superseded = True
                break
            other -= 1
        if superseded:
            conflicts.add(start)
            continue
        payload = bytes.fromhex(entry[3])
        fill = entry[4]
        if not isinstance(fill, int) or not 0 <= fill <= 255 or len(payload) > size:
            conflicts.add(start)
            continue
        expected = payload + bytes([fill]) * (size - len(payload))
        if bytes(rom[start:end]) != expected:
            conflicts.add(start)
            continue
        overlap = [(a, length) for a, (length, _) in rows.items()
                   if a < end and start < a + length]
        unsafe = False
        for a, length in overlap:
            if a < start or (a + length > end and
                            any(c != 0x20 for c in rom[end:a + length])):
                conflicts.update((start, a))
                unsafe = True
        if unsafe:
            continue
        for a, _ in overlap:
            rows.pop(a)
            owners.pop(a, None)
        rows[start] = (size, text)
        owners[start] = (size, text)
    return rows, owners, conflicts


def repoint_messages(rom, orig, *, fixable, fixed_bytes, fit_level_dlg, decode_text,
                     cell_width, slots, line_index, table_offsets, free_start, free_end,
                     extra_messages=None, skip_messages=None, min_level=6, max_cells=50,
                     max_header_gap=16, align=4, log=None, valid_codes=None,
                     original_line_starts=None, line_layouts=None, seam_codes=None):
    """rom(bytearray)에 재배치 적용. 반환: (manifest list, stats dict).

    **안전 설계(짜옹이님 per-line 대사만 복원)**:
    - 고칠 라인 = `fixable(a)`(=dialogue_overrides에 있는 짜옹이님 라인) AND
      `fit_level_dlg(a) >= min_level`(in-place에서 축약/단어붙음됨).
    - 그 외 모든 라인(미열화 / CSV 병합 라인 등)은 **현재 빌드 바이트(rom)를 그대로 보존**
      → 중복/오정렬/회귀 없음.
    - 메시지는 (라인 span + 제어 gap)으로 원본과 정확 분해될 때만, 그리고 고칠 라인이
      ≥1개일 때만 재배치한다. 포인터는 ROM 내 정확히 1개(테이블)일 때만.
    """
    line_layouts = line_layouts or {}
    stats = collections.Counter()
    manifest = []
    free = free_start
    skip_messages = set(skip_messages or ())

    # 현재 여유공간이 정말 비어있는지(0xFF) 확인
    if any(b != 0xFF for b in rom[free_start:free_end]):
        raise AssertionError('repoint free-space not empty (0xFF expected)')

    # 모든 테이블의 (ptr_off -> msg_addr) 수집 + 메시지 span
    all_targets = set()
    table_entries = []  # (ptr_off, msg_addr, table_off)
    for tbl in table_offsets:
        ents = _read_table(orig, tbl)
        for off, tgt in ents:
            table_entries.append((off, tgt, tbl))
            all_targets.add(tgt)
        stats[f'table_0x{tbl:06X}_entries'] = len(ents)
    # Part1: 0x19(show-message) 커맨드로 참조되는 메시지(2026-06-23 런타임 트레이싱으로 확증).
    # extra_messages = {msg_addr: [ptr_offset...]}. 테이블이 아니라 흩어진 포인터지만 같은 로직으로 처리.
    # 전체 메시지를 sorted_t에 넣어야 span(=다음 메시지 시작)이 정확하다.
    extra_messages = extra_messages or {}
    for msg, offs in extra_messages.items():
        for off in offs:
            table_entries.append((off, msg, None))
        all_targets.add(msg)
    if extra_messages:
        stats['extra_messages'] = len(extra_messages)
    sorted_t = sorted(all_targets)

    def span_of(msg):
        # 메시지 끝 = 다음 메시지 시작. 마지막 메시지는 ROM 끝 또는 자신 뒤의 포인터 테이블 시작
        # (스크립트 영역은 그 포인터 테이블 앞에서 끝남) 중 가까운 쪽. 테이블 오프셋에만 의존하면
        # 향후 영역 확장 시 nxt<=msg가 되어 분해검증이 무조건 깨지는 취약점이 있어 견고화(codex/agy 리뷰).
        i = sorted_t.index(msg)
        if i + 1 < len(sorted_t):
            nxt = sorted_t[i + 1]
        else:
            nxt = len(orig)
            for t in table_offsets:
                if msg < t < nxt:
                    nxt = t
        # 2026-06-25 terminator 세분화(A5c): 0x19 메시지는 sparse라 'next 메시지 시작'까지의 span이
        # 다음 0x19 미참조 메시지들까지 grab → 거대블록·거짓 merged 유발. SJIS 본문엔 0x00 없으므로
        # 첫 0x00이 실제 메시지 종단. min(next, terminator+1)로 실제 메시지에 한정(merged 오탐 제거).
        term = msg
        while term < nxt and orig[term] != 0x00:
            term += 1
        if term < nxt:
            # 0x00 런 끝까지 포함(연속 패딩 0x00). 다음 라인은 0x00 뒤부터.
            e = term
            while e < nxt and orig[e] == 0x00:
                e += 1
            nxt = e
        return nxt

    # msg_addr -> 그 메시지의 라인 [(addr,len)] (정렬)
    msg_lines = collections.defaultdict(list)
    import bisect
    for a, (L, _t) in line_index.items():
        i = bisect.bisect_right(sorted_t, a) - 1
        if i < 0:
            continue
        ms = sorted_t[i]
        if ms <= a < span_of(ms):
            msg_lines[ms].append((a, L))
    for ms in msg_lines:
        msg_lines[ms].sort()

    # 전역 정렬 hit를 모두 유지. 대상 ROM 소비 경로로 증명된 PCM 3건만
    # 원본/현재 코드·데이터 가드 아래 분류하며 새 미인식 hit는 기존 가드로 보낸다.
    pcm_classifications = {}
    def ptr_sites(msg_addr):
        needle = struct.pack('<I', GBA + msg_addr)
        sites = []
        pos = 0
        while True:
            i = orig.find(needle, pos)
            if i < 0:
                break
            if i % 4 == 0:
                sites.append(i)
            pos = i + 1
        sites, evidence = classify_pointer_sites(msg_addr, sites, orig, rom)
        if evidence is not None:
            pcm_classifications[msg_addr] = evidence
        return sites

    table_off_set = set()
    for tbl in table_offsets:
        for off, _tgt in _read_table(orig, tbl):
            table_off_set.add(off)
    for offs in extra_messages.values():
        table_off_set.update(offs)

    # 고아 포인터 방지(agy 리뷰 2026-06-25): 대사/스크립트 영역(0xA00000~0xE10000) 정렬 포인터가 가리키는
    # **텍스트 엔트리 타깃 주소** 집합. 전역 워드 스캔은 그래픽/압축데이터 안의 pointer-shaped 값을
    # 많이 잡으므로, 라인 시작 또는 알려진 메시지 시작이 아닌 본문 중간 바이트는 고아 위험으로 보지 않는다.
    # 실제 중간 라인 주소를 참조하는 포인터가 따로 있으면 재배치 시 시작 포인터만 갱신되고 중간 포인터는
    # 구주소에 남아(고아) 불일치 → 그런 메시지는 skip.
    import array as _arr
    _w = _arr.array('I')
    _w.frombytes(orig[:(len(orig) // 4) * 4])
    entry_targets = set(line_index) | set(all_targets) | set(original_line_starts or ())
    referenced_targets = set()
    for _i, _v in enumerate(_w):
        if 0x08A00000 <= _v < 0x08E10000:
            _tgt = _v - GBA
            if _tgt not in entry_targets:
                continue
            referenced_targets.add(_tgt)
    _sorted_ref = sorted(referenced_targets)

    # 재배치 대상: 라인 중 하나라도 완전충실 인코딩이 슬롯 초과(=in-place 열화) + 한글 포함
    _relocated_msgs = set()   # Process each message once, including skipped messages.
    for ptr_off, msg, _tbl in sorted(table_entries, key=lambda e: (e[0], e[1], -1 if e[2] is None else e[2])):
        if msg in _relocated_msgs:
            continue
        _relocated_msgs.add(msg)
        if msg in skip_messages:
            stats['skip_forced_message'] = stats.get('skip_forced_message', 0) + 1
            manifest.append({'msg': f'0x{msg:06X}', 'status': 'skip_forced'})
            continue
        lines = msg_lines.get(msg, [])
        if not lines:
            continue
        # 고아 포인터 가드(agy 2026-06-25): 메시지 **span 내 임의 중간주소**(시작 외)를 참조하는 포인터가
        # 따로 있으면 재배치 시 그 포인터가 구주소에 남아 불일치(고아) → skip. bisect로 (msg, me) 범위 검사.
        # (시작 주소 참조 ptr_off는 new_addr로 갱신됨. 라인 시작뿐 아니라 라인 내부 주소도 포함해 보수적.)
        _me_chk = span_of(msg)
        _ri = bisect.bisect_right(_sorted_ref, msg)
        if _ri < len(_sorted_ref) and _sorted_ref[_ri] < _me_chk:
            stats['skip_mid_ref'] = stats.get('skip_mid_ref', 0) + 1
            manifest.append({'msg': f'0x{msg:06X}', 'status': 'skip_mid_ref'})
            continue
        # 구조 가드(2026-06-23 Part1 RE 교훈): 진짜 대사 메시지는 첫 라인이 메시지 시작 근처(헤더갭 작음,
        # Part2 실측 최대 12)에서 시작한다. struct/이벤트 테이블은 텍스트 라인 앞에 큰 비-텍스트 헤더
        # (실측 178~195B)가 있어 decompose는 통과해도 대사가 아니다. 헤더갭이 크면 비-대사로 보고 skip
        # → 잘못된 테이블을 넘겨도 struct 재배치(게임 손상)를 차단한다.
        if lines[0][0] - msg > max_header_gap:
            stats['skip_struct_header'] += 1
            continue
        # 고칠 라인(짜옹이님 per-line 대사 + in-place 열화) 존재?
        # 폭 가드: 단어붙음은 공백을 지워 폭을 줄였을 수 있다. un-jam(공백 복원) 후 시각 폭이
        # 박스 한계(max_cells, 원본 대사 최대폭 50 관측)를 넘으면 잘림 위험 → 그 라인은 수정 제외
        # (in-place 단어붙음 유지가 폭 안전). repoint가 새 잘림을 만들지 않게 한다.
        fix_addrs = set()
        skipped_wide = 0
        for a, L in lines:
            if fixable(a) and fit_level_dlg(a) >= min_level:
                layout = line_layouts.get(a)
                if layout is not None:
                    if (len(layout) != 2 or any(not part or any(b < 0x20 for b in part) for part in layout)
                            or b'\x81\x40'.join(layout) != fixed_bytes(a)):
                        raise ValueError('Explicit line layout must preserve exact full text')
                    width = max(text_segment_cells(normalize_text_segment(part, needs_safe_dialogue_punctuation(msg), msg)) for part in layout)
                else:
                    width = cell_width(a)
                if width > max_cells:
                    skipped_wide += 1
                    continue
                fix_addrs.add(a)
        if skipped_wide:
            stats['skip_wide_line'] += skipped_wide
        if not fix_addrs:
            # 2026-06-25 render-jam 허용: fixable 라인이 없어도 **content 사이 반각공백(0x20)**이 있으면
            # 재배치 블롭의 interior 변환(0x20→0x8140)이 화면 단어붙음을 해소하므로 재배치한다.
            # (클린소스 없는 잼=무포인터 외 단일포인터분 커버). 2바이트 코드 lead는 건너뛰어 오탐 방지.
            _has_jam = False
            for a, L in lines:
                seg = rom[a:a + L]
                i = 0
                while i < len(seg) - 1:
                    b = seg[i]
                    if is_sjis_lead(b):
                        i += 2
                        continue
                    if b == 0x20 and (is_sjis_lead(seg[i + 1]) or 0x21 <= seg[i + 1] <= 0x7E):
                        _has_jam = True
                        break
                    i += 1
                if _has_jam:
                    break
            if not _has_jam and seam_codes is not None and is_part2_story_address(msg):
                # Seams with fewer than two padding bytes cannot take an in-place
                # 0x8140; relocation inserts it (see apply_seam_spaces).
                _end = msg
                while _end < len(rom) and rom[_end] != 0:
                    _end += 1
                _cur = bytes(rom[msg:_end])
                _org_end = orig.find(b'\x00', msg)
                _org = bytes(orig[msg:_org_end if _org_end >= 0 else msg])
                if any(seam['pads'] < 2 and seam_is_bound(seam, *source_context(_org, _cur, seam)) is False
                       for seam in find_seams(_cur, seam_codes)):
                    _has_jam = True
                    stats['relocate_seam'] = stats.get('relocate_seam', 0) + 1
            if not _has_jam:
                continue
            stats['relocate_renderjam'] = stats.get('relocate_renderjam', 0) + 1

        # 안전 가드: **실제 렌더 텍스트** 기준 라인 간 중첩 검사.
        # 각 라인의 effective 텍스트 = fixed면 override(새 텍스트), 아니면 현재 rom 바이트 디코드.
        # 한 라인의 텍스트가 다른 라인 텍스트의 부분문자열(공백제거 길이>=4)이면, 미션 목표처럼
        # 멀티라인 병합 저장된 케이스 → 재배치 시 중복 노출 위험 → 메시지 전체 skip(회귀 0).
        def nosp(s):
            return ''.join(c for c in (s or '') if c not in ' 　')
        eff = []
        for a, L in lines:
            if a in fix_addrs:
                eff.append(nosp(decode_text(fixed_bytes(a))))
            else:
                eff.append(nosp(decode_text(bytes(rom[a:a + L]))))
        # ★2026-06-25 정밀화: 부분문자열 라인(jj)이 **별도 메시지로도 참조**(sorted_t=테이블/0x19 타깃)될 때만
        # 병합-중복노출 위험 → skip. jj가 이 메시지 내부 sub-line일 뿐(별도 포인터 0)이면 메시지 단위로 함께
        # 이동해 L1+L2 구조가 그대로 보존되므로 안전(미션목표 "...공격하라!"+"공격하라!" 류 4건 재배치 가능).
        sorted_t_set = set(sorted_t)
        merged = has_independently_referenced_overlap(msg, lines, eff, sorted_t_set)
        if merged:
            stats['skip_merged_fragment'] += 1
            manifest.append({'msg': f'0x{msg:06X}', 'status': 'skip_merged'})
            continue

        me = span_of(msg)
        # 과확장 span 가드(2026-06-23 Part1): 메시지의 참조 포인터가 자기 span 안에 있으면
        # span이 메시지 종단을 넘어 (다음 0x19 시작까지) 커맨드-스트림/타 메시지를 포함한 것.
        # 재배치 시 그 포인터를 갱신하면 구위치가 바뀌고(렌더는 종단서 멈춰 무해하나) 여유공간 낭비·
        # 검증 복잡. 정상 메시지는 참조 포인터가 텍스트 앞(span 밖)이다 → 안쪽이면 skip(보수적).
        if any(msg <= off < me for off in ptr_sites(msg)):
            stats['skip_overextended'] += 1
            manifest.append({'msg': f'0x{msg:06X}', 'status': 'skip_overextended'})
            continue
        # 안전: 포인터가 1개 이상 & **전부** 테이블 안(2026-06-25 다중포인터 지원: 모든 site가 인식된
        # 포인터테이블 엔트리면 1회 재배치 후 전 site를 새 주소로 갱신 → 고아 없음. 우연/미인식 포인터가
        # 섞이면 보수적 skip).
        sites = ptr_sites(msg)
        if len(sites) < 1 or not all(s in table_off_set for s in sites):
            stats['skip_ptr_ambiguous'] += 1
            manifest.append({'msg': f'0x{msg:06X}', 'status': 'skip_ptr', 'sites': [hex(s) for s in sites]})
            continue

        # 스켈레톤 분해 검증: 라인 span + 제어 gap == 원본
        rebuilt_orig = bytearray()
        cur = msg
        ok = True
        for a, L in lines:
            if a < cur or a + L > me:
                ok = False
                break
            rebuilt_orig += orig[cur:a]
            rebuilt_orig += orig[a:a + L]
            cur = a + L
        if not ok:
            stats['skip_decompose'] += 1
            manifest.append({'msg': f'0x{msg:06X}', 'status': 'skip_decompose'})
            continue
        rebuilt_orig += orig[cur:me]
        if bytes(rebuilt_orig) != bytes(orig[msg:me]):
            stats['skip_decompose'] += 1
            manifest.append({'msg': f'0x{msg:06X}', 'status': 'skip_decompose'})
            continue

        # Normalize each text span independently. Control gaps must match the
        # original and are copied verbatim; punctuation-like operands are data.
        pieces = []
        text_failure = None
        cur = msg
        for a, L in lines:
            gap = bytes(rom[cur:a])
            pieces.append(['gap', gap, bytes(orig[cur:a])])
            payload = fixed_bytes(a) if a in fix_addrs else bytes(rom[a:a + L])
            # Control bytes inside an alleged text span mean its boundaries
            # are unproven. Preserve the in-place message rather than guessing.
            if any(b < 0x20 for b in payload):
                text_failure = 'skip_impure_span'
                break
            parts = line_layouts.get(a, (payload,)) if a in fix_addrs else (payload,)
            normalized_parts = [normalize_text_segment(part, needs_safe_dialogue_punctuation(msg), msg) for part in parts]
            normalized = b'\x72\x0a\x09'.join(normalized_parts)
            if any(text_segment_cells(part) > max_cells for part in normalized_parts):
                text_failure = 'skip_normalized_wide'
                break
            pieces.append(['text', normalized, bytes(orig[a:a + L])])
            cur = a + L
        if text_failure:
            stats[text_failure] = stats.get(text_failure, 0) + 1
            manifest.append({'msg': f'0x{msg:06X}', 'status': text_failure})
            continue
        gap = bytes(rom[cur:me])
        pieces.append(['gap', gap, bytes(orig[cur:me])])
        seams_fixed = seams_wide = 0
        if seam_codes is not None and is_part2_story_address(msg):
            seams_fixed, seams_wide = apply_seam_spaces(pieces, seam_codes)
        new_msg = bytearray()
        controls = []
        for piece in pieces:
            if piece[0] == 'gap':
                controls.append((len(new_msg), piece[1], piece[2]))
            new_msg += piece[1]
        if any(gap != original or bytes(new_msg[pos:pos + len(gap)]) != original
               for pos, gap, original in controls):
            stats['skip_control_changed'] = stats.get('skip_control_changed', 0) + 1
            manifest.append({'msg': f'0x{msg:06X}', 'status': 'skip_control_changed'})
            continue

        # ★stray-code 안전게이트(2026-06-25): new_msg의 **모든 2바이트 코드가 렌더 가능**(예약 한글 / 한자테이블 /
        # 전각공백 0x8140 / 전각 기호·영숫자 0x81-0x82)한지 전수 검증. 다른 writer의 slot 경계가 코드를 분할해
        # 생긴 orphan(8DEF '수'→0xEF + 다음 = garbage 0xEF81), number-template 잔여(8F92), 특수문자 미변환
        # (ー→0x849F) 등 **invalid 코드가 하나라도 있으면 재배치 skip → in-place(마지막 writer, render hook이
        # 0x20 렌더) 유지**. garbage 출하 방지(decode-safety 워크플로 발견 + 완전 valid-codes 재스캔으로 확장).
        if valid_codes is not None:
            _j = 0
            _stray = False
            while _j < len(new_msg):
                _bb = new_msg[_j]
                if (0x81 <= _bb <= 0x9F or 0xE0 <= _bb <= 0xEF) and _j + 1 < len(new_msg):
                    _cc = (_bb << 8) | new_msg[_j + 1]
                    _lo = _cc & 0xFF
                    _ok = (_cc in valid_codes) or (
                        (_cc >> 8) in (0x81, 0x82) and (0x40 <= _lo <= 0x7E or 0x80 <= _lo <= 0xFC))
                    if not _ok:
                        _stray = True
                        break
                    _j += 2
                elif _bb < 0x80 or 0xA1 <= _bb <= 0xDF:
                    _j += 1
                else:                       # 0x80, 0xA0, 0xF0-0xFF (유효 lead 아님)
                    _stray = True
                    break
            if _stray:
                stats['skip_stray_code'] = stats.get('skip_stray_code', 0) + 1
                manifest.append({'msg': f'0x{msg:06X}', 'status': 'skip_stray_code'})
                continue

        # terminator 보존 검증(2026-06-25, codex/agy 보수화): **원본이 0x00 종단인 메시지만** 재배치하고,
        # 그 경우 new_msg도 0x00 종단이어야 함. 원본 비-0x00 종단(다음 메시지까지 span)은 엔진 소비범위 불명
        # → 재배치 시 run-off 위험이므로 보수적 skip. patch_script_row류(라인이 종단 삼킴)도 여기서 차단.
        if me <= msg or orig[me - 1] != 0 or (not new_msg or new_msg[-1] != 0):
            stats['skip_no_terminator'] = stats.get('skip_no_terminator', 0) + 1
            manifest.append({'msg': f'0x{msg:06X}', 'status': 'skip_no_terminator'})
            continue

        nlen = len(new_msg)
        if free + nlen > free_end:
            raise AssertionError('repoint free-space exhausted')
        new_addr = free
        rom[new_addr:new_addr + nlen] = new_msg
        free += nlen
        if free % align:
            free += align - (free % align)
        # 포인터 갱신 — 다중포인터면 전 site 갱신(고아 방지)
        for _s in sites:
            struct.pack_into('<I', rom, _s, GBA + new_addr)
        if len(sites) > 1:
            stats['relocated_multi'] = stats.get('relocated_multi', 0) + 1
        _relocated_msgs.add(msg)
        stats['relocated'] += 1
        stats['seam_spaces'] += seams_fixed
        stats['seam_skip_wide'] += seams_wide
        stats['lines_fixed'] += len(fix_addrs)
        manifest.append({
            'msg': f'0x{msg:06X}', 'status': 'relocated',
            'ptr_off': f'0x{ptr_off:06X}', 'new_addr': f'0x{new_addr:06X}',
            'old_len': me - msg, 'new_len': nlen, 'lines': len(lines),
            'fixed': sorted(f'0x{a:06X}' for a in fix_addrs),
            **({'seam_spaces': seams_fixed} if seams_fixed else {}),
        })

    for record in manifest:
        evidence = pcm_classifications.get(int(record['msg'], 16))
        if evidence is not None:
            record['pointer_classification'] = evidence
    for evidence in pcm_classifications.values():
        stats['pcm_collision_sites_excluded'] += len(evidence['excluded_sites'])
        if evidence['status'] == 'guard_rejected':
            stats['pcm_collision_guard_rejected'] += 1
    stats['free_used'] = free - free_start
    stats['free_avail'] = free_end - free_start
    return manifest, dict(stats)
