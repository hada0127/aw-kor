#!/usr/bin/env python3
"""B팀(짜옹이) 권위 번역 drift 검사(QA).

절대제약: B팀/짜옹이 캠페인 번역 문구는 수정 불가(재배치/복원만). 2026-06-24 codex 적대
리뷰가 작업트리에서 B팀 대사 3건이 슬롯 여유에도 축약·개작된 것을 적발 → 이런 우발적 변형을
영구 자동 검출하기 위한 게이트.

방식: `data/bteam_baseline.json`(B팀 적용 주소의 권위 override 스냅샷)과 현재
`data/dialogue_overrides.json`을 주소별로 비교. 값이 다르면 DRIFT(우발적 변형 의심).

짜옹이 본인이 의도적으로 B팀 문구를 바꾸려면: 편집 후 `--accept`로 baseline을 재생성한다
(의도적 변경만 통과시키고, 그 외 우발 변형은 차단).

사용:
  python3 tools/qa_bteam_drift.py            # drift 있으면 출력 + 비0 종료
  python3 tools/qa_bteam_drift.py --accept   # 현재 override로 baseline 갱신(의도적 변경 확정)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import unicodedata
from pathlib import Path

from qa_integrity_map import decode_enc, fill_pattern, load_syl
from dialogue_regions import is_part2_story_address

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OVERRIDES = os.path.join(BASE, 'data', 'dialogue_overrides.json')
BASELINE = os.path.join(BASE, 'data', 'bteam_baseline.json')


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
PINNED_CORE_DIGEST = '302714f230a55428cf80434a58b223e8742ea0be9e79c6f962025d4afe0c482c'


# User-approved B-team wording exceptions, exact (address, from, to). The
# baseline's _user_approved_exceptions must equal this table; adding or editing
# one is a reviewed code change. 0xDD0D1A: じょうでき=上出来, user 「제안대로」 2026-10-07.
APPROVED_EXCEPTIONS = {
    '0x00DD0D1A': ('뭐,자네치고는,상등품이군.', '뭐, 자네치고는 잘했군.'),
}


def core_digest(base: dict) -> str:
    exceptions = base.get('_user_approved_exceptions', {})
    core = {k: v for k, v in base.get('overrides', {}).items() if k not in exceptions}
    return hashlib.sha256(json.dumps(core, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def exception_errors(base: dict, overrides: dict) -> list:
    """Each exception is valid only for its exact (address, from, to) tuple."""
    errors = []
    recorded = base.get('_user_approved_exceptions', {})
    if {a: (e.get('from'), e.get('to')) for a, e in recorded.items() if isinstance(e, dict)} != APPROVED_EXCEPTIONS:
        errors.append('baseline exceptions differ from the approved (address, from, to) table')
    for addr, exc in recorded.items():
        if (not isinstance(exc, dict) or not exc.get('approved') or not exc.get('from')
                or not exc.get('to') or exc['from'] == exc['to']):
            errors.append(f'{addr}: malformed user-approved exception')
            continue
        if base.get('overrides', {}).get(addr) != exc['to']:
            errors.append(f'{addr}: baseline differs from the approved exception text')
        if overrides.get(addr) != exc['to']:
            errors.append(f'{addr}: override differs from the approved exception text')
    return errors


def check(base: dict, overrides: dict, pinned: str = None) -> dict:
    expected = base.get('overrides', {})
    drift = [(a, w, overrides[a]) for a, w in expected.items() if a in overrides and overrides[a] != w]
    missing = [(a, w) for a, w in expected.items() if a not in overrides]
    errors = exception_errors(base, overrides)
    pinned = PINNED_CORE_DIGEST if pinned is None else pinned
    if core_digest(base) != pinned:
        errors.append('baseline entries outside the approved exceptions changed (core digest mismatch)')
    return {'drift': drift, 'missing': missing, 'errors': errors}


def accept(base: dict, overrides: dict, *, allow_bteam_changes: bool = False, pinned: str = None) -> dict:
    """New baseline from current overrides. Refuses to widen beyond the exceptions."""
    new = dict(base)
    new['overrides'] = {a: overrides[a] for a in base.get('overrides', {}) if a in overrides}
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
              map_rom_path: str | None = None) -> list[dict]:
    """Compare protected text with final ROM bytes, including relocated messages.

    Relocation metadata records each original line's final byte span. Reject
    stale write metadata before checking text so a mismatched map cannot pass.
    """
    rom = Path(rom_path).read_bytes()
    map_rom = Path(map_rom_path).read_bytes() if map_rom_path else rom
    if len(map_rom) != len(rom):
        raise ValueError('ROM and map ROM lengths differ')
    writes = json.loads(Path(map_path).read_text(encoding='utf-8'))
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
    def display_equivalent(value: str, address: int) -> str:
        # Normalize only display-equivalent variants emitted by the writer.
        part2 = is_part2_story_address(address)
        value = unicodedata.normalize('NFKC', value)
        if part2:
            value = (value.replace('“', '「').replace('”', '」')
                     .replace('『', '「').replace('』', '」'))
        for run in ('・・・', '···', '・・', '··', '・·', '·・'):
            value = value.replace(run, '...')
        value = value.translate(str.maketrans(
            {'、': ',', '。': '.', '〜': '~', '・': ' ', '·': ' ',
             '‘': "'", '’': "'"}))
        value = ''.join(ch for ch in value if ch not in '[]{};▼')
        if not part2:
            value = value.translate(str.maketrans({'「': '"', '」': '"', '『': '"', '』': '"',
                                                   '“': '"', '”': '"'}))
        return ' '.join(value.split())

    issues = []
    for key, baseline in base['overrides'].items():
        addr = int(key, 16)
        i = bisect.bisect_right(starts, addr) - 1
        relocation = relocated[i] if i >= 0 and addr < relocated[i][1] else None
        row = covering.get(addr) or by_addr.get(addr)
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
            span = m.get('line_spans', {}).get(f'0x{addr:06X}')
            payload = None
            if bad_sites:
                actual = '<bad repoint pointer at ' + ', '.join(bad_sites) + '>'
                cause = 'repoint pointer mismatch'
            elif not span:
                actual = '<protected row missing from relocated line spans>'
                cause = 'repoint line mapping missing'
            else:
                off, length = span
                if off < 0 or length < 0 or off + length > int(m['new_len']):
                    actual = '<invalid relocated line span>'
                    cause = 'repoint line mapping invalid'
                else:
                    payload = rom[target + off:target + off + length]
                    # A wrapped row may contain this verified internal control.
                    actual = decode_enc(payload.replace(b'\x72\x0a\x09', b'\x81\x40'), codes).rstrip(' \u3000')
                    cause = 'relocated row differs from protected baseline'
            wanted = display_equivalent(baseline, addr)
            matched = wanted == display_equivalent(actual, addr)
            if not matched and payload is not None:
                # The explicit wrap replaced an authored space; some older
                # baselines had no space at that point. Keep both readings.
                no_wrap_space = decode_enc(payload.replace(b'\x72\x0a\x09', b''), codes)
                matched = wanted == display_equivalent(no_wrap_space, addr)
            if not matched and payload is not None:
                # A few authority rows cover consecutive physical rows.
                ordered = sorted(m['line_spans'].items(), key=lambda entry: entry[1][0])
                idx = next((n for n, (key2, _) in enumerate(ordered)
                            if int(key2, 16) == addr), -1)
                if idx >= 0:
                    parts = [actual]
                    for _next_key, (next_off, next_len) in ordered[idx + 1:idx + 3]:
                        parts.append(decode_enc(rom[target + next_off:target + next_off + next_len], codes))
                        if wanted in (display_equivalent(''.join(parts), addr),
                                      display_equivalent(' '.join(parts), addr)):
                            actual = ' | '.join(parts)
                            matched = True
                            break
        elif row:
            row_start = int(row[0])
            enc_end = row_start + int(row[2])
            if map_rom_path and rom[addr:row_start + int(row[1])] != map_rom[addr:row_start + int(row[1])]:
                raise ValueError(f'{key}: overlay changed protected in-place slot')
            actual = decode_enc(rom[addr:max(addr, enc_end)], codes).rstrip(' \u3000')
            if row[7] == 'part2-prologue-inline-renderer':
                # The writer owns a whole multi-line script at this address;
                # the B-team authority applies to its first displayed row.
                payload = rom[addr:enc_end].split(b'\x77\x72', 1)[0]
                actual = decode_enc(payload, codes).rstrip(' \u3000')
            matched = display_equivalent(actual, addr) == display_equivalent(baseline, addr)
            if not matched and row_start == addr and display_equivalent(baseline, addr).startswith(display_equivalent(actual, addr)):
                end = row_start + int(row[1])
                next_rows = [candidate for candidate in writes
                             if candidate[3] and end <= int(candidate[0]) <= end + 4]
                if next_rows:
                    following = min(next_rows, key=lambda candidate: int(candidate[0]))
                    next_addr = int(following[0])
                    next_text = decode_enc(rom[next_addr:next_addr + int(following[2])], codes)
                    if display_equivalent(baseline, addr) in (
                            display_equivalent(actual + next_text, addr),
                            display_equivalent(actual + ' ' + next_text, addr)):
                        matched = True
            cause = (f'final in-place writer {row[7]} level={row[6]}'
                     f' at 0x{row_start:08X}; source={row[5]!r}')
        else:
            # No write evidence is a hard failure; guessing a text boundary
            # would turn unknown controls or binary assets into a false pass.
            actual = '<no text write in integrity map>'
            matched = False
            cause = 'protected address has no final text write evidence'
        if not matched:
            issues.append({'address': key, 'baseline': baseline, 'rom_text': actual,
                           'cause': cause})
    return issues


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
        print(f'B팀 최종 ROM 검사: {len(expected)}개, mismatch {len(issues)}개')
        for issue in issues:
            print(f"  [ROM-DRIFT] {issue['address']} baseline={issue['baseline']!r} "
                  f"ROM={issue['rom_text']!r} cause={issue['cause']}")
        if issues:
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
