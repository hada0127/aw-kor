#!/usr/bin/env python3
import subprocess
from pathlib import Path

codex_cmd = Path(r'C:\Users\taro1\AppData\Roaming\npm\codex.cmd')

print(f"Codex path: {codex_cmd}")
print(f"Exists: {codex_cmd.exists()}")

if codex_cmd.exists():
    print("\nTrying to call codex.cmd...")
    try:
        result = subprocess.run(
            [str(codex_cmd), 'exec'],
            input="테스트\n",
            capture_output=True,
            text=True,
            timeout=10,
            encoding='utf-8'
        )
        print(f"stdout: {result.stdout[:500]}")
        print(f"stderr: {result.stderr[:500]}")
        print(f"returncode: {result.returncode}")
    except subprocess.TimeoutExpired:
        print("TIMEOUT: Process timed out")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
