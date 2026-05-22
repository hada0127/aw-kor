#!/usr/bin/env python3
"""Test if API key is accessible"""

import os
import sys
from anthropic import Anthropic

print("Testing API key access...")
print()

# Check environment
api_key_env = os.environ.get('ANTHROPIC_API_KEY')
if api_key_env:
    print(f"[FOUND] ANTHROPIC_API_KEY in environment: {api_key_env[:20]}...")
else:
    print("[NOT FOUND] ANTHROPIC_API_KEY in environment")

# Try to initialize Anthropic client
try:
    client = Anthropic()
    print("[OK] Anthropic client initialized successfully")

    # Try a simple test message
    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=50,
        messages=[{"role": "user", "content": "Say OK"}]
    )
    print("[OK] API call successful")
    print(f"Response: {response.content[0].text[:50]}")
    sys.exit(0)

except TypeError as e:
    if "authentication" in str(e).lower():
        print("[ERROR] API key not accessible")
        print()
        print("To set up API key, run:")
        print('  export ANTHROPIC_API_KEY="sk-..."')
        sys.exit(1)
    else:
        print(f"[ERROR] {e}")
        sys.exit(1)
except Exception as e:
    print(f"[ERROR] {e}")
    sys.exit(1)
