@echo off
REM Game Wars GBA 한글화 ROM 빌드 스크립트
REM 사용법: build.bat <game_index> [output_name]
REM 예: build.bat 1
REM 예: build.bat 2 game_wars_2_kor

setlocal enabledelayedexpansion

if "%1"=="" (
    echo 사용법: build.bat ^<game_index^> [output_name]
    echo.
    echo game_index: 1 (Game Wars 1) 또는 2 (Game Wars 2)
    echo output_name: 출력 ROM 이름 (선택사항, 기본값: game_wars_X_kor)
    echo.
    exit /b 1
)

set GAME_INDEX=%1
set OUTPUT_NAME=%2

if "%OUTPUT_NAME%"=="" (
    set OUTPUT_NAME=game_wars_%GAME_INDEX%_kor
)

set ORIGINAL_ROM=original/game_wars_%GAME_INDEX%.gba
set TRANSLATION_CSV=data/game_wars_%GAME_INDEX%_translation.csv
set POINTERS_CSV=data/pointers_%GAME_INDEX%.csv
set TBL_FILE=tools/game_wars.tbl
set OUTPUT_ROM=output/%OUTPUT_NAME%.gba

REM 파일 존재 확인
if not exist "%ORIGINAL_ROM%" (
    echo 오류: ROM 파일을 찾을 수 없습니다: %ORIGINAL_ROM%
    exit /b 1
)

if not exist "%TBL_FILE%" (
    echo 오류: .tbl 파일을 찾을 수 없습니다: %TBL_FILE%
    exit /b 1
)

echo.
echo ================================================
echo Game Wars %GAME_INDEX% 한글화 ROM 빌드
echo ================================================
echo.

REM 1단계: 텍스트 추출
if not exist "%TRANSLATION_CSV%" (
    echo [1/4] 텍스트 추출 중...
    python tools/extract_text.py "%ORIGINAL_ROM%" "%TBL_FILE%" data/game_wars_%GAME_INDEX%_text.csv
    if errorlevel 1 (
        echo 텍스트 추출 실패
        exit /b 1
    )
    echo 완료: data/game_wars_%GAME_INDEX%_text.csv
) else (
    echo [1/4] 번역 CSV 존재 (추출 스킵)
)

REM 2단계: 포인터 테이블 확인
if not exist "%POINTERS_CSV%" (
    echo [2/4] 경고: 포인터 테이블을 찾을 수 없습니다 (%POINTERS_CSV%)
    echo 포인터 업데이트를 스킵합니다.
) else (
    echo [2/4] 포인터 테이블 로드: %POINTERS_CSV%
)

REM 3단계: 번역 텍스트 삽입
if exist "%TRANSLATION_CSV%" (
    echo [3/4] 번역 텍스트 삽입 중...
    python tools/import_text.py "%ORIGINAL_ROM%" "%TRANSLATION_CSV%" "%TBL_FILE%" output/temp_%OUTPUT_NAME%.gba
    if errorlevel 1 (
        echo 텍스트 삽입 실패
        exit /b 1
    )
    echo 완료: output/temp_%OUTPUT_NAME%.gba
) else (
    echo [3/4] 경고: 번역 CSV를 찾을 수 없습니다 (%TRANSLATION_CSV%)
    echo 텍스트 삽입을 스킵합니다.
)

REM 4단계: ROM 최종화
echo [4/4] ROM 최종화 중...
if exist "output/temp_%OUTPUT_NAME%.gba" (
    if exist "%OUTPUT_ROM%" (
        del "%OUTPUT_ROM%"
    )
    move "output/temp_%OUTPUT_NAME%.gba" "%OUTPUT_ROM%"
    echo 완료: %OUTPUT_ROM%
) else (
    echo 최종 ROM 생성 실패
    exit /b 1
)

echo.
echo ================================================
echo 빌드 완료!
echo 생성된 ROM: %OUTPUT_ROM%
echo ================================================
echo.

endlocal
exit /b 0
