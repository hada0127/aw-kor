# 2026-10-02 개별 한글화 회귀 복원

현재 개발 후보: `temp/continuation_2026-10-02/result_rank_word/candidate.gba`
SHA-256: `2a81ca7ec54368e7e63efd314ef5cc46ceea6d49d8d1721f7873ef1384b65638`.
보호 원문 불일치 **31건**이 남는다. 이는 baseline/override 직접 비교 결과이며 전체 배포 QA 통과를 뜻하지 않는다. 실행 중 ROM과 배포 output 3종은 변경하지 않았다. 아래 새 수정의 실화면은 미검증이다.

- DF2A64: 승인된 `모드 선택으로 돌아갈까요?` 복원. 후보 b3b33e…에서 기존 대비4B만 변경.
- DFD082: `이건 비밀인데, 그 헬보우즈를 고용할 수 있다네!` 원장 복원. 54셀 한 줄 대신 기존 native 행전환으로16/36셀 두 줄 표시. 기존 재배치 엔진의 할당/충돌/제어 검사를 사용한다.
- D82028: `여기서는 맵을 자유롭게 만들 수 있어요.` 복원. 후보 a96a1f…에서 원래44B슬롯의4B만 변경.
- DFA6E2: 원장 `워즈코인을 사용해서`, 승인 compact 표시 `워즈 코인으로`를 기존 display_overrides로 분리. 전체빌드 ROM은 a96a1f…와16MB 완전동일. 과거 표시 근거는 success.md의 2026-06-27 shop read-watch 기록이며 새 화면 검증을 주장하지 않는다.
- D82058: `만드는 방법은 「도움말」에 적혀 있어요.`를36B원본슬롯에서44B전체문장으로 기존 포인터 재배치.
- D8F6FE: `미안해요` 복원. 기존 슬롯·제어·포인터 유지.

이전 맵 도움말/사과문 묶음은 전용5회귀, Claude 엄격 리뷰, 전체빌드, 기본 QA 통과. 기존2,255개 재배치 payload는 전부 동일하고, 추가70개 alias포인터를 원본source/이전target/새target으로 각각 대조했다. 132,732B차이는 신규문장/소스슬롯/할당이동/포인터로 설명되며 미설명 차이0이다. 증거는 `temp/continuation_2026-10-02/map_design_help/`에 있다.

QA 수집기가 외부 SHIP_HELP_ROWS/SUBMARINE_HELP_ROWS의 실제 late writer를 누락하던 오류도 수정했다. 기존92회귀와 추가4회귀 및 Claude 리뷰를 통과했다. 보호baseline과 기존 B팀게이트 SHA는 유지했다.

작업 원칙: 문장별 일본어 원문·보호 정본·실제 writer·포인터·제어·폭을 개별 확인한다. 의미를 줄이거나 보호기준을 바꾸지 않는다. 검증된 소수 항목의 전체빌드만 합쳐 중복비용을 줄인다.

등록안내 DF9656 `그럼, 힘내요!` / DF9676 `이름을 저장해도 될까요?` 복원도 완료했다. 원본24B/26B 슬롯, 메시지별단일포인터와 선택제어7251590A00000000은 유지했다. 전용4회귀·Claude·전체빌드·기본QA 통과. b605대비 두문장슬롯 안15B만 바뀌었으며 그외ROM전체동일. 증거 `temp/continuation_2026-10-02/polite_registration/`. 실화면은미검증이다.

선택질문 DF8EAE `혹시, 이 게임은 처음이신가요?` / DF969A `어머, 역시 그만두시나요?` 복원. 후자는 기존재배치 메시지 A78288의38B payload를40B로 확장하며 기존선택제어를 그대로 유지했다. 직전2ac1대비55B변경, 나머지2,255개 재배치payload동일/설명밖차이0. 전용5회귀·Claude·전체빌드·기본QA통과. 증거 `temp/continuation_2026-10-02/polite_choice/`. 실제선택지화면미검증이며 라이브ROM에는 적용하지 않았다.

P1 M16승리후 2417/frame272042의 プラチナ 잔류를 BF15F8 압축자산으로확인하고 `플래티넘`으로수정. 공개VRAM14720의256B가원본자산과일치했다. 원본소비102B 안새94B, 다음할당/2B정렬패딩/포인터보존. 7회귀·Claude·전체빌드·기본QA통과. 직전f447대비해당압축할당안92B만변경. receipt차이는빌더가새플래티넘editor항목을기록한 sprite_build_layouts.json 한파일뿐이며 before/after전체동일로주장하지않는다. 새화면미검증. 별도2414 B배지의 ランク 잔류도확정: raw atlas BEB0FC..BEB17C,entry87 D8D7BC,공개OAM36/37+VRAM128B원본일치. 해당 배지 후속 수정은 아래와 같다.

B 배지 ランク→랭크: 소유 raw strip BEB0FC..BEB17C의 실제 표시3타일만 Galmuri7과 흰색/검정 그림자로 교체, 보이지 않는4번째타일과 entry87/88 경계 보존. B 및 S(8441) 기록에서 같은 원본128B/팔레트1=흰색·5=검정 확인. 5회귀·Claude 2회·격리 전체빌드·기본QA 통과. 직전84d 후보 대비 소유영역 안81B만 변경되고 나머지ROM전체동일. 에디터 픽셀 편집은 기존 정책대로 허용하되 적용후 snapshot을 최종 gate로 검사한다. receipt의 입력 차이는 빌더가 생성한 sprite_build_layouts.json/objlabel_sprites.json만이며 외부입력 변경으로 숨기지 않는다. 패치된 실제 배지와 A/C 등급은 아직 미검증, 보호원문31건도 그대로 남는다. 라이브P1 ab9627 및 P2 기존ROM/배포3종은 불변. 증거: `temp/continuation_2026-10-02/result_rank_word/`.

캡처 보존 정리: committed-prefix 시트 정리 모드를 추가해 종료 실패/진행 중 원장의 확정된 과거 구간만 다룬다. 최초·최근20개, 원본frames/endpoint/checkpoint/상태/원장/실패exit는 유지하며 시트 전체 RGB 재구성 일치와 복원 영수증 fsync 후 삭제한다. 전체 최초/최종 SHA 확인, 200개 배치별 현재 원본·새참조·열린파일 검사, 삭제 직전 원본 재검사를 유지했다. 전용16회귀+기존11회귀, Claude 재리뷰 차단 없음. P1 measured_resumed 278개/47,758,118B, P2 resumed_gzip 2,078개/427,674,667B, P1/P2 round32_cold 154개/44,751,311B, 합계2,510개/520,184,096B 회수. 중간 P2 1,100개 실행은 읽기 rg 배치 경계에서 의도적으로 exit1 종료했고 이를 성공으로 바꾸지 않았다. 독립검증에서32,879개 고정파일·원장prefix SHA와1,100쌍 영수증이 일치했다. 근거: temp/continuation_2026-10-02/sheet_pruning/ 및 각 temp/sheet_prune_* 영수증.

APFS 동일 ROM 공간 공유: tools/clone_closed_frames.py에 명시적 --rom 모드를 추가했다. 16MiB 전체SHA/동일bytes, 원본 로고·게임코드·GBA 헤더checksum, clean closed 상태, checkpoint ROM/state/ledger 계약, live/시작 중 recorder 및 checkpoint/SRAM 조상 제외를 검사한다. 별도 inode/nlink1과 원본target 메타데이터를 보존하며 shared lock 아래 prepared fsync→원자교체→전체보호SHA 검사→committed를 수행한다. copyfile이 stage quarantine timestamp를 바꾸는 첫 probe는 원자교체 전 실패했고 보호14파일SHA 불변을 확인했다. stage에만 정확한 원본xattr를 복원하는 보강 후30회귀 및Claude 재리뷰 차단 없음. 2probe+21개 후속, 총23개/385,875,968B(368MiB) 논리적중복을 clone으로전환했다. 후속21개 실행 중 df 증가339,828,736B는 동시작업 영향이 포함된 관측값이며 독점물리회수량으로 주장하지 않는다. 23개 독립 최종감사에서322개 보호파일SHA, target메타데이터/별도inode/nlink1/source와동일bytes 모두통과. 09-15 run01의 오래된checkpoint에 ledger_sha256가 없어22번째후속은preflight exit1로중단했고원본미변경,나머지총3개미처리. 기존실패로그/partial/원래exit1은보존했다. 근거 temp/continuation_2026-10-02/apfs_clone_probe/rom_final_audit.json 및 rom_batch_summary.json. 활성캡처/ROM내용/원장/정상저장/배포파일변경없음.

유사 ROM CoW 소규모 검증: --rom --near-rom은 source와target 각각16MiB/전체SHA/GBA헤더를 검증한뒤 source의private clone에원래target과다른정렬4KiB페이지만복원한다. 마지막전체targetbytes/SHA/메타데이터일치후원자교체하므로ROM내용은불변이다. 다른페이지1..1024한도,15GiBfloor+최악16MiBprivate할당여유,기존closed/활성조상/--rom입력/원장/lsof/잠금보호를유지했다.39회귀·Claude차단없음. 후보파일들은읽기인벤토리만했으며실제변경은closedbaseline두개: round18_m8_live를round27_bomber_cold에서158페이지복원nearclone,동일SHA의round18_m8_intro_probe는첫파일에서exactclone.두실행exit0·별도최종감사에서보호28파일SHA/원본ROMbytes/nlink1/메타데이터모두보존. 첫파일df -1,007,616B,두번째+17,297,408B(각작업창합+16,289,792B),사이동시캡처포함전체경과는-19,795,968B. 실제독점물리절감으로단정하지않는다.기존exactclone그룹을하나만재연결하면oldextent가남으므로첫near→그룹나머지exact순서가필요하다.증거 temp/continuation_2026-10-02/near_rom_clone/probe_audit.json 및inventory.json.

플레이 후속: 1편 M17 Andy DAY14/B 정상 승리와 SRAM 저장을 확인했다(3777 성공,3779 WIN,3783 저장; temp/continuation_2026-10-02/m17_success_evidence.json). M18 Sami 첫 시도는 DAY5 보호 보병을 실은 수송헬기 격추로 실패했고 정상 재시도했다. 재시도 DAY4에는 보병→수송헬기→순양함 중첩 탑재를 실제 확인(4634/frame468122), DAY5 순양함에서 TC0,11 하차(4691/frame474530)까지 진행했다. 승리/엔딩은 아직 확인하지 않았다. 2편 M9 DAY57은 북쪽 폭격기24HP 및 수송헬기 손실을 확인했으나 공개 녹화만으로 공격자 병종은 미확정이다. native 실행은 유지한 채 디스크 하한 때문에 다음입력625가 대기한다. 원본 프레임과 실패 증거를 삭제하지 않았다.

후속baseline묶음회수완료: 동일closed canonical에서31개SHA그룹의첫baseline을nearclone,같은그룹나머지24개를exactclone하여총55개전부exit0. 독립최종감사에서392개고유보호파일SHA및55개별도inode/nlink1/메타데이터일치. 그룹별공통페이지합480,624,640B는논리상한이며실행구간df증가421,814,272B에는동시캡처영향이포함된다. snapshot/외부clone등의독점extent소유는증명하지않았다.모든ROM내용은원본그대로이고candidate수정0. baseline_final_audit.json / baseline_batch_summary.json에근거를남겼다.후속candidate는현재·조상SHA24종을추가제외하여31개/29SHA/공통445MiB상한을읽기검토만했으며,기존closedrun게이트를우회해처리하지않는다.

M18 Sami 후속 정상승리: 4750 작전성공,4751 B,4752 WIN/8일 화면을 확보했고 root가4752를직접확인했다. 성공재시도893.726초(14분53.7초), 첫실패시도시간은포함하지않는다. 증거SHA temp/continuation_2026-10-02/m18_success_evidence.json. 기존live ab9627의결과배지잔류와최신후보실화면미검증은그대로이며엔딩도달로집계하지않는다. 정상저장후M19계속.

M19 DAY2 후속: TC+Mech100HP16,18, 입력224/core515013에서 디스크 여유15GiB대로 보류. 시스템 정상 메뉴로 전투 애니메이션을 표시 안함으로 바꿨고 다음 전투 처리시간은 미측정이다. 기존 empty PTY poll의 최소5초 대기를 제거한 정상 A180 네 구간 평균1.415초는 화면/부하가 다른 관측이며 전체 플레이 배속으로 일반화하지 않는다.

M19 title 일본어 2人のリョウ는 C15A68의498B LZ77→2048B와 공개 OBJ 타일 전체일치, 포인터E12CDC 및 다음할당C15C5C 확인. 기존승인번역 두 명의 료를 Galmuri7 정수2배로 64x32 OBJ 두 개의 실제 배치에 맞췄다. 최종 에디터 LZ77 VRAM-safe 검사와 뒤 writer 검사를 추가하고6테스트/Claude 정적리뷰를 완료했다. 에디터 cached palette가 native bank6을 덮어쓰는 지적은 고정 bank/palbase 및 회귀검사로 수정했다. 팔레트 근거는0019 한 상태이며 temp 팔레트가 없으면 에디터 일반팔레트로 fallback, 빌드에는 영향없음. 모든소비자/연출 및 patched native 검증은 미완료. D8F3B6 문장복원, DCF656 portrait 줄바꿈과 합칠 빌드는 공간확보대기.

통합 후보5279e19f: D8 문장/M19줄바꿈/title 묶음빌드exit0, phase6기본무결성exit0, title생성픽셀·최종경계·빌드입력안정성확인. 실제패치화면은미검증. 디스크15GiB반복중단은root가추가한운영값이었음(QA프로토콜기본10GiB설정가능); 새플레이12hard/13soft로조정하고이전실패증거는유지했다. P1 FIFO trial12 첫실제capture515014에서raw/FIFO153605B/SHA동일,counter세번모두515014,추가게임프레임0확인후임무재개. 전체trial후속consumer통합검증은별도대기하며구수집기로새proof를검증했다고주장하지않는다.
