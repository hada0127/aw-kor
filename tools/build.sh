#!/bin/bash
# Game Wars GBA 한글화 ROM 빌드 스크립트
# 사용법: ./build.sh <game_index> [output_name]
# 예: ./build.sh 1
# 예: ./build.sh 2 game_wars_2_kor

if [ $# -lt 1 ]; then
    echo "사용법: ./build.sh <game_index> [output_name]"
    echo ""
    echo "game_index: 1 (Game Wars 1) 또는 2 (Game Wars 2)"
    echo "output_name: 출력 ROM 이름 (선택사항, 기본값: game_wars_X_kor)"
    echo ""
    exit 1
fi

GAME_INDEX=$1
OUTPUT_NAME=${2:-"game_wars_${GAME_INDEX}_kor"}

ORIGINAL_ROM="original/game_wars_${GAME_INDEX}.gba"
TRANSLATION_CSV="data/game_wars_${GAME_INDEX}_translation.csv"
POINTERS_CSV="data/pointers_${GAME_INDEX}.csv"
TBL_FILE="tools/game_wars.tbl"
OUTPUT_ROM="output/${OUTPUT_NAME}.gba"

# 파일 존재 확인
if [ ! -f "$ORIGINAL_ROM" ]; then
    echo "오류: ROM 파일을 찾을 수 없습니다: $ORIGINAL_ROM"
    exit 1
fi

if [ ! -f "$TBL_FILE" ]; then
    echo "오류: .tbl 파일을 찾을 수 없습니다: $TBL_FILE"
    exit 1
fi

echo ""
echo "================================================"
echo "Game Wars $GAME_INDEX 한글화 ROM 빌드"
echo "================================================"
echo ""

# 1단계: 텍스트 추출
if [ ! -f "$TRANSLATION_CSV" ]; then
    echo "[1/4] 텍스트 추출 중..."
    python3 tools/extract_text.py "$ORIGINAL_ROM" "$TBL_FILE" "data/game_wars_${GAME_INDEX}_text.csv"
    if [ $? -ne 0 ]; then
        echo "텍스트 추출 실패"
        exit 1
    fi
    echo "완료: data/game_wars_${GAME_INDEX}_text.csv"
else
    echo "[1/4] 번역 CSV 존재 (추출 스킵)"
fi

# 2단계: 포인터 테이블 확인
if [ ! -f "$POINTERS_CSV" ]; then
    echo "[2/4] 경고: 포인터 테이블을 찾을 수 없습니다 ($POINTERS_CSV)"
    echo "포인터 업데이트를 스킵합니다."
else
    echo "[2/4] 포인터 테이블 로드: $POINTERS_CSV"
fi

# 3단계: 번역 텍스트 삽입
TEMP_ROM="output/temp_${OUTPUT_NAME}.gba"
if [ -f "$TRANSLATION_CSV" ]; then
    echo "[3/4] 번역 텍스트 삽입 중..."
    python3 tools/import_text.py "$ORIGINAL_ROM" "$TRANSLATION_CSV" "$TBL_FILE" "$TEMP_ROM"
    if [ $? -ne 0 ]; then
        echo "텍스트 삽입 실패"
        exit 1
    fi
    echo "완료: $TEMP_ROM"
else
    echo "[3/4] 경고: 번역 CSV를 찾을 수 없습니다 ($TRANSLATION_CSV)"
    echo "텍스트 삽입을 스킵합니다."
    TEMP_ROM="$ORIGINAL_ROM"
fi

# 4단계: ROM 최종화
echo "[4/4] ROM 최종화 중..."
if [ -f "$TEMP_ROM" ]; then
    if [ -f "$OUTPUT_ROM" ]; then
        rm "$OUTPUT_ROM"
    fi
    if [ "$TEMP_ROM" != "$OUTPUT_ROM" ]; then
        mv "$TEMP_ROM" "$OUTPUT_ROM"
    fi
    echo "완료: $OUTPUT_ROM"
else
    echo "최종 ROM 생성 실패"
    exit 1
fi

echo ""
echo "================================================"
echo "빌드 완료!"
echo "생성된 ROM: $OUTPUT_ROM"
echo "================================================"
echo ""

exit 0
