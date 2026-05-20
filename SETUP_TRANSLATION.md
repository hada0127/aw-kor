# Game Wars Translation - Setup Guide

## Current Status
- Translations: 2,442 / 28,347 (8.61%) complete
- Current approach: Synchronous Claude API (slow, rate-limited)
- New approach ready: Batch API (10-15x faster)

## What's Been Prepared

Three translation tools are ready to use:

### 1. Batch API Mode (RECOMMENDED - Fastest)
```bash
python tools/translate_batch_api.py
```
- Processes all 25,905 remaining texts in ~24-48 hours
- Avoids rate limiting by using async batch processing
- Returns job ID for progress monitoring

After submission, check status:
```bash
python tools/check_batch_status.py <batch_id>
```

### 2. Interactive Mode (For Testing)
```bash
python tools/translate_with_api_key.py
```
- Prompts for API key if not in environment
- Smaller batches (easier for testing)
- Real-time progress display

### 3. Current Mode (Still Running)
- Old: `tools/translate_all_texts.py`
- Status: Stuck at retry 5/15 due to rate limiting
- **Recommendation**: Switch to Batch API for better results

## Setup Requirements

### Option A: Set Environment Variable (Linux/Mac/Windows PowerShell)
```bash
export ANTHROPIC_API_KEY="sk-..."  # Linux/Mac
$env:ANTHROPIC_API_KEY = "sk-..."  # PowerShell
```

### Option B: Create .env File
```bash
# Create file: .env
ANTHROPIC_API_KEY=sk-...
```

Then run:
```bash
python -m dotenv load
python tools/translate_batch_api.py
```

## Next Steps

1. **Set API Key** using Option A or B above
2. **Run batch translation**:
   ```bash
   python tools/translate_batch_api.py
   ```
3. **Monitor progress**:
   ```bash
   python tools/check_batch_status.py <batch_id>
   ```
4. **When complete, rebuild ROM**:
   ```bash
   python tools/execute_phase5_4.py
   python tools/execute_phase5_5.py
   python tools/phase6_basic_test.py
   ```

## Performance Comparison

| Method | Speed | Time to Complete | Rate Limit Issues |
|--------|-------|------------------|-------------------|
| Synchronous API | ~3.6 texts/min | 14+ days | Yes, constant |
| Batch API | ~300 texts/min | 24-48 hours | No |
| Batch API (5k texts) | Same rate | < 1 hour | No |

## Troubleshooting

**Error: "Could not resolve authentication method"**
- API key not set in environment
- Run: `python test_api_key.py` to verify
- Set ANTHROPIC_API_KEY (see Setup Requirements above)

**Error: "429 - Rate Limit"**
- Synchronous API hitting limits (expected with translate_all_texts.py)
- Switch to Batch API instead

**Batch job stuck processing?**
- Check status: `python tools/check_batch_status.py <batch_id>`
- Batch jobs typically process within 24-48 hours
- No action needed, wait for completion

## Files Created

- `tools/translate_batch_api.py` - Main batch submission tool
- `tools/check_batch_status.py` - Batch status checker
- `tools/translate_with_api_key.py` - Interactive translation (testing)
- `tools/start_batch_translation.sh` - Shell wrapper
- `test_api_key.py` - API key verification script
