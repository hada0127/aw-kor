# T5 정정 전 원문 — 케이스 13 미완성 자모 coverage 근거로 무효

T7-FIX1(2026-10-23)이 Astra full-v1 지적 F1에 따라 옮긴 파일이다. 아래 파일은 T6이 영구 증거로 복사했던 바이트 그대로이고, sha256은 옮기기 전 `index.json`의 값과 같다.

**무효 사유.** 정정 전 `cases.py` 케이스 13은 「자모 active」 단계에서 `c.jamo('ㄱ')`을 불렀다. 앞 단계의 active `가`에 `ㄱ`이 받침으로 붙어 `각`(완성 음절)이 됐다. 그래서 `dakuten-incomplete`·`handakuten-incomplete`·`R-incomplete` 스텝은 모두 `preview="각"`·live `8841`·tail `01000001` 상태에서 돌았다. 이 원문의 케이스 13 PASS, 그 PASS를 집계한 `summary.json`·T5 보고서·T6 집계 로그는 **미완성 자모(`ㄱ`) 상태 검증의 근거가 아니다.** 한글 active(`가`) 단계 세 스텝과 13b(legacy カ)는 이 결함과 무관하지만, 정정 뒤 같은 검사를 새 실행으로 다시 얻었으므로 판정에는 새 파일을 쓴다.

새 판정 근거는 같은 상위 경로의 [`../cases.py`](../cases.py), [`../runs/case13/result.json`](../runs/case13/result.json), [`../runs/case13/steps.jsonl`](../runs/case13/steps.jsonl), [`../runs/case13/bp.log`](../runs/case13/bp.log), [`../summary.json`](../summary.json), [`../case15-contracts.json`](../case15-contracts.json)이다. 정정 경위는 [`../../t7-fix1/REPORT.md`](../../t7-fix1/REPORT.md).

| 파일 | 정정 전 경로 | temp 출처 | sha256 | bytes |
|---|---|---|---|---:|
| [`cases.py`](cases.py) | `t5/cases.py` | `t7-fix1/pre-fix/cases.py` | `45f6561b22b8c1484f1fa192ff39d2886bfca24ea075212abcf6942e1bfde7bf` | 17,414 |
| [`runs/case13/result.json`](runs/case13/result.json) | `t5/runs/case13/result.json` | `t5-runtime/runs-superseded/case13-1792750756/result.json` | `a6fab0cb3fe6d761d80ae619a93891baa0d0754713f1c27f5211ddc5561b6489` | 638 |
| [`runs/case13/steps.jsonl`](runs/case13/steps.jsonl) | `t5/runs/case13/steps.jsonl` | `t5-runtime/runs-superseded/case13-1792750756/steps.jsonl` | `d5a9cfbd132b1f0125dea824c9612d7670beee678ad88cfb59359abf279ab2f1` | 3,562 |
| [`summary.json`](summary.json) | `t5/summary.json` | `t7-fix1/pre-fix/t5/summary.json` | `3e01dd881d029f1cfb333e24195acf26554b4497a6c9f7a5d132051028b51e93` | 7,296 |
| [`case15-contracts.json`](case15-contracts.json) | `t5/case15-contracts.json` | `t7-fix1/pre-fix/t5/case15-contracts.json` | `382345c41ca954045b9b8f9872fca3ff28b70772f63574557b54370d304eb8b5` | 18,519 |
| [`evidence-manifest.json`](evidence-manifest.json) | `t5/evidence-manifest.json` | `t7-fix1/pre-fix/t5/evidence-manifest.json` | `fcb08421c668870a0f219220f0f4962c915275d3bdf035c1eebcdbb75f79d405` | 18,570 |
| [`REPORT.md`](REPORT.md) | `t5/REPORT.md` | `t7-fix1/pre-fix/t5/REPORT.md` | `37326b309525225e03fd206d4bc1da4c73c50233ebeb5be3492e5d08decd001b` | 16,855 |
| [`t6-verify-rerun.log`](t6-verify-rerun.log) | `t5/t6-verify-rerun.log` | `t6-docs/t5-verify.log` | `2f048db41e5d86955e0086ee59c8cfb8c59527e8d29361feb953b27d16844dd4` | 1,584 |

- 정정 전 `case15-contracts.json`의 S1 mode1 수락 117·S3 mode1 16은 옛 케이스 13의 `ㄱ` 입력 1회를 포함한 수다. 정정 뒤는 116·17이다(`ㄱ` 1회가 `B` 1회로 바뀜). 위반 수는 둘 다 0이다.
- `processes.jsonl`은 덧붙이기만 하는 원장이라 정정 전 내용이 새 파일의 앞부분에 그대로 있다. 따로 옮기지 않았다.
- 옛 케이스 13 실행 폴더의 나머지 원문(`bp.log` 등)은 커밋하지 않는 temp `t5-runtime/runs-superseded/case13-1792750756/`에 남아 있다.
