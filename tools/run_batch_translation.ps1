# PowerShell script to run batch translation with API key

# Get API key from user or environment
$apiKey = $env:ANTHROPIC_API_KEY
if (-not $apiKey) {
    Write-Host "ANTHROPIC_API_KEY not found in environment"
    Write-Host "Please set the API key:"
    Write-Host '  $env:ANTHROPIC_API_KEY = "sk-..."'
    exit 1
}

Write-Host "API Key found (${apiKey.Substring(0,10)}...)"

# Run Python script with API key in environment
$env:ANTHROPIC_API_KEY = $apiKey
& python tools/translate_batch_api.py
