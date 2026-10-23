"""T7-FIX1: write evidence/INDEX.md from evidence/index.json (run from repo root). Copy of t6-docs/make_index.py + two groups and the T7-FIX1 notes."""
import json
from pathlib import Path

E = Path('docs/reports/name_grid_2026-10-23/evidence')
idx = json.loads((E / 'index.json').read_text())['files']

GROUPS = {
    'plan': ('승인 계획·원 요청·수행 주체 결정', '총괄 brief / `harness-plan-write recheck`(PLAN-v5) / 사용자 결정 기록', '—'),
    'research': ('Phase B 사전 조사 판정(원시 보고서 7개 + mode-scope 원시 산출물)', '각 보고서의 「명령·exit」 절', '원본 `a8ad7c7d…831c`, baseline `ebbca0ba…3a8a`, b44 `1ac68443…6f02` (보고서별)'),
    't1': ('T1 자모 자산', '`python3 -I tools/gen_jamo_assets.py` · `test_jamo_assets.py` · `--check`', 'HEAD `9090818` + T1 신규 파일'),
    't2': ('T2 조합 코어·이미지', '`python3 -I tools/test_name_compose_core.py` · `build_image.py --check`', 'HEAD `9090818` + T1/T2 신규 파일'),
    't3': ('T3 빌더 통합', '`test_part2_name_compose_build.py` 외 회귀 테스트·변이 검사', 'HEAD `9090818` + T1~T3 변경, fixture 후보 `1ac790a9…e1eb`'),
    't4': ('T4 후보 빌드·5관문·집합 비교', '`run_build.py`(빌드 1회 + 5관문) · `analyze.py` · `trace_text_fit.py`/`compare_text_fit.py` · `final_check.py`', '후보 `1ac790a9…e1eb`, snapshot manifest `e6c9fcf8…1b66`'),
    't5': ('T5 런타임 QA(공식 mGBA 0.10.5)', '`t5-runtime/*.py`(REPORT 「실행 명령과 종료코드」) · T7-FIX1 케이스 13 재실행·`case15.py analyze`·`verify.py`(2회)', '후보 `1ac790a9…e1eb`(실행마다 assert), 대조 원본·baseline'),
    't5-superseded': ('T5 정정 전 원문(케이스 13 미완성 자모 coverage 근거로 **무효**)', 'T5 원 실행·T6 집계 재실행 — [`t5/superseded-case13/README.md`](<t5/superseded-case13/README.md>)', '후보 `1ac790a9…e1eb`'),
    't7-fix1': ('T7-FIX1 정정(Astra full-v1 F1·F3·N1)', '[`t7-fix1/REPORT.md`](<t7-fix1/REPORT.md>) 「검증 명령」', '후보 `1ac790a9…e1eb`(재빌드 없음), HEAD `9090818` + Phase B 작업트리'),
}

out = ['# Phase B 영구 증거 색인', '',
       '이 폴더는 ignored `temp/name-grid-phaseB/`의 Phase B 증거 가운데 문서가 인용하는 최소분을 **바이트 그대로** 복사한 것이다. '
       '모든 행의 sha256은 복사 직후 원본과 대조해 같았다(`temp/name-grid-phaseB/t6-docs/collect.py`, T6 2026-10-23). 기계 판독용은 [`index.json`](index.json).', '',
       '- **포함하지 않은 것**: ROM(`.gba`), 카트리지 세이브(`.sav`), savestate(`.ss0`), 원본 ZIP·tar, 폰트 원본, 공식 mGBA 소스·바이너리·라이브러리. 이들의 SHA는 보고서와 [`../PHASE_B_QA.md`](../PHASE_B_QA.md)에 있다.',
       '- **원문 그대로라 남은 것**: 로그·`launch.json`·스크립트의 절대 경로는 작업 당시 이 맥 체크아웃 기준이다. 스크립트는 원래 temp 위치를 전제로 한다(복원 방법은 [`../PHASE_B_QA.md`](../PHASE_B_QA.md) §5).',
       '- 원시 로그·diff·route는 공백까지 원문 그대로다. 그래서 `git diff --check`류 공백 검사에 걸리는 파일이 있다(T6 시점 알려진 지적 5파일 19건: `t2/elf_inspect.log` 1, `t3/tracked.diff` 7, `t4/build.log` 1 — 줄 끝 공백, `t5/routes/candidate-fresh-to-name.route` 1 — 끝 빈 줄, `t5/t6-verify-rerun.log`(T7-FIX1에서 `t5/superseded-case13/t6-verify-rerun.log`로 옮김) 9 — 줄 끝 공백·끝 빈 줄. T7-FIX1이 새로 넣은 원시 로그·diff의 지적 수는 [`t7-fix1/REPORT.md`](<t7-fix1/REPORT.md>)에 따로 적었다. `git diff --no-index --check /dev/null <파일>` 기준). SHA 동일성을 지키려고 고치지 않았다. 공백 검사는 생산 코드와 새로 쓴 문서에만 적용한다.',
       '- **T7-FIX1 정정(2026-10-23)**: Astra full-v1 F1(케이스 13이 `각`에서 돌아 미완성 자모를 검사하지 않음)에 따라 케이스 13만 다시 실행하고 집계를 다시 만들었다. 정정 전 `t5/` 파일 8개(스크립트·케이스 13 결과/스텝·summary·case15 집계·manifest·T5 보고서·T6 집계 로그)는 [`t5/superseded-case13/`](<t5/superseded-case13/README.md>)에 SHA 그대로 옮겨 **무효**로 표시했다. `t5/`의 같은 경로 파일은 새 실행 결과다. F3(빌더 테스트 임시 경로) 결과는 `t3/`의 옛 로그를 덮지 않고 [`t7-fix1/`](<t7-fix1/REPORT.md>)에 따로 두었다. 이 정정분은 `temp/name-grid-phaseB/t7-fix1/update_evidence.py`로 복사하고 원본과 SHA를 대조했다.',
       '- **보존하지 않은 temp 원시 자료**(판정 요약과 SHA만 문서에 있음): 빌드 snapshot `namecompose-build/source/`·`baseline-build/source/`(약 290MB씩), T5 나머지 실행 폴더·`runs-failed/`·`runs-superseded/`, 연구 폴더의 RAM/VRAM 전체 덤프·대량 PNG·디스어셈블리 원본, `METADATA.json`·source-tree 해시 JSON, text-fit 첫 시도 JSON(`textfit_*.attempt1.json`), 공식 mGBA 빌드 트리. 재현 경로는 각 보고서의 명령 절을 따른다.', '']
for g, (title, cmd, target) in GROUPS.items():
    rows = [x for x in idx if x['group'] == g]
    out += [f'## {g} — {title}', '', f'- 생성 명령: {cmd}', f'- 대상: {target}', f'- 파일 {len(rows)}개, {sum(x["bytes"] for x in rows):,} B', '',
            '| 경로 | 출처(`temp/name-grid-phaseB/` 기준) | sha256 | bytes |', '|---|---|---|---:|']
    for x in rows:
        src = x['source'].replace('temp/name-grid-phaseB/', '')
        out.append(f'| [`{x["path"]}`](<{x["path"]}>) | `{src}` | `{x["sha256"]}` | {x["bytes"]:,} |')
    out.append('')
(E / 'INDEX.md').write_text('\n'.join(out))
print('INDEX rows', len(idx))
