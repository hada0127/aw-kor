# Phase B 영구 증거 색인

이 폴더는 ignored `temp/name-grid-phaseB/`의 Phase B 증거 가운데 문서가 인용하는 최소분을 **바이트 그대로** 복사한 것이다. 모든 행의 sha256은 복사 직후 원본과 대조해 같았다(`temp/name-grid-phaseB/t6-docs/collect.py`, T6 2026-10-23). 기계 판독용은 [`index.json`](index.json).

- **포함하지 않은 것**: ROM(`.gba`), 카트리지 세이브(`.sav`), savestate(`.ss0`), 원본 ZIP·tar, 폰트 원본, 공식 mGBA 소스·바이너리·라이브러리. 이들의 SHA는 보고서와 [`../PHASE_B_QA.md`](../PHASE_B_QA.md)에 있다.
- **원문 그대로라 남은 것**: 로그·`launch.json`·스크립트의 절대 경로는 작업 당시 이 맥 체크아웃 기준이다. 스크립트는 원래 temp 위치를 전제로 한다(복원 방법은 [`../PHASE_B_QA.md`](../PHASE_B_QA.md) §5).
- 원시 로그·diff·route는 공백까지 원문 그대로다. 그래서 `git diff --check`류 공백 검사에 걸리는 파일이 있다(T6 시점 알려진 지적 5파일 19건: `t2/elf_inspect.log` 1, `t3/tracked.diff` 7, `t4/build.log` 1 — 줄 끝 공백, `t5/routes/candidate-fresh-to-name.route` 1 — 끝 빈 줄, `t5/t6-verify-rerun.log`(T7-FIX1에서 `t5/superseded-case13/t6-verify-rerun.log`로 옮김) 9 — 줄 끝 공백·끝 빈 줄. T7-FIX1이 새로 넣은 원시 로그·diff의 지적 수는 [`t7-fix1/REPORT.md`](<t7-fix1/REPORT.md>)에 따로 적었다. `git diff --no-index --check /dev/null <파일>` 기준). SHA 동일성을 지키려고 고치지 않았다. 공백 검사는 생산 코드와 새로 쓴 문서에만 적용한다.
- **T7-FIX1 정정(2026-10-23)**: Astra full-v1 F1(케이스 13이 `각`에서 돌아 미완성 자모를 검사하지 않음)에 따라 케이스 13만 다시 실행하고 집계를 다시 만들었다. 정정 전 `t5/` 파일 8개(스크립트·케이스 13 결과/스텝·summary·case15 집계·manifest·T5 보고서·T6 집계 로그)는 [`t5/superseded-case13/`](<t5/superseded-case13/README.md>)에 SHA 그대로 옮겨 **무효**로 표시했다. `t5/`의 같은 경로 파일은 새 실행 결과다. F3(빌더 테스트 임시 경로) 결과는 `t3/`의 옛 로그를 덮지 않고 [`t7-fix1/`](<t7-fix1/REPORT.md>)에 따로 두었다. 이 정정분은 `temp/name-grid-phaseB/t7-fix1/update_evidence.py`로 복사하고 원본과 SHA를 대조했다.
- **T7-FIX2 F4 정정(2026-10-23)**: temp/영구 [`t7-fix1/REPORT.md`](<t7-fix1/REPORT.md>)와 QA의 보조 RC0 성공 주장을 철회했다. 이 REPORT는 T7-FIX2에서 temp 원본과 함께 정정했고 아래 SHA·크기도 갱신했다. [`compare_t4_snapshot.log`](<t7-fix1/compare_t4_snapshot.log>)는 최초 단순 비교의 `DIFFERENT`·`MISSING`·**RC=1** 원문이다. [`compare_t4_snapshot.py`](<t7-fix1/compare_t4_snapshot.py>)는 이후 수정본(`DIFF_VS_T4` 등 출력)이며 해당 로그와 동일 실행의 소스로 연결하지 않는다. 두 파일의 출처 열은 각 보존 파일의 과거 복사 경로이며 동일 실행이라는 뜻이 아니다. 후속 RC0 원문 로그는 보존되지 않아 `(unverified)`·판정 근거 제외다. 원시 로그·스크립트 및 다른 증거의 SHA·크기는 그대로다. 기존 SHA 전후·validate_t7 출력·부모 manifest-v2의 독립 근거와 다른 15case·F3 실제 RC0 로그는 유지한다.
- **보존하지 않은 temp 원시 자료**(판정 요약과 SHA만 문서에 있음): 빌드 snapshot `namecompose-build/source/`·`baseline-build/source/`(약 290MB씩), T5 나머지 실행 폴더·`runs-failed/`·`runs-superseded/`, 연구 폴더의 RAM/VRAM 전체 덤프·대량 PNG·디스어셈블리 원본, `METADATA.json`·source-tree 해시 JSON, text-fit 첫 시도 JSON(`textfit_*.attempt1.json`), 공식 mGBA 빌드 트리. 재현 경로는 각 보고서의 명령 절을 따른다.

## plan — 승인 계획·원 요청·수행 주체 결정

- 생성 명령: 총괄 brief / `harness-plan-write recheck`(PLAN-v5) / 사용자 결정 기록
- 대상: —
- 파일 3개, 48,331 B

| 경로 | 출처(`temp/name-grid-phaseB/` 기준) | sha256 | bytes |
|---|---|---|---:|
| [`plan/PLAN-v5.md`](<plan/PLAN-v5.md>) | `PLAN-v5.md` | `60a7574a957e5277ac8bbb826ad3bee54c39362907fd30864cc26c47809521b4` | 39,126 |
| [`plan/PHASE_B_BRIEF.md`](<plan/PHASE_B_BRIEF.md>) | `PHASE_B_BRIEF.md` | `f4682096edfd859a4d61f1866476abe2c5dda744d56a672e9dce5eb825bd01a1` | 8,604 |
| [`plan/ROUTING_UPDATE.md`](<plan/ROUTING_UPDATE.md>) | `ROUTING_UPDATE.md` | `f4b3e9b2c167220923a1a327981d031d0300fa4113c1da2299b9813406ab95b0` | 601 |

## research — Phase B 사전 조사 판정(원시 보고서 7개 + mode-scope 원시 산출물)

- 생성 명령: 각 보고서의 「명령·exit」 절
- 대상: 원본 `a8ad7c7d…831c`, baseline `ebbca0ba…3a8a`, b44 `1ac68443…6f02` (보고서별)
- 파일 40개, 244,565 B

| 경로 | 출처(`temp/name-grid-phaseB/` 기준) | sha256 | bytes |
|---|---|---|---:|
| [`research/native-re/RUNTIME_REPORT.md`](<research/native-re/RUNTIME_REPORT.md>) | `native-re/RUNTIME_REPORT.md` | `4eb9d42f38b42dd3da4c688bf1921353f6223796e5db4b01479b56fbd615067d` | 23,871 |
| [`research/native-re/verification.log`](<research/native-re/verification.log>) | `native-re/verification.log` | `f0e154f2702de75bfc35e9a67b2a10bab5783676c2d8059b6c692f2ca233fcbb` | 615 |
| [`research/native-re/hook-bytes.json`](<research/native-re/hook-bytes.json>) | `native-re/hook-bytes.json` | `0c817a0956357ef102b3feb4d0745100798b418d4522d7b8fbc74b1f8db5e47c` | 460 |
| [`research/native-re/replay-normal/route.txt`](<research/native-re/replay-normal/route.txt>) | `native-re/replay-normal/route.txt` | `2bb3310ec363d63eb8c01fdb815c663d87c7604d758a49bbcbbc631bf188746c` | 1,818 |
| [`research/native-re/replay-cold/route.txt`](<research/native-re/replay-cold/route.txt>) | `native-re/replay-cold/route.txt` | `813f70763f9400636ca7bd7a1e6991160d156646428333c323124739fd60028e` | 1,198 |
| [`research/candidate-re/RUNTIME_REPORT.md`](<research/candidate-re/RUNTIME_REPORT.md>) | `candidate-re/RUNTIME_REPORT.md` | `ba3985bbebad2af965889a71bbc31fa90fbc75c1517d566d4558b2c1362d4d59` | 28,234 |
| [`research/candidate-re/verification.log`](<research/candidate-re/verification.log>) | `candidate-re/verification.log` | `1bbfc042f8fe47a6a0bcca7173a660324f953d5dc995d6a52c8fd4dc61e955d3` | 1,119 |
| [`research/candidate-re/table-audit.json`](<research/candidate-re/table-audit.json>) | `candidate-re/table-audit.json` | `2936132090714e8ba905f1eaae69558c30ffa01285214e5787335aaafb9e4e83` | 667 |
| [`research/candidate-re/call-sites.json`](<research/candidate-re/call-sites.json>) | `candidate-re/call-sites.json` | `dfc97fe6ca34d210243c00d5a3d04629bc9c8e7f524f2294f823ffc606a9ef6e` | 875 |
| [`research/candidate-re/writer-addresses.json`](<research/candidate-re/writer-addresses.json>) | `candidate-re/writer-addresses.json` | `6b9818d4754066ce389c7e393e253de68bd08fb9ba1d1fdf95df96cd82a03126` | 3,312 |
| [`research/list-link-re/RUNTIME_REPORT.md`](<research/list-link-re/RUNTIME_REPORT.md>) | `list-link-re/RUNTIME_REPORT.md` | `ff74497584cd141c70fa9be2a240140a21b473c712f9f82274150265c6c96f46` | 13,924 |
| [`research/list-link-re/verification.txt`](<research/list-link-re/verification.txt>) | `list-link-re/verification.txt` | `8d45ec0386ef5111ee81de63477dea20f1cb551402359a4da15f6937b62495eb` | 2,840 |
| [`research/list-link-re/runtime-identities.json`](<research/list-link-re/runtime-identities.json>) | `list-link-re/runtime-identities.json` | `e497074f6ba237785b64ff42bb317bff50ec925d64010bff4c2353b214ff1902` | 643 |
| [`research/list-link-re/candidate-map.route`](<research/list-link-re/candidate-map.route>) | `list-link-re/candidate-map.route` | `512965635f5e6f7a03da9a92d0a94f53719602d4bf475848e8cd87372bea9a63` | 2,636 |
| [`research/list-link-re/candidate-cold-fixed.route`](<research/list-link-re/candidate-cold-fixed.route>) | `list-link-re/candidate-cold-fixed.route` | `a53ad4cfa6f3de0ff1ffe21700cb8ea58cd19b7db80e55802b97025801d7feec` | 1,155 |
| [`research/mode-scope-re/verification.log`](<research/mode-scope-re/verification.log>) | `mode-scope-re/verification.log` | `41022c8be189dacca36be3d26067d55ee2e8d620437e8aa6b7fd9f22ccad5fbf` | 3,201 |
| [`research/mode-scope-re/model-results.json`](<research/mode-scope-re/model-results.json>) | `mode-scope-re/model-results.json` | `f93b8c013077816e1d3d8821c5ac76740b4a836af6fd703a23571af31cc96b7d` | 7,437 |
| [`research/mode-scope-re/grid-map.json`](<research/mode-scope-re/grid-map.json>) | `mode-scope-re/grid-map.json` | `a3211ae061828b283d21bfceb0786da6d98f5ecbae70bfe84093379df3bbea4d` | 22,052 |
| [`research/mode-scope-re/symbolic-layout.json`](<research/mode-scope-re/symbolic-layout.json>) | `mode-scope-re/symbolic-layout.json` | `0011e2be018d12339459a32ffbbe0547311d5097a8554b2f155ef2a82ddcdcfc` | 8,843 |
| [`research/mode-scope-re/hook-contract-inputs.json`](<research/mode-scope-re/hook-contract-inputs.json>) | `mode-scope-re/hook-contract-inputs.json` | `a621c4e6cdb69afccdbdda5c3286421512a017df5a8ab8f0db561042925d94cf` | 1,107 |
| [`research/mode-scope-re/additional-contracts.json`](<research/mode-scope-re/additional-contracts.json>) | `mode-scope-re/additional-contracts.json` | `e4d9f3fbd003bb29b24c21bc272ff153469273e628c1ca768c06773599b78f89` | 537 |
| [`research/mode-scope-re/execution-summary.json`](<research/mode-scope-re/execution-summary.json>) | `mode-scope-re/execution-summary.json` | `522d1cb9393bef8d207365e2aa5423382891fb69ebc9301cd38b26d6e0dfcb29` | 1,847 |
| [`research/mode-scope-re/runtime-cases.log`](<research/mode-scope-re/runtime-cases.log>) | `mode-scope-re/runtime-cases.log` | `000410c295eefe6fccbdd7cea5555ea4de512691b09f75307f3077380278828e` | 76 |
| [`research/mode-scope-re/constructor-modes.log`](<research/mode-scope-re/constructor-modes.log>) | `mode-scope-re/constructor-modes.log` | `87f0349034fbe0865a069f0af0942ff9a2def2a6d53ff0a65c42abb9ec362a3d` | 108 |
| [`research/mode-scope-re/static-model.log`](<research/mode-scope-re/static-model.log>) | `mode-scope-re/static-model.log` | `681299d5fc58d8ae4aaa25164018b8699093e0ab6cabdd5c0f28a01b399a72a1` | 2,329 |
| [`research/mode-scope-re/baseline-name-module.log`](<research/mode-scope-re/baseline-name-module.log>) | `mode-scope-re/baseline-name-module.log` | `dd8b3a5a5522cfff7c57a8e3bab67336bee1e0aba3a976519902482370dd13b5` | 67,904 |
| [`research/baseline-build/RETRY1_BUILD_REPORT.md`](<research/baseline-build/RETRY1_BUILD_REPORT.md>) | `baseline-build/RETRY1_BUILD_REPORT.md` | `4415cbea3baaf41e1d519bfab79800d87cc056884488aa484e8fbd873680b1ec` | 4,910 |
| [`research/b44-reference/RECOVERY_REPORT.md`](<research/b44-reference/RECOVERY_REPORT.md>) | `b44-reference/RECOVERY_REPORT.md` | `aa69a9dc71ec8f7e257261a52e46eb73facb4254ee9ef9fc6339e5ffd0f401f8` | 5,326 |
| [`research/official-mgba/BUILD_REPORT.md`](<research/official-mgba/BUILD_REPORT.md>) | `official-mgba/BUILD_REPORT.md` | `a624bb84fdc025739fa74e99e31a98cc6ec7b27dc14e1166d3234ea2db035506` | 14,217 |
| [`research/official-mgba/SHA256SUMS`](<research/official-mgba/SHA256SUMS>) | `official-mgba/SHA256SUMS` | `060a198be4e08d5e32189478e7bc7f6709d217eef7adde6f96519e725d1943fa` | 824 |
| [`research/official-mgba/abi-values.json`](<research/official-mgba/abi-values.json>) | `official-mgba/abi-values.json` | `9823a0cba3d82317b4b458028f22b85907744b0b981efebdb64e246f0d73b257` | 681 |
| [`research/official-mgba/build.py`](<research/official-mgba/build.py>) | `official-mgba/build.py` | `026fbe579ac4298d77fc9f57428e8324f1f50aeaf2ef9e260182f2000995bcfb` | 1,766 |
| [`research/official-mgba/verify.py`](<research/official-mgba/verify.py>) | `official-mgba/verify.py` | `ba5e148f3691d0c9e9b5015934f68e9444230932b490a699adea9bba0adabf88` | 1,876 |
| [`research/official-mgba/abi_probe.c`](<research/official-mgba/abi_probe.c>) | `official-mgba/abi_probe.c` | `db0670c5d6d035a5098358d4e7b7ccc647dc1b4a5bb14add51eafb3b930a18c7` | 585 |
| [`research/official-mgba/run-single.sh`](<research/official-mgba/run-single.sh>) | `official-mgba/run-single.sh` | `82ae4f7a22a7c1ce21d2106a807f76b4f2eae8d71d1827ae0e3594d205a65a07` | 427 |
| [`research/official-mgba/run-link.sh`](<research/official-mgba/run-link.sh>) | `official-mgba/run-link.sh` | `264cf866bc4384478078655447fa85ab8a4f7d1051566880cfabe3ebd4e64bb1` | 430 |
| [`research/official-mgba/commands.jsonl`](<research/official-mgba/commands.jsonl>) | `official-mgba/commands.jsonl` | `31dbd803fe9f8f93672c6bc7c6e61ce782eaf6f3a1da9150f2b590426ba5ba4f` | 6,838 |
| [`research/official-mgba/source-verification.log`](<research/official-mgba/source-verification.log>) | `official-mgba/source-verification.log` | `9692bf67044bed969b7e7433ec3076134a7a9a20f155176b453c2cdfbf4eeb78` | 43 |
| [`research/arm-link-proof/PROOF_REPORT.md`](<research/arm-link-proof/PROOF_REPORT.md>) | `arm-link-proof/PROOF_REPORT.md` | `3a284df28fe612db3367713136e9e926398271ea5a542baaf90f2d00719d3193` | 6,980 |
| [`research/arm-link-proof/verification.log`](<research/arm-link-proof/verification.log>) | `arm-link-proof/verification.log` | `2db4d3ae06aae8d9df7f154dfee3868b08895f0316e2c1519492595990f80030` | 854 |

## t1 — T1 자모 자산

- 생성 명령: `python3 -I tools/gen_jamo_assets.py` · `test_jamo_assets.py` · `--check`
- 대상: HEAD `9090818` + T1 신규 파일
- 파일 8개, 12,747 B

| 경로 | 출처(`temp/name-grid-phaseB/` 기준) | sha256 | bytes |
|---|---|---|---:|
| [`t1/REPORT.md`](<t1/REPORT.md>) | `t1-assets/REPORT.md` | `79a5dd0a5f25855efb97cceade9c465e8d5dd3ad05881375fc972d8c9453b331` | 8,887 |
| [`t1/gen.log`](<t1/gen.log>) | `t1-assets/gen.log` | `f49966cf87d679809335f72f5eb119829666422e80b64dad04b68e178685a373` | 117 |
| [`t1/test.log`](<t1/test.log>) | `t1-assets/test.log` | `03d78e503e97fa18b22af98ac36dc2f2f20606bb0d6a74c44d89b716348def76` | 882 |
| [`t1/check.log`](<t1/check.log>) | `t1-assets/check.log` | `d7f6bb0d3c68f21ecdf5b3e44dbf7e084d7d5a861f2dd6dd7973e685e51e15a5` | 83 |
| [`t1/hangul_compose_regress.log`](<t1/hangul_compose_regress.log>) | `t1-assets/hangul_compose_regress.log` | `7310f086a682469a72b606f12bdef76ce444ac28dcbc5b10d35c51933a88d533` | 240 |
| [`t1/fix1.log`](<t1/fix1.log>) | `t1-assets/fix1.log` | `06895bf54497f67242b51d8f50fdf257cb4b6df21d7150ddcc81f37c33757d12` | 1,514 |
| [`t1/fix1_test.log`](<t1/fix1_test.log>) | `t1-assets/fix1_test.log` | `3c024ceadc9ada08a95536c6ed590727349d4b176258b6a91ca2cd063cd76eb7` | 941 |
| [`t1/fix1_check.log`](<t1/fix1_check.log>) | `t1-assets/fix1_check.log` | `d7f6bb0d3c68f21ecdf5b3e44dbf7e084d7d5a861f2dd6dd7973e685e51e15a5` | 83 |

## t2 — T2 조합 코어·이미지

- 생성 명령: `python3 -I tools/test_name_compose_core.py` · `build_image.py --check`
- 대상: HEAD `9090818` + T1/T2 신규 파일
- 파일 9개, 66,596 B

| 경로 | 출처(`temp/name-grid-phaseB/` 기준) | sha256 | bytes |
|---|---|---|---:|
| [`t2/REPORT.md`](<t2/REPORT.md>) | `t2-core/REPORT.md` | `e871416131e3162daec5d0ae42771810a2b38ebb7d0f3ad86c84f039e6a07416` | 12,025 |
| [`t2/test.log`](<t2/test.log>) | `t2-core/test.log` | `7c52dd1a6e2350f8d0c1665343684d2e69d7819aac36f01ce4e7a74a46c70e76` | 1,270 |
| [`t2/blob_check.log`](<t2/blob_check.log>) | `t2-core/blob_check.log` | `dcd1cd8ed8d58080dfcbd875cd847383b58bfbb8b98da9e48459aae4835a46dc` | 495 |
| [`t2/t1_regress.log`](<t2/t1_regress.log>) | `t2-core/t1_regress.log` | `4369f61b0d99325dac3f022e907e2ed767fae3d400a2feb6320198b8701cb6b5` | 902 |
| [`t2/t1_check.log`](<t2/t1_check.log>) | `t2-core/t1_check.log` | `eda307733f80145203668aaa12019bddd03cab97e275561b10f51ceadcd2fd56` | 37 |
| [`t2/hangul_regress.log`](<t2/hangul_regress.log>) | `t2-core/hangul_regress.log` | `a2cb3e8f906048d2426dd83a95748d1eeafc4fd7e8584aaedb3570a6f8452499` | 1,131 |
| [`t2/gridmap_vs_rom.log`](<t2/gridmap_vs_rom.log>) | `t2-core/gridmap_vs_rom.log` | `5c71624a242fb7d505bd71d67275b59c22a9ad3bb6af2f1b3645412f1d93993e` | 226 |
| [`t2/elf_inspect.log`](<t2/elf_inspect.log>) | `t2-core/elf_inspect.log` | `6475eb6ab9e3a6761c96a0914e9db0a260471b467db8b767f18b576b77a262f0` | 3,611 |
| [`t2/objdump.txt`](<t2/objdump.txt>) | `t2-core/objdump.txt` | `71576fc5f9bb2d1d336cb15462f2e16c949555d4c3b7a29c31a5770d410609ff` | 46,899 |

## t3 — T3 빌더 통합

- 생성 명령: `test_part2_name_compose_build.py` 외 회귀 테스트·변이 검사
- 대상: HEAD `9090818` + T1~T3 변경, fixture 후보 `1ac790a9…e1eb`
- 파일 28개, 125,454 B

| 경로 | 출처(`temp/name-grid-phaseB/` 기준) | sha256 | bytes |
|---|---|---|---:|
| [`t3/REPORT.md`](<t3/REPORT.md>) | `t3-builder/REPORT.md` | `64b178f9b8d07d8b5ae4ffecb2d0f7595421629b8edaa99b017cb85b9b0678a7` | 14,617 |
| [`t3/mutation.log`](<t3/mutation.log>) | `t3-builder/mutation.log` | `29b11db6985f0a2394b034ea7ad73aa90a378e1d20e82fac6af9792852fd6050` | 458 |
| [`t3/mutation_logs/M10_native_any.log`](<t3/mutation_logs/M10_native_any.log>) | `t3-builder/mutation_logs/M10_native_any.log` | `8f55f0101e4f59e730d54ee8e6b01e3bf8df69ffc234cda9184daec08ec7d129` | 10,673 |
| [`t3/mutation_logs/M11_max_not_written.log`](<t3/mutation_logs/M11_max_not_written.log>) | `t3-builder/mutation_logs/M11_max_not_written.log` | `f42a1fbfcd8e1c0d1a5fcc67eaea65538680fbe71c93e22c33ba6f623372abd2` | 1,216 |
| [`t3/mutation_logs/M1_site_check.log`](<t3/mutation_logs/M1_site_check.log>) | `t3-builder/mutation_logs/M1_site_check.log` | `a9ad520485c0cb2313f5b3358ba427374177f6919ef2ae9ec9b29162e444d1de` | 5,511 |
| [`t3/mutation_logs/M2_non_atomic.log`](<t3/mutation_logs/M2_non_atomic.log>) | `t3-builder/mutation_logs/M2_non_atomic.log` | `de86e6a887d7f715562076dfa79160f538a3366528ac8dc1dde9541248d6fdb4` | 23,595 |
| [`t3/mutation_logs/M3_a3_stage_guard.log`](<t3/mutation_logs/M3_a3_stage_guard.log>) | `t3-builder/mutation_logs/M3_a3_stage_guard.log` | `561bff309c2e7968602dcb08de7e273042a26082d94f9b9d7f7074f87c93c37c` | 6,661 |
| [`t3/mutation_logs/M4_table_expected.log`](<t3/mutation_logs/M4_table_expected.log>) | `t3-builder/mutation_logs/M4_table_expected.log` | `ea3218cd43eaf0ed25d41ef504a5b1ffc26f4630aea865bf8bb8f5aea2452d48` | 6,253 |
| [`t3/mutation_logs/M5_d1_register.log`](<t3/mutation_logs/M5_d1_register.log>) | `t3-builder/mutation_logs/M5_d1_register.log` | `650179116384eb6a085146f3231c01f07ce8375b15804b6b56db840fba8bbcdb` | 2,050 |
| [`t3/mutation_logs/M6_gap_zero.log`](<t3/mutation_logs/M6_gap_zero.log>) | `t3-builder/mutation_logs/M6_gap_zero.log` | `420e1aed5b1a94fd6be76d3feea44fe6e921cf1e82baea80be22132dcc3ea1e7` | 2,251 |
| [`t3/mutation_logs/M7_pool.log`](<t3/mutation_logs/M7_pool.log>) | `t3-builder/mutation_logs/M7_pool.log` | `67c6ef8e0e8d7f32a0100c21ae5d5be1f93acda4c236612f7c47882fe37d4688` | 2,360 |
| [`t3/mutation_logs/M8_json_sha.log`](<t3/mutation_logs/M8_json_sha.log>) | `t3-builder/mutation_logs/M8_json_sha.log` | `ef3f9f222fd438d7c75726c553bc45b5209eaeda47212a961a0e0bd27e8893d8` | 2,360 |
| [`t3/mutation_logs/M9_end_literal.log`](<t3/mutation_logs/M9_end_literal.log>) | `t3-builder/mutation_logs/M9_end_literal.log` | `1753da0193b9d5249903e7021f941183a987f6d256ad905dd3ec137e0ac066a7` | 3,341 |
| [`t3/native_profile_check.log`](<t3/native_profile_check.log>) | `t3-builder/native_profile_check.log` | `d1e7c02589c2b5c1135903f50784256eae9004f1b75e4fa881b105cb53f179c4` | 183 |
| [`t3/test_dialogue_script_safety.log`](<t3/test_dialogue_script_safety.log>) | `t3-builder/test_dialogue_script_safety.log` | `09effc52fa8cb8e7124a546d7d6dda9a74bd56d389373340ab7a9a0687698c5c` | 9,114 |
| [`t3/test_jamo_assets.log`](<t3/test_jamo_assets.log>) | `t3-builder/test_jamo_assets.log` | `c006df2217e1f87d5df3633015e1910d06adce612c800c7da8df72fe57716822` | 919 |
| [`t3/test_name_compose_core.log`](<t3/test_name_compose_core.log>) | `t3-builder/test_name_compose_core.log` | `41e63139531a0dd2cbecc92871fdddfa97e45a67091df56d6e764e14c31c2f11` | 1,293 |
| [`t3/test_part1_yesno_row.log`](<t3/test_part1_yesno_row.log>) | `t3-builder/test_part1_yesno_row.log` | `c0a9a1264422813415a981bf4e0ff7630375c0e28d4eeda22220a80285830b42` | 614 |
| [`t3/test_part2_context_contract.HEAD.log`](<t3/test_part2_context_contract.HEAD.log>) | `t3-builder/test_part2_context_contract.HEAD.log` | `c5b5fba10a9e2a381d86a951f8552ba7b9592ea2c6befd040fa3a5b0413e698e` | 1,510 |
| [`t3/test_part2_context_contract.log`](<t3/test_part2_context_contract.log>) | `t3-builder/test_part2_context_contract.log` | `a97f7feb8e596d9e4ed6d01fd905299fd349aa32f2188ee2dde97e2ca568cd81` | 1,488 |
| [`t3/test_part2_dialogue_layout_contracts.log`](<t3/test_part2_dialogue_layout_contracts.log>) | `t3-builder/test_part2_dialogue_layout_contracts.log` | `46d93dbd0db9f1a2c80c31a8180515302c455d3d2e53db239c0877cee55b4853` | 869 |
| [`t3/test_part2_name_compose_build.isolated.log`](<t3/test_part2_name_compose_build.isolated.log>) | `t3-builder/test_part2_name_compose_build.isolated.log` | `e3b258aa89693684979b5147e8db416112064b26cc0514d1b37cb90df2b810b6` | 1,237 |
| [`t3/test_part2_name_compose_build.log`](<t3/test_part2_name_compose_build.log>) | `t3-builder/test_part2_name_compose_build.log` | `f6c43236c8614b45d28a8508226371cdf7376158dbd1b0cfce7fb80394e3bb29` | 2,524 |
| [`t3/test_part2_native_controls.log`](<t3/test_part2_native_controls.log>) | `t3-builder/test_part2_native_controls.log` | `736b70eb30baaf1a24c10e782aaa6f858eee0f816f6d933a4f78a698da7062c9` | 963 |
| [`t3/test_part2_volcano_context.log`](<t3/test_part2_volcano_context.log>) | `t3-builder/test_part2_volcano_context.log` | `aae135b696f87304ff226c84c4430797ed865a6c04e6d8a495bdb95e54985de4` | 636 |
| [`t3/test_qa_part2_physical_rows.HEAD.log`](<t3/test_qa_part2_physical_rows.HEAD.log>) | `t3-builder/test_qa_part2_physical_rows.HEAD.log` | `a15a7c628806dbddef766d31f8287c20bf95b316e75bd03398e6bdefea6fd0dd` | 1,851 |
| [`t3/test_qa_part2_physical_rows.log`](<t3/test_qa_part2_physical_rows.log>) | `t3-builder/test_qa_part2_physical_rows.log` | `749ac672d3333f8d532f83fe0597d59ffeeedf28f25ff4f89d2e990fea7970a0` | 1,787 |
| [`t3/tracked.diff`](<t3/tracked.diff>) | `t3-builder/tracked.diff` | `5c461dbcb7bfaa8b3af3246de05d27b7016746c79dd3a62a5fb95b7907c31b76` | 19,120 |

## t4 — T4 후보 빌드·5관문·집합 비교

- 생성 명령: `run_build.py`(빌드 1회 + 5관문) · `analyze.py` · `trace_text_fit.py`/`compare_text_fit.py` · `final_check.py`
- 대상: 후보 `1ac790a9…e1eb`, snapshot manifest `e6c9fcf8…1b66`
- 파일 33개, 1,137,023 B

| 경로 | 출처(`temp/name-grid-phaseB/` 기준) | sha256 | bytes |
|---|---|---|---:|
| [`t4/REPORT.md`](<t4/REPORT.md>) | `namecompose-build/REPORT.md` | `499a4cab592b9234bba21cb0cf40b7f145484e9319de4f0c281a4e120ae83498` | 17,025 |
| [`t4/run_build.py`](<t4/run_build.py>) | `namecompose-build/run_build.py` | `8f38d8a19879b09cda3fcd9a862fe39c01f621d9e6eb6769b148491e237487cd` | 8,117 |
| [`t4/analyze.py`](<t4/analyze.py>) | `namecompose-build/analyze.py` | `94bd06fc5f32e3ba2434310a79f35d66c0328e37602f731ec005379cc2e79ad5` | 16,762 |
| [`t4/trace_text_fit.py`](<t4/trace_text_fit.py>) | `namecompose-build/trace_text_fit.py` | `8a853f439ae7a9348da36c9b98714def9550e18993b11aaa52dae9b1577f1c41` | 3,621 |
| [`t4/compare_text_fit.py`](<t4/compare_text_fit.py>) | `namecompose-build/compare_text_fit.py` | `7695e1bc56e48b75516cdae8bf911cfab74f6c69aaef43d47eb74a6845a98339` | 1,545 |
| [`t4/final_check.py`](<t4/final_check.py>) | `namecompose-build/final_check.py` | `d9d586c9cb596d16e692a5f047b66fd22c9e7719afa6e1d5725131518cca3c7c` | 1,996 |
| [`t4/tree_hash.py`](<t4/tree_hash.py>) | `namecompose-build/tree_hash.py` | `5af1e9c0c34b09f8f0a84ef8ab32dd107e703afad6473b50f9f4e10e24838aca` | 486 |
| [`t4/runner_stdout.log`](<t4/runner_stdout.log>) | `namecompose-build/runner_stdout.log` | `18fd3927dde862a8b66df3b907a48dac5a7ffbeb741a0f46c1c72ee4ed3de373` | 463 |
| [`t4/build.log`](<t4/build.log>) | `namecompose-build/build.log` | `a5167b3aa1c4f1b2fa2d11116a3c7600d800353c5e3f2f20a39178e99c1483b7` | 42,717 |
| [`t4/gate1.log`](<t4/gate1.log>) | `namecompose-build/gate1.log` | `a5704c1c92ffbb4da4c9f7447b4e04adc402a9957eed47b7b779bf8565bcf8e2` | 1,479 |
| [`t4/gate2.log`](<t4/gate2.log>) | `namecompose-build/gate2.log` | `1277c6c01470c55098ba440b23615b9f615204ec97189ef08f231f5dc0c708b3` | 397 |
| [`t4/gate3.log`](<t4/gate3.log>) | `namecompose-build/gate3.log` | `ccd926917bba6b3e9adefc59ebac5d7c7286dbe4fc83d93eb95fcda6411a7ea1` | 727 |
| [`t4/gate4.log`](<t4/gate4.log>) | `namecompose-build/gate4.log` | `6a5f63fc1c99591edfa056a58c7d2019e61cbc16aefd0fe80321d1df0f59a1b0` | 631 |
| [`t4/gate5.log`](<t4/gate5.log>) | `namecompose-build/gate5.log` | `73e4dfd2c0636047c2ec62dcd587f4ac8f0a8a0e6bc8e8618b741ca395ee5fba` | 263 |
| [`t4/analyze.log`](<t4/analyze.log>) | `namecompose-build/analyze.log` | `907da4e51e1916b3bd5e782d0916fa215d53f1dceb2ab47ee41fb56ece902f68` | 2,030 |
| [`t4/compare_text_fit.log`](<t4/compare_text_fit.log>) | `namecompose-build/compare_text_fit.log` | `9c473e9bd1e91555faa9dc65be8da37753c06ca46bb574df95276402faec4e9e` | 801 |
| [`t4/trace_baseline.log`](<t4/trace_baseline.log>) | `namecompose-build/trace_baseline.log` | `36a49a051a52e7192a559f92d2d25990656f96ef32bd32d98e4759b31d5dd53a` | 913 |
| [`t4/trace_candidate.log`](<t4/trace_candidate.log>) | `namecompose-build/trace_candidate.log` | `c6c59c2ba822c0510c18d9d51dca10f82ea9271540487ba3ac17f359ce3eebcd` | 914 |
| [`t4/trace_baseline.attempt1.log`](<t4/trace_baseline.attempt1.log>) | `namecompose-build/trace_baseline.attempt1.log` | `95dcbfce7c41485600edfb3e373d3b60b6b856b5de65534bb964a3111556d322` | 578 |
| [`t4/trace_candidate.attempt1.log`](<t4/trace_candidate.attempt1.log>) | `namecompose-build/trace_candidate.attempt1.log` | `56f7e48f7ca65cbff95f0b37199c921200d61647a09a50500292d1c72202115d` | 582 |
| [`t4/final_check.log`](<t4/final_check.log>) | `namecompose-build/final_check.log` | `9b5b5935eb3c593f59ffc954190ee15d26ecda94fb9d2c3d9e575245f4d593ec` | 6,005 |
| [`t4/snapshot_manifest.json`](<t4/snapshot_manifest.json>) | `namecompose-build/snapshot_manifest.json` | `e6c9fcf8b8b53c6abd68c8cbc73da24fab149bf4ed13424c3fd5e42f38e21b66` | 434,807 |
| [`t4/analysis/summary.json`](<t4/analysis/summary.json>) | `namecompose-build/analysis/summary.json` | `414548a418aaba94d288cfc57f1a3c40181ff043a54b1915b096c0f5d0dfb437` | 2,009 |
| [`t4/analysis/diff_payload.json`](<t4/analysis/diff_payload.json>) | `namecompose-build/analysis/diff_payload.json` | `959cdea7a782ca6190b66856767e39080fd8c895b2172460affa6c68bdaf4cb3` | 159,210 |
| [`t4/analysis/a3_jamo.json`](<t4/analysis/a3_jamo.json>) | `namecompose-build/analysis/a3_jamo.json` | `bef37096498103018e1427e8327f036640332b870dfbb195b44696c754534ee7` | 7,792 |
| [`t4/analysis/shared_glyph.json`](<t4/analysis/shared_glyph.json>) | `namecompose-build/analysis/shared_glyph.json` | `da283eabb4ba63249ae48fa17179aab00b2d2b20b50da1f3cbe50ecdc63cf5ef` | 16,740 |
| [`t4/analysis/writer_crosscheck.json`](<t4/analysis/writer_crosscheck.json>) | `namecompose-build/analysis/writer_crosscheck.json` | `8a1a4eb0c45b46d4c6e112c5723d6e812bc2312938c1f22fcfb2d7622cfac8a4` | 4,263 |
| [`t4/analysis/bteam_diff.json`](<t4/analysis/bteam_diff.json>) | `namecompose-build/analysis/bteam_diff.json` | `f3815ae6b1ad5aeb08da83233cf711dee713e2763b982d530bc22f3ed58b8446` | 281 |
| [`t4/analysis/textfit_baseline.json`](<t4/analysis/textfit_baseline.json>) | `namecompose-build/analysis/textfit_baseline.json` | `faf4813982742697a609bfb6c1a75e0b87867b043d51199830fc0d6c6a7e2de8` | 169,122 |
| [`t4/analysis/textfit_candidate.json`](<t4/analysis/textfit_candidate.json>) | `namecompose-build/analysis/textfit_candidate.json` | `5bc7c62b979f0da522fdf9aef6d052607d417cf0f6c24e0c8e7a3f02fa76b802` | 169,128 |
| [`t4/analysis/textfit_diff.json`](<t4/analysis/textfit_diff.json>) | `namecompose-build/analysis/textfit_diff.json` | `226c2c6a1560268d8176a073a7d0dbfaf6df05e89864ca86e35d68aa73d50fae` | 825 |
| [`t4/bteam/baseline_retry1_bteam_details.json`](<t4/bteam/baseline_retry1_bteam_details.json>) | `baseline-build/source/temp/retry1_bteam_details.json` | `efc9c607004448aa5cc1bbbe4f65985d8e49e06ec97d71ff9ab08dd7f6767c7e` | 32,397 |
| [`t4/bteam/candidate_bteam_details.json`](<t4/bteam/candidate_bteam_details.json>) | `namecompose-build/source/temp/candidate_bteam_details.json` | `efc9c607004448aa5cc1bbbe4f65985d8e49e06ec97d71ff9ab08dd7f6767c7e` | 32,397 |

## t5 — T5 런타임 QA(공식 mGBA 0.10.5)

- 생성 명령: `t5-runtime/*.py`(REPORT 「실행 명령과 종료코드」) · T7-FIX1 케이스 13 재실행·`case15.py analyze`·`verify.py`(2회)
- 대상: 후보 `1ac790a9…e1eb`(실행마다 assert), 대조 원본·baseline
- 파일 176개, 3,363,756 B

| 경로 | 출처(`temp/name-grid-phaseB/` 기준) | sha256 | bytes |
|---|---|---|---:|
| [`t5/t5lib.py`](<t5/t5lib.py>) | `t5-runtime/t5lib.py` | `a426a8f66a03b6f86e623dce4cfd05ef83d5bcc1fbe4946d9fdec27f3be1e843` | 17,382 |
| [`t5/cases.py`](<t5/cases.py>) | `t5-runtime/cases.py` | `e4c3229317e0aabc3c6df1044bfcec6a094e2990266f0549f65a90ca0c5ca5d5` | 18,610 |
| [`t5/case11.py`](<t5/case11.py>) | `t5-runtime/case11.py` | `3fa595d2e0d18f96bad46d5bd93631a48a7f7dc6218510e821c87cb7a1132f9e` | 6,962 |
| [`t5/case12.py`](<t5/case12.py>) | `t5-runtime/case12.py` | `c25bef6a940c15073f7bfedbc6e83226170a3f1af298762a54372d93487ada1d` | 3,960 |
| [`t5/case14.py`](<t5/case14.py>) | `t5-runtime/case14.py` | `619f0344a75bc696c13cbba1a140cf9e3d5661f112795eb3c1a0ff8a98dd9932` | 5,236 |
| [`t5/case15.py`](<t5/case15.py>) | `t5-runtime/case15.py` | `824d031f50a0598a633fd5e072f969ec08ab2bde4057436f8076adcc7c2a97a1` | 12,252 |
| [`t5/case15_rowseq.py`](<t5/case15_rowseq.py>) | `t5-runtime/case15_rowseq.py` | `33c538fb5a5867d0b7cb245d5d48acd7e6e15006565db17fb0a120ea9204769e` | 1,035 |
| [`t5/case15_mode0_vs_baseline.py`](<t5/case15_mode0_vs_baseline.py>) | `t5-runtime/case15_mode0_vs_baseline.py` | `d76ef197a5d87f3d0eb6924d5211c20ac020b8278889196eedf8739ee6a667d6` | 1,969 |
| [`t5/verify.py`](<t5/verify.py>) | `t5-runtime/verify.py` | `287db5ba148a5e2c4f63560b87d3a40ad464b5804ec6096243459037fda90ef3` | 9,869 |
| [`t5/protect.py`](<t5/protect.py>) | `t5-runtime/protect.py` | `d40c0cf81a0d9a7ca4bcf876ac6bd6eb45542345a6c60160019bf5e9bd572668` | 2,030 |
| [`t5/prep_fresh.py`](<t5/prep_fresh.py>) | `t5-runtime/prep_fresh.py` | `b1bf3a655d9bf0019ae3f687ff3e197c1a1785102d84fdb8c9989a6192246692` | 1,167 |
| [`t5/prep_legacy.py`](<t5/prep_legacy.py>) | `t5-runtime/prep_legacy.py` | `b18854353d5daed30c330d403e6a10ad9c12dd66ef86e17dcfd61cd725d44ab4` | 1,256 |
| [`t5/explore.py`](<t5/explore.py>) | `t5-runtime/explore.py` | `e746287d72309c7c4c1e8533274008bc471a00c15deb4c26dabf550b0ae7991c` | 502 |
| [`t5/expectations.json`](<t5/expectations.json>) | `t5-runtime/expectations.json` | `9394e6fac55062ab69b65f2dbe56d1cc79d29a457a19706980763b9e4c2a8ecc` | 1,415 |
| [`t5/summary.json`](<t5/summary.json>) | `t5-runtime/summary.json` | `72b4538552be71af14056d997c31bb6bbc752fe9b01f5a1e0fafe5950e4f9659` | 7,296 |
| [`t5/case12-result.json`](<t5/case12-result.json>) | `t5-runtime/case12-result.json` | `4aebe3676ee7121df0ace72cc6931a00f6983133e2e4a5ead30efb109dc48b40` | 712 |
| [`t5/case15-contracts.json`](<t5/case15-contracts.json>) | `t5-runtime/case15-contracts.json` | `4024326c5bb8fbc934714e0b018dcacea383bd9ed508dc08b97b015b067aab4f` | 18,711 |
| [`t5/case15-rowseq.json`](<t5/case15-rowseq.json>) | `t5-runtime/case15-rowseq.json` | `1378610c7431553e8c5e878e88d5753376878e726d9f7f1d95796c2545ee2225` | 1,367 |
| [`t5/processes.jsonl`](<t5/processes.jsonl>) | `t5-runtime/processes.jsonl` | `e225c00ef1ca7c6b7e304d90b150bdb9df9d7c972841676ad7e62bdda9225e51` | 28,972 |
| [`t5/REPORT.md`](<t5/REPORT.md>) | `t5-runtime/REPORT.md` | `e643304e8cc5fbc3507aa621b9be44c50900fb79131181eb1b3320dcb455b31a` | 19,342 |
| [`t5/harness/harness.diff`](<t5/harness/harness.diff>) | `t5-runtime/harness/harness.diff` | `a71c253aa7e3f838feceaed255b56147ae2f99f60090e34e3766e9ec177643ae` | 920 |
| [`t5/harness/build.json`](<t5/harness/build.json>) | `t5-runtime/harness/build.json` | `9e2cb7469bdfd54a40c196f0cee8872ab97a7aeec5d56da54c5a6657188089bd` | 3,353 |
| [`t5/harness/build.py`](<t5/harness/build.py>) | `t5-runtime/harness/build.py` | `799271ae6ac02c903dfa4433dc3b9525ab88102f93f33ad1b3d3d21d0fcda3d8` | 1,390 |
| [`t5/harness/mgba_harness_t5.c`](<t5/harness/mgba_harness_t5.c>) | `t5-runtime/harness/mgba_harness_t5.c` | `863786403f82a615761ea7506b3d34e06ffafad7842c183e7a9b6900417f1b65` | 15,013 |
| [`t5/harness/flags_make_defines.txt`](<t5/harness/flags_make_defines.txt>) | `t5-runtime/harness/flags_make_defines.txt` | `146c34dc1f2ff6cf3b57be702c153077971309fad3e12495b47bec6a71603101` | 459 |
| [`t5/routes/candidate-fresh-to-name.route`](<t5/routes/candidate-fresh-to-name.route>) | `t5-runtime/routes/candidate-fresh-to-name.route` | `2abb2cda374e564501923ca3320d8455f88025332c2120e7e5e38aa2f0977e6e` | 913 |
| [`t5/routes/legacy-cold-to-name.route`](<t5/routes/legacy-cold-to-name.route>) | `t5-runtime/routes/legacy-cold-to-name.route` | `7ea1ffa25887aea96c7b99389a155ce8d870cf277de4a73487c0ecd8081251fd` | 1,138 |
| [`t5/routes/legacy-cold-to-editor.route`](<t5/routes/legacy-cold-to-editor.route>) | `t5-runtime/routes/legacy-cold-to-editor.route` | `2a733cea349525e76f1aa35bfedd42874409f027836a8ab87b8612c022059213` | 902 |
| [`t5/routes/fresh3-keys.route`](<t5/routes/fresh3-keys.route>) | `t5-runtime/routes/fresh3-keys.route` | `cc742bf50318716db59ee03e8a66629f8a13f826e9ddbf7e8cc2770e29ae46a9` | 912 |
| [`t5/protected-before.json`](<t5/protected-before.json>) | `t5-runtime/protected-before.json` | `9b3afa34eb6937630cd517e4a66b07432432ec10343816626ed5935ef0e92c3d` | 61,799 |
| [`t5/protected-after.json`](<t5/protected-after.json>) | `t5-runtime/protected-after.json` | `9b3afa34eb6937630cd517e4a66b07432432ec10343816626ed5935ef0e92c3d` | 61,799 |
| [`t5/runs/case1-강철/result.json`](<t5/runs/case1-강철/result.json>) | `t5-runtime/runs/case1-강철/result.json` | `54581567cbe6b083d9ef5f03cd007dedfedd8aeaf82af2f449a80b2bef36bab5` | 464 |
| [`t5/runs/case1-강철/steps.jsonl`](<t5/runs/case1-강철/steps.jsonl>) | `t5-runtime/runs/case1-강철/steps.jsonl` | `e01219ef987c4d7b865a6c47d9f1b30d6b41da026056eaa1067af6528a29197c` | 2,813 |
| [`t5/runs/case1-강철/preview.png`](<t5/runs/case1-강철/preview.png>) | `t5-runtime/runs/case1-강철/preview.png` | `70098122612616542024147ac8b5e9fca104b5b33e9177d3db9a4503a390c116` | 14,607 |
| [`t5/runs/case1-강철/vram-ㄱ.bin`](<t5/runs/case1-강철/vram-ㄱ.bin>) | `t5-runtime/runs/case1-강철/vram-ㄱ.bin` | `67f5d9d60292a3ae249ae1250725609d5879c664a3ced4f67025ec325b85ef82` | 64 |
| [`t5/runs/case1-vowel/result.json`](<t5/runs/case1-vowel/result.json>) | `t5-runtime/runs/case1-vowel/result.json` | `4239589bd557968f3d8c93fc29a72e94bac14144002c77cdae85c2a47db2bac2` | 367 |
| [`t5/runs/case1-vowel/vram-ㅏ.bin`](<t5/runs/case1-vowel/vram-ㅏ.bin>) | `t5-runtime/runs/case1-vowel/vram-ㅏ.bin` | `ec517ac8ce2ad0f3d9e323bcb9b2487dc29cf216e0ff7c4910c16e639d04e9f1` | 64 |
| [`t5/runs/case1-vowel/preview-a.png`](<t5/runs/case1-vowel/preview-a.png>) | `t5-runtime/runs/case1-vowel/preview-a.png` | `51f510f32794da5b0a7b90bb5226e558e4d676b272d58ef6df7f26ffcac8a42e` | 14,323 |
| [`t5/runs/case2-wa-vonly/result.json`](<t5/runs/case2-wa-vonly/result.json>) | `t5-runtime/runs/case2-wa-vonly/result.json` | `4f128b775722478bbf20bea009a41aa3513b5465c3cddf91d0d541107b4d1f49` | 489 |
| [`t5/runs/case2-wa-vonly/vram-ㅘ.bin`](<t5/runs/case2-wa-vonly/vram-ㅘ.bin>) | `t5-runtime/runs/case2-wa-vonly/vram-ㅘ.bin` | `ba125cc1bcd0e7f1a4ba168273e0bf44dfff6928954d443f70836ae94c6aedac` | 64 |
| [`t5/runs/case2-wa-vonly/preview.png`](<t5/runs/case2-wa-vonly/preview.png>) | `t5-runtime/runs/case2-wa-vonly/preview.png` | `7e830ca5fe133b74407f1e872eed855a1d68fa76d398889792756a6287360cfc` | 14,387 |
| [`t5/runs/case11a-save/result.json`](<t5/runs/case11a-save/result.json>) | `t5-runtime/runs/case11a-save/result.json` | `83d207d70a4bf92da44322054144a4dc61d7a72ac0069d15bb39646e3ba96d75` | 944 |
| [`t5/runs/case11a-save/steps.jsonl`](<t5/runs/case11a-save/steps.jsonl>) | `t5-runtime/runs/case11a-save/steps.jsonl` | `ebbceabd90534191810f0e6af5e194e2d3f74d236d36c24f438cda71577b7e6a` | 11,208 |
| [`t5/runs/case11a-save/commands.jsonl`](<t5/runs/case11a-save/commands.jsonl>) | `t5-runtime/runs/case11a-save/commands.jsonl` | `3ba4ab950f23b64ea8cb7788b6f918602639fb72251cb41cc8c30fec15926bda` | 147,165 |
| [`t5/runs/case11a-save/full8.png`](<t5/runs/case11a-save/full8.png>) | `t5-runtime/runs/case11a-save/full8.png` | `ca2dc37806fe63582816ee777b8fec6bb924362af749acc12bf6c374acfc8a37` | 14,534 |
| [`t5/runs/case11a-save/sv-confirm.png`](<t5/runs/case11a-save/sv-confirm.png>) | `t5-runtime/runs/case11a-save/sv-confirm.png` | `f90a89c47b080a30039dad68fea474dfbc180e8c25b89318c32eb9476ef17e94` | 14,827 |
| [`t5/runs/case11a-save/sv-done.png`](<t5/runs/case11a-save/sv-done.png>) | `t5-runtime/runs/case11a-save/sv-done.png` | `09ef53479f5e14dd25eb4c0a75d9336c18e5a227a54067bfcbbc08e25648329b` | 17,447 |
| [`t5/runs/case11a-save/confirm-destination.bin`](<t5/runs/case11a-save/confirm-destination.bin>) | `t5-runtime/runs/case11a-save/confirm-destination.bin` | `2105f35c6da26adba0a6100ba1bfea99af8b90ccd289e1af29050b4e2d20ad86` | 16 |
| [`t5/runs/case11a-save/bp.log`](<t5/runs/case11a-save/bp.log>) | `t5-runtime/runs/case11a-save/bp.log` | `5220b6ee72fd35fd5febd38afa3b693faec133ffd8126269794c2d53728891ff` | 483,200 |
| [`t5/runs/case11a-save/launch.json`](<t5/runs/case11a-save/launch.json>) | `t5-runtime/runs/case11a-save/launch.json` | `b1acbacbfa7068553a34965d311dda6e1c472860aa5f5ca3909711727a6a16b0` | 1,129 |
| [`t5/runs/case11a-save/exit.json`](<t5/runs/case11a-save/exit.json>) | `t5-runtime/runs/case11a-save/exit.json` | `f2e23d1da4c8b090df27585ce7fa5b9a92ec8d0a6b8942a62d692a67f6257d23` | 27 |
| [`t5/runs/case11a-cold/result.json`](<t5/runs/case11a-cold/result.json>) | `t5-runtime/runs/case11a-cold/result.json` | `57045d2a0e2e8e988d721f6de3471ad5712adb80e236aa87b8d6895ad1f2ad6d` | 707 |
| [`t5/runs/case11a-cold/commands.jsonl`](<t5/runs/case11a-cold/commands.jsonl>) | `t5-runtime/runs/case11a-cold/commands.jsonl` | `bc9d4a4f8b771e055ce689d32c1ee9ade7de7499e82ff37ba1e193d00629249d` | 15,619 |
| [`t5/runs/case11a-cold/cold-list.png`](<t5/runs/case11a-cold/cold-list.png>) | `t5-runtime/runs/case11a-cold/cold-list.png` | `230b39da82fb426cca819ed6591312e752ccf3d38b163742e19857f8c115d06c` | 16,615 |
| [`t5/runs/case11a-cold/reentry.png`](<t5/runs/case11a-cold/reentry.png>) | `t5-runtime/runs/case11a-cold/reentry.png` | `942d8b57a8f7324b571729d611222fc72f4283c6c9c711318053f9df57fbabac` | 14,448 |
| [`t5/runs/case11a-cold/reentry-obj.bin`](<t5/runs/case11a-cold/reentry-obj.bin>) | `t5-runtime/runs/case11a-cold/reentry-obj.bin` | `e20a7aef51ff336490e4616a98c78ddbf2b954147fcfe408dc5bf1fbfa3fb8f3` | 128 |
| [`t5/runs/case11a-cold/list-name-0200B204.bin`](<t5/runs/case11a-cold/list-name-0200B204.bin>) | `t5-runtime/runs/case11a-cold/list-name-0200B204.bin` | `2105f35c6da26adba0a6100ba1bfea99af8b90ccd289e1af29050b4e2d20ad86` | 16 |
| [`t5/runs/case11a-cold/launch.json`](<t5/runs/case11a-cold/launch.json>) | `t5-runtime/runs/case11a-cold/launch.json` | `1c1c7fea1ce2392b4dbd3b42b9e06f68ee824dd501737dabd6d44998e12f05ee` | 1,397 |
| [`t5/runs/case11a-cold/exit.json`](<t5/runs/case11a-cold/exit.json>) | `t5-runtime/runs/case11a-cold/exit.json` | `3b5aa170b90b40ea272ac1d6fe2c6919ccb8dd762bc8a161c8aa68644c7c6d45` | 27 |
| [`t5/runs/case11b-save/result.json`](<t5/runs/case11b-save/result.json>) | `t5-runtime/runs/case11b-save/result.json` | `59d82d4aa83fe13f854d49d5ea2218dad51cd18d1d58485d2e917e72c421282d` | 1,080 |
| [`t5/runs/case11b-save/commands.jsonl`](<t5/runs/case11b-save/commands.jsonl>) | `t5-runtime/runs/case11b-save/commands.jsonl` | `fbe5014f7898a74a239a27df286e0deb381a26d53069e2b1d24f5c43b40d1434` | 158,296 |
| [`t5/runs/case11b-save/sv-confirm.png`](<t5/runs/case11b-save/sv-confirm.png>) | `t5-runtime/runs/case11b-save/sv-confirm.png` | `9fd593b6b2d2d6ae5a7fa53131a133453c0c4a4372af20e05f6f0f42428850f7` | 13,709 |
| [`t5/runs/case11b-save/sv-yes-selected.png`](<t5/runs/case11b-save/sv-yes-selected.png>) | `t5-runtime/runs/case11b-save/sv-yes-selected.png` | `24139cb8a4ad8a6bcfedbaeb42943299399a44548abfe48668d12b73e7a515d0` | 13,711 |
| [`t5/runs/case11b-save/confirm-destination.bin`](<t5/runs/case11b-save/confirm-destination.bin>) | `t5-runtime/runs/case11b-save/confirm-destination.bin` | `2105f35c6da26adba0a6100ba1bfea99af8b90ccd289e1af29050b4e2d20ad86` | 16 |
| [`t5/runs/case11b-save/launch.json`](<t5/runs/case11b-save/launch.json>) | `t5-runtime/runs/case11b-save/launch.json` | `4235502e4c22f06498c3fe589dbb3b8419080523ada33d1472bc60a9c6b72621` | 1,394 |
| [`t5/runs/case11b-save/exit.json`](<t5/runs/case11b-save/exit.json>) | `t5-runtime/runs/case11b-save/exit.json` | `64363c8e94f2a6a21e620883851f5c5a8f1a3099d925636975a02b76ed7d2b87` | 27 |
| [`t5/runs/case11b-cold/result.json`](<t5/runs/case11b-cold/result.json>) | `t5-runtime/runs/case11b-cold/result.json` | `f1659cf3a9d64084564b681ab28ec1a72415ab5f40a640a584dcb10cf1576e2e` | 707 |
| [`t5/runs/case11b-cold/commands.jsonl`](<t5/runs/case11b-cold/commands.jsonl>) | `t5-runtime/runs/case11b-cold/commands.jsonl` | `947377f29d9dbba6df31b1d484dff157f656abde14f58a301b717de084b5eb18` | 15,617 |
| [`t5/runs/case11b-cold/cold-list.png`](<t5/runs/case11b-cold/cold-list.png>) | `t5-runtime/runs/case11b-cold/cold-list.png` | `021cccccf1c406703a8de2a518aa9c3262c579b3782a966b770e19efd54fa287` | 16,633 |
| [`t5/runs/case11b-cold/reentry.png`](<t5/runs/case11b-cold/reentry.png>) | `t5-runtime/runs/case11b-cold/reentry.png` | `942d8b57a8f7324b571729d611222fc72f4283c6c9c711318053f9df57fbabac` | 14,448 |
| [`t5/runs/case11b-cold/reentry-obj.bin`](<t5/runs/case11b-cold/reentry-obj.bin>) | `t5-runtime/runs/case11b-cold/reentry-obj.bin` | `e20a7aef51ff336490e4616a98c78ddbf2b954147fcfe408dc5bf1fbfa3fb8f3` | 128 |
| [`t5/runs/case11b-cold/launch.json`](<t5/runs/case11b-cold/launch.json>) | `t5-runtime/runs/case11b-cold/launch.json` | `2c9138b2e63f2190fcd7ec9be7fc0a33eae4e2d11d23009834027560a327a988` | 1,397 |
| [`t5/runs/case11b-cold/exit.json`](<t5/runs/case11b-cold/exit.json>) | `t5-runtime/runs/case11b-cold/exit.json` | `3b5aa170b90b40ea272ac1d6fe2c6919ccb8dd762bc8a161c8aa68644c7c6d45` | 27 |
| [`t5/runs/case12-build/valid-map.png`](<t5/runs/case12-build/valid-map.png>) | `t5-runtime/runs/case12-build/valid-map.png` | `29ccdc19df31ddf080e1589f982df880e6f3a311e627bc398b4607b73d7f3e9d` | 19,030 |
| [`t5/runs/case12-build/commands.jsonl`](<t5/runs/case12-build/commands.jsonl>) | `t5-runtime/runs/case12-build/commands.jsonl` | `342a95e13314a78a00df4a2d362e95ddc3838fcf67017da168b543761a497868` | 24,322 |
| [`t5/runs/case12-build/launch.json`](<t5/runs/case12-build/launch.json>) | `t5-runtime/runs/case12-build/launch.json` | `a640a3b80718f02cbee6918eb4d5ad88a2789ea611137717b31a2b66fb10665d` | 1,397 |
| [`t5/runs/case12-cold-versus/category5.png`](<t5/runs/case12-cold-versus/category5.png>) | `t5-runtime/runs/case12-cold-versus/category5.png` | `42f983fdcdfb74619aff03999e8661e41a6ae5bc9ed33d10e35c808417e781e8` | 13,947 |
| [`t5/runs/case12-cold-versus/selected.png`](<t5/runs/case12-cold-versus/selected.png>) | `t5-runtime/runs/case12-cold-versus/selected.png` | `02f5bda8d6b2d7e41281a4a932e34fcc08182c6872a0f19f359b582c1c4b5746` | 16,179 |
| [`t5/runs/case12-cold-versus/commands.jsonl`](<t5/runs/case12-cold-versus/commands.jsonl>) | `t5-runtime/runs/case12-cold-versus/commands.jsonl` | `5eb11a605d0d2160cd3006cf71e4663eaa3f13791d8c401ac61ffd15df4fef7c` | 15,873 |
| [`t5/runs/case12-cold-versus/launch.json`](<t5/runs/case12-cold-versus/launch.json>) | `t5-runtime/runs/case12-cold-versus/launch.json` | `0af9d1b8a15b1f5f34df47901d112f15874ae7d28a2dc7d868a909a7c857b7ad` | 1,438 |
| [`t5/runs/case13/result.json`](<t5/runs/case13/result.json>) | `t5-runtime/runs/case13/result.json` | `558957b4c175e31bd4806109418cac6517e43485583b831848c93d361385f622` | 2,084 |
| [`t5/runs/case13/steps.jsonl`](<t5/runs/case13/steps.jsonl>) | `t5-runtime/runs/case13/steps.jsonl` | `1c728b471f6c5dc39dc22d569d6624497424dd590776490404768ecb29545dc8` | 3,438 |
| [`t5/runs/case13b-candidate-legacy-kana/result.json`](<t5/runs/case13b-candidate-legacy-kana/result.json>) | `t5-runtime/runs/case13b-candidate-legacy-kana/result.json` | `7a6125d0f615499ac6439e1039412039449b1a3360dd6251c7819cc6976847f7` | 1,730 |
| [`t5/runs/case13b-candidate-legacy-kana/cand-dakuten.png`](<t5/runs/case13b-candidate-legacy-kana/cand-dakuten.png>) | `t5-runtime/runs/case13b-candidate-legacy-kana/cand-dakuten.png` | `b4c931e0eb6e053b129e4b77cdcdf609b1d81558b0bd19e640040134e7b6194b` | 14,644 |
| [`t5/runs/case14-original/result.json`](<t5/runs/case14-original/result.json>) | `t5-runtime/runs/case14-original/result.json` | `7a7cc5474072b6b5a752c0715686e4baca7f695b3ae11f2c0d2b60cbae783c40` | 1,424 |
| [`t5/runs/case14-original/one-a.png`](<t5/runs/case14-original/one-a.png>) | `t5-runtime/runs/case14-original/one-a.png` | `b50299a0df22dd5254ecb0a490537ab2b1e8a3b2f778d12d4148cf04b95131f9` | 22,742 |
| [`t5/runs/case14-original/orig-dakuten.png`](<t5/runs/case14-original/orig-dakuten.png>) | `t5-runtime/runs/case14-original/orig-dakuten.png` | `7d15c7a1193f5d8cc5d615780c64391d6c95a18de8aae2a8b6a5fb16ae700330` | 22,224 |
| [`t5/runs/case14-original/launch.json`](<t5/runs/case14-original/launch.json>) | `t5-runtime/runs/case14-original/launch.json` | `605b922b9d789bd03bbf6fc72a319b61204744f45f3d282a7c647b2843934123` | 1,140 |
| [`t5/runs/case15-mode1/bp.log`](<t5/runs/case15-mode1/bp.log>) | `t5-runtime/runs/case15-mode1/bp.log` | `f42923dc66337c16289b0e74be5e1f6508b598f36ec39406b08b016dac004cad` | 677,206 |
| [`t5/runs/case15-mode1/notes.json`](<t5/runs/case15-mode1/notes.json>) | `t5-runtime/runs/case15-mode1/notes.json` | `cf98714d8f80284170ea4038dd7f4cf52c42215531d49767cdc7efee706b9413` | 285 |
| [`t5/runs/case15-mode0-SYNTHETIC/bp.log`](<t5/runs/case15-mode0-SYNTHETIC/bp.log>) | `t5-runtime/runs/case15-mode0-SYNTHETIC/bp.log` | `7c43638da533842eaa9db8123b91afde27922c127daeb24d688b93c57dcf62cf` | 704,315 |
| [`t5/runs/case15-mode0-SYNTHETIC/notes.json`](<t5/runs/case15-mode0-SYNTHETIC/notes.json>) | `t5-runtime/runs/case15-mode0-SYNTHETIC/notes.json` | `2c055245766f5e355f9c8bbc12d64f2367e17075aec652125b7bfa4ca30fd420` | 325 |
| [`t5/runs/case15-mode0-SYNTHETIC/after-a.png`](<t5/runs/case15-mode0-SYNTHETIC/after-a.png>) | `t5-runtime/runs/case15-mode0-SYNTHETIC/after-a.png` | `c181d095476ad2e71b46a58678a8d1ee89aac9164f457bbc262d49681a061a03` | 16,160 |
| [`t5/runs/case15-baseline-native/result.json`](<t5/runs/case15-baseline-native/result.json>) | `t5-runtime/runs/case15-baseline-native/result.json` | `4c4cd7e7c3ecad6fba0a479021037ce23049921ef74965f8ab003c5943465fdb` | 457 |
| [`t5/runs/case15-baseline-native/after-a.png`](<t5/runs/case15-baseline-native/after-a.png>) | `t5-runtime/runs/case15-baseline-native/after-a.png` | `35505d5e98114ddadd768eb07c67a943e775c459c5e85f09a56f3ce5a0cd0981` | 16,045 |
| [`t5/runs/case15-pending/bp.log`](<t5/runs/case15-pending/bp.log>) | `t5-runtime/runs/case15-pending/bp.log` | `1288228a58dc98c1a001bd2c9e8879c28dbdb6f6493aecb18edcaebba808abcf` | 49,597 |
| [`t5/runs/prep-fresh/name-entry.png`](<t5/runs/prep-fresh/name-entry.png>) | `t5-runtime/runs/prep-fresh/name-entry.png` | `17d57bc0a65f2bbd91dd0c3e85c6d25539a068b3f7a03bdde9c16d8c5377158a` | 14,791 |
| [`t5/runs/prep-fresh/bp.log`](<t5/runs/prep-fresh/bp.log>) | `t5-runtime/runs/prep-fresh/bp.log` | `6d762ab1045f8b645001aab68dd0963a8e72a8ab23814fe04f1b82d0caa7e9d5` | 113,479 |
| [`t5/runs/prep-fresh/commands.jsonl`](<t5/runs/prep-fresh/commands.jsonl>) | `t5-runtime/runs/prep-fresh/commands.jsonl` | `4a334a8e449df3f401b48ef4bb48063ed61bd516a9b0742df00d7eaa6a71417d` | 14,669 |
| [`t5/runs/prep-legacy/reentry.png`](<t5/runs/prep-legacy/reentry.png>) | `t5-runtime/runs/prep-legacy/reentry.png` | `439dda470c95854b81a090acf500eed955ec9fe5d3d517b4d22a3bac2794151b` | 14,243 |
| [`t5/runs/prep-legacy/commands.jsonl`](<t5/runs/prep-legacy/commands.jsonl>) | `t5-runtime/runs/prep-legacy/commands.jsonl` | `da43348ab3625cf7595fd96d65571d3c7618e07b4fa8067d12294a2785fcf754` | 16,429 |
| [`t5/evidence-manifest.json`](<t5/evidence-manifest.json>) | `t5-runtime/evidence-manifest.json` | `c00a97ef229c201c63a909dde484a004575d5aadd5765170467f32c747323668` | 18,571 |
| [`t5/manager-cleanup/p1-return-witness.json`](<t5/manager-cleanup/p1-return-witness.json>) | `manager-cleanup/p1-return-witness.json` | `63a4c2a2718d03e7c4a7bc40f8b5db921e103a1f876cd8e5d001eb904ca6fb5e` | 861 |
| [`t5/manager-cleanup/cleanup.json`](<t5/manager-cleanup/cleanup.json>) | `manager-cleanup/cleanup.json` | `24a66a28cff952428ee984b676b0baf6343717895caea909a8089eb636c1ba59` | 333 |
| [`t5/runs/case1-vowel/steps.jsonl`](<t5/runs/case1-vowel/steps.jsonl>) | `t5-runtime/runs/case1-vowel/steps.jsonl` | `8e998175236b46e76eb894d8ad2a2c51acbbaad22df6f5a2f7759de0c29ce74c` | 455 |
| [`t5/runs/case1-붉은달/result.json`](<t5/runs/case1-붉은달/result.json>) | `t5-runtime/runs/case1-붉은달/result.json` | `b2a4708b24db493a95a1b82082752c7b233088034786889f0693b25cf84d37fa` | 219 |
| [`t5/runs/case1-붉은달/steps.jsonl`](<t5/runs/case1-붉은달/steps.jsonl>) | `t5-runtime/runs/case1-붉은달/steps.jsonl` | `dc8b29415e40f1fc7b022d77d4745b4e5e3344c31b341187759d7370f78e27ba` | 5,105 |
| [`t5/runs/case1-한글/result.json`](<t5/runs/case1-한글/result.json>) | `t5-runtime/runs/case1-한글/result.json` | `956d3de86b3b743e99a434c2871188e852f346a7ba00282590234cc27633bd25` | 213 |
| [`t5/runs/case1-한글/steps.jsonl`](<t5/runs/case1-한글/steps.jsonl>) | `t5-runtime/runs/case1-한글/steps.jsonl` | `c8278245ee99104b0222c0200292ee12bebaa265caa8b579d065d926c8d5974e` | 3,009 |
| [`t5/runs/case10/result.json`](<t5/runs/case10/result.json>) | `t5-runtime/runs/case10/result.json` | `18a3da5fda305596c467129c21be226011462e686f83b68cbaa00f18e9f95c65` | 456 |
| [`t5/runs/case10/steps.jsonl`](<t5/runs/case10/steps.jsonl>) | `t5-runtime/runs/case10/steps.jsonl` | `26e238c541e5ed18063a274b366e4b01c6fcd22440a5982f3288c5e9a9903929` | 2,958 |
| [`t5/runs/case11a-cold/steps.jsonl`](<t5/runs/case11a-cold/steps.jsonl>) | `t5-runtime/runs/case11a-cold/steps.jsonl` | `e3f50efc22dc62b1445e4b8376c4f8094cc09f6dfe26e77b290754bca39123d5` | 438 |
| [`t5/runs/case11b-cold/steps.jsonl`](<t5/runs/case11b-cold/steps.jsonl>) | `t5-runtime/runs/case11b-cold/steps.jsonl` | `9263d3164a7386b8df2a84581445841023d878eccacb4f0fc70fd857ec86cc34` | 438 |
| [`t5/runs/case11b-save/steps.jsonl`](<t5/runs/case11b-save/steps.jsonl>) | `t5-runtime/runs/case11b-save/steps.jsonl` | `1334fdf754140de39df1caa7e9ea737514a76c6d2729b096fa394a77ddc7404e` | 14,571 |
| [`t5/runs/case2-wa-vonly/steps.jsonl`](<t5/runs/case2-wa-vonly/steps.jsonl>) | `t5-runtime/runs/case2-wa-vonly/steps.jsonl` | `df19cbc2092b37818edc7b553ad9860f1cc2fd186714269a49728bbb2bdc14e3` | 1,028 |
| [`t5/runs/case2-가한/result.json`](<t5/runs/case2-가한/result.json>) | `t5-runtime/runs/case2-가한/result.json` | `fd5248de9df1afcb610598e1a181ce9f5711bc26498b8db4c9ae0cfeee425183` | 339 |
| [`t5/runs/case2-가한/steps.jsonl`](<t5/runs/case2-가한/steps.jsonl>) | `t5-runtime/runs/case2-가한/steps.jsonl` | `2e78462a88b13cf6e7dc77caf2f0df1264aec99f8ab19cfe32bb212f611408ab` | 2,448 |
| [`t5/runs/case2-달가/result.json`](<t5/runs/case2-달가/result.json>) | `t5-runtime/runs/case2-달가/result.json` | `c4c5f6c2aa8e4b90a4b960095133d989125682d4cfb8e7acd85e9539d4e65060` | 339 |
| [`t5/runs/case2-달가/steps.jsonl`](<t5/runs/case2-달가/steps.jsonl>) | `t5-runtime/runs/case2-달가/steps.jsonl` | `292fcb3359a805f867c42ac5d743ce09f7b01d945626c011594526346d938d2b` | 2,405 |
| [`t5/runs/case2-와/result.json`](<t5/runs/case2-와/result.json>) | `t5-runtime/runs/case2-와/result.json` | `57e814bcef4e7e476fdfdee3a6fe89d4e2e10bfa4844ac95f8c5ec895bd2e23e` | 228 |
| [`t5/runs/case2-와/steps.jsonl`](<t5/runs/case2-와/steps.jsonl>) | `t5-runtime/runs/case2-와/steps.jsonl` | `8309ad5b6a646e4a767a6ab07036691b3c9ce3f17b1109607d72876c0e8d7f1a` | 1,455 |
| [`t5/runs/case2-한가/result.json`](<t5/runs/case2-한가/result.json>) | `t5-runtime/runs/case2-한가/result.json` | `39561b182f97e3b962bda81cb9d13683b0ccb91de5a7141eb91d9bb8e2120339` | 238 |
| [`t5/runs/case2-한가/steps.jsonl`](<t5/runs/case2-한가/steps.jsonl>) | `t5-runtime/runs/case2-한가/steps.jsonl` | `4f7c9504193de9cac58da360dac34c6ad20124a0b35053df8f1448e2030b40e9` | 2,466 |
| [`t5/runs/case3/result.json`](<t5/runs/case3/result.json>) | `t5-runtime/runs/case3/result.json` | `445e8cfba079658dc6bfdffbc959724fc336bcde998d768700fe49aa59daf6ba` | 589 |
| [`t5/runs/case3/steps.jsonl`](<t5/runs/case3/steps.jsonl>) | `t5-runtime/runs/case3/steps.jsonl` | `8436c4286b0844fead4cce541cf1708cb9e42e8e9c3a3f3a9e4b822534deaf73` | 1,262 |
| [`t5/runs/case4-가+ㅋ/result.json`](<t5/runs/case4-가+ㅋ/result.json>) | `t5-runtime/runs/case4-가+ㅋ/result.json` | `f1df70a9ddcc6dcccba71e5fd9efe675a1e535714639e904b567ba7a7a465405` | 284 |
| [`t5/runs/case4-가+ㅋ/steps.jsonl`](<t5/runs/case4-가+ㅋ/steps.jsonl>) | `t5-runtime/runs/case4-가+ㅋ/steps.jsonl` | `f634c3242c180e2d686bb05fad65367b811840e8386b6fe91e26e76f46553302` | 1,371 |
| [`t5/runs/case4-간+ㅒ/result.json`](<t5/runs/case4-간+ㅒ/result.json>) | `t5-runtime/runs/case4-간+ㅒ/result.json` | `f97331a60308569df4aa9471d3157c07e675a3b69e12830c7250868d72664032` | 284 |
| [`t5/runs/case4-간+ㅒ/steps.jsonl`](<t5/runs/case4-간+ㅒ/steps.jsonl>) | `t5-runtime/runs/case4-간+ㅒ/steps.jsonl` | `8b351972edb1dbafde5a72076f058039559f6891f77c71285fa3d1a1cb19b5c0` | 1,820 |
| [`t5/runs/case4-개+ㄷ/result.json`](<t5/runs/case4-개+ㄷ/result.json>) | `t5-runtime/runs/case4-개+ㄷ/result.json` | `d6369598b128d2f2474a19228e47b8056dbd78b55fc79603a58bf560525fe4bc` | 284 |
| [`t5/runs/case4-개+ㄷ/steps.jsonl`](<t5/runs/case4-개+ㄷ/steps.jsonl>) | `t5-runtime/runs/case4-개+ㄷ/steps.jsonl` | `d52dd873129c19a7226eeb8a949028d2610c01799c5fb6a87a491cdf8c283553` | 1,363 |
| [`t5/runs/case5-literals/result.json`](<t5/runs/case5-literals/result.json>) | `t5-runtime/runs/case5-literals/result.json` | `f1e12022667ea25efbbded6032b268f1debd34154676f3e8f58dcacd2a2ca37a` | 366 |
| [`t5/runs/case5-literals/steps.jsonl`](<t5/runs/case5-literals/steps.jsonl>) | `t5-runtime/runs/case5-literals/steps.jsonl` | `d76b689670b5c4fd017c2ad39136e4aef35478a9265d852795f19fe76c3fb48a` | 3,472 |
| [`t5/runs/case5-mid-space/result.json`](<t5/runs/case5-mid-space/result.json>) | `t5-runtime/runs/case5-mid-space/result.json` | `2f5f8fb0c7952d5390297c662777cb022082f49551b195208c00634a6ae162ba` | 295 |
| [`t5/runs/case5-mid-space/steps.jsonl`](<t5/runs/case5-mid-space/steps.jsonl>) | `t5-runtime/runs/case5-mid-space/steps.jsonl` | `94b734c18a1f0d3716dd456d5f6c2690d9d19db04eed80744c30e57447653500` | 3,274 |
| [`t5/runs/case5-trail-space/result.json`](<t5/runs/case5-trail-space/result.json>) | `t5-runtime/runs/case5-trail-space/result.json` | `b1597ec3db05577671d0512c10c093aee78dbcc982e8bdbe4f50e60ae3626426` | 291 |
| [`t5/runs/case5-trail-space/steps.jsonl`](<t5/runs/case5-trail-space/steps.jsonl>) | `t5-runtime/runs/case5-trail-space/steps.jsonl` | `f706fc5704d03075095f4670be3ab386e05608f188581fd004dfd0e55c77baa2` | 2,233 |
| [`t5/runs/case7-committed/result.json`](<t5/runs/case7-committed/result.json>) | `t5-runtime/runs/case7-committed/result.json` | `560a1eadac8def5b9567fa6df751382942e603fe92f8fb10fdc7830a3eb2c10a` | 192 |
| [`t5/runs/case7-committed/steps.jsonl`](<t5/runs/case7-committed/steps.jsonl>) | `t5-runtime/runs/case7-committed/steps.jsonl` | `a649a5d85ebf261f6d3b624c545694b8621ebacadda453456a54c0f408c1abc6` | 3,171 |
| [`t5/runs/case7-gang/result.json`](<t5/runs/case7-gang/result.json>) | `t5-runtime/runs/case7-gang/result.json` | `346eee17f24f8b9eaa48f4ffb96256d893ff31cd1fdfe7b1aac62e3ef52eeb1f` | 167 |
| [`t5/runs/case7-gang/steps.jsonl`](<t5/runs/case7-gang/steps.jsonl>) | `t5-runtime/runs/case7-gang/steps.jsonl` | `94701c8e6577385bd7b58c2b0e4f014be2f314cc8999c808b151d766ceccdd2d` | 2,592 |
| [`t5/runs/case8/result.json`](<t5/runs/case8/result.json>) | `t5-runtime/runs/case8/result.json` | `88f35e4bdeefb4946ae81fb799b452090bb75eab325113110d59071939771136` | 801 |
| [`t5/runs/case8/steps.jsonl`](<t5/runs/case8/steps.jsonl>) | `t5-runtime/runs/case8/steps.jsonl` | `cae8e2c34dfaa8c0c2cc09134d3874c9bd4841540406c6a88070e3e6e4dcff2b` | 1,730 |
| [`t5/runs/case9/result.json`](<t5/runs/case9/result.json>) | `t5-runtime/runs/case9/result.json` | `584a122fbc6e7100ef46614013d98056e77366523bdf9ab93da28db2c4417014` | 225 |
| [`t5/runs/case9/steps.jsonl`](<t5/runs/case9/steps.jsonl>) | `t5-runtime/runs/case9/steps.jsonl` | `53bf6494f113cb98e347a47bc36aad537db61809d20186ce1e9dac9c6acd45f4` | 1,187 |
| [`t5/logs/case1-2.log`](<t5/logs/case1-2.log>) | `t5-runtime/logs/case1-2.log` | `fd0a5cf50253e0688a66686599814464e145be5f31d8faafd65d85f353e0d359` | 1,794 |
| [`t5/logs/case11a.log`](<t5/logs/case11a.log>) | `t5-runtime/logs/case11a.log` | `664cecca41e434f1e1952a6222f51684663c2246076830a9e9044936156b1d55` | 1,117 |
| [`t5/logs/case11b.log`](<t5/logs/case11b.log>) | `t5-runtime/logs/case11b.log` | `faa4090ebc4bb213b89eabfc950f88adb0ad8022608d35b5821bd6a5d1af28d4` | 1,117 |
| [`t5/logs/case12-cold2.log`](<t5/logs/case12-cold2.log>) | `t5-runtime/logs/case12-cold2.log` | `c60050e913212ef41ce94ec0710d21651ad8bfbe5185f5d44852e1386fbbdafa` | 634 |
| [`t5/logs/case12.log`](<t5/logs/case12.log>) | `t5-runtime/logs/case12.log` | `c60050e913212ef41ce94ec0710d21651ad8bfbe5185f5d44852e1386fbbdafa` | 634 |
| [`t5/logs/case14.log`](<t5/logs/case14.log>) | `t5-runtime/logs/case14.log` | `e4218c437bf3050a52d27074f84024be5520d6129d4e7ea76dfaf0e46a71c887` | 1,825 |
| [`t5/logs/case15-analyze.log`](<t5/logs/case15-analyze.log>) | `t5-runtime/logs/case15-analyze.log` | `39b8dcf402af3dc2ad0809f18110c47ea7ddd7843a308a1637b842cd20d1c81c` | 227 |
| [`t5/logs/case15-baseline.log`](<t5/logs/case15-baseline.log>) | `t5-runtime/logs/case15-baseline.log` | `653b61f010d21140af524049711bdb4d34c0de3fa89add5064be582335e03fbe` | 401 |
| [`t5/logs/case15-modes.log`](<t5/logs/case15-modes.log>) | `t5-runtime/logs/case15-modes.log` | `752cbeac9109d085b785f3981abade5579357a43b13736951216fd954ca44d11` | 525 |
| [`t5/logs/case15-pending.log`](<t5/logs/case15-pending.log>) | `t5-runtime/logs/case15-pending.log` | `70c45f65f013a54ff68fe7ff1cd8ca94ff1eb1b16a7e696d94f4fefb66f3b2e3` | 39 |
| [`t5/logs/case3-13.log`](<t5/logs/case3-13.log>) | `t5-runtime/logs/case3-13.log` | `89fc77498bf00c559ca162775f979e0f574f845ca056e01086cb44b4b4a2b705` | 3,454 |
| [`t5/logs/case5-13-r2.log`](<t5/logs/case5-13-r2.log>) | `t5-runtime/logs/case5-13-r2.log` | `d02990380ffc3dd1b67fd3a2f6cfa374dccf4212cbf0c27013d23fa34d768f09` | 1,904 |
| [`t5/deps/native-re/replay-cold/route.txt`](<t5/deps/native-re/replay-cold/route.txt>) | `native-re/replay-cold/route.txt` | `813f70763f9400636ca7bd7a1e6991160d156646428333c323124739fd60028e` | 1,198 |
| [`t5/deps/list-link-re/candidate-map.route`](<t5/deps/list-link-re/candidate-map.route>) | `list-link-re/candidate-map.route` | `512965635f5e6f7a03da9a92d0a94f53719602d4bf475848e8cd87372bea9a63` | 2,636 |
| [`t5/deps/list-link-re/candidate-cold-fixed.route`](<t5/deps/list-link-re/candidate-cold-fixed.route>) | `list-link-re/candidate-cold-fixed.route` | `a53ad4cfa6f3de0ff1ffe21700cb8ea58cd19b7db80e55802b97025801d7feec` | 1,155 |
| [`t5/runs/case13/bp.log`](<t5/runs/case13/bp.log>) | `t5-runtime/runs/case13/bp.log` | `cad5928e5ec11e6e09c49b5bfaf534bb057cb554386bac63f766251842ab0835` | 91,366 |
| [`t5/runs/case13/commands.jsonl`](<t5/runs/case13/commands.jsonl>) | `t5-runtime/runs/case13/commands.jsonl` | `6b4979a6b4d45a6d4b3b4b67e4952663f4c44be47f991de7fedb765b1dc7dbc4` | 30,766 |
| [`t5/runs/case13/launch.json`](<t5/runs/case13/launch.json>) | `t5-runtime/runs/case13/launch.json` | `c2518a8013b904d91758b8329102e60d636d2467fdd286af25501084057ac851` | 1,099 |
| [`t5/runs/case13/exit.json`](<t5/runs/case13/exit.json>) | `t5-runtime/runs/case13/exit.json` | `dcde08aeed676fb501187f690337064772394e56fc2790c2558c77c13925d66b` | 26 |
| [`t5/logs/case13-t7fix1.exit.txt`](<t5/logs/case13-t7fix1.exit.txt>) | `t5-runtime/logs/case13-t7fix1.exit.txt` | `7e1cd69fab85528649b3c67810caed1f9db026f90623c7d226ea1477c93b6a46` | 5 |
| [`t5/logs/case13-t7fix1.stderr.log`](<t5/logs/case13-t7fix1.stderr.log>) | `t5-runtime/logs/case13-t7fix1.stderr.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 |
| [`t5/logs/case13-t7fix1.stdout.log`](<t5/logs/case13-t7fix1.stdout.log>) | `t5-runtime/logs/case13-t7fix1.stdout.log` | `64dc512e1cb37ae9d8d35e9dbc31ef1cc26cabef0aba465b85ded92b1c4d2121` | 626 |
| [`t5/logs/case15-analyze-t7fix1.exit.txt`](<t5/logs/case15-analyze-t7fix1.exit.txt>) | `t5-runtime/logs/case15-analyze-t7fix1.exit.txt` | `7e1cd69fab85528649b3c67810caed1f9db026f90623c7d226ea1477c93b6a46` | 5 |
| [`t5/logs/case15-analyze-t7fix1.stderr.log`](<t5/logs/case15-analyze-t7fix1.stderr.log>) | `t5-runtime/logs/case15-analyze-t7fix1.stderr.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 |
| [`t5/logs/case15-analyze-t7fix1.stdout.log`](<t5/logs/case15-analyze-t7fix1.stdout.log>) | `t5-runtime/logs/case15-analyze-t7fix1.stdout.log` | `ab360d262f4a3d5d09c761f2e256f2217242ea24c6d83fa1f822fcff78aa4f58` | 227 |
| [`t5/logs/verify-t7fix1-r2.exit.txt`](<t5/logs/verify-t7fix1-r2.exit.txt>) | `t5-runtime/logs/verify-t7fix1-r2.exit.txt` | `7e1cd69fab85528649b3c67810caed1f9db026f90623c7d226ea1477c93b6a46` | 5 |
| [`t5/logs/verify-t7fix1-r2.stderr.log`](<t5/logs/verify-t7fix1-r2.stderr.log>) | `t5-runtime/logs/verify-t7fix1-r2.stderr.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 |
| [`t5/logs/verify-t7fix1-r2.stdout.log`](<t5/logs/verify-t7fix1-r2.stdout.log>) | `t5-runtime/logs/verify-t7fix1-r2.stdout.log` | `26785bf05cca8d665ba32561c18d8b70062d0907391093f17201eec4f1fc7bac` | 1,299 |
| [`t5/logs/verify-t7fix1.exit.txt`](<t5/logs/verify-t7fix1.exit.txt>) | `t5-runtime/logs/verify-t7fix1.exit.txt` | `7e1cd69fab85528649b3c67810caed1f9db026f90623c7d226ea1477c93b6a46` | 5 |
| [`t5/logs/verify-t7fix1.stderr.log`](<t5/logs/verify-t7fix1.stderr.log>) | `t5-runtime/logs/verify-t7fix1.stderr.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 |
| [`t5/logs/verify-t7fix1.stdout.log`](<t5/logs/verify-t7fix1.stdout.log>) | `t5-runtime/logs/verify-t7fix1.stdout.log` | `26785bf05cca8d665ba32561c18d8b70062d0907391093f17201eec4f1fc7bac` | 1,299 |

## t5-superseded — T5 정정 전 원문(케이스 13 미완성 자모 coverage 근거로 **무효**)

- 생성 명령: T5 원 실행·T6 집계 재실행 — [`t5/superseded-case13/README.md`](<t5/superseded-case13/README.md>)
- 대상: 후보 `1ac790a9…e1eb`
- 파일 9개, 88,037 B

| 경로 | 출처(`temp/name-grid-phaseB/` 기준) | sha256 | bytes |
|---|---|---|---:|
| [`t5/superseded-case13/cases.py`](<t5/superseded-case13/cases.py>) | `t7-fix1/pre-fix/cases.py` | `45f6561b22b8c1484f1fa192ff39d2886bfca24ea075212abcf6942e1bfde7bf` | 17,414 |
| [`t5/superseded-case13/runs/case13/result.json`](<t5/superseded-case13/runs/case13/result.json>) | `t5-runtime/runs-superseded/case13-1792750756/result.json` | `a6fab0cb3fe6d761d80ae619a93891baa0d0754713f1c27f5211ddc5561b6489` | 638 |
| [`t5/superseded-case13/runs/case13/steps.jsonl`](<t5/superseded-case13/runs/case13/steps.jsonl>) | `t5-runtime/runs-superseded/case13-1792750756/steps.jsonl` | `d5a9cfbd132b1f0125dea824c9612d7670beee678ad88cfb59359abf279ab2f1` | 3,562 |
| [`t5/superseded-case13/summary.json`](<t5/superseded-case13/summary.json>) | `t7-fix1/pre-fix/t5/summary.json` | `3e01dd881d029f1cfb333e24195acf26554b4497a6c9f7a5d132051028b51e93` | 7,296 |
| [`t5/superseded-case13/case15-contracts.json`](<t5/superseded-case13/case15-contracts.json>) | `t7-fix1/pre-fix/t5/case15-contracts.json` | `382345c41ca954045b9b8f9872fca3ff28b70772f63574557b54370d304eb8b5` | 18,519 |
| [`t5/superseded-case13/evidence-manifest.json`](<t5/superseded-case13/evidence-manifest.json>) | `t7-fix1/pre-fix/t5/evidence-manifest.json` | `fcb08421c668870a0f219220f0f4962c915275d3bdf035c1eebcdbb75f79d405` | 18,570 |
| [`t5/superseded-case13/REPORT.md`](<t5/superseded-case13/REPORT.md>) | `t7-fix1/pre-fix/t5/REPORT.md` | `37326b309525225e03fd206d4bc1da4c73c50233ebeb5be3492e5d08decd001b` | 16,855 |
| [`t5/superseded-case13/t6-verify-rerun.log`](<t5/superseded-case13/t6-verify-rerun.log>) | `t6-docs/t5-verify.log` | `2f048db41e5d86955e0086ee59c8cfb8c59527e8d29361feb953b27d16844dd4` | 1,584 |
| [`t5/superseded-case13/README.md`](<t5/superseded-case13/README.md>) | `t7-fix1/superseded-case13-README.md` | `cd286eeefd80b3f1c266f2d16670fa2c8d5ffdf421b85a4533577d9e2ede2547` | 3,599 |

## t7-fix1 — T7-FIX1 정정(Astra full-v1 F1·F3·N1)

- 생성 명령: [`t7-fix1/REPORT.md`](<t7-fix1/REPORT.md>) 「검증 명령」
- 대상: 후보 `1ac790a9…e1eb`(재빌드 없음), HEAD `9090818` + Phase B 작업트리
- 파일 18개, 47,250 B

| 경로 | 출처(`temp/name-grid-phaseB/` 기준) | sha256 | bytes |
|---|---|---|---:|
| [`t7-fix1/REPORT.md`](<t7-fix1/REPORT.md>) | `t7-fix1/REPORT.md` | `b2dba79b9300b163e27e3d16f9a34d2befa100923725e0e4c3f1b64d5eabf628` | 13,160 |
| [`t7-fix1/test_part2_name_compose_build.stdout.log`](<t7-fix1/test_part2_name_compose_build.stdout.log>) | `t7-fix1/test_part2_name_compose_build.stdout.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 |
| [`t7-fix1/test_part2_name_compose_build.stderr.log`](<t7-fix1/test_part2_name_compose_build.stderr.log>) | `t7-fix1/test_part2_name_compose_build.stderr.log` | `65d4dbd3c6a89beaccc52a3b88bd3b8f3bc81ae26a7c600e22f69a2d90791613` | 2,487 |
| [`t7-fix1/test_part2_name_compose_build.exit.txt`](<t7-fix1/test_part2_name_compose_build.exit.txt>) | `t7-fix1/test_part2_name_compose_build.exit.txt` | `7e1cd69fab85528649b3c67810caed1f9db026f90623c7d226ea1477c93b6a46` | 5 |
| [`t7-fix1/test_part2_name_compose_build.env.txt`](<t7-fix1/test_part2_name_compose_build.env.txt>) | `t7-fix1/test_part2_name_compose_build.env.txt` | `a1833f1d521a3e598e83946e9b9a48992d4d89a31e8e430f32fb8ec78a9ca715` | 178 |
| [`t7-fix1/audit_tmp.py`](<t7-fix1/audit_tmp.py>) | `t7-fix1/audit_tmp.py` | `4b0c95aac0fe38d6277b8cd9a5f42eee2463888c7b2cd76aa793c757500a51c6` | 1,026 |
| [`t7-fix1/audit_tmp.stdout.log`](<t7-fix1/audit_tmp.stdout.log>) | `t7-fix1/audit_tmp.stdout.log` | `0d106592a971c4d9d0c3d192475aae85bbd34a91554e43a238c9f839689ccbe2` | 118 |
| [`t7-fix1/audit_tmp.stderr.log`](<t7-fix1/audit_tmp.stderr.log>) | `t7-fix1/audit_tmp.stderr.log` | `3b9cca7e5ecebe8264d893eabee755a541a1da8133da95e060c8a069f5f13eb3` | 1,295 |
| [`t7-fix1/audit_tmp.exit.txt`](<t7-fix1/audit_tmp.exit.txt>) | `t7-fix1/audit_tmp.exit.txt` | `7e1cd69fab85528649b3c67810caed1f9db026f90623c7d226ea1477c93b6a46` | 5 |
| [`t7-fix1/test_part2_name_compose_build.t3-to-fix1.diff`](<t7-fix1/test_part2_name_compose_build.t3-to-fix1.diff>) | `t7-fix1/test_part2_name_compose_build.t3-to-fix1.diff` | `1a72ceb9a31311dbf615afa69755139d84382603b27b6e8110c930953c4d0f80` | 958 |
| [`t7-fix1/cases.py.fix1.diff`](<t7-fix1/cases.py.fix1.diff>) | `t7-fix1/cases.py.fix1.diff` | `1c03a5385e758664bd3747365120c18b7f40143e3bbb205dfe04dfc8f2c1691d` | 3,122 |
| [`t7-fix1/compare_t4_snapshot.py`](<t7-fix1/compare_t4_snapshot.py>) | `t7-fix1/compare_t4_snapshot.py` | `9d0788af2534cb21715a36cca49d97fea572390e059f7301bde50aeabcf2529e` | 1,547 |
| [`t7-fix1/compare_t4_snapshot.log`](<t7-fix1/compare_t4_snapshot.log>) | `t7-fix1/compare_t4_snapshot.log` | `0ffe1d76193032aea0f2faaa11fdea6eff70548a6feb3671847123e32bf33293` | 230 |
| [`t7-fix1/sha-before.txt`](<t7-fix1/sha-before.txt>) | `t7-fix1/sha-before.txt` | `3803cd08f68350b04854ba595a9ad0c028f33fabbb054ccb68631d45763daf50` | 2,373 |
| [`t7-fix1/sha-after.txt`](<t7-fix1/sha-after.txt>) | `t7-fix1/sha-after.txt` | `c6566ed4e5d1c66446687445b3c9df706420553a762f047f9e74206f56d41514` | 2,373 |
| [`t7-fix1/update_evidence.py`](<t7-fix1/update_evidence.py>) | `t7-fix1/update_evidence.py` | `698c8645e77d2cad3e4f24d61b4ecc92321162cee3e6fdc328a0704b3ec57c33` | 6,025 |
| [`t7-fix1/make_index_t7.py`](<t7-fix1/make_index_t7.py>) | `t7-fix1/make_index_t7.py` | `f91ef2152fef7596e0a24a850897aa2dd6447a57aa297c146ace4d2e5e0415c1` | 5,792 |
| [`t7-fix1/validate_t7.py`](<t7-fix1/validate_t7.py>) | `t7-fix1/validate_t7.py` | `36ab0cb5adbe525c7f67d259749864bfe3fedbf7d8e418896edbe9cc37280e7d` | 6,556 |
