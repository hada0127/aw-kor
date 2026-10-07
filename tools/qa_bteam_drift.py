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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--accept', action='store_true',
                    help='현재 override로 baseline 갱신(승인된 예외 범위만; 그 밖의 변경은 거부)')
    ap.add_argument('--allow-bteam-changes', action='store_true',
                    help='--accept와 함께: 예외 밖 B팀 문구 변경까지 확정(별도 승인 필요, PINNED_CORE_DIGEST도 갱신해야 게이트 통과)')
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
