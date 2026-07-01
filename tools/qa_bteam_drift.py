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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--accept', action='store_true',
                    help='현재 override로 baseline 갱신(의도적 B팀 변경 확정)')
    args = ap.parse_args()

    ovn = load_overrides()

    if args.accept:
        # 우발 drift를 권위본으로 봉인하는 사고 방지: 명시적 환경변수 승인 필요(codex 리뷰).
        if os.environ.get('AW_BTEAM_ACCEPT') != '1':
            print('거부: baseline 갱신은 의도적 B팀 변경 확정 전용. 변경 내역을 git diff로 확인 후\n'
                  '  AW_BTEAM_ACCEPT=1 python3 tools/qa_bteam_drift.py --accept 로 재실행하라.', file=sys.stderr)
            sys.exit(2)
        base = json.load(open(BASELINE, encoding='utf-8'))
        addrs = list(base.get('overrides', {}))
        base['overrides'] = {a: ovn[a] for a in addrs if a in ovn}
        base['count'] = len(base['overrides'])
        json.dump(base, open(BASELINE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'baseline 갱신: {base["count"]}개 B팀 주소를 현재 override로 확정')
        return

    base = json.load(open(BASELINE, encoding='utf-8'))
    expected = base.get('overrides', {})
    drift = []
    missing = []
    for addr, want in expected.items():
        cur = ovn.get(addr)
        if cur is None:
            missing.append((addr, want))
        elif cur != want:
            drift.append((addr, want, cur))

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
