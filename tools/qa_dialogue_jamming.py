#!/usr/bin/env python3
"""QA: 대사(dialogue_overrides=짜옹이님/B팀) 단어붙음/축약 추적 + repoint 해소 효과.

기존 qa_text_fit는 dialogue_overrides를 walk에서 누락해 단어붙음 504건을 못 봤다(사각지대).
이 도구는 dialogue_overrides의 모든 라인에 대해 in-place fit level을 계산하고,
repoint 매니페스트(temp/repoint_manifest.json)로 해소된 라인을 차감해 **잔여 단어붙음**을 보고한다.

  level >= 10 : 공백 제거(단어붙음)   level 6~9 : 축약/부호 폴백
  repoint로 해소된 라인은 완전충실 렌더 → 잔여에서 제외.

사용: python3 tools/qa_dialogue_jamming.py [--list]
종료코드: 잔여 단어붙음이 BASELINE_JAMMED를 **초과**하면 1 (회귀 게이트). --list로 잔여 주소 출력.
  (현 baseline = Part1/0xB8 분산포인터 미적용 영역 + merged/wide-skip. 이보다 늘면 새 회귀.)
"""
import csv, json, os, sys, collections

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, 'tools'))
import build_korean_full as B

FOUND = os.path.join(BASE, 'data', 'game_wars_found_texts.csv')
DLG = os.path.join(BASE, 'data', 'dialogue_overrides.json')
MANIFEST = os.path.join(BASE, 'temp', 'repoint_manifest.json')

# 회귀 게이트 기준: Part2+Part1 repoint 후 잔여 단어붙음(0xB8/0xEC 비-0x19 영역 + merged/wide/multi-ptr
# skip). 이 값을 '초과'하면 새 회귀로 간주. repoint 영역 확장 시 함께 낮춘다.
# 2026-06-23: Part1 0x19-커맨드 메시지 repoint로 244→117(안전 강화: 다중참조 의심 메시지 보수적 skip) 감소.
BASELINE_JAMMED = 117


def main():
    show = '--list' in sys.argv
    slots = {}
    for r in csv.DictReader(open(FOUND, encoding='utf-8', errors='ignore')):
        try:
            slots[int((r.get('address') or '').strip(), 16)] = int(r.get('length') or 0)
        except (ValueError, TypeError):
            pass
    dlg = {}
    for k, v in json.load(open(DLG, encoding='utf-8')).items():
        try:
            dlg[int(k, 16) if isinstance(k, str) else int(k)] = (v or '').strip()
        except (ValueError, TypeError):
            pass
    syl = {s: int(c, 16) for s, c in json.load(open(B.SYLCODE, encoding='utf-8')).items()}
    um = collections.Counter()

    repointed = set()
    if os.path.exists(MANIFEST):
        for m in json.load(open(MANIFEST, encoding='utf-8')):
            if m.get('status') == 'relocated':
                for fa in m.get('fixed', []):
                    repointed.add(int(fa, 16))

    levels = collections.Counter()
    jammed_in, abbr_in = [], []
    jammed_remain, abbr_remain = [], []
    for a, ko in dlg.items():
        if not ko or not any('가' <= ch <= '힣' for ch in ko):
            continue
        slot = slots.get(a, 0)
        if slot <= 0 or a < B.SAFE_MIN_ADDR:
            continue
        enc, lvl = B.encode_fit(ko, slot, syl, um)
        if enc is None:
            continue
        levels[lvl] += 1
        if lvl >= 10:
            jammed_in.append(a)
            if a not in repointed:
                jammed_remain.append(a)
        elif lvl >= 6:
            abbr_in.append(a)
            if a not in repointed:
                abbr_remain.append(a)

    print('=== 대사(dialogue_overrides) 단어붙음/축약 QA ===')
    print(f'dialogue 라인(한글·슬롯有): {sum(levels.values())}')
    print(f'in-place 단어붙음(level>=10): {len(jammed_in)}   축약(6~9): {len(abbr_in)}')
    print(f'repoint 해소 라인: {len(repointed)}')
    print(f'→ 잔여 단어붙음: {len(jammed_remain)}   잔여 축약: {len(abbr_remain)}')
    print('level 분포:', {f'L{k}': levels[k] for k in sorted(levels) if levels[k]})
    if show:
        for a in sorted(jammed_remain)[:60]:
            print(f'  잔여JAM 0x{a:06X} slot={slots.get(a)} ko={dlg[a]!r}')
    # 회귀 게이트: 잔여 단어붙음이 baseline을 초과하면 새 회귀 → 비정상 종료.
    if len(jammed_remain) > BASELINE_JAMMED:
        print(f'\n[FAIL] 잔여 단어붙음 {len(jammed_remain)} > baseline {BASELINE_JAMMED} — '
              f'새 단어붙음 회귀 발생(또는 repoint 영역 축소). 원인 확인 필요.')
        return 1
    print(f'\n[OK] 잔여 단어붙음 {len(jammed_remain)} <= baseline {BASELINE_JAMMED} '
          f'(Part1/0xB8 분산포인터 영역 + merged/wide-skip — repoint 테이블 확장 시 감소).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
