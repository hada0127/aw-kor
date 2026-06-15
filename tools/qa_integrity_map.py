#!/usr/bin/env python3
"""무결성맵 QA 게이트 (Phase C-min).

build_korean_full.py가 빌드 중 남긴 temp/integrity_map.json(텍스트 write 실행 순서)을
빌드 ROM과 대조한다. 두 가지를 검사한다:

1) 바이트 무결성: WRITE_LOG를 실행 순서대로(last-writer-wins) 재구성한 기대 바이트가
   실제 ROM과 일치하는가. 불일치 = 맵이 ROM을 정확히 기술하지 못함(비계측 write가 텍스트
   영역을 덮었거나 버그). 1차 게이트.
2) 문장부호 소실: import 경로(ko 보유) 행에서 원문 ko의 문장부호가 출하 바이트에서
   사라졌는지. encode_fit blanket strip(build:8844) 회귀를 정량화 — Phase B 전/후 지표.

exit 0=PASS, 1=FAIL.
"""
import argparse
import collections
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYLCODE = os.path.join(BASE, 'data', 'syllable_to_code.json')

# encode_fit(build:8844)가 제거하는 문장부호 집합
STRIP_SET = set(',.!?:;()[]{}"\'‘’“”・…。、「」『』▼')
# 의미 있는(연출/가독성) 문장부호 — 소실 집계 핵심 대상(괄호/콜론 등 경미한 건 제외 가능하나 포함)
MEANINGFUL = set('.!?…。、「」『』')


def load_syl():
    syl = json.load(open(SYLCODE, encoding='utf-8'))
    code2syl = {}
    for h, c in syl.items():
        code2syl[int(c) if isinstance(c, int) else int(c, 0)] = h
    return code2syl


def decode_enc(enc, code2syl):
    """enc 바이트열을 사람이 읽는 문자열로 역디코드(encode_text 역연산 근사)."""
    out = []
    i = 0
    n = len(enc)
    while i < n:
        b = enc[i]
        if i + 1 < n and ((0x81 <= b <= 0x9f) or (0xe0 <= b <= 0xef)):
            code = (b << 8) | enc[i + 1]
            if code in code2syl:
                out.append(code2syl[code]); i += 2; continue
            if code == 0x8140:
                out.append('　'); i += 2; continue
            try:
                out.append(bytes([b, enc[i + 1]]).decode('shift_jis')); i += 2; continue
            except Exception:
                pass
        if 0x20 <= b <= 0x7e:
            out.append(chr(b)); i += 1; continue
        out.append('▯'); i += 1
    return ''.join(out)


def canon_punct(s):
    """문장부호를 ASCII 등가로 정규화한 멀티셋(소실 비교용)."""
    s = s.replace('…', '...').replace('。', '.').replace('、', ',')
    s = s.replace('！', '!').replace('？', '?').replace('，', ',').replace('．', '.')
    s = s.replace('「', '"').replace('」', '"').replace('『', '"').replace('』', '"')
    s = s.replace('‘', "'").replace('’', "'").replace('“', '"').replace('”', '"')
    return collections.Counter(c for c in s if c in set('.!?,;:()[]"\''))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rom', default=os.path.join(BASE, 'output', 'game_wars_korean_full.gba'))
    ap.add_argument('--map', default=os.path.join(BASE, 'temp', 'integrity_map.json'))
    ap.add_argument('--show', type=int, default=12, help='소실 샘플 표시 개수')
    args = ap.parse_args()

    if not os.path.exists(args.map):
        print(f'[FAIL] 무결성맵 없음: {args.map} (빌드를 먼저 실행)')
        return 1
    rom = bytearray(open(args.rom, 'rb').read())
    wl = json.load(open(args.map, encoding='utf-8'))
    code2syl = load_syl()
    print(f'=== 무결성맵 QA: {os.path.basename(args.rom)} vs {os.path.basename(args.map)} ({len(wl)} writes) ===')

    # --- 1) 바이트 무결성 (last-writer-wins 재구성) ---
    expected = {}   # addr -> byte
    for addr, slot, enc_len, enc_hex, fill, ko, level, kind in wl:
        enc = bytes.fromhex(enc_hex)
        if fill is not None:
            for k in range(slot):
                expected[addr + k] = fill
        for k in range(len(enc)):
            expected[addr + k] = enc[k]
    mism = []
    for a in sorted(expected):
        if a >= len(rom):
            mism.append((a, 'oob', None)); continue
        if rom[a] != expected[a]:
            mism.append((a, expected[a], rom[a]))
    ok = (len(mism) == 0)
    print(f'[{"OK" if ok else "FAIL"}] 바이트 무결성: 기대 {len(expected)}바이트 중 불일치 {len(mism)}')
    if mism:
        # 불일치를 주소군으로 요약
        groups = collections.Counter(a >> 12 for a, _, _ in mism)
        print('  불일치 상위 페이지(0x__xxx):', ', '.join(f'0x{p:X}xxx={n}' for p, n in groups.most_common(8)))
        for a, e, r in mism[:args.show]:
            print(f'  0x{a:08X}: 기대 {e} != ROM {r}')

    # --- 2) 문장부호 소실 (import 경로) ---
    import_entries = [e for e in wl if str(e[7]).startswith('import')]
    loss_rows = 0
    loss_chars = collections.Counter()
    samples = []
    for addr, slot, enc_len, enc_hex, fill, ko, level, kind in import_entries:
        if not ko:
            continue
        ko_p = canon_punct(ko)
        if not ko_p:
            continue
        dec = decode_enc(bytes.fromhex(enc_hex), code2syl)
        dec_p = canon_punct(dec)
        lost = ko_p - dec_p
        if sum(lost.values()) > 0:
            loss_rows += 1
            loss_chars.update(lost)
            if len(samples) < args.show:
                samples.append((addr, ko, dec))
    total_punct_rows = sum(1 for e in import_entries if e[5] and canon_punct(e[5]))
    print(f'\n[부호소실] import 행 {len(import_entries)} 중 부호보유 {total_punct_rows}, '
          f'소실 발생 {loss_rows}행, 소실 문자수 {sum(loss_chars.values())}')
    if loss_chars:
        print('  소실 문자 분포:', ', '.join(f'{repr(c)}={n}' for c, n in loss_chars.most_common()))
        print('  샘플(주소 | 원문 | 출하디코드):')
        for a, ko, dec in samples:
            print(f'   0x{a:08X} | {ko!r} | {dec!r}')

    # --- 3) 中점(・/·) 잔존 검사 (codex 리뷰): encode_fit가 남기면 단어 결합/글리프 불확실 ---
    mid_import = 0
    mid_other = 0
    mid_samples = []
    for addr, slot, enc_len, enc_hex, fill, ko, level, kind in wl:
        d = decode_enc(bytes.fromhex(enc_hex), code2syl)
        if '・' in d or '·' in d:
            if str(kind).startswith('import'):
                mid_import += 1
                if len(mid_samples) < args.show:
                    mid_samples.append((addr, kind, d[:36]))
            else:
                mid_other += 1
    print(f'\n[中점잔존] import 디코드 ・/· {mid_import}행, 기타(override 등) {mid_other}행 (import는 0이어야 함)')
    for a, k, s in mid_samples:
        print(f'   0x{a:08X} [{k}] {s!r}')
    mid_ok = (mid_import == 0)
    if not mid_ok:
        ok = False

    print('\n=== 결과: ' + ('PASS' if ok else 'FAIL')
          + f' / 바이트{"OK" if not mism else f"불일치{len(mism)}"} / 부호소실 {loss_rows}행 / 中점잔존(import) {mid_import} ===')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
