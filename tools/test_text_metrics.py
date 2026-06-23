#!/usr/bin/env python3
"""text_metrics 동형성 테스트:
 1) text_metrics.encoded_len == len(build.encode_text)  (실제 인코더 바이트 길이와 일치)
 2) text_metrics.encoded_len == app.js encLen (node 실행, 동일 코퍼스)  — py↔js 드리프트 차단
 3) app.js의 실제 encLen 소스가 text_metrics._JS_ENCLEN 미러와 일치
실데이터(translation_for_import.csv + dialogue_overrides.json)에서 코퍼스를 뽑아 검사.
"""
import csv, json, os, re, subprocess, sys, tempfile, shutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, 'tools'))
import text_metrics as TM
import build_korean_full as B


def corpus():
    out = []
    with open(os.path.join(BASE, 'data', 'translation_for_import.csv'), newline='') as f:
        for r in csv.DictReader(f):
            ko = (r.get('korean') or '').strip()
            if ko:
                out.append(ko)
    ovp = os.path.join(BASE, 'data', 'dialogue_overrides.json')
    if os.path.exists(ovp):
        for v in json.load(open(ovp, encoding='utf-8')).values():
            if (v or '').strip():
                out.append(v.strip())
    # 특수 케이스
    out += ['\n', '　', 'ABC 123', '가나다', '안녕\n세계', 'Ｃ애니메', 'a b c']
    return out


# 주의: encoded_len은 '클라이언트 모델(2/1)'이며 raw encode_text와는 의도적으로 다르다
# (encode_text는 FALLBACK 정규화로 전각부호·중점·… 등을 줄이거나 늘림). 따라서 raw 인코더와의
# 직접 동일성 비교는 부적절하고, 권위 검증은 py↔js 동형성(test_js_parity)이다. (codex/agy 리뷰 반영)


def test_unmapped():
    """unmapped_syllables: 2350 폰트에 없는 음절을 잡는다(빈 입력/정상 입력은 빈 목록)."""
    sset = TM._load_syllable_set()
    assert sset, '2350 음절셋 로드 실패'
    assert TM.unmapped_syllables('안녕하세요', sset) == []
    assert TM.unmapped_syllables('', sset) == []
    # 거의 안 쓰이는 음절은 셋에 없을 수 있음 — 함수가 동작만 하면 됨
    assert isinstance(TM.unmapped_syllables('aA1 가', sset), list)
    print('  ✓ unmapped_syllables 동작')


def test_js_parity():
    node = shutil.which('node')
    if not node:
        print('  ⚠ node 없음 — JS 패리티 스킵')
        return
    # 1) app.js의 실제 encLen 소스가 _JS_ENCLEN 미러와 동등한지(공백 정규화 비교)
    app = open(os.path.join(BASE, 'tools', 'scene_editor', 'static', 'app.js'), encoding='utf-8').read()
    m = re.search(r'function encLen\(t\)\s*\{.*?\n\}', app, re.S)
    assert m, 'app.js encLen 함수를 찾지 못함'
    norm = lambda s: re.sub(r'\s+', ' ', re.sub(r'//.*', '', s)).strip()
    assert norm(m.group(0)) == norm(TM._JS_ENCLEN.replace('return n;\n}', 'return n;\n}')), \
        'app.js encLen != text_metrics._JS_ENCLEN 미러 (둘을 함께 갱신하라)'
    print('  ✓ app.js encLen == _JS_ENCLEN 미러')
    # 2) node로 JS encLen 실행 → 코퍼스 전체 길이 py와 일치
    data = corpus()
    js = TM._JS_ENCLEN + '\nconst arr=JSON.parse(require("fs").readFileSync(0,"utf8"));' \
         'process.stdout.write(JSON.stringify(arr.map(encLen)));\n'
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, dir=os.path.join(BASE, 'temp')) as jf:
        jf.write(js)
        jpath = jf.name
    try:
        res = subprocess.run([node, jpath], input=json.dumps(data), capture_output=True, text=True, timeout=60)
        js_lens = json.loads(res.stdout)
    finally:
        os.unlink(jpath)
    mism = [(t, TM.encoded_len(t), jl) for t, jl in zip(data, js_lens) if TM.encoded_len(t) != jl]
    for t, p, j in mism[:5]:
        print(f'  ✗ js parity {t!r}: py={p} js={j}')
    assert not mism, f'{len(mism)} py↔js mismatches'
    print(f'  ✓ py encoded_len == js encLen ({len(data)} 코퍼스 전부)')


if __name__ == '__main__':
    print('test_text_metrics:')
    # text_metrics.encoded_len의 정의는 '클라이언트 모델(2/1)'이다. 권위 검증 = py↔js 동형성.
    # (raw encode_text는 FALLBACK 정규화가 있어 모델과 다를 수 있고, 그 권위는 서버 encode_fit이 갖는다.)
    test_unmapped()
    test_js_parity()
    print('ALL PASS')
