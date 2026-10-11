"""Part 2 ending-QA dialogue fragment repairs (2026-10-08).

Rows observed jammed, stuttered or mistranslated in the Part 2 ending playthrough
(temp/claude_2026-10-08/part2_findings_triage.tsv). Each row is one original
source fragment [start, end) ending at a control byte; the text is exact (a
trailing space is the visible separator before the next {57}/wait fragment).
The builder writes them as playthrough repair rows and relocates their
messages, so the complete text is kept. None is a B-team protected address.
"""
ROWS = (
    (0xA156F4, 0xA156F8, '네, '),  # 89 stutter は、 -> 네,
    (0xA16BEC, 0xA16BF0, '네, '),  # 90 stutter は、 -> 네,
    (0xA16E37, 0xA16E47, '겨우 절반...'),  # 91 やっと半分: 드디어 -> 겨우
    (0xA1FC7C, 0xA1FC90, '적은 없을 거라고...'),  # 92 duplicated ending
    (0xA1FC91, 0xA1FC9B, '했는데'),  # 92 だったのに
    (0xA1FD04, 0xA1FD08, '그, '),  # 93 stutter で、
    (0xA1FD09, 0xA1FD13, '그래도...'),  # 93 でも
    (0xA15643, 0xA15647, '그, '),  # 93b stutter で、 (same pattern)
    (0xA15648, 0xA15650, '그렇지만,'),  # 93b ですが、
    (0xA1FDBC, 0xA1FDBE, '이나'),  # 94 particle after 보병
    (0xA1FDCA, 0xA1FDD8, '으로 사용 가능해.'),  # 94 で使用可能よ。
    (0xA1FE58, 0xA1FE5C, '세, '),  # 95 stutter つ、
    (0xA1FE79, 0xA1FE85, '힘에서 밀렸다고?'),  # 95 力負けだと？
    (0xA1FF09, 0xA1FF29, '아스카의 미사일 기지가 있었기에'),  # 96
    (0xA1FF2B, 0xA1FF3B, '이길 수 있었던 거다.'),  # 96 勝利できたのだ。
    (0xA251AD, 0xA251B1, '나, '),  # 101 stutter て(天気)
    (0xA251C5, 0xA251DB, '분명 그 때문입니다!'),  # 101b そうに決まっています！ (certainty, Astra review)
    (0xA196F0, 0xA196F8, '남은 건 '),  # 103 jam before わが
    (0xA19774, 0xA19784, '반격에 나서는 거지?'),  # 103 反攻に出るのね？
    (0xA19787, 0xA1978D, '그럼, '),  # 103 なら、
    (0xA19CB9, 0xA19CBD, '지금, '),  # 105 今、
    (0xA19DF9, 0xA19E05, '고통받는 것을, '),  # 105 苦しむのを、
    (0xA19EDB, 0xA19EEB, '미니 캐논이, '),  # 106 ミニキャノンが、
    (0xA19EEC, 0xA19EF0, '전, '),  # 106 stutter す、
    (0xA1A399, 0xA1A3A9, '전멸 전까진 '),  # 107 jam
    (0xA1A3AA, 0xA1A3C0, '무슨 일이 생길지 모른다.'),  # 107
    (0xA1A3C1, 0xA1A3D9, '긴장을 늦추지 말라고'),  # 107
    (0xA1A3DB, 0xA1A3EB, '병사들에게 전하라.'),  # 107
    (0xA1A61A, 0xA1A622, '그것도, '),  # 108 それも、
    (0xA1A74C, 0xA1A76A, '블랙캐논을 노리도록 '),  # 108 jam
    (0xA1AA75, 0xA1AA83, '재앙의 근원은 '),  # 109 jam
    (0xA1ACB8, 0xA1ACBE, '그래, '),  # 110 おう、
    (0xA1ACCC, 0xA1ACD2, '그럼, '),  # 110 では、
    (0xA1B180, 0xA1B184, '하, '),  # 112 stutter は、
    (0xA1C330, 0xA1C334, '하, '),  # 112 stutter は、
    (0xA1BE44, 0xA1BE56, '조금 손봐서, '),  # 111
    (0xA1BEF0, 0xA1BEF8, '이걸로, '),  # 111
    (0xA1BF0E, 0xA1BF22, '아무것도 할 수 없겠군요.'),  # 111 なにもできませんね
    (0xA1BF98, 0xA1BFA2, '얌전히 '),  # 111 jam
    (0xA1E923, 0xA1E929, '이보게, '),  # 117 のう、
    (0xA1E93C, 0xA1E942, '그래.'),  # 117 ええ。
    (0xA1E944, 0xA1E95C, '우리도 힘을 보태고 싶어.'),  # 117
    (0xA1EA03, 0xA1EA09, '자, '),  # 117 さあ、
    (0xA1EDAC, 0xA1EDB4, '어리석군.'),  # 118 バカな。
    (0xA1EF40, 0xA1EF46, '그래.'),  # 118 そう。
    (0xA1EF80, 0xA1EF86, '그래.'),  # 118 ああ。
    (0xA1F06C, 0xA1F074, '아앗, '),  # 118 あーっ、
    (0xA1F1E4, 0xA1F1EA, '그래. '),  # 118 ええ。
    (0xA25E2F, 0xA25E43, '그 정도일까요, '),  # 122
    (0xA25E44, 0xA25E54, '캐서린 사령관.'),  # 122 司令
    (0xA25D60, 0xA25D7A, '옮겨졌을지도 모른다, '),  # 123
    (0xA25D7B, 0xA25D7F, '그 말이야?'),  # 123 と？
    (0xA262DC, 0xA262E2, '그래.'),  # 124 ええ。
    (0xA262E4, 0xA262EE, '아무래도, '),  # 124
    (0xA262EF, 0xA26307, '코스모 랜드나 타 대륙을'),  # 124 や
    (0xA27274, 0xA2727A, '그럼, '),  # 128 なら、
    (0xA2727B, 0xA2728B, '먼저 공격해서, '),  # 128
    (0xA2728C, 0xA2729A, '입을 막는 편이'),  # 128
    (0xA272CC, 0xA272D0, '그래서, '),  # 127 で、 (not a stutter)
    (0xA27858, 0xA2785C, '기, '),  # 130 stutter ま、
    (0xA2785D, 0xA27863, '기다려!'),  # 130 まて！
    (0xA27865, 0xA2786B, '네놈, '),  # 130 てめぇ
    (0xA27908, 0xA2790C, '이 '),  # 131 この
    (0xA27ECC, 0xA27ED2, '기다려! '),  # 132 まて！
    (0xA280A3, 0xA280B1, '나중 얘기는 '),  # 133
    (0xA280B2, 0xA280B8, '됐어!'),  # 133 いい！
)


def check_composed_rows(rom, manifest, max_half_cells=None):
    """Width gate for the assembled rows: every repaired fragment sits in a
    relocated message, and the whole display row containing it (fragments
    joined across 0x57/0x77 same-row waits) fits the portrait text box.
    Fragment slot checks alone miss rows continued by {57}."""
    from dialogue_repoint import PORTRAIT_ROW_HALF_CELLS
    from qa_part2_physical_rows import assemble_rows, tokenize
    from part2_native_controls import CONSUMER, NativeProfile
    import build_korean_full as builder
    import json
    import struct
    from pathlib import Path
    original = Path('original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
    limit = PORTRAIT_ROW_HALF_CELLS if max_half_cells is None else max_half_cells
    if type(limit) is not int or limit <= 0:
        raise AssertionError('invalid Part 2 row capacity')
    # The token vocabulary and consume-only semantics are valid only while the
    # actual ROM still carries the verified 0x31424C script parser.
    profile = NativeProfile(rom)
    codes = {s: int(code, 16) for s, code in json.loads(Path(builder.SYLCODE).read_text()).items()}
    spans = {}
    span_locations = set()
    intervals = []
    for message in manifest:
        if message.get('status') != 'relocated':
            continue
        try:
            target, size = int(message['new_addr'], 16), message['new_len']
            if type(size) is not int or not 0 <= target < target + size <= len(rom):
                raise ValueError('message outside ROM')
            pointer = int(message['ptr_off'], 16)
            source, old_size = int(message['msg'], 16), message['old_len']
            if (type(old_size) is not int or
                    not 0 <= source < source + old_size <= len(original) or
                    original.find(b'\x00', source, source + old_size) < 0 or
                    not 0 <= pointer <= len(original) - 4 or
                    struct.unpack_from('<I', original, pointer)[0] != source + 0x08000000):
                raise ValueError('original source/pointer boundary mismatch')
            if not 0 <= pointer <= len(rom) - 4 or struct.unpack_from('<I', rom, pointer)[0] != target + 0x08000000:
                raise ValueError('relocation pointer does not target message')
            intervals.append((target, target + size))
            for key, pair in message['line_spans'].items():
                start = int(key, 16)
                if start in spans or not isinstance(pair, (list, tuple)) or len(pair) != 2:
                    raise ValueError('duplicate or malformed fragment span')
                off, length = pair
                if (type(off) is not int or type(length) is not int or
                        not 0 <= off < off + length <= size or
                        not source <= start < source + old_size or
                        (target, off) in span_locations):
                    raise ValueError('fragment outside message')
                spans[start] = (target, size, off, length)
                span_locations.add((target, off))
        except (KeyError, TypeError, ValueError) as error:
            raise AssertionError(f'invalid Part 2 ending-QA manifest span: {error}') from error
    for left, right in zip(sorted(intervals), sorted(intervals)[1:]):
        if left[1] > right[0]:
            raise AssertionError('invalid Part 2 ending-QA manifest span: overlapping relocations')
    widths, wide = {}, []
    parsed = {}
    for start, _end, text in ROWS:
        if start not in spans:
            raise AssertionError(f'Part 2 ending-QA row not relocated: 0x{start:06X}')
        target, size, off, length = spans[start]
        if target not in parsed:
            data = bytes(rom[target:target + size])
            tokens = tokenize(data, consumer=CONSUMER, native_profile=profile)
            rows, unknown, terminated = assemble_rows(
                tokens, {}, 'portrait', portrait_capacity=PORTRAIT_ROW_HALF_CELLS,
                consumer=CONSUMER, native_profile=profile)
            if unknown or not terminated:
                raise AssertionError(
                    f'Part 2 ending-QA malformed/unknown control at 0x{target:06X}: {unknown!r}; terminated={terminated}')
            # The manifest is a bounded message. Bytes after its first NUL may
            # only be NUL slot padding; no content may hide beyond the parser.
            end = tokens[-1]['offset']
            if any(data[end + 1:]):
                raise AssertionError(f'Part 2 ending-QA data after terminator at 0x{target:06X}')
            bounds = []
            row_start = 0
            for token in tokens:
                if token['kind'] in ('newline', 'page', 'end'):
                    if any(t['kind'] == 'text' for t in tokens if row_start <= t['offset'] < token['offset']):
                        bounds.append((row_start, token['offset']))
                    row_start = token['offset'] + 1
            if len(bounds) != len(rows):
                raise AssertionError(f'Part 2 ending-QA physical-row mapping failed at 0x{target:06X}')
            parsed[target] = (tokens, rows, bounds, end)
        tokens, rows, bounds, end = parsed[target]
        if off + length > end or not any(lo <= off and off + length <= hi for lo, hi in bounds):
            raise AssertionError(f'invalid Part 2 ending-QA manifest span: 0x{start:06X}')
        fragment_tokens = [t for t in tokens if off <= t['offset'] < off + length]
        if (not fragment_tokens or fragment_tokens[0]['offset'] != off or
                fragment_tokens[-1]['offset'] + len(bytes.fromhex(fragment_tokens[-1]['raw'])) != off + length or
                any(t['kind'] not in ('text', 'padding') for t in fragment_tokens)):
            raise AssertionError(f'invalid Part 2 ending-QA manifest span: 0x{start:06X}')
        expected = builder.encode_required_full_fidelity(text, codes, {}, start)
        actual = bytes(rom[target + off:target + off + length])
        # Seam decisions may append a visible fullwidth separator to the
        # source fragment. It is still counted by the physical-row parser.
        if not actual.startswith(expected) or actual[len(expected):].replace(b'\x81\x40', b''):
            raise AssertionError(f'Part 2 ending-QA fragment payload mismatch: 0x{start:06X}')
        width = next(row['half_cells'] for row, (lo, hi) in zip(rows, bounds)
                     if lo <= off and off + length <= hi)
        if width > limit:
            wide.append(f'0x{start:06X} {width}>{limit} {text!r}')
        widths[start] = width
    if wide:
        raise AssertionError('Part 2 ending-QA row assembled width exceeds the box: ' + '; '.join(wide))
    return widths
