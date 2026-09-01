# Start the serving API on Windows.
#
#     .\scripts\serve.ps1
#
# scripts/serve.py takes its configuration from the environment and refuses to
# boot without it, which is right for a service and tedious to type. This sets
# the pilot's values, reads VOYAGE_API_KEY out of .env, and starts it.
#
# The thresholds are the shipped pair from EVALUATION_LEDGER, not defaults. If
# they stop matching src/agts/retrieval/sufficiency.py the service logs a
# warning at boot rather than quietly running a gate nobody measured.

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path ".env")) { throw "no .env here; VOYAGE_API_KEY has to come from somewhere" }
Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.+?)\s*$') {
        Set-Item -Path ("env:" + $matches[1]) -Value $matches[2]
    }
}
if (-not $env:VOYAGE_API_KEY) { throw "VOYAGE_API_KEY not found in .env" }

$env:AGTS_DATABASE_URL   = "postgresql://agts:agts_dev_password@localhost:5434/agts_dev"
$env:AGTS_EMBEDDING_CACHE = "artifacts/embeddings/voyage-4-large.json"
$env:AGTS_ABSTAIN_FLOOR   = "0.744"
$env:AGTS_HIGH_CONFIDENCE = "0.765"
$env:AGTS_RELEASE_MANIFEST_ID = "rm-pilot-2-chapters-0001"
$env:AGTS_API_TOKENS = "dev-token:tenant-dev"
# Only while the corpus is unapproved, which is today. Without it the service
# refuses to boot, on purpose.
$env:AGTS_ALLOW_QUARANTINED_CONTENT = "yes-i-accept-unapproved-content"
$env:PYTHONIOENCODING = "utf-8"

Write-Host "starting on http://localhost:8000 - ctrl-c to stop" -ForegroundColor Green
Write-Host "ask it things from another terminal:" -ForegroundColor DarkGray
Write-Host "    python scripts/ask.py `"what is the nature of roots`"" -ForegroundColor DarkGray
python scripts/serve.py
