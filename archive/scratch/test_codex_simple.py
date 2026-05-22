#!/usr/bin/env python3
"""간단한 Codex 번역 테스트"""

import subprocess
from pathlib import Path

codex_cmd = Path(r'C:\Users\taro1\AppData\Roaming\npm\codex.cmd')

# 5개 텍스트만 테스트
test_texts = [
    "攻撃",
    "防御",
    "逃げる",
    "できる",
    "ユニット"
]

prompt = """한글로 번역하세요. 게임 텍스트.
형식: 번호|한글

1. 攻撃
2. 防御
3. 逃げる
4. できる
5. ユニット

번역 (번호|한글):"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

print("Codex 테스트 시작...")
print(f"프롬프트:\n{prompt}\n")

try:
    result = subprocess.run(
        [str(codex_cmd), 'exec'],
        input=prompt,
        capture_output=True,
        text=True,
        encoding='utf-8',
        timeout=30
    )

    print("=== Codex 응답 ===")
    print(result.stdout)
    if result.stderr:
        print("=== stderr ===")
        print(result.stderr)

    print(f"\n반환 코드: {result.returncode}")

except subprocess.TimeoutExpired:
    print("타임아웃!")
except Exception as e:
    print(f"에러: {e}")
