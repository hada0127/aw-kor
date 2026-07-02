#!/usr/bin/env python3
"""aw-kor 고유명사 통일 사전 추출기 (카테고리형).

muramasa-kor `tools/export_proper_nouns.py` / `translations/proper_nouns.json`
포맷을 미러해, Game Boy Wars Advance 1+2 한글화용 고유명사 사전을 만든다.

기존 `tools/export_proper_nouns.py`(불일치/반복용어 자동탐지)와 보완 관계.
이 도구는 **문서화된 캐릭터/CO·국가·지명·공통어**를 카테고리로 시드하고,
데이터에서 빈도·표기 흔들림(variants)을 집계해 채운다.

스캔 소스
  - data/translation_for_import.csv   (address, japanese, korean, length)
  - data/game_wars_found_texts.csv    (address, hex_bytes, text, ...)
  - tools/build_korean_full.py        TERM_NORMALIZATION / TEXT_OVERRIDES /
                                      SOURCE_TEXT_OVERRIDES (AST literal_eval,
                                      실행하지 않음)

출력: data/proper_nouns.json (muramasa 포맷 미러)
  {
    "_readme", "counts",
    "characters": [ {ja, ko, freq, note, variants, edit}, ... ],
    "nations":    [ ... ],
    "places":     [ ... ],
    "discovered_candidates": [ {ja, ko, freq, note, edit}, ... ],
    "common_terms": [ {term, ja_note, current, edit}, ... ],
    "issues":     [ {ja, chosen_ko, other_ko, hint}, ... ]
  }

`freq`     = 대사 행(import + found) 중 해당 ja 토큰을 포함한 행 수.
`variants` = import CSV의 korean 칼럼에서 관측된 표기 분포 {ko: count}.
`edit`     = 비우면 ko/current 유지, 채우면 그 한국어로 통일(apply 단계 참조).

사용:
    python3 tools/export_proper_nouns_dict.py [--out data/proper_nouns.json] [--min-freq 4]
"""
import argparse
import ast
import csv
import json
import os
import re
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANS = os.path.join(BASE, 'data', 'translation_for_import.csv')
FOUND = os.path.join(BASE, 'data', 'game_wars_found_texts.csv')
BUILD = os.path.join(BASE, 'tools', 'build_korean_full.py')
DEFAULT_OUT = os.path.join(BASE, 'data', 'proper_nouns.json')

# ---------------------------------------------------------------------------
# 시드 — CLAUDE.md / 메모리에 문서화된 정식 고유명사. ko 가 의도된 통일 표기.
# ja 는 원본 ROM 일본어(외래명은 가타카나).
# ---------------------------------------------------------------------------
SEED_CHARACTERS = [
    ('リョウ', '료', 'CO / 플레이어'),
    ('キャサリン', '캐서린', 'CO'),
    ('マックス', '맥스', 'CO'),
    ('ドミノ', '도미노', 'CO'),
    ('ビリー', '빌리', 'CO'),
    ('ヤン', '얀', 'CO (얀 델타)'),
    ('ホイップ', '호이프', 'CO. B팀 기준 호이프 단일 표기'),
    ('アスカ', '아스카', '캐릭터'),
    ('ナナ', '나나', '캐릭터'),
    ('ボテト', '보테토', '캐릭터'),
    ('グルモ', '구루모', '캐릭터'),
    ('ヘズ', '헤즈', '캐릭터'),
]

SEED_NATIONS = [
    ('レッドスター', '레드스타', '국가'),
    ('ブルームーン', '블루문', '국가'),
    ('グリーンアース', '그린어스', '국가'),
    ('イエローコメット', '옐로코멧', '국가'),
    ('ブラックホール', '블랙홀', '국가'),
]

SEED_PLACES = [
    ('コスモランド', '코스모 랜드', '지명'),
    ('マクロランド', '매크로 랜드', '지명'),
    ('カララ', '카라라', '지명'),
    ('アララ', '아라라', '지명'),
]

# 통일 유지가 필요한 공통어. current=현재 표기, edit=덮어쓰기.
SEED_COMMON_TERMS = [
    {'term': '사령관 (쇼군/장군 금지)', 'ja_note': 'ショーグン', 'current': '쇼군/장군', 'edit': '사령관'},
    {'term': '사령관 브레이크', 'ja_note': 'ショーグンブレイク',
     'current': '쇼군브레이크/쇼군 브레이크/장군브레이크/장군 브레이크', 'edit': '사령관 브레이크'},
    {'term': '사령관 선택', 'ja_note': 'ショーグン選択',
     'current': '쇼군선택/쇼군 선택/장군선택/장군 선택', 'edit': '사령관 선택'},
    {'term': '호이프', 'ja_note': 'ホイップ', 'current': '호이프', 'edit': '호이프'},
    {'term': '코스모 랜드', 'ja_note': 'コスモランド', 'current': '코스모랜드', 'edit': '코스모 랜드'},
    {'term': '매크로 랜드', 'ja_note': 'マクロランド',
     'current': '매크로랜드/마크로랜드/마크로 랜드', 'edit': '매크로 랜드'},
    {'term': '맵 디자인', 'ja_note': 'マップデザイン',
     'current': '지도 디자인/디자인 지도', 'edit': '맵 디자인/디자인 맵'},
    {'term': '브레이크', 'ja_note': 'ブレイク', 'current': '브레이크', 'edit': ''},
]

# 휴리스틱이 고유명사로 오인하지만 일반/노이즈인 토큰.
HEURISTIC_BLOCKLIST = {
    'システム', 'ダミー', 'セーブ', 'ロード', 'コンピュータ', 'プレイヤ',
    'チュートリアル', 'キャンペーン', 'タイセン', 'トライアル', 'ルール',
    'マップメニュー', 'ワンダーサーチ', 'メカ',
}

KATAKANA_RE = re.compile(r'^[ァ-ヶー・]+$')
HANGUL_RE = re.compile(r'[가-힣]')
REPEAT3_RE = re.compile(r'(.)\1\1')  # ガガガ 등 의성/노이즈 제거

# 표기 흔들림 탐지를 위한 추가 후보 철자(데이터에서 관측된 변형).
# 카논 ko + 띄어쓰기 변형은 자동 생성되고, 여기엔 그 외 변형만 둔다.
KO_VARIANT_SPELLINGS = {
    'コスモランド': ['코스모랜드'],
    'マクロランド': ['매크로랜드', '마크로랜드', '마크로 랜드'],
    'リョウ': ['료우'],
    'ホイップ': ['휩', '휘프'],
}


def parse_build_tables():
    """build_korean_full.py 의 normalization/override 테이블을 AST로 안전 추출."""
    out = {'TERM_NORMALIZATION': [], 'TEXT_OVERRIDES': {}, 'SOURCE_TEXT_OVERRIDES': {}}
    try:
        src = open(BUILD, encoding='utf-8').read()
    except OSError:
        return out
    tree = ast.parse(src)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for tgt in node.targets:
            if isinstance(tgt, ast.Name) and tgt.id in out:
                try:
                    out[tgt.id] = ast.literal_eval(node.value)
                except Exception:
                    pass
    return out


def load_rows(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def _spelling_candidates(ja_token, canon_ko):
    """카논 ko + 띄어쓰기 변형(있음/없음) + 등록된 추가 철자."""
    cands = set()
    if canon_ko:
        cands.add(canon_ko)
        if ' ' in canon_ko:
            cands.add(canon_ko.replace(' ', ''))
        elif len(canon_ko) >= 4:
            # 4글자 이상은 가운데 띄어쓰기 변형이 흔함(블루 문, 옐로 코멧 등).
            mid = len(canon_ko) // 2
            cands.add(canon_ko[:mid] + ' ' + canon_ko[mid:])
    for v in KO_VARIANT_SPELLINGS.get(ja_token, []):
        cands.add(v)
    return cands


def collect_ko_variants(import_rows, ja_token, canon_ko):
    """ja 토큰의 한국어 *철자* 분포를 KO 텍스트에서 직접 집계.

    substring 매칭 시 문장 전체가 아니라 토큰 철자(블루문 vs 블루 문 등)만 센다.
    긴 철자부터 카운트해 부분 겹침(블루문 ⊂ 블루 문 아님; 료 ⊂ 료우)을 방지."""
    cands = sorted(_spelling_candidates(ja_token, canon_ko), key=len, reverse=True)
    counts = Counter()
    for r in import_rows:
        ja = (r.get('japanese') or '').strip()
        ko = r.get('korean') or ''
        if not ko or (ja_token not in ja and not any(c in ko for c in cands)):
            continue
        remaining = ko
        for c in cands:
            n = remaining.count(c)
            if n:
                counts[c] += n
                # 카운트한 철자는 제거해 더 짧은 철자(료 등)의 중복 카운트 방지.
                remaining = remaining.replace(c, '\x00')
    return counts


def count_freq(import_rows, found_rows, ja_token):
    n = sum(1 for r in import_rows if ja_token in (r.get('japanese') or ''))
    n += sum(1 for r in found_rows if ja_token in (r.get('text') or ''))
    return n


def build_seed_entries(seed, import_rows, found_rows):
    entries = []
    for ja, ko, note in seed:
        # variants: 토큰의 한국어 *철자* 분포(블루문 vs 블루 문 등).
        variants = dict(collect_ko_variants(import_rows, ja, ko))
        freq = count_freq(import_rows, found_rows, ja)
        entries.append({
            'ja': ja,
            'ko': ko,
            'freq': freq,
            'note': note,
            'variants': variants,
            'edit': '',
        })
    return entries


def discover_katakana_candidates(import_rows, seed_ja, min_freq, max_len=10):
    """시드/블록리스트에 없는 가타카나-only 짧은 토큰(고유명사 후보) 수집."""
    counter = Counter()
    ko_for = {}
    for r in import_rows:
        ja = (r.get('japanese') or '').strip()
        ko = (r.get('korean') or '').strip()
        if not (2 <= len(ja) <= max_len) or not KATAKANA_RE.match(ja):
            continue
        if REPEAT3_RE.search(ja):
            continue
        counter[ja] += 1
        if ko and ja not in ko_for:
            ko_for[ja] = ko
    out = []
    for ja, n in counter.most_common():
        if n < min_freq or ja in seed_ja or ja in HEURISTIC_BLOCKLIST:
            continue
        out.append({'ja': ja, 'ko': ko_for.get(ja, ''), 'freq': n,
                    'note': 'auto-discovered', 'edit': ''})
    return out


def detect_issues(groups):
    """선택 ko 와 다른 한글 표기가 변형에 존재하면 흔들림으로 표기."""
    issues = []
    for group in groups:
        for e in group:
            others = {k: v for k, v in (e.get('variants') or {}).items()
                      if HANGUL_RE.search(k) and k != e['ko']}
            if others:
                issues.append({
                    'ja': e['ja'],
                    'chosen_ko': e['ko'],
                    'other_ko': others,
                    'hint': '대사 내 표기 흔들림 — apply 로 통일 검토',
                })
    return issues


MANUAL_FIELDS = ('edit', 'allowed', 'allowed_ko')


def _manual_key(category, entry):
    if category == 'common_terms':
        return (entry.get('term') or '', entry.get('ja_note') or '')
    if category == 'issues':
        return (entry.get('ja') or '', entry.get('chosen_ko') or '')
    return (entry.get('ja') or '', entry.get('ko') or '')


def preserve_manual_fields(out_path, out):
    """기존 사전의 수동 필드(edit/allowed)를 새 스캔 결과에 병합."""
    if not os.path.exists(out_path):
        return out
    try:
        old = json.load(open(out_path, encoding='utf-8'))
    except Exception:
        return out
    for category in ('characters', 'nations', 'places',
                     'discovered_candidates', 'common_terms', 'issues'):
        by_key = {_manual_key(category, e): e for e in old.get(category, [])}
        by_ja = {e.get('ja'): e for e in old.get(category, [])
                 if e.get('ja') and category != 'common_terms'}
        for entry in out.get(category, []):
            src = by_key.get(_manual_key(category, entry))
            if src is None and category != 'common_terms':
                src = by_ja.get(entry.get('ja'))
            if not src:
                continue
            for field in MANUAL_FIELDS:
                if field in src:
                    entry[field] = src[field]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=DEFAULT_OUT)
    ap.add_argument('--min-freq', type=int, default=4,
                    help='auto-discovery 최소 빈도 (default 4)')
    args = ap.parse_args()

    import_rows = load_rows(TRANS)
    found_rows = load_rows(FOUND)
    tables = parse_build_tables()

    seed_ja = {ja for ja, *_ in SEED_CHARACTERS + SEED_NATIONS + SEED_PLACES}

    characters = build_seed_entries(SEED_CHARACTERS, import_rows, found_rows)
    nations = build_seed_entries(SEED_NATIONS, import_rows, found_rows)
    places = build_seed_entries(SEED_PLACES, import_rows, found_rows)
    discovered = discover_katakana_candidates(import_rows, seed_ja, args.min_freq)

    common_terms = [dict(t) for t in SEED_COMMON_TERMS]
    for src, dst in tables.get('TERM_NORMALIZATION', []):
        common_terms.append({
            'term': f'{src} -> {dst}',
            'ja_note': '(build TERM_NORMALIZATION)',
            'current': dst,
            'edit': '',
        })

    issues = detect_issues([characters, nations, places])

    out = {
        '_readme': (
            'aw-kor 고유명사 통일 사전. 각 행의 `edit` 필드를 채우면 그 한국어로 '
            '통일한다(비우면 ko/current 유지). tools/apply_proper_nouns_dict.py 로 '
            'translation_for_import.csv 에 적용. freq=대사 등장 횟수, '
            'variants=import CSV 관측 표기 분포. muramasa-kor proper_nouns.json 포맷 미러.'
        ),
        'counts': {
            'characters': len(characters),
            'nations': len(nations),
            'places': len(places),
            'discovered_candidates': len(discovered),
            'common_terms': len(common_terms),
            'issues': len(issues),
        },
        'characters': characters,
        'nations': nations,
        'places': places,
        'discovered_candidates': discovered,
        'common_terms': common_terms,
        'issues': issues,
    }
    out = preserve_manual_fields(args.out, out)

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f'Wrote {args.out}')
    for k, v in out['counts'].items():
        print(f'  {k}: {v}')
    if issues:
        print('\n표기 흔들림 후보 (issues):')
        for it in issues[:20]:
            print(f"  {it['ja']}  chosen={it['chosen_ko']}  others={it['other_ko']}")


if __name__ == '__main__':
    main()
