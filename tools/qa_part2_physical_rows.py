#!/usr/bin/env python3
"""Audit bounded Part 2 messages without running a core or scanning raw strings.

Exit 0: report written (NOT an all-clear). Exit 1: structural/pair errors found.
Exit 2: artifact binding/configuration failure. Unverified counts are mandatory.
"""
from __future__ import annotations
import argparse
import bisect
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import zlib

sys.dont_write_bytecode = True
ROOT = next(p for p in Path(__file__).resolve().parents if (p/'tools/dialogue_repoint.py').is_file())
sys.path.insert(0, str(ROOT/'tools'))
from dialogue_repoint import _read_table, is_sjis_lead, text_segment_cells
import part2_native_controls as NC
from dialogue_regions import PART2_STORY_RANGES, PART2_MISSION_BLURB_RANGE, PART2_OBJECTIVE_DIALOGUE_RANGE
from part2_mission_title_fit import active_titles, strict_titles, valid_pair, is_pair_title
from sprite_relocations import SPRITE_STORAGE_START

ORIGINAL_SHA = 'a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c'
GBA = 0x08000000
TABLE = 0xA357B4
TABLE_COUNT = 3315
CODE_KEY = 'data/syllable_to_code_2350.json'
MANIFEST_KEY = 'temp/repoint_manifest.json'
KNOWN = {0: 'end', 0x72: 'newline', 0x77: 'same_row', 0x6B: 'page'}
# Additional controls and nonadvancing 20 require per-message native evidence.
# The default vocabulary gives conditional rows, never a verified consumer.


class AuditError(ValueError):
    pass


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def address(n):
    return f'0x{n:08X}'


def bind_artifacts(original, rom, manifest_raw, receipt, codes_raw, expected_original=ORIGINAL_SHA):
    if digest(original) != expected_original:
        raise AuditError('원본 SHA가 프로젝트 정본과 다름')
    if receipt.get('source_sha256') != digest(original) or receipt.get('rom_sha256') != digest(rom):
        raise AuditError('ROM/원본과 build receipt SHA 불일치')
    if receipt.get('build_metadata', {}).get(MANIFEST_KEY) != digest(manifest_raw):
        raise AuditError('manifest가 build receipt에 묶이지 않음')
    if receipt.get('inputs_before', {}).get('files', {}).get(CODE_KEY) != digest(codes_raw):
        raise AuditError('코드맵이 build receipt와 불일치')
    if receipt.get('inputs_after', {}).get('files', {}).get(CODE_KEY) != digest(codes_raw):
        raise AuditError('빌드 후 코드맵이 build receipt와 불일치')
    if len(original) != len(rom):
        raise AuditError('원본/대상 크기 불일치')


def relocation_index(records):
    result = {}
    for record in records:
        if record.get('status') != 'relocated':
            continue
        source = int(record['msg'], 16)
        if source in result:
            raise AuditError('중복 relocation manifest source: '+address(source))
        result[source] = record
    return result


def source_span(original, source, upper):
    if not 0 <= source < upper <= len(original):
        raise AuditError('원본 메시지 경계 오류')
    end = original.find(b'\0', source, upper)
    if end < 0:
        raise AuditError('원본 포인터 경계 안에 종단 없음')
    # Match dialogue_repoint.span_of: include the source's consecutive NUL
    # padding, stopping before the next native pointer partition.
    while end < upper and original[end] == 0:
        end += 1
    return end


def validate_relocation_intervals(original, rom, relocations):
    intervals = []
    for source, record in relocations.items():
        start, size = int(record['new_addr'], 16), record['new_len']
        if type(size) is not int or size <= 0 or not 0xA3D000 <= start < start + size <= min(len(rom), SPRITE_STORAGE_START):
            raise AuditError('재배치 구간이 검증된 대사 예약 영역 밖: '+address(source))
        if any(b != 0xFF for b in original[start:start + size]):
            raise AuditError('재배치가 원본 데이터와 겹침: '+address(source))
        intervals.append((start, start + size, source))
    intervals.sort()
    for left, right in zip(intervals, intervals[1:]):
        if left[1] > right[0]:
            raise AuditError('재배치 구간 중첩: '+address(left[2])+' / '+address(right[2]))


def bound_message(original, rom, pointer, source, upper, relocations):
    if not 0 <= pointer <= len(rom)-4:
        raise AuditError('포인터 필드가 ROM 밖')
    if struct.unpack_from('<I', original, pointer)[0] != source+GBA:
        raise AuditError('원본 포인터/소스 불일치')
    end = source_span(original, source, upper)
    target = struct.unpack_from('<I', rom, pointer)[0]-GBA
    record = relocations.get(source)
    if target == source:
        if record:
            raise AuditError('manifest는 재배치했으나 현재 포인터는 원본')
        length = end-source
    else:
        if not record:
            raise AuditError('재배치 근거 없는 변경 포인터')
        if int(record['ptr_off'], 16) != pointer or int(record['new_addr'], 16) != target:
            raise AuditError('현재 포인터와 relocation 불일치')
        if record['old_len'] != end-source:
            raise AuditError('manifest 원본 경계 불일치')
        length = record['new_len']
    if type(length) is not int or not 0 < length <= len(rom) or not 0 <= target <= len(rom)-length:
        raise AuditError('대상 메시지 길이/주소가 ROM 밖')
    return target, rom[target:target+length]


def decode_pairs(raw, codes):
    return ''.join(codes.get(int.from_bytes(raw[i:i+2], 'big')) or
                   raw[i:i+2].decode('shift_jis', 'replace') for i in range(0, len(raw), 2))


def tokenize(payload, *, consumer=None, native_profile=None):
    """Same vocabulary as build_dialogue_groups controls; unknowns preserved.

    That grouping tool also lists 57/69/09, but does not prove their semantics.
    Those, variable commands, and all unfamiliar bytes remain unknown here.
    """
    verified = NC.is_verified_consumer(consumer, native_profile)
    known = {**KNOWN, **NC.KNOWN} if verified else KNOWN
    result = []
    i = 0
    while i < len(payload):
        b = payload[i]
        if is_sjis_lead(b):
            raw = payload[i:i+2]
            kind = 'text' if len(raw) == 2 and valid_pair(int.from_bytes(raw, 'big')) else 'invalid_pair'
            result.append({'kind': kind, 'offset': i, 'raw': raw.hex()})
            if kind == 'invalid_pair':
                # Do not hide a terminator by consuming it as an invalid trail.
                i += 1
            else:
                i += 2
            continue
        kind = 'padding' if b == 0x20 else known.get(b, 'unknown')
        result.append({'kind': kind, 'offset': i, 'raw': f'{b:02x}'})
        i += 1
        if kind == 'end':
            break
    return result


def assemble_rows(tokens, codes, context, portrait_capacity=None, *, consumer=None, native_profile=None):
    verified = NC.is_verified_consumer(consumer, native_profile)
    if portrait_capacity is not None and not verified:
        raise AuditError('확정 폭 판정에는 메시지 소비 증거와 검증된 native profile이 필요')
    if portrait_capacity is not None and (context != 'portrait' or portrait_capacity != 44):
        raise AuditError('44 half-cell 한계는 증거 있는 초상 대화에만 허용')
    rows, raw, joins = [], bytearray(), []
    page = line = 0
    unknown = [t for t in tokens if t['kind'] in ('unknown', 'invalid_pair')]
    terminated = bool(tokens and tokens[-1]['kind'] == 'end')
    uncertain_spacing = spacing_classification(tokens, consumer=consumer, native_profile=native_profile)
    row_start = 0

    def flush(end_token):
        nonlocal raw, joins, row_start
        if raw:
            width = text_segment_cells(bytes(raw))
            row_spacing = [t for t in uncertain_spacing if row_start <= t['offset'] < end_token['offset']]
            rows.append({'page': page, 'line': line, 'offset': row_start,
                'text': decode_pairs(bytes(raw), codes), 'half_cells': width,
                'end_control': end_token['raw'], 'same_row_joins': joins,
                'controls_understood': verified and not unknown and terminated and not row_spacing,
                'native_controls_verified': verified,
                'unverified_spacing': row_spacing,
                'width_basis': ('verified P2 script: 20/09/0A consume-only; 57/77 wait; 4B/6B page' if verified else
                    'conditional 2-byte cells; native consumer unverified; interior20 excluded'),
                'capacity_half_cells': portrait_capacity,
                'confirmed_capacity_exceeded': portrait_capacity is not None and width > portrait_capacity and not unknown and terminated and not row_spacing,
                'conditional_portrait_width_candidate': context in ('story_layout_unverified', 'portrait') and width > 44})
        raw, joins, row_start = bytearray(), [], end_token['offset']+1

    for token in tokens:
        kind = token['kind']
        if kind == 'text':
            raw.extend(bytes.fromhex(token['raw']))
        elif kind == 'same_row':
            joins.append({'offset': token['offset'], 'left': decode_pairs(bytes(raw), codes)})
        elif kind in ('newline', 'page', 'end'):
            flush(token)
            if kind == 'newline':
                line += 1
            elif kind == 'page':
                page += 1; line = 0
    if raw:
        flush({'raw': 'BOUND_END', 'offset': tokens[-1]['offset'] if tokens else 0})
    return rows, unknown, terminated


def spacing_classification(tokens, *, consumer=None, native_profile=None):
    """Interior 20 advance is unproved for P2; no following-ink assumption.

    Trailing 20 before an established line/page/end has no later ink on that
    row. 77 is same-row, so it does not turn interior spacing into trailing pad.
    """
    if NC.is_verified_consumer(consumer, native_profile):
        return []  # Native 0831431C consumes 20 without any position advance.
    uncertain = []
    for index, token in enumerate(tokens):
        if token['kind'] != 'padding':
            continue
        next_token = next((t for t in tokens[index+1:] if t['kind'] not in ('padding', 'same_row')), None)
        if next_token is None or next_token['kind'] not in ('newline', 'page', 'end'):
            uncertain.append(token)
    return uncertain


def pair_violations(payload):
    result = []
    i = 0
    while i < len(payload) and payload[i] != 0:
        raw = payload[i:i+2]
        if len(raw) != 2 or not valid_pair(int.from_bytes(raw, 'big')):
            result.append({'offset': i, 'raw': raw.hex(), 'kind': 'invalid_strict_pair'})
            # A misalignment prevents trustworthy interpretation of all later pairs.
            break
        i += 2
    if i == len(payload):
        result.append({'offset': i, 'raw': '', 'kind': 'no_title_terminator'})
    return result


def validate_portrait_evidence(path, rom_sha, payload_by_source):
    if path is None:
        return {}
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or data.get('schema') != 1 or not isinstance(data.get('records'), list):
        raise AuditError('초상 증거 schema/records 오류')
    result = {}
    for e in data['records']:
        source = int(e['source'], 16)
        if source not in payload_by_source or source in result:
            raise AuditError('초상 증거의 소스가 없거나 중복')
        if e.get('renderer') != 'part2_a3_portrait' or e.get('capacity_half_cells') != 44:
            raise AuditError('초상 증거 renderer/capacity 미확정')
        if e.get('rom_sha256') != rom_sha or e.get('payload_sha256') != digest(payload_by_source[source]):
            raise AuditError('초상 증거 revision/payload 불일치')
        screenshot = Path(e['screenshot'])
        if not screenshot.is_absolute():
            screenshot = path.parent/screenshot
        raw = screenshot.read_bytes()
        if digest(raw) != e.get('screenshot_sha256') or not raw.startswith(b'\x89PNG\r\n\x1a\n'):
            raise AuditError('초상 화면 근거 SHA/PNG 불일치')
        from PIL import Image
        try:
            with Image.open(io.BytesIO(raw)) as png:
                if png.format != 'PNG' or png.size != (240, 160):
                    raise AuditError('초상 화면 근거가 원해상도 240x160 PNG가 아님')
                png.verify()
            # verify() checks PNG chunk integrity; decoding IDAT requires a
            # fresh image because verify() invalidates the first file handle.
            with Image.open(io.BytesIO(raw)) as png:
                png.load()
        except AuditError:
            raise
        except (OSError, SyntaxError, ValueError, zlib.error) as error:
            raise AuditError('초상 화면 PNG가 손상됨') from error
        result[source] = e
    return result


def audit(original, rom, relocations, codes, portrait_path=None, consumer_path=None):
    entries = _read_table(original, TABLE)
    if len(entries) != TABLE_COUNT:
        raise AuditError('native 3315 pointer inventory 변경')
    targets = sorted(set(source for _, source in entries))
    native_titles = active_titles(original, original)
    native_strict = strict_titles(original, native_titles)
    if len(native_titles) != 179 or not 0 < len(native_strict) <= len(native_titles):
        raise AuditError('native 180맵→179포인터/known-pair inventory 변경')
    strict_set = {row[0] for row in native_strict}
    native_title_set = {row[0] for row in native_titles}
    messages, errors, titles, unsupported_titles = [], [], [], []
    try:
        # Recheck the actual descriptor indices, current pointer bounds, title
        # terminators and verified length limit, independently of build success.
        active_titles(original, rom)
    except AssertionError as error:
        errors.append({'kind': 'current_title_inventory', 'error': str(error)})
    try:
        validate_relocation_intervals(original, rom, relocations)
    except AuditError as error:
        errors.append({'kind': 'relocation_intervals', 'error': str(error)})
    for pointer, source in entries:
        region = next((r for r in PART2_STORY_RANGES if r[0] <= source < r[1]), None)
        is_title = is_pair_title(source)
        if pointer in native_title_set-strict_set:
            target = struct.unpack_from('<I', rom, pointer)[0]-GBA
            if not 0 <= target < len(rom):
                errors.append({'source': address(source), 'pointer': address(pointer),
                               'error': '미확정 제목 포인터가 ROM 밖'})
            unsupported_titles.append({'source': address(source), 'pointer': address(pointer),
                'target': address(target), 'pointer_in_rom': 0 <= target < len(rom),
                'status': 'unsupported: upper-level font/entry consumer not established; no pair/glyph pass claim'})
        if region is None and not is_title:
            continue
        index = bisect.bisect_right(targets, source)
        upper = targets[index] if index < len(targets) else TABLE
        try:
            target, payload = bound_message(original, rom, pointer, source, upper, relocations)
        except AuditError as error:
            errors.append({'source': address(source), 'pointer': address(pointer), 'error': str(error)})
            continue
        common = {'source': address(source), 'pointer': address(pointer), 'target': address(target),
                  'bound_bytes': len(payload), 'payload_sha256': digest(payload)}
        if is_title:
            titles.append({**common, 'native_active': pointer in strict_set,
                           'violations': pair_violations(payload), 'payload_hex': payload.hex()})
        else:
            context = ('intro' if PART2_MISSION_BLURB_RANGE[0] <= source < PART2_MISSION_BLURB_RANGE[1]
                       else 'objective' if PART2_OBJECTIVE_DIALOGUE_RANGE[0] <= source < PART2_OBJECTIVE_DIALOGUE_RANGE[1]
                       else 'prologue' if source < 0xA024A0 else 'story_layout_unverified')
            messages.append({**common, 'context': context, '_payload': payload})
    evidence = validate_portrait_evidence(portrait_path, digest(rom),
                                          {int(m['source'], 16): m['_payload'] for m in messages})
    bindings = NC.load_consumer_bindings(consumer_path, original, rom, messages)
    profile = NC.NativeProfile(rom) if bindings else None
    rows, unknown_counts, unmapped_codes = [], Counter(), Counter()
    unverified_spacing_count = trailing_padding_count = verified_padding_count = 0
    syntactically_invalid_pairs = 0
    for m in messages:
        source = int(m['source'], 16)
        payload = m.pop('_payload')
        if source in evidence:
            if m['context'] != 'story_layout_unverified':
                raise AuditError('소개/목표/프롤로그에 초상44 규칙 적용 금지')
            m['context'] = 'portrait'
        proof = bindings.get(source)
        options = dict(consumer=proof['consumer'], native_profile=profile) if proof else {}
        capacity = 44 if source in evidence and proof else None
        capacity_missing = ([] if source in evidence else ['portrait_layout_evidence_missing'])
        if not proof:
            capacity_missing.append('native_consumer_evidence_missing')
        tokens = tokenize(payload, **options)
        spacing = spacing_classification(tokens, **options)
        unverified_spacing_count += len(spacing)
        padding_count = sum(t['kind'] == 'padding' for t in tokens)
        # Trailing is a syntactic position, distinct from verified zero advance.
        trailing_padding_count += padding_count-len(spacing_classification(tokens))
        verified_padding_count += padding_count if proof else 0
        decode_unknown = []
        for token in tokens:
            if token['kind'] == 'invalid_pair':
                syntactically_invalid_pairs += 1
            if token['kind'] != 'text':
                continue
            raw = bytes.fromhex(token['raw'])
            if int.from_bytes(raw, 'big') in codes:
                continue
            try:
                raw.decode('shift_jis', 'strict')
            except UnicodeDecodeError:
                decode_unknown.append(token)
                unmapped_codes[token['raw']] += 1
        built, unknown, terminated = assemble_rows(tokens, codes, m['context'], capacity, **options)
        m.update(tokens=tokens, unknown=unknown, terminated=terminated,
                 unverified_spacing=spacing, consumer_proof=proof,
                 consumer_status='native_verified' if proof else 'unverified',
                 layout_evidence_verified=source in evidence,
                 capacity_half_cells=capacity, capacity_unverified_reasons=capacity_missing,
                 decode_unmapped_pairs=decode_unknown, glyph_coverage_checked=False)
        unknown_counts.update(t['raw'] for t in unknown)
        if not terminated:
            errors.append({'source': m['source'], 'error': '검증된 bound 안에 종단 없음'})
        for row in built:
            rows.append({**row, 'source': m['source'], 'target': m['target'], 'context': m['context'],
                         'layout_evidence_verified': source in evidence,
                         'capacity_unverified_reasons': capacity_missing})
    candidates = [r for r in rows if r['conditional_portrait_width_candidate']]
    summary = {'native_pointer_count': len(entries), 'messages': len(messages), 'physical_rows': len(rows),
        'contexts': dict(Counter(m['context'] for m in messages)), 'unknown_control_counts': dict(unknown_counts),
        'unknown_messages': sum(bool(m['unknown']) for m in messages),
        'unverified_spacing_bytes': unverified_spacing_count,
        'unverified_spacing_messages': sum(bool(m['unverified_spacing']) for m in messages),
        'trailing_padding_bytes': trailing_padding_count,
        'verified_nonadvancing_padding_bytes': verified_padding_count,
        'native_consumer_verified_messages': len(bindings),
        'consumer_unverified_messages': len(messages)-len(bindings),
        'layout_evidence_messages': len(evidence),
        'capacity_verified_messages': sum(m['capacity_half_cells'] is not None for m in messages),
        'png_only_messages': sum(m['layout_evidence_verified'] and not m['consumer_proof'] for m in messages),
        'native_profile': ({'consumer': NC.CONSUMER, 'rom_sha256': profile.rom_sha256,
                            'regions': profile.regions, 'connections': profile.connections} if profile else None),
        'consumer_evidence_inputs': {p: sha for proof in bindings.values() for p, sha in proof['inputs'].items()},
        'invalid_pair_tokens': syntactically_invalid_pairs,
        'decode_unmapped_pair_counts': dict(unmapped_codes),
        'final_glyph_bytes_checked': False,
        'layout_unverified_messages': sum(m['context'] != 'portrait' for m in messages),
        'structural_errors': len(errors), 'width_candidates': len(candidates),
        'known_control_width_candidates': sum(r['controls_understood'] for r in candidates),
        'confirmed_portrait_width_candidates': sum(r['confirmed_capacity_exceeded'] for r in candidates),
        'native_map_descriptors': 180, 'native_title_pointers': 179,
        'native_strict_title_pointers': len(native_strict),
        'native_title_unverified_pointers': len(unsupported_titles),
        'all_table_strict_title_entries': len(titles),
        'active_title_pair_errors': sum(bool(t['violations']) and t['native_active'] for t in titles),
        'inactive_title_pair_errors': sum(bool(t['violations']) and not t['native_active'] for t in titles),
        'coverage_status': 'incomplete: pixel layout, unknown commands and other UI consumers need separate evidence',
        'scope_limits': ['44 requires both revision-bound portrait PNG and per-message verified native consumer evidence',
                         'relocation overlap checks cover manifest records and original occupied bytes; other writers require build-integrity QA',
                         'historical trace/ROM pairing is declared local provenance, not an independently attested trace header',
                         'source ranges and A3 glyph-entry traces do not establish a command consumer',
                         '57/4b/09/0a/styles/20 are verified only for bound 31424c-script messages; other consumers stay unknown',
                         'unverified interior20 advance blocks the affected row verdict',
                         'width is a conditional screen-size filter, not a pixel clipping verdict',
                         'OBJ/menu assets and translation meaning are outside this audit']}
    summary['scope_limits'].append('syntactically valid/decoded SJIS does not prove a registered or visible final ROM glyph; glyph bytes are unverified')
    return {'summary': summary, 'messages': messages, 'rows': rows, 'width_candidates': candidates,
            'structural_errors': errors, 'strict_titles': titles, 'unsupported_titles': unsupported_titles}


def failure_status(summary):
    return int(any(summary[key] for key in ('structural_errors', 'active_title_pair_errors',
        'invalid_pair_tokens', 'confirmed_portrait_width_candidates')))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('rom', 'original', 'manifest', 'receipt', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--codes', type=Path, default=ROOT/CODE_KEY)
    parser.add_argument('--layout-evidence', type=Path)
    parser.add_argument('--consumer-evidence', type=Path)
    args = parser.parse_args(argv)
    try:
        original, rom = args.original.read_bytes(), args.rom.read_bytes()
        manifest_raw, codes_raw = args.manifest.read_bytes(), args.codes.read_bytes()
        receipt = json.loads(args.receipt.read_text())
        bind_artifacts(original, rom, manifest_raw, receipt, codes_raw)
        codes = {int(v, 16): k for k, v in json.loads(codes_raw).items()}
        result = audit(original, rom, relocation_index(json.loads(manifest_raw)), codes, args.layout_evidence, args.consumer_evidence)
        result['summary']['inputs'] = {str(p): digest(p.read_bytes()) for p in
            [args.original, args.rom, args.manifest, args.receipt, args.codes,
             args.layout_evidence, args.consumer_evidence] if p is not None}
        args.output.mkdir(parents=True, exist_ok=True)
        for name, value in result.items():
            (args.output/(name+'.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
        print(json.dumps(result['summary'], ensure_ascii=False))
        return failure_status(result['summary'])
    except (AuditError, OSError, KeyError, TypeError, ValueError, AssertionError,
            AttributeError, IndexError, ImportError, struct.error, zlib.error) as error:
        print('audit binding/configuration error: '+str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
