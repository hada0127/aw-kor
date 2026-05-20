# PowerShell script to start batch translation with API key setup

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Game Wars Translation - Batch Mode Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if API key is already set
if ($env:ANTHROPIC_API_KEY) {
    Write-Host "[OK] ANTHROPIC_API_KEY found in environment" -ForegroundColor Green
    Write-Host "     Key: $($env:ANTHROPIC_API_KEY.Substring(0,15))..." -ForegroundColor Green
} else {
    Write-Host "[INFO] ANTHROPIC_API_KEY not set" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To set it for this session, run:" -ForegroundColor Yellow
    Write-Host '  $env:ANTHROPIC_API_KEY = "sk-your-key-here"' -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Then run this script again." -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

Write-Host ""
Write-Host "Translation Progress:" -ForegroundColor Cyan
Write-Host "  Current: 2,442 / 28,347 (8.61%)" -ForegroundColor Cyan
Write-Host "  Remaining: 25,905 texts" -ForegroundColor Cyan
Write-Host ""

Write-Host "Starting Batch Translation..." -ForegroundColor Green
Write-Host ""

# Run the batch translation
& python tools/translate_batch_api.py

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Batch Job Submitted Successfully!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "To check status, run:" -ForegroundColor Cyan
    Write-Host "  python tools/check_batch_status.py <batch_id>" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "Error running batch translation" -ForegroundColor Red
}
