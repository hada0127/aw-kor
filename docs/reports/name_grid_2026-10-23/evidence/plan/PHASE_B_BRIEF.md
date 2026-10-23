# 이름 그리드 Phase B 실행 계획 작성 요청
한국어로 작성. cwd /Users/konest/project/aw-kor, HEAD90908180938c2bf40ee38dea43c4c1304b09df8a, branch sweep3-p2-20261023c. 사용자 승인된 요청: 2편 맵 에디터 이름 입력을 완전 두벌식 조합으로 변경, 최대8글자/글자2바이트, 2350 밖 중간 후보는 원자 거부(대체 금지), 조합 자모부터 삭제. 공유 A3 가나 그림 변경 금지. 구현/테스트/Astra 리뷰는 harness-codex, Fable은 계획 작성만. 사용자 개입 없이 수행하고 결과/필수 결정만 company 전달. 원본만 제공받았으며 이전세이브/nyarch 접근불가지만 새 정상 세이브를 만들어 해결함.

이 문서는 계획이 아닌 총괄 브리프다. 실제 코드/바이트/트램펄린 설계를 읽고 독립 테스트 가능한 실행계획을 작성해라. 새 구현은 아직 없다. 기존 AGENTS.md/CLAUDE.md/todo와 tools/hangul_compose.py/test, docs/reports/name_grid_2026-10-23/COMPOSITION_SPEC.md, EXTERNAL_RESEARCH.md, INTERNAL_RESEARCH.md를 읽어라. Phase A 문서의 자산대기/unverified 부분은 아래 새 실측으로 superseded되며 계약 변경은 아니다.

필수 원시 조사 보고서(요약만으로 추측 금지):
- temp/name-grid-phaseB/native-re/RUNTIME_REPORT.md
- temp/name-grid-phaseB/candidate-re/RUNTIME_REPORT.md
- temp/name-grid-phaseB/list-link-re/RUNTIME_REPORT.md
- temp/name-grid-phaseB/baseline-build/RETRY1_BUILD_REPORT.md
- temp/name-grid-phaseB/b44-reference/RECOVERY_REPORT.md
- temp/name-grid-phaseB/official-mgba/BUILD_REPORT.md
- temp/name-grid-phaseB/arm-link-proof/PROOF_REPORT.md
필요한 디스어셈블리/명령/메타데이터는 각 디렉터리. 연구 산출물 자체는 temp에만 있고 tracked 변경 없음.

## 확보 자산
원본 original/Game Boy Wars Advance 1+2 (Japan).gba SHA a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c, ignored readonly. b44 output/game_wars_korean_b44_reference_20261023.gba SHA1ac68443d8fa48ef50a5a73290f94d65ff90997b4e6f38bc60410c9d424c6f02. 현소스 baseline output/game_wars_korean_namegrid_baseline_20261023.gba SHAebbca0babca25e4ed9d77c88af0b159fab567c9e8d708bd69a46f281e38a3a8a. 원본/default full/final/title_test/dist/b44 보호, 새 후보 --out --no-sync-outputs 사용.
Baseline 빌더는 data/sprite_build_layouts.json,objlabel_sprites.json을 쓰므로 temp의 git archive source snapshot에서 빌드했다. 생성물2개는 결국 원본동일. 같은 빌드 source/temp/integrity_map.json,repoint_manifest.json과5관문 모두exit0. 잔여 Bteam114(listed103,deferred11,unlisted0),overflow273,widthrisk507은 기존값이며 주소/유형 세트 비교해 신규회귀만 판정. 보고서 경로 참조.
Font env AW_FONT_DIR=temp/name-grid-phaseB/fonts (공식 pinned OkDanDan), AW_HADASANS_FONT=/Users/konest/project/hada-font/fonts/hada-sans/otf/HadaSans-Bold.otf, BLACK 같은폴더 HadaSans-Black.otf. 버전/SHA는보고서.
공식mGBA0.10.5 source commit26b7884bc25a5933960f3cdcd98bac1ae14d42e2, 미수정 기존harness 단일/링크 바이너리 official-mgba/ 아래. 실제 cold 실행 완료. ARM 도구 Appleclang21 armv4t-none-eabi Thumb + arm-none-eabi-binutils2.47 확보, temp linkerproof .o->ELF->raw34bytes/relocation0/undefined0/ELF바이트동일 확인. 게임통합증거는아님.

## 실측 핵심(원시보고서로확인)
이름객체는 global03004650가 가리키는 동적02003010(주소고정금지), 기존size70. allocation0834B970, B974 movr0,#70, allocator16byte정렬/header16/zeroing없음. free0834BA00는 header크기를쓰므로 80확장+tail70..7F 전용+명시초기화가 별도할당보다작다. 기존00..6F 전부보존(65/66/67/68/6A사용). setupB9C4 mode1 max8 dest5C; B988 mode0 사용불명. mode1 디자인맵만범위화하고 mode0보존. constructorA9FC len61 buffer2C old44. pointercallbacks FD58alloc/FD78constructor/FE30free. init/reset/cancel/reentry active 명시처리, mallocfailure기존동작확인. C호출시 기존SP4align관측되므로8align+복원,callee/highregs/flags/Thumb return 보존 구체화.
선택table0883FAF6 15x6 vs표시0883FE40 별도. main0834AFA0, normal0834B0BC(sound, B0C2->append0834AE00->B0C6 redraw/len증가), delete0834B20E, R B222, START/OKconfirmB00C/B012 trim/copy. 단순append만후킹하면native8번째덮어쓰기/len증가/특수경로가깨짐. RE 바이트/ABI기반패치계약과전후가드 필요. 원본9번째는8번째덮어쓰기지만새계약은거부. B/삭제셀동일, START=OK, Cancel은destcopy없음. R/탁점/반탁점은조합UI에서명시정책. 실제공백8140, 끝공백trim, 중간공백유지,shortname종료첫byte만0/잔여suffix가능. 모델serialize zero-fill은reference표현이며 rawnative16zero를추가계약으로강요금지. 모델↔nativeadapter로의미prefix/종료를검증,full8은정확16bytes. 기존숫자/문장부호보존은최소literalappend확장+atomicactive확정으로설계가능; 불필요일반화금지.
기존A3는완성한글이름을이미렌더링함. preview/load/save/Versus소비자실제RAM→A3→VRAM64바이트매치,8자 가한글가한글가한 native저장/candidate+b44콜드로드성공. 해당테스트는RAM주입으로초기이름만만들었으므로자모입력증거아님. 소비자별추가훅은필요없다는실측. SRAM현재bank1F504 vs예전1E504 둘다존재,단일offset고정판정금지. standaloneeditorHUDtitle는입증안됨. Link기존harness가clientfullROM을GBALoadMB(multiboot256KB)로읽어원본/후보모두흰화면, counter0; actualfullcartridgeload전경계,IRQ원인아님. 링크수신소비자는unverified로명시하고시리얼프레임워크개발을본기능의자가게이트로추가하지마라. 새게임유효맵2색HQ+각공장정상입력생성/cold/Versus선택성공. 세이브추가요청불필요.
A3relocation F20000..F243A4=2886entries(원536+2350),IWRAM03006084는ROM A3C7E8에서복사되어F30281로점프. maxE2A7범위. unusedcodes는build_korean2350.extend_pool(original)3326중976개로첫E2A8,E2AB...비연속,JSON샘플만쓰지말것. 선택33/preview40자모,기존2350매핑불변+신규40코드/atlas/table/max확장동시.
Glyph F09F20blank1273,F09F40private자1274 보존,새glyph1275부터가능,실제zero F09F60..F10000 24736bytes. dense음절표11172*2=22344. mission-title예약F66000..F70000 zero꼬리포함,코드/lookup새범위F70000이후가능하나실제직접writer/deny/repoint테이블조사로검증하고기존DENY_REGIONS에좁게추가. F31FEC..F3F000통째빈공간가정금지. privategrid mode1display+selectiondispatch로globalkana손상방지. 정확레이아웃/disabledvsspace/행폭은계획에서정해라.

## 구현/검증계획 요구
기존Python모델계약준수(특히 개+ㄷ reject,간+ㅒ 두음절원자거부,8번째active편집,5도달불가정직보고). 해결선택지는간단히비교하고최소설계채택. freestandingCcore+작은Thumbtrampoline+source/linkerscript+생성hex모듈/hash로일반빌드는Python-only유지하는방안이기존hexASM패턴과맞음. 모델만기계적으로복제한테스트말고별도고정기대값/전수표/keysequence/oracle대조. generatedartifact재생성일치/undefinedhelper0/relocation0/ARMv4T/stack레지스터무결성필요. 새추상framework금지. 실제코어세부설계결정은작성자판단.
독립검증가능작업으로나눠각파일소유권/명령/완료조건/롤백/증거명시. plan승인후단계별harness-codexcode,소유권중복금지,검증후단일Astrafullreview. 코어hostvsPython랜덤/전수+실제ROM키그리드/받침이동/복합/미완성확인거부/공백/숫자/8자/9번째거부/지우기/취소/legacy불러오기/재진입/한글강철붉은달/정상저장콜드/소비자화면. 2350모든ROM화면이요구되는것은아님. 후보명과동일빌드map을명시,5관문/공유글리프56종또는실제노드전체/장음게이트/보호파일SHA 검증. 미검증Link/실기한계는정직보고.
완료시실측RE/계획승인/QA를docs/reports/name_grid_2026-10-23에영구보존,AGENTS/CLAUDE/todo자산대기서술을최신화(PhaseA이력은보존). 모든변경줄원요청추적. scopedsecret-scan후한국어Conventionalcommit/push,승인/검증된최종feature는원handoff의main병합단계까지수행가능(이레포에는mapdev/stg관문없음). b44/dist/정본ROM재배포는범위밖. company결과전달및작업소유프로세스정리. 실패시3회동일수정한계/rollback은commit後revert,보호파일 덮어쓰기 금지。
