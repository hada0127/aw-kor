# 작전룸 '룸' 가독성 후속 수정

사용자 재지적에 따라 큰 옵션 `0xC03AF0`과 작은 제목 `0xC18CB4`의 마지막 음절만 수정했다.
같은 NotoSansKR 계열에서 룸만 Black 대신 Bold로 렌더링해 ㄹ의 아래쪽 틈과 받침 ㅁ 내부를 열었다.
작전의 픽셀, 전체 배치 bbox, 팔레트, 그라데이션 규칙, 작은 제목의 OPERATION은 수정 전과 같다.
큰 옵션의 ㄹ/ㅁ 내부에는 각각 두 행의 어두운 간격이 생겼다. 수동 획 덮어쓰기는 사용하지 않는다.

## 비교와 범위

- [원본 / 수정 전 / 수정 후 비교](../screenshots/room_readability_2026-09-07/index.html)
- 큰 옵션 126px, 작은 제목 130px 변경. 두 원본 압축 할당 구간 밖 ROM 변경 0바이트.
- 압축 크기: 큰 옵션 816/1144바이트, 작은 제목 607/660바이트. 재배치 없음.
- fresh-boot 캡처의 `main_0`, `branch_0_item_1`을 비교했다. 큰 옵션은 활성 OAM까지 자동 대응했다.
  작은 제목은 화면을 직접 확인했으나 자동 OAM 대응기는 분류하지 못했으므로 자동 검증 완료로 집계하지 않는다.
- 이번 수정은 룸 두 자산에 한정된다. 다른 스프라이트 전수 검증 및 실기 검증 완료를 뜻하지 않는다.

## 빌드 환경

기존 Black 폰트 외에 `~/Library/Fonts/NotoSansKR-Bold.otf`가 필요하다.
Bold SHA256: `7deb7d6a71b3230a8a505d2cfaa484baacb953c79ca5b28dcc78db8077774c0d`.
현재 Pillow basic layout 환경에서 검증했으며 다른 shaping 환경은 재검증 대상이다.
앞 글자 위치 보존은 glyph advance 검사와 실제 수정 전 렌더 경로에 대한 픽셀 비교로 검사한다.

```sh
python3 tools/refresh_part1_menu_overrides.py
python3 tools/build_korean_full.py --out temp/room_full.gba --no-sync-outputs
python3 -m unittest discover -s tools -p test_room_readability.py
python3 -m unittest discover -s tools -p 'test_sprite_*.py'
python3 tools/audit_sprite_override_report.py --strict
python3 tools/qa_integrity_map.py --rom temp/room_full.gba --byte-only
```

전체 빌드와 비교 후보의 SHA가 일치한 뒤 output의 full/final/title_test 3종을 동기화했다.
SHA256: `909828af725a38d1a267fbeaa13d9bd9e80879d889549cff7d205dc6dc18fc23`.
단위 테스트 17개, visual QA 54검사, phase6 기본 무결성, override strict 검사 통과.
무결성맵 기대 388547바이트 중 불일치 0. visual QA의 저장게임 기반 행동 메뉴/전투 검사는 제외했다.

## 리뷰와 배포

Codex와 Claude의 읽기 전용 엄격 리뷰에서 확정 버그나 회귀는 발견하지 못했다.
Claude 제안에 따라 테스트 기준을 실제 기존 렌더 함수로 바꾸고 대상 외 옵션 불변 검사를 추가했다.
새 폰트 의존과 shaping 환경 한계는 위에 명시했다. agy는 `timeout waiting for response`로 실패했으며
리뷰 통과로 간주하지 않는다. 같은 회귀/경계/테스트 체크리스트는 Codex와 Claude가 검토했다.
배포 BPS/IPS는 갱신하지 않았다. 기존 전체 텍스트 QA 실패와 미검증 화면은 별도 미완료 상태다.
