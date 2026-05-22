#!/usr/bin/env python3
import subprocess
import sys

print("Test 1: Check if codex is available...")
try:
    result = subprocess.run(['which', 'codex'], capture_output=True, text=True)
    print(f"  codex path: {result.stdout.strip()}")
except Exception as e:
    print(f"  Error: {e}")

print("\nTest 2: Try simple codex command with timeout...")
try:
    result = subprocess.run(
        ['codex', 'exec'],
        input="한글로 번역하세요: Hello\n번역:",
        capture_output=True,
        text=True,
        timeout=10
    )
    print(f"  stdout: {result.stdout[:200]}")
    print(f"  stderr: {result.stderr[:200]}")
    print(f"  returncode: {result.returncode}")
except subprocess.TimeoutExpired:
    print("  TIMEOUT: Codex exec timed out after 10 seconds")
except Exception as e:
    print(f"  Error: {e}")
