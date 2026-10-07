# Weekly live run for Windows Task Scheduler (optional).
# Register (once):  schtasks /Create /SC WEEKLY /D MON /ST 09:00 /TN market-forecaster-live /TR "powershell -NoProfile -File C:\path\to\market-forecaster\scripts\live_weekly.ps1"
# This script commits locally only; push manually after reviewing.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
uv run mf score-live
uv run mf live --n 10 --allow-spend --max-usd 1.50
uv run mf verify-ledger
$head = (uv run mf verify-ledger) -replace '.*head=(\w{8}).*', '$1'
$n = (Get-Content data/live/forecasts.jsonl | Measure-Object -Line).Lines
git add data/live
git commit -m "live: $(Get-Date -Format yyyy-MM-dd) n=$n head=$head"
