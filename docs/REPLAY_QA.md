# 모델 호출 없는 반복 재생

`tools/replay_campaign_qa.py`는 로컬 에뮬레이터만 실행한다. 재시작·입력 재생·매 프레임 PNG 저장·무결성 검사·기준 실행과의 픽셀 비교에는 LLM/API 호출이 없다. 새로운 경로를 찾거나 번역의 의미를 판단하는 기능은 없다.

## 기록한 경로 내보내기

```sh
python3 tools/replay_campaign_qa.py export \
  --run output/qa/기존_콜드부팅_실행 \
  --out temp/route.txt
```

정상 종료하고 무결성 검사를 통과한 실행의 입력만 내보낸다. 미완료 실행이나 중간 세이브에서 시작한 실행은 거부한다. 입력은 `A 120`, `NONE 300` 형식이며 버튼은 2프레임 누른 뒤 지정 프레임 동안 놓는다.

## 자동 재시작과 비교

```sh
python3 tools/replay_campaign_qa.py run \
  --rom temp/candidate.gba \
  --harness temp/part1_playthrough_2026-09-15/mgbah_capture \
  --inputs temp/route.txt \
  --out output/qa/새_반복실행 \
  --reference output/qa/기준_완료실행 \
  --repeat 2 --min-free-gib 15
```

각 회차는 새 ROM 복사본으로 콜드부팅한다. 다른 빌드의 세이브스테이트를 재사용하지 않는다. 기존 출력 디렉터리는 덮어쓰지 않는다. 디스크 여유가 기준보다 작아지면 다음 프레임을 실행하지 않고 중단한다.

각 회차의 기본 시간 제한은 6시간이다(`--run-timeout-seconds`). 시간 초과·중단 신호를 받으면 해당 회차가 만든 프로세스 그룹을 종료한다. 외부 기준 실행은 재생 전에 먼저 검증한다.

- `summary.json`: 완료·실패·시각 검토 필요 여부를 짧게 표시한다.
- `run_*/comparison.json`: 모든 프레임을 비교한 차이 구간과 첫 증거 이미지 경로다. 애니메이션 중간 프레임도 포함한다.
- `run_*/frames.jsonl`: 각 프레임의 입력·픽셀 해시·PNG 경로다. 동일 픽셀 PNG는 중복 저장하지 않는다.
- `run_*.log`: 상세 실행 로그다. 반복 중 모델에 로그를 보낼 필요가 없다.

종료코드 `0`은 기록 경로 재생 완료, `2`는 화면 차이 발견이다. 실패는 비정상 종료하며 다음 반복을 실행하지 않는다. 기준을 생략하면 첫 실행을 **미검토 기준**으로 삼아 이후 반복의 결정성을 확인한다. **화면이 동일해도 기존 번역 오류가 그대로 있을 수 있으므로 전체 한글화 합격을 뜻하지 않는다.**

이미 끝난 실행 두 개만 비교할 수도 있다.

```sh
python3 tools/replay_campaign_qa.py compare \
  --reference output/qa/기준_완료실행 \
  --candidate output/qa/새_완료실행 \
  --out temp/comparison.json
```

양쪽 프레임 번호·입력·프레임 수·하네스·libmgba가 일치해야 한다. ROM 해시는 달라도 비교할 수 있다. 프레임 수나 입력이 달라지면 정렬되지 않은 비교로 거부한다.

진행 중인 캡처의 종료까지 로컬에서 기다리려면 `compare --wait-seconds 7200`을 추가한다. 같은 디렉터리끼리의 비교와 기존 비교 보고서 덮어쓰기는 거부한다.

## 수정 ROM에 정상 SRAM 이관

기본 `--game-save`는 출처와 대상 ROM SHA가 같아야 한다. 기존 검증된 패치 사이에서 게임 자체 저장을 이관할 때는 `--game-save-source-rom-sha256 <출처 ROM SHA>`를 함께 지정한다. 출처·대상 해시는 달라야 하며 receipt·출처 체크포인트·원본 SRAM 무결성을 그대로 검증한다. baseline에는 두 해시를 기록하고 재개 시 그 연결도 검사한다. 이 옵션은 save 형식 호환성을 증명하지 않으므로 이관 후 임무·턴·자금·아군 상태를 비교한다. 에뮬레이터 state에는 이관 옵션이 적용되지 않는다.

새 캡처 baseline은 schema4로 이관 출처·대상 연결을 필수 검사한다. schema1~3의 과거 캡처는 기존 SRAM/receipt/loaded-copy 해시 검증을 유지하며 당시 없던 이관 메타데이터를 새로 요구하지 않는다. 이를 schema4 이관 검증 통과로 집계하지 않는다. 이관 시작 전에 출처·대상의 저장 타입 시그니처와 정상 SRAM 크기도 비교한다.
