#!/bin/bash
# Start batch translation with API key setup

# Check for API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "=========================================="
    echo "ANTHROPIC_API_KEY not found"
    echo "=========================================="
    echo ""
    echo "To continue translation, set your API key:"
    echo ""
    echo "  export ANTHROPIC_API_KEY='sk-...'"
    echo ""
    echo "Then run:"
    echo "  python tools/translate_batch_api.py"
    echo ""
    exit 1
fi

echo "============================================"
echo "Starting Game Wars Translation (Batch Mode)"
echo "============================================"
echo ""
echo "API Key found: ${ANTHROPIC_API_KEY:0:10}..."
echo ""

# Run batch translation
python tools/translate_batch_api.py
